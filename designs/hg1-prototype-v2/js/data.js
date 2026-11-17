/*
 * data.js — synthetic cross-border portfolio dataset and pure accessors.
 * Owned by designer-09 (phase 1); HG1 round-4 analytical-truth corrections by
 * designer-19 (this pass). Data + accessors ONLY — no rendering, no DOM.
 * See ../CONTRACT.md "Data access API" and its round-4 addendum for the accessor list.
 *
 * Every number below is derived deterministically from a seeded PRNG, not hand-typed,
 * so that return/vol/beta/alpha/Sharpe/Sortino/drawdown/correlation are internally
 * consistent with each other and with the series a chart would plot — computing them
 * from the same underlying series is what makes "numbers agree across surfaces" true
 * by construction rather than by careful hand-editing.
 *
 * This file self-identifies as SYNTHETIC PROTOTYPE DATA throughout. It is not, and must
 * never be read as, the deterministic engine P1 describes for the real product.
 *
 * =====================================================================================
 * HG1 ROUND 4 — analytical-truth correction pass (designer-19). Summary; see the
 * CONTRACT.md addendum and this worker's handoff for the full account.
 * =====================================================================================
 *   - ONE CANONICAL PORTFOLIO STATE (PD-0014 §2.5): sleeve weights (SLEEVE_WEIGHTS) are
 *     now DERIVED from actual HOLDINGS market values, not a hardcoded 40/30/20/10 that
 *     disagreed with the exposure surfaces' real ~48/35/10/6. HOLDINGS/ACCOUNTS/FX_RATES
 *     moved earlier in the file so this derivation can happen before return generation.
 *   - The portfolio return series now genuinely APPLIES FX to the Hong Kong and Mainland
 *     China sleeves (previously PERIOD_RETURN contained no FX at all, per
 *     methodology/HG1_ROUND4_METHODOLOGY_FINDINGS.md §4.1). Every downstream risk/return
 *     statistic (vol, beta, alpha, Sharpe, Sortino, drawdown, tracking error, VaR,
 *     portfolio-vs-benchmark correlation) is computed from this corrected,
 *     reporting-currency (FX-inclusive) series. Expect every one of these numbers to
 *     differ from prior builds and from the methodology findings' own illustrative
 *     figures (computed against the OLD, FX-less, 40/30/20/10 series) — that is
 *     required and expected (task framing: "do not preserve an old figure for
 *     continuity"), and is why HG1 round-4 requires independent quant_analyst
 *     re-verification before this gate can return.
 *   - The Sleeve Correlation Matrix (metric.correlation) deliberately KEEPS the
 *     LOCAL-currency sleeve series (unchanged) — a different, legitimate analytical
 *     question (asset-level co-movement) that quant_analyst's review validated against
 *     and did not ask to change. Contribution-to-Risk and the SML sleeve points use the
 *     FX-inclusive ("base") series instead, to stay Euler-exact with the corrected
 *     canonical portfolio series.
 *   - FX attribution is rebuilt on the quant-specified exact identity
 *     (R_base = (1+R_local)(1+R_fx)-1; FX effect = R_base,P - R_local,P), replacing the
 *     inverted-sign, no-FX-in-the-total defect. See methodology/HG1_ROUND4_METHODOLOGY_
 *     FINDINGS.md §4.
 *   - Hardcoded conclusion/caveat/insight strings that asserted the OPPOSITE of their
 *     own adjacent computed values (beta "moved more" at beta<1; risk contribution
 *     naming HK+CN when US is largest; correlation calling the WEAKEST equity pair
 *     "strong"; a false 24-observation caveat contradicted by the Proof Packet's own
 *     252; drawdown calling the shallower series "deeper"; volatility's unchecked
 *     more/less claim) are now DERIVED from the values they describe, per PD-0014 §2.2's
 *     claim-traceability invariant. See js/selfcheck.js for the semantic assertions that
 *     verify this at page load.
 *   - Sortino's downside-deviation denominator is corrected to divide by the full
 *     sample N (not the count of downside days only) — see downsideDeviation() below.
 *     The metric remains INSUFFICIENT_DATA (a legitimate demonstration of that render
 *     path, per the methodology findings), but its caveat no longer asserts a specific,
 *     false observation shortfall.
 *   - VaR now renders as a non-negative, unsigned, non-directional magnitude with its
 *     realized exceedance count disclosed, per the quant-specified convention.
 *   - CN A-share freshness is measured in local trading sessions, not wall-clock age,
 *     derived from an explicit SSE trading-session calendar (SSE_HOLIDAYS_2026,
 *     sseSessionInfo(), sseSessionsElapsed()) rather than asserted in prose. CORRECTED
 *     later this round: an earlier pass wrongly assumed 2026-09-03 was a Shanghai/
 *     Shenzhen holiday and derived zero elapsed sessions from that false premise; the
 *     owner caught it. 2026-09-03 was an ordinary trading Thursday, so the A-share
 *     print (dated 2026-09-02) is genuinely STALE by one completed session — see
 *     FRESHNESS_AXES's own comment for the full correction record and its stated
 *     no-network-egress limitation.
 *   - metric.benchmarkRelative's caveat no longer asserts "is not degraded" (PD-0014
 *     Part 1 §1.2): it now discloses limited temporal comparability between its two
 *     legs, a distinct, non-sufficiency disclosure dimension.
 *   - A NEW file, js/selfcheck.js, recomputes and verifies the above at page load,
 *     exposed as window.APP.selfcheck.run(). Since this designer's write path does not
 *     include index.html, that file is loaded via a dynamic <script> injection at the
 *     very end of this one (see §20 below) rather than a static <script> tag.
 */
(function () {
  "use strict";
  window.APP = window.APP || {};
  var APP = window.APP;

  // =======================================================================
  // 0. Deterministic PRNG + math helpers
  // =======================================================================
  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  var rand = mulberry32(20260904); // fixed seed: same inputs, same output (P12 spirit)

  function gaussian() {
    // Box-Muller
    var u = Math.max(rand(), 1e-9), v = Math.max(rand(), 1e-9);
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  function mean(arr) { return arr.reduce(function (a, b) { return a + b; }, 0) / arr.length; }
  function variance(arr) {
    var m = mean(arr);
    return mean(arr.map(function (x) { return (x - m) * (x - m); }));
  }
  function stdev(arr) { return Math.sqrt(variance(arr)); }
  function covariance(a, b) {
    var ma = mean(a), mb = mean(b), sum = 0;
    for (var i = 0; i < a.length; i++) sum += (a[i] - ma) * (b[i] - mb);
    return sum / a.length;
  }
  function pearson(a, b) {
    var sa = stdev(a), sb = stdev(b);
    if (sa === 0 || sb === 0) return 0;
    return covariance(a, b) / (sa * sb);
  }
  // HG1 round 4 fix (methodology findings §7.5) — the Sortino/Satchell target
  // semideviation divides by the FULL sample size N; downside days contribute a squared
  // deviation, up days contribute zero, but N itself never shrinks. The prior
  // implementation divided by the COUNT of downside observations only, which inflates
  // downside deviation (by ~39% at this dataset's mix of up/down days) and understates
  // Sortino by roughly a quarter. See methodology.sortino below and js/selfcheck.js.
  function downsideDeviation(returns, mar) {
    var sumSq = returns.reduce(function (s, r) {
      var d = r < mar ? (r - mar) : 0;
      return s + d * d;
    }, 0);
    return Math.sqrt(sumSq / returns.length);
  }
  function percentile(arr, p) {
    var sorted = arr.slice().sort(function (a, b) { return a - b; });
    var idx = Math.floor(p * (sorted.length - 1));
    return sorted[idx];
  }
  function rollingWindow(arr, size, fn) {
    var out = [];
    for (var i = 0; i < arr.length; i++) {
      if (i < size - 1) { out.push(null); continue; }
      out.push(fn(arr.slice(i - size + 1, i + 1)));
    }
    return out;
  }
  function groupBy(items, keyFn, valueFn) {
    var map = {};
    items.forEach(function (it) {
      var k = keyFn(it);
      map[k] = (map[k] || 0) + valueFn(it);
    });
    var total = Object.keys(map).reduce(function (s, k) { return s + map[k]; }, 0);
    return Object.keys(map).map(function (k) {
      return { label: k, value: map[k], pct: total ? map[k] / total : 0 };
    }).sort(function (a, b) { return b.value - a.value; });
  }
  // HG1 round 4 (pm-01 live verification) — all three formatters in this family used
  // to return a bare "—" for null/undefined, which is §D3.2's forbidden em-dash-as-
  // numeric-placeholder pattern, recurring here for a THIRD time in this project
  // (shell.js's own comment already names two prior instances). None of these
  // functions is the claim-value RENDERER (that is shell.js's renderMetricValue,
  // which correctly implements INSUFFICIENT_DATA) — they build hand-authored PROSE
  // strings inside data.js, so a null reaching one of them means a caller embedded an
  // unchecked (possibly-insufficient) value directly into prose without gating on
  // sufficiency first. Every current call site in this file always passes a real
  // number (verified by inspection when this fix was made), so this throws rather
  // than silently degrading — "fail loudly" per the coordinator's instruction, not a
  // live behavior change today, and a real guard against the next accidental instance.
  function APP_fmtPctNullGuard(fnName, v) {
    if (v === null || v === undefined) {
      throw new Error(fnName + "() called with null/undefined — a value must be sufficiency-checked before being formatted into prose; do not let it silently become an em-dash placeholder (the §D3.2 defect class, already recurred twice in this project before this guard).");
    }
  }
  // SIGNED — for a genuine CHANGE: gains/losses, returns, alpha, a distance/delta,
  // weight CHANGES, signed contributions, scenario deltas (owner's §6.3). Never use
  // this for a static level (volatility, a rate assumption, a concentration share) —
  // see APP_fmtLevelPct below, added specifically because this function was being
  // reused for levels and unconditionally prefixing a false "+".
  function APP_fmtPct(v) { APP_fmtPctNullGuard("APP_fmtPct", v); return (v >= 0 ? "+" : "") + (v * 100).toFixed(1) + "%"; }
  // Unsigned magnitude formatter — HG1 round 4 VaR convention requires no sign
  // character and no directional colour on a loss-magnitude figure (methodology
  // findings §3.2). Callers must pass an already-non-negative value (or a value this
  // formatter should treat as a magnitude regardless of its own sign, e.g. an
  // already-abs'd FX-drag figure — Math.abs() is applied here too, redundantly-but-
  // harmlessly, so callers never need to abs() their own input first).
  function APP_fmtMagnitudePct(v) { APP_fmtPctNullGuard("APP_fmtMagnitudePct", v); return (Math.abs(v) * 100).toFixed(1) + "%"; }
  // UNSIGNED level formatter — HG1 round 4 (pm-01 live verification, owner's §6.3): a
  // STATIC LEVEL (annualized volatility, a risk-free-rate assumption, a concentration
  // share) is a magnitude of a stock quantity, not a change, and must never carry a
  // leading "+" the way APP_fmtPct's gains/returns/alpha DO. Unlike
  // APP_fmtMagnitudePct, this does NOT force a positive sign convention either — a
  // level is whatever sign it actually has (there is no meaningful "direction" to a
  // level, so there is nothing to strip); it only suppresses the superfluous "+" on an
  // ordinary positive value.
  function APP_fmtLevelPct(v) { APP_fmtPctNullGuard("APP_fmtLevelPct", v); return (v * 100).toFixed(1) + "%"; }

  // =======================================================================
  // 1. Calendar — business days ending at a fixed synthetic "as of" date
  // =======================================================================
  var TRADING_DAYS = 504; // ~2 years
  var END_DATE = new Date(Date.UTC(2026, 8, 3)); // 2026-09-03, last close before "today"

  var DATES = (function () {
    var out = [];
    var d = new Date(END_DATE);
    while (out.length < TRADING_DAYS) {
      var day = d.getUTCDay();
      if (day !== 0 && day !== 6) out.unshift(d.toISOString().slice(0, 10));
      d = new Date(d.getTime() - 86400000);
    }
    return out;
  })();

  // =======================================================================
  // 1.5 Accounts, cash, holdings — MOVED HERE (was section 4) so that sleeve
  //     weights (§2 below) can be DERIVED from real holdings before the return
  //     series are generated, closing PD-0014 §2.5's "one canonical portfolio
  //     state" gap: risk statistics and exposure surfaces must describe the
  //     same portfolio, not a hardcoded 40/30/20/10 vs. a computed ~48/35/10/6.
  // =======================================================================
  var ACCOUNTS = [
    { id: "acct-us-1", name: "US Broker Brokerage (US)", currency: "USD", type: "taxable", market: "US" },
    { id: "acct-us-2", name: "US Broker IRA (US)", currency: "USD", type: "retirement", market: "US" },
    { id: "acct-hk-1", name: "Futu Hong Kong Brokerage", currency: "HKD", type: "taxable", market: "HK" },
    { id: "acct-cn-1", name: "Shanghai/Shenzhen A-Share Brokerage", currency: "CNY", type: "taxable", market: "CN" },
    { id: "acct-cash-1", name: "Multi-Currency Cash Sweep", currency: "USD", type: "cash", market: "GLOBAL" }
  ];

  var CASH_BALANCES = [
    { accountId: "acct-us-1", currency: "USD", amount: 18400.32 },
    { accountId: "acct-us-2", currency: "USD", amount: 4200.00 },
    { accountId: "acct-hk-1", currency: "HKD", amount: 62500.00 },
    { accountId: "acct-cn-1", currency: "CNY", amount: 38000.00 },
    { accountId: "acct-cash-1", currency: "USD", amount: 12000.00 },
    { accountId: "acct-cash-1", currency: "HKD", amount: 15000.00 },
    { accountId: "acct-cash-1", currency: "CNY", amount: 9000.00 }
  ];

  var FX_RATES = { USD: 1, HKD: 0.1282, CNY: 0.1406 }; // native -> USD, illustrative fixed snapshot rates

  // economicGeography differs from listingMarket for ADR/dual-listed cases (§10.3/10.4)
  var HOLDINGS = [
    { id: "AAPL", name: "Apple Inc.", accountId: "acct-us-1", listingMarket: "US", economicGeography: "US", currency: "USD", sector: "Information Technology", assetClass: "Equity", quantity: 120, avgCost: 148.20, price: 231.55 },
    { id: "MSFT", name: "Microsoft Corp.", accountId: "acct-us-1", listingMarket: "US", economicGeography: "US", currency: "USD", sector: "Information Technology", assetClass: "Equity", quantity: 60, avgCost: 312.10, price: 441.20 },
    { id: "NVDA", name: "NVIDIA Corp.", accountId: "acct-us-1", listingMarket: "US", economicGeography: "US", currency: "USD", sector: "Information Technology", assetClass: "Equity", quantity: 40, avgCost: 410.75, price: 118.40 },
    { id: "VOO", name: "Vanguard S&P 500 ETF", accountId: "acct-us-2", listingMarket: "US", economicGeography: "US", currency: "USD", sector: "Diversified Fund", assetClass: "Equity Fund", quantity: 85, avgCost: 390.00, price: 512.30 },
    { id: "TLT", name: "iShares 20+ Year Treasury Bond ETF", accountId: "acct-us-2", listingMarket: "US", economicGeography: "US", currency: "USD", sector: "Government Bonds", assetClass: "Fixed Income Fund", quantity: 150, avgCost: 92.40, price: 88.10 },
    { id: "0700.HK", name: "Tencent Holdings", accountId: "acct-hk-1", listingMarket: "HK", economicGeography: "China", currency: "HKD", sector: "Communication Services", assetClass: "Equity", quantity: 800, avgCost: 310.00, price: 398.20 },
    { id: "0941.HK", name: "China Mobile", accountId: "acct-hk-1", listingMarket: "HK", economicGeography: "China", currency: "HKD", sector: "Telecommunications", assetClass: "Equity", quantity: 2000, avgCost: 58.20, price: 82.60 },
    { id: "9988.HK", name: "Alibaba Group (HK listing)", accountId: "acct-hk-1", listingMarket: "HK", economicGeography: "China", currency: "HKD", sector: "Consumer Discretionary", assetClass: "Equity", quantity: 600, avgCost: 78.50, price: 91.40 },
    { id: "3690.HK", name: "Meituan", accountId: "acct-hk-1", listingMarket: "HK", economicGeography: "China", currency: "HKD", sector: "Consumer Discretionary", assetClass: "Equity", quantity: 300, avgCost: 102.00, price: 128.90 },
    { id: "2800.HK", name: "CSOP Structured Note (warrant-linked)", accountId: "acct-hk-1", listingMarket: "HK", economicGeography: "China", currency: "HKD", sector: "Structured Product", assetClass: "Derivative", quantity: 2000, avgCost: 3.20, price: 3.85, analyticsSupport: "UNSUPPORTED_ASSET" },
    { id: "600519.SS", name: "Kweichow Moutai", accountId: "acct-cn-1", listingMarket: "CN", economicGeography: "China", currency: "CNY", sector: "Consumer Staples", assetClass: "Equity", quantity: 20, avgCost: null, price: 1542.00, costBasisState: "INSUFFICIENT_DATA", costBasisReason: "MISSING_COST_BASIS", addedDate: "2026-07-02" },
    { id: "300750.SZ", name: "CATL", accountId: "acct-cn-1", listingMarket: "CN", economicGeography: "China", currency: "CNY", sector: "Industrials", assetClass: "Equity", quantity: 500, avgCost: 168.40, price: 221.80 },
    { id: "601318.SS", name: "Ping An Insurance", accountId: "acct-cn-1", listingMarket: "CN", economicGeography: "China", currency: "CNY", sector: "Financials", assetClass: "Equity", quantity: 300, avgCost: 45.60, price: 49.90, thinlyTraded: true }
  ];

  function marketValueUSD(h) {
    return h.quantity * h.price * FX_RATES[h.currency];
  }
  var TOTAL_HOLDINGS_VALUE = HOLDINGS.reduce(function (s, h) { return s + marketValueUSD(h); }, 0);
  var TOTAL_CASH_VALUE = CASH_BALANCES.reduce(function (s, c) { return s + c.amount * FX_RATES[c.currency]; }, 0);
  var TOTAL_PORTFOLIO_VALUE = TOTAL_HOLDINGS_VALUE + TOTAL_CASH_VALUE;

  // HG1 round 4 (PD-0014 §2.5, Task 1) — sleeve classification + weight derivation.
  // Bond sleeve is identified by assetClass (only TLT carries "Fixed Income Fund" in
  // this dataset); every other holding is classified by its listingMarket. This is a
  // FACT derived from HOLDINGS, not a target mix asserted independently of it — the
  // failure mode this replaces (SLEEVE_WEIGHTS = {us:0.40,hk:0.30,cn:0.20,bond:0.10},
  // a literal that quietly diverged from the real ~48/35/10/6 and gave the Mainland
  // China sleeve DOUBLE its actual weight in every risk statistic) cannot recur here,
  // because there is no longer a second number to diverge from the first.
  function sleeveKeyForHolding(h) {
    if (h.assetClass === "Fixed Income Fund") return "bond";
    if (h.listingMarket === "US") return "us";
    if (h.listingMarket === "HK") return "hk";
    if (h.listingMarket === "CN") return "cn";
    return null; // no holding in this dataset falls through; see js/selfcheck.js's
                 // sleeveWeights.matchHoldings assertion, which would fail loudly if one did.
  }
  var SLEEVE_MARKET_VALUE = { us: 0, hk: 0, cn: 0, bond: 0 };
  HOLDINGS.forEach(function (h) {
    var k = sleeveKeyForHolding(h);
    if (k) SLEEVE_MARKET_VALUE[k] += marketValueUSD(h);
  });
  var SLEEVE_WEIGHTS = {
    us: SLEEVE_MARKET_VALUE.us / TOTAL_HOLDINGS_VALUE,
    hk: SLEEVE_MARKET_VALUE.hk / TOTAL_HOLDINGS_VALUE,
    cn: SLEEVE_MARKET_VALUE.cn / TOTAL_HOLDINGS_VALUE,
    bond: SLEEVE_MARKET_VALUE.bond / TOTAL_HOLDINGS_VALUE
  };

  // =======================================================================
  // 2. Factor-model return generation — common market factor + sleeve loadings
  //    + idiosyncratic noise. Everything downstream (beta, alpha, vol, Sharpe,
  //    Sortino, drawdown, correlation, contribution-to-risk, SML) is computed
  //    from these arrays, not asserted independently.
  //
  //    HG1 round 4: the ORDER in which this section consumes the PRNG (rand()/
  //    gaussian()) is UNCHANGED from the prior build — marketFactor, then the
  //    four sleeves, then fxHKD, then fxCNY — even though HOLDINGS moved above
  //    this section, because HOLDINGS consumes no PRNG calls at all. Determinism
  //    (P12) is preserved; only the WEIGHTS blending these series, and whether
  //    FX is applied before blending, changed.
  // =======================================================================
  var RF_ANNUAL = 0.045;
  var RF_DAILY = RF_ANNUAL / 252;

  var marketFactor = DATES.map(function () { return gaussian() * 0.0075 + 0.00030; }); // benchmark-ish factor

  function sleeveReturns(loading, idioSigma, driftAdj) {
    return DATES.map(function (_, i) {
      return loading * marketFactor[i] + gaussian() * idioSigma + (driftAdj || 0);
    });
  }

  var benchmarkReturns = marketFactor.slice(); // MSCI ACWI proxy IS the factor itself
  var usEquitySleeve = sleeveReturns(1.05, 0.0065, 0.00005);
  var hkEquitySleeve = sleeveReturns(1.15, 0.0110, -0.00005);
  var cnEquitySleeve = sleeveReturns(0.85, 0.0140, -0.00015);
  var bondSleeve = sleeveReturns(0.15, 0.0035, 0.00002);

  // Local-currency (FX held constant / not yet applied) portfolio blend — this is
  // R_local,P in methodology findings §4.3's identity: the ledger valued at each
  // date's local prices, translated at a FIXED (beginning-of-period) FX rate. Since
  // this blend never varies the FX rate at all, it already IS that definition.
  var portfolioReturnsLocal = DATES.map(function (_, i) {
    return SLEEVE_WEIGHTS.us * usEquitySleeve[i] + SLEEVE_WEIGHTS.hk * hkEquitySleeve[i] +
      SLEEVE_WEIGHTS.cn * cnEquitySleeve[i] + SLEEVE_WEIGHTS.bond * bondSleeve[i];
  });

  // FX daily returns (USD strength = positive means USD appreciates, i.e. foreign
  // sleeve's reporting-currency return < its local return)
  var fxHKD = DATES.map(function () { return gaussian() * 0.0009; });   // USD/HKD, low vol (pegged-ish)
  var fxCNY = DATES.map(function () { return gaussian() * 0.0022 - 0.00006; }); // mild CNY depreciation drift

  // HG1 round 4 (methodology findings §4.1, §4.3) — the CANONICAL, reporting-currency
  // ("base") return series. Exact per-day sleeve identity: R_base = (1+R_local)(1+R_fx)-1.
  // US and bond sleeves are USD-denominated already (no FX leg), so their "base" series
  // is identical to their local series.
  function combineLocalFx(localReturn, fxReturn) { return (1 + localReturn) * (1 + fxReturn) - 1; }
  var usEquitySleeveBase = usEquitySleeve;
  var bondSleeveBase = bondSleeve;
  var hkEquitySleeveBase = hkEquitySleeve.map(function (r, i) { return combineLocalFx(r, fxHKD[i]); });
  var cnEquitySleeveBase = cnEquitySleeve.map(function (r, i) { return combineLocalFx(r, fxCNY[i]); });

  // THE canonical portfolio return series — every risk/return statistic in §3 below is
  // computed from THIS series, not the local-only one. This is what fixes methodology
  // findings §4.1 ("PERIOD_RETURN contains no FX at all") and, as a direct consequence,
  // §7.11 (VaR previously excluded currency risk) and the false "including... FX
  // effects" claim in metric.return.1y.explanationSimple, which is now true.
  var portfolioReturns = DATES.map(function (_, i) {
    return SLEEVE_WEIGHTS.us * usEquitySleeveBase[i] + SLEEVE_WEIGHTS.hk * hkEquitySleeveBase[i] +
      SLEEVE_WEIGHTS.cn * cnEquitySleeveBase[i] + SLEEVE_WEIGHTS.bond * bondSleeveBase[i];
  });

  function cumulativeIndex(returns, base) {
    base = base || 100;
    var out = [base];
    for (var i = 0; i < returns.length; i++) out.push(out[out.length - 1] * (1 + returns[i]));
    return out.slice(1);
  }
  var portfolioIndex = cumulativeIndex(portfolioReturns);           // canonical (base, FX-inclusive)
  var portfolioIndexLocal = cumulativeIndex(portfolioReturnsLocal); // local-only, FX held at start
  var benchmarkIndex = cumulativeIndex(benchmarkReturns);

  function drawdownSeriesFromIndex(idx) {
    var runMax = -Infinity, out = [];
    idx.forEach(function (v) { runMax = Math.max(runMax, v); out.push(v / runMax - 1); });
    return out;
  }
  var portfolioDrawdown = drawdownSeriesFromIndex(portfolioIndex);
  var benchmarkDrawdown = drawdownSeriesFromIndex(benchmarkIndex);

  var rollingVolPortfolio = rollingWindow(portfolioReturns, 90, function (w) { return stdev(w) * Math.sqrt(252); });
  var rollingVolBenchmark = rollingWindow(benchmarkReturns, 90, function (w) { return stdev(w) * Math.sqrt(252); });

  function sliceRange(range) {
    var n = { "1M": 21, "3M": 63, "6M": 126, "1Y": 252, "ALL": TRADING_DAYS }[range] || 252;
    return Math.max(0, DATES.length - n);
  }

  // =======================================================================
  // HG1 M1 fix (BINDING — methodology/HG1_M1_PERIOD_RETURN_BASE_CONVENTION_RULING.md,
  // RULING 2/3, quant_analyst). This is the ONE place the base-of-a-trailing-window
  // convention is decided. `sliceRange(range)` above is UNCHANGED and still returns what
  // it always returned — the index of the first IN-WINDOW return (call it `i`). What was
  // wrong was every CALLER's own ad hoc handling of "what is one before `i`," repeated
  // three different ways (the `i1y - 1 >= 0 ? i1y - 1 : 0` clamp below, and the bare
  // `sliceRange` used directly as a LEVEL-array start in getPortfolioSeries). This
  // function replaces both with one declared rule.
  //
  // RULING 1(a): the base of a trailing window is the last observation STRICTLY BEFORE
  // the window (the "prior close") — never a member of the window itself. A window of N
  // return observations is bounded by N+1 valuation points.
  //
  // RULING 3 / 3(a): at range="ALL", `i` is 0 — there is no close before DATES[0], so
  // PRIOR_CLOSE is unavailable. The declared convention there is FIRST_AVAILABLE_CLOSE:
  // base = DATES[0] itself, and the window is every return STRICTLY AFTER it
  // (DATES[1]..end). r[0] (dated DATES[0]) is the return from `cumulativeIndex`'s
  // notional, non-market base of 100 to the first real close — it has no observable prior
  // close, and RULING 3(a) forbids inventing a calendar entry to give it one, so it is
  // excluded from the declared window. This is a DECLARED rule (`baseRule`), not a silent
  // clamp — a boundary mislabeled PRIOR_CLOSE when no prior close exists is now a
  // detectable defect (§34/P12 — was M1-F4) rather than an undeclared convention switch.
  //
  // RULING 2(iii)/3: no published metric's VALUE moves. `i - 1` for every range with a
  // prior close, and `0` for ALL, are exactly what the old inline clamp already computed.
  // =======================================================================
  function periodWindow(range) {
    var i = sliceRange(range);
    var lastIndex = DATES.length - 1;
    if (i > 0) {
      return {
        range: range,
        firstReturnIndex: i,
        baseIndex: i - 1,
        baseDate: DATES[i - 1],
        windowStart: DATES[i],
        windowEnd: DATES[lastIndex],
        observationCount: lastIndex - i + 1,
        baseRule: "PRIOR_CLOSE"
      };
    }
    // i === 0 — RULING 3's ALL boundary. No close exists before DATES[0].
    return {
      range: range,
      firstReturnIndex: 1,
      baseIndex: 0,
      baseDate: DATES[0],
      windowStart: DATES[1],
      windowEnd: DATES[lastIndex],
      observationCount: lastIndex, // === lastIndex - 1 + 1
      baseRule: "FIRST_AVAILABLE_CLOSE"
    };
  }
  // The engine's own period-return arithmetic — literally the division every published
  // PERIOD_RETURN-family fact below performs, generalized so it is written ONCE and
  // parameterized by a declared window rather than repeated inline three times. Exposed
  // read-only on `_internal` below (NOT a new metric/claim — publishing a per-range
  // return for 1M/3M/6M/ALL is a product-scope decision this designer does not make; see
  // the ruling's Part 11 / finding M1-F8) purely so a render-layer regression can
  // reconcile against the SAME engine formula for a range with no published
  // metric.return.* fact.
  function enginePeriodReturnOn(idx, w) {
    return idx[idx.length - 1] / idx[w.baseIndex] - 1;
  }

  // =======================================================================
  // 3. Computed portfolio-level statistics (period = trailing 1Y unless noted)
  // =======================================================================
  var i1y = sliceRange("1Y");
  var pr1y = portfolioReturns.slice(i1y);       // canonical (base, FX-inclusive)
  var pr1yLocal = portfolioReturnsLocal.slice(i1y);
  var br1y = benchmarkReturns.slice(i1y);

  // RULING 2(v): re-derived from periodWindow("1Y") instead of computed separately —
  // removes the second, parallel definition of the same window. Values are unchanged:
  // periodWindow("1Y").windowStart === DATES[i1y], .observationCount === pr1y.length, by
  // construction (i1y === firstReturnIndex for range "1Y").
  var WINDOW_1Y = periodWindow("1Y");
  var WINDOW_START_DATE = WINDOW_1Y.windowStart;
  var WINDOW_END_DATE = WINDOW_1Y.windowEnd;
  var WINDOW_OBS_COUNT = WINDOW_1Y.observationCount;

  // RULING 2(iii): reads periodWindow("1Y").baseIndex instead of the inline
  // `i1y - 1 >= 0 ? i1y - 1 : 0` clamp repeated three times. baseIndex is 251 before and
  // after this change on this fixture — these three published facts do NOT move.
  var PERIOD_RETURN = enginePeriodReturnOn(portfolioIndex, WINDOW_1Y);
  var PERIOD_RETURN_LOCAL = enginePeriodReturnOn(portfolioIndexLocal, WINDOW_1Y);
  var BENCHMARK_PERIOD_RETURN = enginePeriodReturnOn(benchmarkIndex, WINDOW_1Y);
  var ANNUAL_VOL = stdev(pr1y) * Math.sqrt(252);
  var BENCHMARK_ANNUAL_VOL = stdev(br1y) * Math.sqrt(252);
  var BETA = covariance(pr1y, br1y) / variance(br1y);
  var ALPHA_DAILY = mean(pr1y) - RF_DAILY - BETA * (mean(br1y) - RF_DAILY);
  var ALPHA_ANNUAL = ALPHA_DAILY * 252;
  var SHARPE = (mean(pr1y) - RF_DAILY) / stdev(pr1y) * Math.sqrt(252);
  var DOWNSIDE_DEV = downsideDeviation(pr1y, RF_DAILY); // HG1 round 4: now divides by full N
  var DOWNSIDE_DEV_ANNUAL = DOWNSIDE_DEV * Math.sqrt(252);
  var DOWNSIDE_DAY_COUNT = pr1y.filter(function (r) { return r < RF_DAILY; }).length;
  var SORTINO = DOWNSIDE_DEV > 0 ? (mean(pr1y) - RF_DAILY) / DOWNSIDE_DEV * Math.sqrt(252) : null; // computed for
  // methodology/audit purposes ONLY — never surfaced as a claim value, since this
  // metric deliberately demonstrates the INSUFFICIENT_DATA render path (see §9 below
  // and methodology.sortino). P5 forbids showing a suppressed number; it does not
  // forbid documenting, internally, the formula that WOULD apply.
  var MAX_DRAWDOWN = Math.min.apply(null, portfolioDrawdown.slice(i1y));
  var BENCHMARK_MAX_DRAWDOWN_1Y = Math.min.apply(null, benchmarkDrawdown.slice(i1y));
  var TRACKING_ERROR = stdev(pr1y.map(function (r, i) { return r - br1y[i]; })) * Math.sqrt(252);
  var VAR_95 = percentile(pr1y, 0.05);
  var VAR_EXCEEDANCE_COUNT = pr1y.filter(function (r) { return r <= VAR_95; }).length;
  var VAR_HAS_LOSS_THRESHOLD = VAR_95 < 0; // methodology findings §3.4 edge case
  var VAR_MAGNITUDE = VAR_HAS_LOSS_THRESHOLD ? -VAR_95 : null;
  var CORR_PORT_BENCH = pearson(pr1y, br1y);

  // HG1 round 4 (quant_analyst verification §6) — beta's standard error, exposed so a
  // directional claim about beta can be gated by statistical significance rather than
  // a bare sign check. This exact formula (OLS residual s.d. over sqrt(n)*sd(benchmark))
  // was independently specified and verified live by quant_analyst; reproduced here
  // verbatim rather than re-derived, since this is quant methodology this designer may
  // not invent (PD-0014 §3) — only implement as specified.
  var BETA_RESIDUAL_SSE = pr1y.reduce(function (s, x, i) {
    var e = x - (mean(pr1y) + BETA * (br1y[i] - mean(br1y)));
    return s + e * e;
  }, 0);
  var BETA_SE = Math.sqrt(BETA_RESIDUAL_SSE / (WINDOW_OBS_COUNT - 2)) / (Math.sqrt(variance(br1y)) * Math.sqrt(WINDOW_OBS_COUNT));
  var BETA_SIGMAS_FROM_ONE = Math.abs(BETA - 1) / BETA_SE;
  var BETA_CI95 = [BETA - 1.96 * BETA_SE, BETA + 1.96 * BETA_SE];
  // HG1 round 4 (quant_analyst re-verification, HARMONIZED) — THE single documented
  // threshold for "may a directional/classification claim be asserted about which side
  // of a boundary an estimate falls on." quant_analyst's original §6 rule for beta set
  // a bare 1 se; the correlation classification-band precision guard (below,
  // correlationBandAssertable) was independently tightened to 1.96 se after a
  // mis-attributed se figure let its verdict flip on basis choice. That left two
  // different thresholds for the same class of judgment, with nothing recording why
  // they differed — a "parallel truth" one level up from the data itself (PD-0014
  // §2.5). A directional claim at a bare 1 se carries roughly a 1-in-6 chance of
  // pointing the wrong way; both judgments now read this ONE constant, equivalent to
  // requiring the reference value (1.0 for beta, a classification boundary for
  // correlation) to fall outside the estimate's own 95% confidence interval before a
  // direction/classification may be asserted at all.
  var DIRECTIONAL_CLAIM_SE_MULTIPLIER = 1.96;
  var BETA_WITHIN_TOLERANCE_BAND = Math.abs(BETA - 1) <= DIRECTIONAL_CLAIM_SE_MULTIPLIER * BETA_SE;

  // LOCAL-currency sleeve slices — used ONLY by the Sleeve Correlation Matrix below,
  // a deliberately different analytical question (asset-level co-movement,
  // independent of currency) that quant_analyst's review validated against these exact
  // local-series figures and did not ask to change.
  var usSlice1y = usEquitySleeve.slice(i1y), hkSlice1y = hkEquitySleeve.slice(i1y),
    cnSlice1y = cnEquitySleeve.slice(i1y), bondSlice1y = bondSleeve.slice(i1y);

  // BASE (reporting-currency, FX-inclusive) sleeve slices — used by Contribution-to-Risk
  // and the SML sleeve points, so those stay Euler-exact / consistent with the corrected
  // canonical portfolio series (pr1y above), which is itself built from these same base
  // sleeve series.
  var usSlice1yBase = usSlice1y, bondSlice1yBase = bondSlice1y; // USD sleeves: base === local
  var hkSlice1yBase = hkEquitySleeveBase.slice(i1y);
  var cnSlice1yBase = cnEquitySleeveBase.slice(i1y);

  // =======================================================================
  // 4. Transactions — buys, sells, dividends, deposits, FX
  // =======================================================================
  var TRANSACTIONS = [
    { id: "tx-0001", date: "2025-01-06", type: "DEPOSIT", accountId: "acct-us-1", amount: 25000, currency: "USD", note: "Initial funding" },
    { id: "tx-0002", date: "2025-01-08", type: "BUY", accountId: "acct-us-1", instrumentId: "AAPL", quantity: 80, price: 149.10, currency: "USD" },
    { id: "tx-0003", date: "2025-01-15", type: "BUY", accountId: "acct-us-1", instrumentId: "MSFT", quantity: 40, price: 309.50, currency: "USD" },
    { id: "tx-0004", date: "2025-02-03", type: "BUY", accountId: "acct-hk-1", instrumentId: "0700.HK", quantity: 500, price: 305.00, currency: "HKD" },
    { id: "tx-0005", date: "2025-02-10", type: "DEPOSIT", accountId: "acct-hk-1", amount: 100000, currency: "HKD", note: "Wire funding" },
    { id: "tx-0006", date: "2025-03-01", type: "BUY", accountId: "acct-hk-1", instrumentId: "0941.HK", quantity: 2000, price: 58.20, currency: "HKD" },
    { id: "tx-0007", date: "2025-03-14", type: "DIVIDEND", accountId: "acct-us-1", instrumentId: "AAPL", amount: 62.40, currency: "USD" },
    { id: "tx-0008", date: "2025-04-02", type: "BUY", accountId: "acct-us-1", instrumentId: "NVDA", quantity: 40, price: 410.75, currency: "USD" },
    { id: "tx-0009", date: "2025-04-18", type: "FX", accountId: "acct-cash-1", fromCurrency: "USD", toCurrency: "HKD", amount: 20000, rate: 7.808, note: "Rebalance funding transfer" },
    { id: "tx-0010", date: "2025-05-05", type: "BUY", accountId: "acct-hk-1", instrumentId: "9988.HK", quantity: 600, price: 78.50, currency: "HKD" },
    { id: "tx-0011", date: "2025-05-20", type: "DIVIDEND", accountId: "acct-hk-1", instrumentId: "0941.HK", amount: 1840.00, currency: "HKD" },
    { id: "tx-0012", date: "2025-06-02", type: "BUY", accountId: "acct-us-2", instrumentId: "VOO", quantity: 85, price: 390.00, currency: "USD" },
    { id: "tx-0013", date: "2025-06-15", type: "BUY", accountId: "acct-us-2", instrumentId: "TLT", quantity: 150, price: 92.40, currency: "USD" },
    { id: "tx-0014", date: "2025-07-02", type: "BUY", accountId: "acct-hk-1", instrumentId: "3690.HK", quantity: 300, price: 102.00, currency: "HKD" },
    { id: "tx-0015", date: "2025-08-11", type: "DIVIDEND", accountId: "acct-us-1", instrumentId: "MSFT", amount: 44.40, currency: "USD" },
    { id: "tx-0016", date: "2025-09-09", type: "DEPOSIT", accountId: "acct-cn-1", amount: 800000, currency: "CNY", note: "Wire funding, China A-share brokerage account opened" },
    { id: "tx-0017", date: "2025-09-16", type: "BUY", accountId: "acct-cn-1", instrumentId: "300750.SZ", quantity: 500, price: 168.40, currency: "CNY" },
    { id: "tx-0018", date: "2025-10-07", type: "BUY", accountId: "acct-cn-1", instrumentId: "601318.SS", quantity: 300, price: 45.60, currency: "CNY" },
    { id: "tx-0019", date: "2025-11-04", type: "BUY", accountId: "acct-hk-1", instrumentId: "2800.HK", quantity: 2000, price: 3.20, currency: "HKD" },
    { id: "tx-0020", date: "2026-01-12", type: "DIVIDEND", accountId: "acct-hk-1", instrumentId: "0700.HK", amount: 1240.00, currency: "HKD" },
    { id: "tx-0021", date: "2026-02-20", type: "FX", accountId: "acct-cash-1", fromCurrency: "USD", toCurrency: "CNY", amount: 15000, rate: 7.12, note: "Rebalance funding transfer" },
    { id: "tx-0022", date: "2026-03-05", type: "BUY", accountId: "acct-us-1", instrumentId: "AAPL", quantity: 40, price: 146.80, currency: "USD" },
    { id: "tx-0023", date: "2026-03-18", type: "SELL", accountId: "acct-us-1", instrumentId: "NVDA", quantity: 0, price: 0, currency: "USD", note: "Placeholder — no sells this period; kept for taxonomy coverage", voided: true },
    { id: "tx-0024", date: "2026-04-22", type: "BUY", accountId: "acct-us-1", instrumentId: "MSFT", quantity: 20, price: 398.10, currency: "USD" },
    { id: "tx-0025", date: "2026-05-14", type: "DIVIDEND", accountId: "acct-us-2", instrumentId: "VOO", amount: 312.60, currency: "USD" },
    { id: "tx-0026", date: "2026-06-01", type: "DIVIDEND", accountId: "acct-cn-1", instrumentId: "300750.SZ", amount: 640.00, currency: "CNY" },
    { id: "tx-0027", date: "2026-07-02", type: "TRANSFER_IN", accountId: "acct-cn-1", instrumentId: "600519.SS", quantity: 20, price: null, currency: "CNY", note: "In-kind transfer from a legacy custodian; original cost basis not provided by sending broker", costBasisMissing: true },
    { id: "tx-0028", date: "2026-08-19", type: "DEPOSIT", accountId: "acct-cash-1", amount: 5000, currency: "USD" },
    { id: "tx-0029", date: "2026-09-02", type: "DIVIDEND", accountId: "acct-cn-1", instrumentId: "601318.SS", amount: 180.00, currency: "CNY", fxHistoryState: "MISSING_FX_HISTORY", note: "Reporting-currency conversion pending — no FX print on file yet for this transaction date" },
    { id: "tx-0030", date: "2025-12-01", type: "DEPOSIT", accountId: "acct-us-1", amount: 3000, currency: "USD" }
  ].filter(function (t) { return !t.voided; });

  // HG1 round 4 (quant_analyst verification §7.2) — external contributions within the
  // trailing year, computed from the ledger rather than hand-typed, so metric.pl.absolute's
  // caveat states the true figure and stays correct if the ledger ever changes. Cutoff is
  // a calendar year before the as-of date (not the exact 252-observation window), matching
  // how a reader would think about "contributions in the trailing year."
  var TRAILING_YEAR_CUTOFF_DATE = new Date(END_DATE.getTime() - 365 * 86400000).toISOString().slice(0, 10);
  var TRAILING_YEAR_CONTRIBUTIONS_USD = TRANSACTIONS.filter(function (t) { return t.type === "DEPOSIT" && t.date >= TRAILING_YEAR_CUTOFF_DATE; })
    .reduce(function (s, t) { return s + t.amount * FX_RATES[t.currency]; }, 0);

  // =======================================================================
  // 5. Exposure breakdowns (facts, computed from HOLDINGS — no sufficiency issue
  //    except currency exposure, below, which carries one deliberately)
  // =======================================================================
  var EXPOSURE = {
    assetClass: groupBy(HOLDINGS, function (h) { return h.assetClass; }, marketValueUSD),
    sector: groupBy(HOLDINGS, function (h) { return h.sector; }, marketValueUSD),
    listingMarket: groupBy(HOLDINGS, function (h) { return h.listingMarket; }, marketValueUSD),
    economicGeography: groupBy(HOLDINGS, function (h) { return h.economicGeography; }, marketValueUSD),
    country: groupBy(HOLDINGS, function (h) { return h.economicGeography; }, marketValueUSD),
    currency: groupBy(HOLDINGS.concat(CASH_BALANCES.map(function (c) { return { currency: c.currency, quantity: 1, price: c.amount, listingMarket: null }; })),
      function (h) { return h.currency; }, function (h) { return h.quantity !== undefined && h.price !== undefined ? h.quantity * h.price * FX_RATES[h.currency] : marketValueUSD(h); })
  };

  // =======================================================================
  // 6. Concentration, correlation, contribution-to-risk, SML/CAPM
  // =======================================================================
  var holdingsWithValue = HOLDINGS.map(function (h) { return { id: h.id, name: h.name, value: marketValueUSD(h) }; })
    .sort(function (a, b) { return b.value - a.value; });
  var TOP5_SUM = holdingsWithValue.slice(0, 5).reduce(function (s, h) { return s + h.value; }, 0);
  var HHI = holdingsWithValue.reduce(function (s, h) { return s + Math.pow(h.value / TOTAL_HOLDINGS_VALUE, 2); }, 0);
  var EFFECTIVE_N = 1 / HHI;

  // Sleeve Correlation Matrix — LOCAL-currency series for the four sleeves, DISPLAYED
  // and rounded to 2dp, deliberately (see §3 comment). HG1 round 4 (quant_analyst
  // verification §4.3): the fifth row/column (the benchmark) is a USD series, not
  // local-currency — this mixes bases in one table. Fixing the LABEL (referencePoint/
  // caveat on metric.correlation, below) is HG1 scope; migrating the whole DISPLAYED
  // matrix to one basis is CP1 (numbers barely move: max abs difference 0.0088 across
  // the whole matrix, and the equity-pair ranking is identical either way, so no
  // currently-displayed conclusion changes).
  var CORR_LABELS = ["US Equity Sleeve", "HK Equity Sleeve", "CN Equity Sleeve", "Bonds", "Benchmark (MSCI ACWI)"];
  var CORR_SERIES_1Y = [usSlice1y, hkSlice1y, cnSlice1y, bondSlice1y, br1y];
  var CORR_MATRIX = CORR_SERIES_1Y.map(function (a) {
    return CORR_SERIES_1Y.map(function (b) { return Math.round(pearson(a, b) * 100) / 100; });
  });

  // NOT displayed anywhere and NOT a basis migration (that stays CP1) — computed only
  // so the classification-band precision guard below (quant verification §5.2, which is
  // explicit that "classification applies to the base (reporting-currency) matrix")
  // can be evaluated on the correct basis, at full precision (not rounded to 2dp, since
  // the standard-error comparison needs the true value). The four base sleeve slices
  // (usSlice1yBase/hkSlice1yBase/cnSlice1yBase/bondSlice1yBase) already exist for
  // Contribution-to-Risk/SML; reused here rather than duplicated.
  var CORR_SERIES_1Y_BASE = [usSlice1yBase, hkSlice1yBase, cnSlice1yBase, bondSlice1yBase, br1y];
  var CORR_MATRIX_BASE = CORR_SERIES_1Y_BASE.map(function (a) {
    return CORR_SERIES_1Y_BASE.map(function (b) { return pearson(a, b); });
  });

  // HG1 round 4 (quant_analyst verification §5.2, re-verification tightening) — the
  // correlation classification rule this designer correctly declined to invent is now
  // specified by quant_analyst and implemented verbatim (methodology/
  // HG1_ROUND4_VERIFICATION.md §5.2). Bands are derived from realized diversification
  // benefit for an equal-weight pair (1 − sqrt((1+rho)/2)), not asserted; the
  // precision guard (se(rho) ≈ (1-rho^2)/sqrt(n-1), boundary must be ≥
  // DIRECTIONAL_CLAIM_SE_MULTIPLIER [1.96] se away — 95% confidence, harmonized with
  // beta's own directional-claim threshold below) is what makes a band label safe to
  // assert rather than a rank-only comparison.
  function correlationBand(rho, lang) {
    if (lang === "zh") {
      if (rho >= 0.80) return "几乎完全同步——彼此分散化效果很小";
      if (rho >= 0.60) return "强联动";
      if (rho >= 0.35) return "中度联动";
      if (rho >= 0.15) return "弱联动";
      return "在本样本中基本独立";
    }
    if (rho >= 0.80) return "move almost identically — little diversification benefit between them";
    if (rho >= 0.60) return "strongly co-moving";
    if (rho >= 0.35) return "moderately co-moving";
    if (rho >= 0.15) return "weakly co-moving";
    return "largely independent in this sample";
  }
  var CORRELATION_BAND_BOUNDARIES = [0.80, 0.60, 0.35, 0.15];
  function correlationBandStandardError(rho, n) { return (1 - rho * rho) / Math.sqrt(n - 1); }
  function correlationBandNearestBoundaryDistance(rho) {
    return Math.min.apply(null, CORRELATION_BAND_BOUNDARIES.map(function (b) { return Math.abs(rho - b); }));
  }
  // HG1 round 4 (quant_analyst re-verification) — TIGHTENED from a bare 1 standard
  // error to 1.96 (95% confidence). quant_analyst's original §5.2 rule quoted
  // se(HK/CN)=0.048, which was actually the US/HK row's standard error; the correct
  // se at rho(HK,CN)~0.20-0.21 is ~0.060, and at that se the 1-se guard let the
  // verdict flip depending on which basis (local 0.203, 0.869 se vs base 0.211,
  // 1.018 se) was used to evaluate it — the same value asserted as both "rank-only"
  // and "assertable" depending on an implementation detail invisible to the reader. At
  // 1.96 se the HK/CN pair no longer clears on EITHER basis (only US/HK does, at
  // ~2.45 se), so the basis-sensitivity vanishes rather than merely narrowing, and the
  // rule keeps doing real work elsewhere (5 of 6 pairs are correctly rank-only under
  // it). This also closes a second defect as a direct consequence: the band sentence
  // previously quoted rho=0.21 (the base-basis value) immediately after the DISPLAYED
  // matrix's own rho=0.20 (local basis) for the identical cell — two numbers for one
  // number, reconcilable only by reading the methodology entry. Since the band clause
  // no longer fires for HK/CN at all under the tightened guard, that mismatch cannot
  // recur for this pair.
  function correlationBandAssertable(rho, n) {
    // Reads the SAME DIRECTIONAL_CLAIM_SE_MULTIPLIER (1.96, defined above alongside
    // BETA_SE) the beta directional-claim guard uses — one documented threshold for
    // "may a directional/classification claim be asserted," not a locally re-typed
    // number that could quietly drift from beta's.
    return correlationBandNearestBoundaryDistance(rho) >= DIRECTIONAL_CLAIM_SE_MULTIPLIER * correlationBandStandardError(rho, n);
  }
  var CORR_HK_IDX_BASE = CORR_LABELS.indexOf("HK Equity Sleeve"), CORR_CN_IDX_BASE = CORR_LABELS.indexOf("CN Equity Sleeve");
  var CORR_HK_CN_RHO_BASE = CORR_MATRIX_BASE[CORR_HK_IDX_BASE][CORR_CN_IDX_BASE];
  var CORR_HK_CN_BAND_INFO = {
    rhoBase: CORR_HK_CN_RHO_BASE,
    se: correlationBandStandardError(CORR_HK_CN_RHO_BASE, WINDOW_OBS_COUNT),
    band: correlationBand(CORR_HK_CN_RHO_BASE),
    bandZh: correlationBand(CORR_HK_CN_RHO_BASE, "zh"),
    assertable: correlationBandAssertable(CORR_HK_CN_RHO_BASE, WINDOW_OBS_COUNT)
  };

  function volOf(arr) { return stdev(arr) * Math.sqrt(252); }
  // BASE (FX-inclusive) sleeve vols/correlations — Euler-exact against the canonical pr1y.
  var sleeveVols = { us: volOf(usSlice1yBase), hk: volOf(hkSlice1yBase), cn: volOf(cnSlice1yBase), bond: volOf(bondSlice1yBase) };
  var sleeveCorrToPortfolio = {
    us: pearson(usSlice1yBase, pr1y), hk: pearson(hkSlice1yBase, pr1y), cn: pearson(cnSlice1yBase, pr1y), bond: pearson(bondSlice1yBase, pr1y)
  };
  // Exact Euler (marginal-contribution-to-volatility) decomposition: weight * vol *
  // correlation-to-portfolio. HG1 round 4 (methodology findings §7.7): this is NOT an
  // approximation — Sum_i w_i*sigma_i*rho(i,P) = sigma_P exactly for a linear portfolio,
  // which the replication script confirms to 10 decimal places. The prior comment
  // calling this "a simplified illustrative approximation... NOT a certified
  // risk-decomposition engine" understated an exact method; corrected below and in
  // methodology.contributionToRisk.
  var rawContrib = {
    us: SLEEVE_WEIGHTS.us * sleeveVols.us * sleeveCorrToPortfolio.us,
    hk: SLEEVE_WEIGHTS.hk * sleeveVols.hk * sleeveCorrToPortfolio.hk,
    cn: SLEEVE_WEIGHTS.cn * sleeveVols.cn * sleeveCorrToPortfolio.cn,
    bond: SLEEVE_WEIGHTS.bond * sleeveVols.bond * sleeveCorrToPortfolio.bond
  };
  var rawContribTotal = Object.keys(rawContrib).reduce(function (s, k) { return s + rawContrib[k]; }, 0);
  var CONTRIBUTION_TO_RISK = [
    { label: "US Equity Sleeve", weight: SLEEVE_WEIGHTS.us, value: rawContrib.us / rawContribTotal, unit: "percent", sufficiency: "AVAILABLE", reasonCode: null, caveat: "" },
    { label: "Hong Kong Equity Sleeve", weight: SLEEVE_WEIGHTS.hk, value: rawContrib.hk / rawContribTotal, unit: "percent", sufficiency: "AVAILABLE", reasonCode: null, caveat: "" },
    { label: "Mainland China Equity Sleeve", weight: SLEEVE_WEIGHTS.cn, value: null, unit: "percent", reasonCode: "CALCULATION_ERROR",
      sufficiency: "INSUFFICIENT_DATA",
      caveat: "Residual reconciliation failed for this segment during the last recompute; contribution figure withheld pending recalculation.",
      // HG1 Round 5 micro-pass (Item 3) — added `i18n.zh.caveat` (PM-cited
      // example: "Residual reconciliation failed for this segment..."). This
      // segment object is not a `claim()`-wrapped object, but
      // js/surfaces/analytics.js's contribution-list already calls
      // `ctx.ui.localizeClaimField(seg, "caveat")` on every segment (that
      // function only requires `.i18n[lang][field]`, not a claim wrapper) — so
      // this was a missing-DATA gap, not a missing-mechanism one.
      i18n: { zh: { caveat: "该板块在上次重新计算时的余额核对失败;贡献占比数值予以隐去,待重新计算后再显示。" } } },
    { label: "Bonds", weight: SLEEVE_WEIGHTS.bond, value: rawContrib.bond / rawContribTotal, unit: "percent", sufficiency: "AVAILABLE", reasonCode: null, caveat: "" }
  ];

  // HG1 round 4 (methodology findings §7.7) — the withheld segment's gap must be a
  // labelled remainder, not a silent one: the three AVAILABLE shares below sum to
  // whatever they sum to (NOT necessarily 100%, since the withheld segment's weight is
  // still in the normalization denominator, which is the CORRECT arithmetic).
  var CONTRIB_AVAILABLE = CONTRIBUTION_TO_RISK.filter(function (s) { return s.sufficiency === "AVAILABLE" && typeof s.value === "number"; });
  var CONTRIB_WITHHELD = CONTRIBUTION_TO_RISK.filter(function (s) { return s.sufficiency !== "AVAILABLE"; });
  var CONTRIB_AVAILABLE_SUM = CONTRIB_AVAILABLE.reduce(function (s, x) { return s + x.value; }, 0);

  function shortSleeveName(label) { return label.replace(" Equity Sleeve", "").replace(" Sleeve", ""); }

  // HG1 round 4 (Task 2, PD-0014 §2.3 binding example 2) — "X and Y contribute the
  // most" must be DERIVED from the ranked, AVAILABLE contribution values, never
  // hand-asserted. A withheld segment can never be named as "contributing the most,"
  // since it has no shown value to rank (P5).
  function contributionRiskConclusion(segments, lang) {
    var avail = segments.filter(function (s) { return s.sufficiency === "AVAILABLE" && typeof s.value === "number"; });
    if (avail.length === 0) {
      return lang === "zh" ? "本期风险贡献无法排序——没有可计算数值的板块。" : "Risk contribution cannot be ranked this period — no segment has a computed value.";
    }
    var ranked = avail.slice().sort(function (a, b) { return b.value - a.value; });
    var withheld = segments.filter(function (s) { return s.sufficiency !== "AVAILABLE"; });
    // HG1 round 4 (quant_analyst verification §6) — this claim is only statistically
    // safe BECAUSE it names the top two as a set: on this data US (46.36%) and HK
    // (45.10%) are 1.26 percentage points apart, which would NOT support singling out
    // one as "the" leader. DO NOT change this to `[ranked[0]]` when >=2 segments are
    // AVAILABLE — that would reintroduce a false-precision claim of exactly the shape
    // the beta directional-claim defect was (see betaDirectionConclusion above). This
    // applies identically to BOTH language branches below.
    var names = ranked.length >= 2 ? [ranked[0], ranked[1]] : [ranked[0]];
    var text;
    // HG1 round 4 (quant_analyst re-verification) — a risk-contribution share is a
    // LEVEL (owner's §6.3), so it must never carry the spurious "+" APP_fmtPct would
    // add — but unlike a level that is always non-negative (volatility, a rate
    // assumption), MCTR_i = w_i·σ_i·ρ_i,P is GENUINELY NEGATIVE when a sleeve is
    // negatively correlated with the portfolio (a hedge — the one case where the sign
    // carries all the meaning). APP_fmtMagnitudePct's Math.abs() would silently turn a
    // -8% hedging contribution into "8%", erasing exactly the fact the number exists
    // to show. APP_fmtLevelPct is therefore the correct formatter here: it preserves
    // whatever sign the value actually has while still suppressing the superfluous
    // "+" on an ordinary positive contribution. All four segments are positive in
    // this dataset today, so this is a forward guard, not a rendering that changes
    // right now.
    if (lang === "zh") {
      var nameTextZh = names.map(function (s) { return sleeveNameZh(shortSleeveName(s.label)); }).join("和");
      text = nameTextZh + (names.length > 1 ? "板块合计贡献了" : "板块贡献了") +
        "本期最大的组合风险,分别占已排序(可用)板块中的" +
        names.map(function (s) { return APP_fmtLevelPct(s.value); }).join("和") + "。";
      if (withheld.length) {
        text += withheld.map(function (s) { return sleeveNameZh(shortSleeveName(s.label)); }).join("、") +
          "的风险贡献因数据不足在上方被隐去,已从本排序中剔除,并非被视为占比很小。";
      }
    } else {
      var nameText = names.map(function (s) { return shortSleeveName(s.label); }).join(" and ");
      text = (names.length > 1 ? nameText + " sleeves contribute" : nameText + " sleeve contributes") +
        " the most to overall portfolio risk this period, at " +
        names.map(function (s) { return APP_fmtLevelPct(s.value); }).join(" and ") + " of the ranked (AVAILABLE) segments.";
      if (withheld.length) {
        text += " " + withheld.map(function (s) { return shortSleeveName(s.label); }).join(", ") +
          "'s contribution is withheld above (insufficient data) and is excluded from this ranking, not assumed small.";
      }
    }
    return text;
  }

  var SML_LINE = { slope: BENCHMARK_PERIOD_RETURN - RF_ANNUAL, intercept: RF_ANNUAL };
  // HG1 round 4 (methodology findings §2) — sleeve points now use the BASE (FX-inclusive,
  // reporting-currency) series for HK/CN, consistent with the Y axis's stated basis
  // ("Realized total return, trailing 1Y, USD, compounded") and with beta being computed
  // in reporting currency.
  var SML_POINTS = [
    { label: "Your Portfolio", beta: BETA, ret: PERIOD_RETURN, group: "portfolio" },
    { label: "Benchmark (MSCI ACWI)", beta: 1, ret: BENCHMARK_PERIOD_RETURN, group: "benchmark" },
    { label: "US Sleeve", beta: pearson(usSlice1yBase, br1y) * volOf(usSlice1yBase) / BENCHMARK_ANNUAL_VOL, ret: cumulativeIndex(usEquitySleeveBase.slice(i1y))[usEquitySleeveBase.slice(i1y).length - 1] / 100 - 1, group: "sleeve" },
    { label: "HK Sleeve", beta: pearson(hkSlice1yBase, br1y) * volOf(hkSlice1yBase) / BENCHMARK_ANNUAL_VOL, ret: cumulativeIndex(hkEquitySleeveBase.slice(i1y))[hkEquitySleeveBase.slice(i1y).length - 1] / 100 - 1, group: "sleeve" },
    { label: "CN Sleeve", beta: pearson(cnSlice1yBase, br1y) * volOf(cnSlice1yBase) / BENCHMARK_ANNUAL_VOL, ret: cumulativeIndex(cnEquitySleeveBase.slice(i1y))[cnEquitySleeveBase.slice(i1y).length - 1] / 100 - 1, group: "sleeve" }
  ];
  // HG1 round 4 (methodology findings §2.2) — CONCEPT 4, the line's actual vertical
  // distance at the portfolio's own beta: realized portfolio return minus the ex-post
  // line's implied return at that beta. This is a DIFFERENT quantity from ALPHA_ANNUAL
  // (concept 3: an OLS regression estimate on arithmetic daily excess returns,
  // annualized x252) — the two are usually close but not identical (a geometric-vs-
  // arithmetic gap), and the chart must annotate its own vertical distance with THIS
  // number, not with regression alpha. See getSMLPoints()'s exposed `verticalDistance`
  // field and this worker's handoff for the analytics.js/charts.js wiring this requires
  // (outside this designer's write path).
  var SML_LINE_IMPLIED_PORTFOLIO_RETURN = SML_LINE.intercept + BETA * SML_LINE.slope;
  var SML_VERTICAL_DISTANCE = PERIOD_RETURN - SML_LINE_IMPLIED_PORTFOLIO_RETURN;

  // FX / performance attribution — HG1 round 4 rebuild (methodology findings §4.3).
  // Sleeve-level components (local / FX / interaction / base), computed from the raw
  // LOCAL sleeve and FX series, exact per-sleeve identity:
  //   R_base = (1+R_local)(1+R_fx) - 1 = R_local + R_fx + (R_local * R_fx)
  var hkLocalReturn = cumulativeIndex(hkEquitySleeve.slice(i1y))[hkEquitySleeve.slice(i1y).length - 1] / 100 - 1;
  var hkFxReturn = cumulativeIndex(fxHKD.slice(i1y))[fxHKD.slice(i1y).length - 1] / 100 - 1;
  var hkInteraction = hkLocalReturn * hkFxReturn;
  var hkBaseSleeveReturn = combineLocalFx(hkLocalReturn, hkFxReturn);
  var cnLocalReturn = cumulativeIndex(cnEquitySleeve.slice(i1y))[cnEquitySleeve.slice(i1y).length - 1] / 100 - 1;
  var cnFxReturn = cumulativeIndex(fxCNY.slice(i1y))[fxCNY.slice(i1y).length - 1] / 100 - 1;
  var cnInteraction = cnLocalReturn * cnFxReturn;
  var cnBaseSleeveReturn = combineLocalFx(cnLocalReturn, cnFxReturn);

  // Portfolio-level FX effect — HG1 round 4: EXACT by construction (methodology findings
  // §4.3's ruling), replacing the prior weighted-FX-return-sum approximation, which was
  // ALSO the wrong sign relative to how it was consumed downstream (analytics.js derived
  // "local return" as total-minus-FX, which only works if the total genuinely contains
  // the FX effect being subtracted — it previously did not, per §4.1).
  var FX_ATTRIBUTION_PCT = PERIOD_RETURN - PERIOD_RETURN_LOCAL;

  // =======================================================================
  // 7. Freshness axes (D5) — categorical states, never merged, ranked by
  //    severity rather than raw clock comparison (see shell.js rankLeastFresh).
  //
  //    HG1 round 4 (methodology findings §5.4, PD-0014 Part 1 §1.2 point 3) —
  //    freshness is measured in LOCAL TRADING SESSIONS elapsed since the print, never
  //    wall-clock age. The SESSION-AWARE PRINCIPLE is correct and is preserved below.
  //
  //    CORRECTION (human product owner, this round): an EARLIER version of this file
  //    asserted, in a comment and in the cn_equity axis's own `note`, that
  //    "Shanghai/Shenzhen closed for a local holiday on 2026-09-03" and derived ZERO
  //    elapsed sessions from that claim. THE OWNER IS RIGHT THAT THIS IS FALSE:
  //    2026-09-03 is a Thursday (deterministically verified — not a weekend), and it
  //    is not a standing PRC public holiday: September 3 (Victory Day, a commemorative
  //    date) was made a one-off public holiday only in 2015 (70th anniversary) and
  //    2025 (80th anniversary) by specific State Council announcement each time; 2026
  //    is the 81st anniversary, not a year that historical pattern covers. No other
  //    PRC holiday falls near this date (Mid-Autumn ~2026-09-25, National Day
  //    2026-10-01 to -07). SSE/SZSE traded normally on 2026-09-03.
  //
  //    LIMITATION, stated explicitly per the owner's instruction: this harness has NO
  //    NETWORK EGRESS. The weekday determination below is deterministic (day-of-week
  //    arithmetic on a plain calendar date, always correct). The HOLIDAY list is NOT
  //    sourced from an authoritative exchange calendar lookup — it reflects
  //    established PRC public-holiday practice as understood at the time this was
  //    written, not a fetched SSE/SZSE trading calendar. An authoritative calendar
  //    confirmation remains an outstanding human/network step this fixture cannot
  //    close on its own.
  //
  //    THE FIX IS TO THE CALENDAR/REFERENCE DATA, NOT THE PRINCIPLE. A wall-clock rule
  //    would still be wrong; a session-aware rule fed a false calendar produced this
  //    defect. The calendar below is now explicit, testable DATA — SSE_HOLIDAYS_2026,
  //    sseSessionInfo(), sseSessionsElapsed() — that the classification is DERIVED
  //    from in one place, rather than a fact restated independently in prose (a
  //    freshness note, an insight string, a comparability caveat) that can drift from
  //    the code and from itself. See js/selfcheck.js's five sseCalendar.* assertions.
  var SSE_HOLIDAYS_2026 = [
    // National Day golden week — a standing, law-mandated 7-day PRC public holiday
    // every year (State Council). High confidence on these base dates; year-specific
    // "makeup workday" weekend swaps sometimes layered around it are NOT modeled here
    // (not needed for this window) and would require the network-verified calendar
    // named above if a future window needs them.
    { date: "2026-10-01", name: "National Day (PRC)" },
    { date: "2026-10-02", name: "National Day (PRC)" },
    { date: "2026-10-03", name: "National Day (PRC)" },
    { date: "2026-10-04", name: "National Day (PRC)" },
    { date: "2026-10-05", name: "National Day (PRC)" },
    { date: "2026-10-06", name: "National Day (PRC)" },
    { date: "2026-10-07", name: "National Day (PRC)" },
    // Approximate: Mid-Autumn Festival follows the lunar calendar. Not independently
    // verified against an authoritative calendar in this network-free environment —
    // included only because it is outside the window any current claim depends on,
    // so an error here does not affect anything this file currently asserts.
    { date: "2026-09-25", name: "Mid-Autumn Festival (approximate; unverified)" }
    // 2026-09-03 is DELIBERATELY NOT listed — see the correction note above. This
    // fixture's own prior error is the reason this list exists as data rather than
    // as unchecked prose.
  ];
  var SSE_HOLIDAY_DATES = {};
  SSE_HOLIDAYS_2026.forEach(function (h) { SSE_HOLIDAY_DATES[h.date] = h.name; });

  function sseDayOfWeek(dateStr) { return new Date(dateStr + "T00:00:00Z").getUTCDay(); } // 0=Sun..6=Sat, deterministic
  function sseIsWeekend(dateStr) { var d = sseDayOfWeek(dateStr); return d === 0 || d === 6; }
  // Classifies ONE calendar date. Checks weekend before the holiday list (a date that
  // happens to be both is still, correctly, just a non-trading day either way, but
  // WEEKEND is the more informative reason when both apply).
  function sseSessionInfo(dateStr) {
    if (sseIsWeekend(dateStr)) return { date: dateStr, tradingDay: false, reason: "WEEKEND" };
    if (Object.prototype.hasOwnProperty.call(SSE_HOLIDAY_DATES, dateStr)) {
      return { date: dateStr, tradingDay: false, reason: "HOLIDAY", holidayName: SSE_HOLIDAY_DATES[dateStr] };
    }
    return { date: dateStr, tradingDay: true, reason: "TRADING_DAY" };
  }
  // Counts SSE trading SESSIONS strictly AFTER `fromDate` and at or before `toDate`
  // (both "YYYY-MM-DD") — "sessions elapsed since the print," the exact quantity
  // §5.4's session-aware freshness rule is defined over. A weekend or holiday between
  // the two dates does not add to the count (staleness is measured in sessions the
  // market actually held, not in calendar days).
  function sseSessionsElapsed(fromDate, toDate) {
    var count = 0;
    var d = new Date(fromDate + "T00:00:00Z");
    var end = new Date(toDate + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + 1);
    while (d.getTime() <= end.getTime()) {
      if (sseSessionInfo(d.toISOString().slice(0, 10)).tradingDay) count++;
      d.setUTCDate(d.getUTCDate() + 1);
    }
    return count;
  }
  // The §5.4 threshold table (methodology findings, quant_analyst-set), now a
  // function of the computed session count rather than an assumption — the same
  // table used before, just correctly fed. 0 sessions reuses the "just closed"
  // category (END_OF_DAY) already used for HK/US; STALE begins at 1.
  function sseFreshnessState(sessionsElapsed) { return sessionsElapsed <= 0 ? "END_OF_DAY" : "STALE"; }
  function sseSufficiencyForSessions(sessionsElapsed) {
    if (sessionsElapsed <= 0) return { sufficiency: "AVAILABLE", reasonCode: null };
    if (sessionsElapsed === 1) return { sufficiency: "AVAILABLE", reasonCode: "STALE_DATA" };
    if (sessionsElapsed <= 4) return { sufficiency: "LIMITED", reasonCode: "STALE_DATA" };
    return { sufficiency: "INSUFFICIENT_DATA", reasonCode: "STALE_DATA" };
  }

  // CN A-share print is dated 2026-09-02; the snapshot's own as-of date (see
  // meta.asOfDefinition) is 2026-09-03. Computed, not asserted:
  var CN_PRINT_DATE = "2026-09-02";
  var CN_ASOF_DATE = END_DATE.toISOString().slice(0, 10); // "2026-09-03"
  var CN_SESSIONS_ELAPSED = sseSessionsElapsed(CN_PRINT_DATE, CN_ASOF_DATE);
  var CN_SESSION_INFO_ASOF = sseSessionInfo(CN_ASOF_DATE); // what 2026-09-03 itself actually is
  var CN_FRESHNESS_STATE = sseFreshnessState(CN_SESSIONS_ELAPSED);
  var CN_FRESHNESS_SUFFICIENCY = sseSufficiencyForSessions(CN_SESSIONS_ELAPSED);

  var FRESHNESS_AXES = [
    { axis: "us_equity", label: "US equity", state: "END_OF_DAY", asOf: "2026-09-03 16:00 ET" },
    { axis: "hk_equity", label: "HK equity", state: "END_OF_DAY", asOf: "2026-09-03 16:08 HKT" },
    { axis: "cn_equity", label: "CN A-share", state: CN_FRESHNESS_STATE, asOf: "2026-09-02 15:00 CST",
      sessionsElapsed: CN_SESSIONS_ELAPSED,
      note: "SSE/SZSE traded normally on " + CN_ASOF_DATE + " (a " +
        ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"][sseDayOfWeek(CN_ASOF_DATE)] +
        "; not a weekend, and not a PRC public holiday — September 3 was a one-off holiday only in the 2015 and 2025 anniversary years, not 2026). " +
        "This print has not been updated since " + CN_PRINT_DATE + ", so " + CN_SESSIONS_ELAPSED +
        " completed local trading session" + (CN_SESSIONS_ELAPSED === 1 ? " has" : "s have") +
        " elapsed without an update. Measured in local trading sessions (PD-0014 Part 1 §1.2), derived from an explicit SSE session calendar (SSE_HOLIDAYS_2026), not asserted in prose. An authoritative exchange-calendar confirmation has not been obtained (no network egress in this environment)." },
    { axis: "usd_hkd_fx", label: "USD/HKD FX", state: "DELAYED", asOf: "2026-09-03 16:45 ET", delayMinutes: 15 },
    { axis: "usd_cny_fx", label: "USD/CNY FX", state: "DELAYED", asOf: "2026-09-03 17:10 ET", delayMinutes: 45 }
  ];
  var CN_FRESHNESS_AXIS = FRESHNESS_AXES.filter(function (a) { return a.axis === "cn_equity"; })[0];

  // HG1 round 4 (methodology findings §5.2/§5.3, PD-0014 Part 1) — a two-leg,
  // benchmark-relative comparison whose legs carry materially different EFFECTIVE
  // TIMESTAMPS may stay AVAILABLE (computable, deterministic) but must disclose
  // limited temporal comparability. This is a DIFFERENT dimension from freshness/
  // sufficiency (a leg can be perfectly "current" under §5.4's session-aware rule and
  // still sit across a comparability seam, because markets close at different local
  // times) — it is NOT a fourth sufficiency state and NOT a new reason code (PD-0014
  // Part 1 §1.2/§1.3); it is a disclosure dimension on the existing D5 freshness axis.
  // This conclusion is UNCHANGED by the calendar correction above — the two legs were
  // never measured at the same instant either way — only the REASON changed: the gap
  // is genuine staleness (CN_SESSIONS_ELAPSED session(s) with no update), not a
  // market holiday.
  var BENCHMARK_RELATIVE_COMPARABILITY_NOTE =
    "Calculation available. One input market (Mainland China A-shares) is priced at its most recent available close, " +
    CN_FRESHNESS_AXIS.asOf + ", which is behind this comparison's as-of date (" + CN_ASOF_DATE +
    "). The portfolio and benchmark legs are therefore not measured at the same instant, and the difference shown " +
    "includes that timing gap. See the freshness indicator.";
  // HG1 round 4 (bilingual gap) — same underlying values (CN_FRESHNESS_AXIS.asOf,
  // CN_ASOF_DATE), Chinese sentence derived alongside the English one rather than
  // translated from a snapshot of it.
  var BENCHMARK_RELATIVE_COMPARABILITY_NOTE_ZH =
    "计算结果可用。其中一个输入市场(中国内地A股)的价格为其最近一次可得收盘价," +
    CN_FRESHNESS_AXIS.asOf + ",晚于本次比较的截止日期(" + CN_ASOF_DATE +
    ")。因此投资组合与基准两端并非在同一时点计量,所显示的差异中包含了这一时间差。详见新鲜度指标。";

  function getFreshness() {
    // Genuine order dependency, not defensive paranoia: this reads shell.js's
    // APP.ui.rankLeastFresh, which the fixed load order (shell.js, then data.js — see
    // CONTRACT.md §1) guarantees exists by the time this ever runs. The guard/fallback
    // exists so a future reorder fails soft (wrong axis) rather than throwing, and
    // CONTRACT.md §1 says so explicitly — this comment is not the only place that's
    // written down.
    return { axes: FRESHNESS_AXES, leastFreshAxis: window.APP.ui ? window.APP.ui.rankLeastFresh(FRESHNESS_AXES) : "cn_equity" };
  }

  // =======================================================================
  // 8. Claim objects (D2.2 shared claim object + D5 freshness slot + P8 stateType)
  // =======================================================================
  function claim(fields) {
    return Object.assign({
      stateType: "ACTUAL",
      sufficiency: "AVAILABLE",
      reasonCode: null,
      caveat: "",
      referencePoint: "",
      freshness: null,
      methodologyId: null,
      proofPacketId: null,
      scenarioId: null,
      // HG1 round 4 (bilingual gap) — populated ONLY for claims rendered on the two
      // "representative full screens" (Overview, Analytics) per the owner's §12.2 bar;
      // Portfolio/Ingest/Scenario claims are left null (deferred, stated plainly in the
      // CONTRACT.md addendum). Shape: { zh: { conclusionQuick?, explanationSimple?,
      // caveat?, investorDetail?, professionalDetail?, referencePoint? } }.
      // APP.ui.localizeClaimField(claim, field) reads this and falls back to the
      // English field when a language or a specific field is absent — a claim with
      // i18n:null (or a claim missing one field under i18n.zh) degrades gracefully to
      // English, it does not break. PD-0012 §3: canonical identifiers (tickers, ISO
      // codes, index/instrument names, currency codes, metric ids) are NEVER
      // translated inside these strings — only the surrounding prose is Chinese.
      i18n: null,
      // HG1 Condition 2 — `directional` is a rendering hint added this pass, read only by
      // js/shell.js's renderMetricValue to decide whether a value earns real green/red
      // ("reserve green/red for genuinely directional financial meaning"). Deliberately
      // NOT set here as a default — only the specific claims below opt in, by passing
      // `directional: true` in their own `fields`. A risk/ratio characteristic (beta,
      // volatility, Sharpe/Sortino, VaR, drawdown magnitude), a correlation sign, or any
      // SCENARIO-side comparison figure must never carry this flag — see the per-claim
      // comments below and tokens.css's --color-positive/--color-negative note.
      directional: false
    }, fields);
  }

  // ---- Dynamic conclusion helpers (PD-0014 §2.2 — derive claims from structured
  // values rather than hand-asserting an interpretation). Each of these replaces a
  // string that was previously hardcoded independently of the value beside it. ----

  // HG1 round 4 (quant_analyst verification §6) — a directional claim about beta may be
  // asserted only when it clears the ONE-STANDARD-ERROR band the quant set (their own
  // specification gap, closed there: deriving the sentence from the value was correct;
  // deriving it with NO tolerance band produced a false-precision claim once beta moved
  // to 0.994 ± 0.042 — a 0.143-sigma difference from 1.0 that this sample cannot
  // distinguish). Below the band, state indistinguishable and disclose the margin —
  // never a bare sign-based claim. This rule is quant methodology (PD-0014 §3); the
  // exact wording below is the quant's own required rendering, reproduced verbatim.
  // HG1 round 4 (bilingual gap) — every derived function below now takes a trailing
  // `lang` parameter ("en" default, "zh" for Chinese). The CONDITION that selects which
  // sentence fires is IDENTICAL in both branches (same `beta`, `se`, `pv`/`bv`, etc.) —
  // only the output template differs. This is the whole point: the coordinator's
  // instruction was that a derived claim's Chinese must be derived from the SAME
  // values, not hand-translated from one snapshot of the English output, so a future
  // change to the underlying number updates both languages identically and neither
  // can drift from the other. Canonical identifiers (market/currency codes, index
  // names, tickers) are never touched by the zh branch; only surrounding prose is
  // Chinese (PD-0012 §3). A small map, sleeveNameZh(), translates the plain-English
  // sleeve/asset-class NAMES (not identifiers) "US"/"HK"/"CN"/"Bonds"/"Hong Kong"/
  // "Mainland China" the way a security's name (not its ticker) may be translated.
  function sleeveNameZh(shortName) {
    var map = { "US": "美股", "HK": "港股", "CN": "A股", "Bonds": "债券", "Hong Kong": "港股", "Mainland China": "A股" };
    return map[shortName] || shortName;
  }

  // HG1 round 4 (quant_analyst re-verification) — the within-band sentence previously
  // said "the estimate's margin of error (±se) spans 1.0." A lay reader takes "margin
  // of error" to mean the 95% interval, not one standard error, so stating ±se under
  // that phrase understates the imprecision by half. Fixed by stating BOTH numbers
  // explicitly and never calling ±se alone a "margin of error": "standard error ±se,
  // and the 95% CI [lo, hi] spans 1.0." ci95 (BETA_CI95) is threaded through as its
  // own parameter rather than recomputed, so this can never drift from the same
  // interval exposed on the Proof Packet (getEvidence("metric.beta").confidence_interval_95).
  // HG1 round 4 (harmonized threshold) — uses DIRECTIONAL_CLAIM_SE_MULTIPLIER (1.96,
  // defined above), the SAME constant the correlation classification-band guard reads,
  // not a locally re-typed number. `se` stays the raw (1-se) standard error passed in
  // (and separately exposed on the Proof Packet, see registerEvidenceFor) — this
  // function is the one place that multiplies it up to the assertion threshold.
  function betaDirectionConclusion(beta, se, obsCount, ci95, lang) {
    if (lang === "zh") {
      if (Math.abs(beta - 1) <= DIRECTIONAL_CLAIM_SE_MULTIPLIER * se) {
        return "您投资组合的贝塔(β)与市场大体一致(β=" + beta.toFixed(2) + ")。基于" + obsCount +
          "个交易日的观测,标准误为±" + se.toFixed(2) + ",95%置信区间为 [" + ci95[0].toFixed(2) + ", " + ci95[1].toFixed(2) + "],覆盖了1.0,因此本样本无法将其与「与市场同步波动」区分开。";
      }
      if (beta < 1) return "您投资组合的历史波动幅度小于市场(β=" + beta.toFixed(2) + ",低于1,且差异超过1.96个标准误[95%置信水平])。";
      return "您投资组合的历史波动幅度大于市场(β=" + beta.toFixed(2) + ",高于1,且差异超过1.96个标准误[95%置信水平])。";
    }
    if (Math.abs(beta - 1) <= DIRECTIONAL_CLAIM_SE_MULTIPLIER * se) {
      return "Your portfolio has moved broadly in line with the market (beta " + beta.toFixed(2) + "). At " + obsCount +
        " daily observations, standard error ±" + se.toFixed(2) + ", and the 95% CI [" + ci95[0].toFixed(2) + ", " + ci95[1].toFixed(2) + "] spans 1.0, so this sample does not distinguish it from moving with the market.";
    }
    if (beta < 1) return "Your portfolio has historically moved less than the market (beta " + beta.toFixed(2) + ", below 1 by more than 1.96 standard errors [95% confidence]).";
    return "Your portfolio has historically moved more than the market (beta " + beta.toFixed(2) + ", above 1 by more than 1.96 standard errors [95% confidence]).";
  }

  function volatilityConclusion(pv, bv, lang) {
    if (lang === "zh") {
      if (pv > bv) return "您投资组合的收益率历史波动大于基准。";
      if (pv < bv) return "您投资组合的收益率历史波动小于基准。";
      return "您投资组合的收益率历史波动与基准大致相当。";
    }
    if (pv > bv) return "Your portfolio's return has historically varied more than its benchmark.";
    if (pv < bv) return "Your portfolio's return has historically varied less than its benchmark.";
    return "Your portfolio's return has historically varied about the same as its benchmark.";
  }

  function drawdownConclusion(pfDD, benchDD, lang) {
    var deeper = pfDD < benchDD; // more negative = deeper
    if (lang === "zh") {
      return "您投资组合本期的最大回撤(" + APP_fmtPct(pfDD) + ")" + (deeper ? "跌幅深于" : "跌幅浅于") + "基准的最大回撤(" + APP_fmtPct(benchDD) + ")。";
    }
    return "Your portfolio's maximum drawdown this period (" + APP_fmtPct(pfDD) + ") was " +
      (deeper ? "deeper than" : "shallower than") + " the benchmark's (" + APP_fmtPct(benchDD) + ").";
  }

  // HG1 round 4 (Task 2, PD-0014 §2.3 binding example 3) — "move together strongly" is
  // replaced with purely RANK-BASED (ordinal) language derived directly from the
  // matrix: strongest/weakest equity-sleeve pair, and whether bonds are actually any
  // more diversifying against one sleeve than the other. This deliberately avoids
  // asserting an absolute strong/moderate/weak classification, because no such
  // threshold has been set by quant_analyst (methodology findings, §2 of this file's
  // handoff) — PD-0014 §2.3 requires that a classification rule "must exist and be
  // owned by quant_analyst" before absolute-strength language is used at all. Rank-
  // based comparison needs no such threshold and is fully self-checkable (see
  // js/selfcheck.js).
  function correlationConclusion(labels, matrix, hkCnBandInfo, lang) {
    var equity = labels.map(function (l, i) { return { l: l, i: i }; }).filter(function (x) { return x.l.indexOf("Equity Sleeve") >= 0; });
    var pairs = [];
    for (var a = 0; a < equity.length; a++) {
      for (var b = a + 1; b < equity.length; b++) {
        pairs.push({ a: equity[a].l, b: equity[b].l, v: matrix[equity[a].i][equity[b].i] });
      }
    }
    pairs.sort(function (x, y) { return y.v - x.v; });
    var strongest = pairs[0], weakest = pairs[pairs.length - 1];
    var text;
    if (lang === "zh") {
      text = "在您的股票板块中," + sleeveNameZh(shortSleeveName(strongest.a)) + "与" + sleeveNameZh(shortSleeveName(strongest.b)) +
        "在本样本期间显示出最强的历史联动性(相关系数 " + strongest.v.toFixed(2) + ");" +
        sleeveNameZh(shortSleeveName(weakest.a)) + "与" + sleeveNameZh(shortSleeveName(weakest.b)) + "的联动性最弱(" + weakest.v.toFixed(2) + ")。";
    } else {
      text = "Among your equity sleeves, " + shortSleeveName(strongest.a) + " and " + shortSleeveName(strongest.b) +
        " show the strongest historical co-movement in this sample (correlation " + strongest.v.toFixed(2) + "); " +
        shortSleeveName(weakest.a) + " and " + shortSleeveName(weakest.b) + " show the weakest (" + weakest.v.toFixed(2) + ").";
    }
    var bondIdx = labels.indexOf("Bonds"), hkIdx = labels.indexOf("HK Equity Sleeve"), cnIdx = labels.indexOf("CN Equity Sleeve");
    if (bondIdx >= 0 && hkIdx >= 0 && cnIdx >= 0) {
      var hkBond = matrix[hkIdx][bondIdx], cnBond = matrix[cnIdx][bondIdx];
      if (lang === "zh") {
        text += "债券与港股(" + hkBond.toFixed(2) + ")、A股(" + cnBond.toFixed(2) + ")的相关性同样较弱——债券对二者的分散化效果并无明显差异。";
      } else {
        text += " Bonds show a similarly weak correlation to both Hong Kong (" + hkBond.toFixed(2) + ") and Mainland China (" +
          cnBond.toFixed(2) + ") in this sample — bonds are not meaningfully more diversifying against one than the other.";
      }
    }
    // HG1 round 4 (quant_analyst verification §5.2, re-verification tightening to
    // 1.96 se) — this rank-based check stays UNCHANGED above (per the quant's explicit
    // instruction); the band-classification rule is a strict ADDITION, only asserted
    // when its own precision guard holds (nearest boundary ≥1.96 standard errors away
    // — 95% confidence, tightened from a bare 1 se after the quant found its original
    // se(HK/CN) figure was actually the US/HK row's, which had let the verdict flip
    // on basis choice for this exact pair). Computed on the reporting-currency
    // ("base") basis per §4.3, even though the DISPLAYED matrix above stays local-
    // currency pending the CP1 basis migration — the two bases are close enough on
    // this dataset (max diff 0.0088) that this never changes which pair is named,
    // only whether a band label may additionally be asserted (at 1.96 se, HK/CN no
    // longer clears on either basis — only US/HK does).
    if (hkCnBandInfo && hkCnBandInfo.assertable) {
      if (lang === "zh") {
        text += "按报告货币基础计算,该配对的相关性归类为" + hkCnBandInfo.bandZh +
          "(ρ=" + hkCnBandInfo.rhoBase.toFixed(2) + "),超出最近的分类边界1.96个标准误(95%置信水平)以上——详见 methodology.correlation。";
      } else {
        text += " On the reporting-currency basis this pair is classified as " + hkCnBandInfo.band +
          " (ρ=" + hkCnBandInfo.rhoBase.toFixed(2) + "), clearing the nearest classification boundary by more than 1.96 standard errors (95% confidence) — see methodology.correlation.";
      }
    }
    return text;
  }
  var CORR_CONCLUSION = correlationConclusion(CORR_LABELS, CORR_MATRIX, CORR_HK_CN_BAND_INFO);
  var CORR_CONCLUSION_ZH = correlationConclusion(CORR_LABELS, CORR_MATRIX, CORR_HK_CN_BAND_INFO, "zh");
  var CORR_HK_CN = CORR_MATRIX[CORR_LABELS.indexOf("HK Equity Sleeve")][CORR_LABELS.indexOf("CN Equity Sleeve")];

  // =======================================================================
  // HG1 Round 5, Phase 2 (S5 / PD-0016 Part 1 §1.3 — "Analogy simplifies the
  // interpretation; it never replaces the literal financial definition").
  // `claim.analogyQuick` is a NEW, deterministic field, derived here from the
  // same computed value the claim already carries — never a second, hand-typed
  // number — and js/shell.js renders it BESIDE renderMetricValue's own output
  // (the literal figure, glyph, and mandatory state chips), never instead of
  // it. Every branch below is a magnitude/order-of-magnitude comparison only —
  // no personalized constraint (P7), no forecast (P6), no softened caveat (P3).
  //
  // The owner's own counter-example — beta must not become "7% less risk" — is
  // the load-bearing test this function's beta case is written against: it
  // states ONLY a co-movement comparison ("tracked roughly in step with... /
  // moved less than..."), then explicitly disclaims that co-movement is not a
  // complete measure of risk, so it cannot be mistaken for the owner's
  // forbidden rewrite.
  // =======================================================================
  function returnAnalogyQuick(value, lang) {
    var pct = value * 100;
    var bucket;
    if (lang === "zh") {
      if (pct >= 15) bucket = "大致相当于全球股票组合表现强劲的一年";
      else if (pct >= 5) bucket = "大致相当于全球股票组合表现平稳的一年";
      else if (pct >= -5) bucket = "大致相当于基本持平、接近打平的一年";
      else bucket = "大致相当于全球股票组合表现疲软的一年";
      return "作为量级参照:" + bucket + "——这只是数量级上的类比,并非预测(P6),具体数字以上方为准。";
    }
    if (pct >= 15) bucket = "roughly the size of a strong year for a globally diversified stock portfolio";
    else if (pct >= 5) bucket = "roughly the size of an average year for a globally diversified stock portfolio";
    else if (pct >= -5) bucket = "roughly the size of a flat, close-to-breakeven year";
    else bucket = "roughly the size of a weak year for a globally diversified stock portfolio";
    return "For scale: " + bucket + " — a magnitude comparison only, not a forecast (P6); the number above is the actual figure.";
  }
  function betaAnalogyQuick(beta, withinBand, lang) {
    if (lang === "zh") {
      if (withinBand) {
        return "作为量级参照:在本样本下,其历史波动幅度与市场大体同步——这只是共同变动幅度的类比,并非「风险更低」的说法;风险还包含共同变动幅度之外的其他因素(P3)。";
      }
      return "作为量级参照:" + (beta < 1 ? "其历史波动幅度小于市场" : "其历史波动幅度大于市场") +
        "——这只是共同变动幅度的类比,并非「风险更低/更高」的完整说法;风险还包含共同变动幅度之外的其他因素(P3)。";
    }
    if (withinBand) {
      return "For scale: at this sample size, it has historically tracked roughly in step with the market — a co-movement comparison only, not a claim of \"less risk\"; risk includes more than co-movement with the market (P3).";
    }
    return "For scale: it has historically " + (beta < 1 ? "moved less than" : "moved more than") +
      " the market — a co-movement comparison only, not a complete \"more/less risk\" statement; risk includes more than co-movement with the market (P3).";
  }

  // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, methodology/
  // HG1_ROUND5_CAVEAT_AND_SML_DOMAIN_RULING.md, Part A.4's `metric.benchmarkRelative`
  // exception). Computed unconditionally (not only when the claim happens to be
  // LIMITED today) so the string is always ready and always derived from the SAME
  // CN_SESSIONS_ELAPSED variable the freshness axis and the comparability note read —
  // B1's "read from the same evidence object," applied here even though this specific
  // claim's qualifierShort is latent under today's fixture (CN_SESSIONS_ELAPSED = 1,
  // which is the AVAILABLE+STALE_DATA band, not the LIMITED one — see
  // sseSufficiencyForSessions). Session count is interpolated, never hardcoded, so a
  // future fixture change that pushes this claim into the LIMITED band (2-4 sessions)
  // is disclosed correctly with no further edit here.
  function benchmarkRelativeQualifierShort(sessionsElapsed, lang) {
    if (lang === "zh") return "有限 · A股端已滞后" + sessionsElapsed + "个交易日";
    return "limited · A-share leg " + sessionsElapsed + " sessions stale";
  }

  var METRICS = {
    "metric.return.1y": claim({
      id: "metric.return.1y", label: "Portfolio Return (1Y)", value: PERIOD_RETURN, unit: "percent",
      directional: true, // HG1 Condition 2: a genuine historical gain/loss sign (P6: describes what happened, not a forecast)
      conclusionQuick: PERIOD_RETURN >= 0 ? "Your portfolio gained value over the trailing year." : "Your portfolio lost value over the trailing year.",
      // HG1 Round 5, Phase 2 (S5 / PD-0016 Part 1) — the deterministic analogy field for
      // Overview's Quick-mode hero claim; derived from PERIOD_RETURN, never hand-typed.
      analogyQuick: returnAnalogyQuick(PERIOD_RETURN),
      explanationSimple: "This is the total change in your portfolio's reporting-currency value over the trailing 12 months, including price moves and FX effects, before any tax adjustment.",
      investorDetail: "Reporting currency USD, trailing 1 year (" + WINDOW_OBS_COUNT + " observations, " + WINDOW_START_DATE + " to " + WINDOW_END_DATE + "), vs. MSCI ACWI benchmark.",
      professionalDetail: "Time-weighted return, daily valuation, USD reporting currency (FX applied per sleeve, HG1 round 4), no tax adjustment (§15.3 out of scope).",
      referencePoint: "MSCI ACWI benchmark, same trailing 1Y window",
      methodologyId: "methodology.portfolioReturn",
      i18n: { zh: {
        label: "投资组合收益率(1年)",
        conclusionQuick: PERIOD_RETURN >= 0 ? "过去一年您的投资组合价值上涨。" : "过去一年您的投资组合价值下跌。",
        analogyQuick: returnAnalogyQuick(PERIOD_RETURN, "zh"),
        explanationSimple: "这是您投资组合在过去12个月内以报告货币计价的总价值变化,包含价格波动和汇率影响,尚未扣除任何税项调整。",
        investorDetail: "报告货币为美元(USD),过去一年(" + WINDOW_OBS_COUNT + " 个观测值," + WINDOW_START_DATE + " 至 " + WINDOW_END_DATE + "),对比基准 MSCI ACWI。",
        professionalDetail: "时间加权收益率,按日估值,以美元(USD)为报告货币(汇率已按各板块计入,HG1 第四轮修正),不含税项调整(§15.3 不在本版本范围内)。",
        referencePoint: "基准 MSCI ACWI,同一过去一年区间"
      } }
    }),
    "metric.totalPortfolioValue": claim({
      id: "metric.totalPortfolioValue", label: "Total Portfolio Value", value: TOTAL_PORTFOLIO_VALUE, unit: "currency",
      conclusionQuick: "This is your total portfolio value across all accounts, in reporting currency.",
      explanationSimple: "The sum of every holding's market value plus every cash balance, each converted to USD at this dataset's snapshot FX rates.",
      investorDetail: "Aggregates " + ACCOUNTS.length + " account containers across US, Hong Kong, and Mainland China holdings and cash.",
      referencePoint: "Snapshot as of " + END_DATE.toISOString().slice(0, 10) + ", reporting currency USD",
      methodologyId: "methodology.totalPortfolioValue",
      i18n: { zh: {
        label: "投资组合总价值",
        conclusionQuick: "这是您所有账户的投资组合总价值,以报告货币计价。",
        explanationSimple: "所有持仓的市值加上所有现金余额之和,均按本数据集的快照汇率换算为美元(USD)。",
        investorDetail: "汇总了 " + ACCOUNTS.length + " 个账户容器,涵盖美国、香港和中国内地的持仓与现金。",
        referencePoint: "截至 " + END_DATE.toISOString().slice(0, 10) + " 的快照,报告货币为美元(USD)"
      } }
    }),
    "metric.pl.absolute": claim({
      // HG1 round 4 (quant_analyst verification §7.2) — renamed. A caveat cannot rescue
      // a label that misdescribes the number: this window contains roughly
      // TRAILING_YEAR_CONTRIBUTIONS_USD of external deposits (a CNY 800,000 deposit plus
      // two smaller USD deposits), so a figure computed by applying the time-weighted
      // return to today's total value is NOT a realized dollar gain or loss — it implies
      // a starting value the ledger never actually had. The number itself is unchanged
      // (still TWR-implied, still not money-weighted); only the label and prose now say
      // what it actually is, per the quant's ruling ("rename... or suppress"; renamed).
      id: "metric.pl.absolute", label: "Value Change Implied by 1Y Time-Weighted Return (USD)", value: TOTAL_PORTFOLIO_VALUE * PERIOD_RETURN / (1 + PERIOD_RETURN), unit: "currency",
      directional: true, // HG1 Condition 2 — currency-unit + directional gets a leading "+" for a gain (see shell.js formatCurrency's opts.signed)
      conclusionQuick: "What the 1-year time-weighted return implies about your total value's change — not a realized dollar gain or loss net of this period's contributions and withdrawals.",
      explanationSimple: "Computed by applying the trailing-year time-weighted return to the current total portfolio value. This period's contributions and withdrawals (see Transactions) are NOT removed, so this figure should not be read as money you gained or lost.",
      referencePoint: "Trailing 1 year, reporting currency USD",
      caveat: "Not a money-weighted gain/loss: this window includes roughly $" + Math.round(TRAILING_YEAR_CONTRIBUTIONS_USD).toLocaleString("en-US") + " of external contributions (deposits — see Transactions), which are not netted out here. A true dollar gain/loss requires V_end − V_start − contributions + withdrawals, computed from the ledger; that engine does not exist in this prototype (see methodology.portfolioGainLoss).",
      methodologyId: "methodology.portfolioGainLoss",
      i18n: { zh: {
        label: "1年期时间加权收益率隐含的价值变化(美元)",
        conclusionQuick: "这是过去一年的时间加权收益率对您总价值变化的推算——并非扣除本期存取款后的实际盈亏。",
        explanationSimple: "计算方式为将过去一年的时间加权收益率应用于当前投资组合总价值。本期的存入与取出款项(见交易记录)并未从中剔除,因此本数字不应被解读为您实际盈亏的金额。",
        caveat: "并非资金加权的盈亏:本期包含约 $" + Math.round(TRAILING_YEAR_CONTRIBUTIONS_USD).toLocaleString("en-US") + " 的外部存入款项(见交易记录),这些款项并未在此扣除。真实的金额盈亏需要按 期末价值−期初价值−存入+取出 从账本计算得出;本原型尚未实现该引擎(见 methodology.portfolioGainLoss)。",
        referencePoint: "过去一年,报告货币为美元(USD)"
      } }
    }),
    "metric.pl.percent": claim({
      id: "metric.pl.percent", label: "Gain / Loss %", value: PERIOD_RETURN, unit: "percent",
      directional: true,
      conclusionQuick: "Same period gain/loss, expressed as a percentage of starting value.",
      explanationSimple: "Percentage form of the absolute gain/loss above.",
      referencePoint: "Trailing 1 year", methodologyId: "methodology.portfolioGainLoss",
      i18n: { zh: {
        label: "盈亏百分比",
        conclusionQuick: "同期盈亏,以起始价值的百分比表示。",
        explanationSimple: "即上方绝对盈亏金额的百分比形式。",
        referencePoint: "过去一年"
      } }
    }),
    "metric.benchmarkRelative": claim({
      id: "metric.benchmarkRelative", label: "vs. Benchmark", value: PERIOD_RETURN - BENCHMARK_PERIOD_RETURN, unit: "percent",
      // HG1 Condition 2 — this is the single SCALAR "did I beat my benchmark" figure,
      // not the two-line chart. The owner's teal-vs-gray instruction governs the hero
      // chart's two SERIES (Condition 2's own example); it does not forbid coloring a
      // genuinely directional outperformance/underperformance number by its own sign.
      // The chart lines themselves (chart-line-portfolio/chart-line-benchmark, in
      // app.css) stay teal/gray regardless of this claim's color.
      directional: true,
      // HG1 round 4 CORRECTION (owner's calendar correction; see FRESHNESS_AXES's own
      // comment for the full record) — the CN axis is genuinely STALE by
      // CN_SESSIONS_ELAPSED completed session(s), not "session-current" as an earlier
      // pass concluded from a false holiday assumption. sufficiency/reasonCode are
      // DERIVED from CN_FRESHNESS_SUFFICIENCY (itself derived from the explicit
      // SSE session calendar), not hardcoded either way — this is deliberately NOT a
      // reversion to "how it used to read" but a re-derivation that happens to land
      // on the same reason code PD-0006/PD-0007 always permitted for exactly this
      // case (STALE_DATA pairing with AVAILABLE is the "routine, expected staleness"
      // combination those decisions established; at 1 session elapsed that is
      // precisely where this claim sits — see sseSufficiencyForSessions). The
      // temporal-COMPARABILITY concern below is a SEPARATE, additional dimension
      // (PD-0014 Part 1) — present regardless of staleness, disclosed via caveat +
      // freshness.comparability, not via this reasonCode.
      sufficiency: CN_FRESHNESS_SUFFICIENCY.sufficiency,
      reasonCode: CN_FRESHNESS_SUFFICIENCY.reasonCode,
      freshness: {
        axis: CN_FRESHNESS_AXIS.axis, label: CN_FRESHNESS_AXIS.label, state: CN_FRESHNESS_AXIS.state, asOf: CN_FRESHNESS_AXIS.asOf,
        // HG1 round 4 (PD-0014 Part 1 §1.2 point 2) — comparability is a disclosure
        // DIMENSION alongside freshness, not a new sufficiency state or reason code.
        // NOTE for whoever next touches js/shell.js: renderMetricValue currently has no
        // rendering branch that surfaces this field in the compact metric-strip view
        // (it only attaches a pill when reasonCode === "STALE_DATA"); today this
        // disclosure reaches the user only via claim.caveat below, which renderClaim's
        // ladder always renders regardless of depth. Flagged in this designer's handoff.
        comparability: { limited: true, note: BENCHMARK_RELATIVE_COMPARABILITY_NOTE }
      },
      // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.4's "genuine exception").
      // Latent under today's fixture (CN_SESSIONS_ELAPSED=1 sits in the AVAILABLE+
      // STALE_DATA band, not the LIMITED one — `sufficiency` above is derived, not
      // hardcoded, so this field simply has no visible effect until a future session
      // count pushes this claim LIMITED). BINDING per the ruling: this claim's
      // comparability note may only be demoted out of the always-visible unit once it
      // has a non-tooltip, one-click rendering — see js/shell.js's
      // renderComparabilityFlagEl, now a real button opening this claim's own Evidence
      // record (F5) — never only a hover title.
      qualifierShort: benchmarkRelativeQualifierShort(CN_SESSIONS_ELAPSED),
      conclusionQuick: (PERIOD_RETURN - BENCHMARK_PERIOD_RETURN) >= 0 ? "Your portfolio outperformed its benchmark over this period." : "Your portfolio underperformed its benchmark over this period.",
      explanationSimple: "The difference between your portfolio's return and the benchmark's return over the same window, historically — not a forecast of future relative performance.",
      referencePoint: "MSCI ACWI, trailing 1Y",
      caveat: BENCHMARK_RELATIVE_COMPARABILITY_NOTE,
      methodologyId: "methodology.benchmarkRelative",
      i18n: { zh: {
        label: "相对基准",
        qualifierShort: benchmarkRelativeQualifierShort(CN_SESSIONS_ELAPSED, "zh"),
        conclusionQuick: (PERIOD_RETURN - BENCHMARK_PERIOD_RETURN) >= 0 ? "本期您的投资组合跑赢了基准。" : "本期您的投资组合跑输了基准。",
        explanationSimple: "您投资组合的收益率与基准在同一区间内的收益率之差,描述的是历史情况——并非对未来相对表现的预测。",
        referencePoint: "基准 MSCI ACWI,过去一年",
        caveat: BENCHMARK_RELATIVE_COMPARABILITY_NOTE_ZH
      } }
    }),
    "metric.fxAttribution": claim({
      id: "metric.fxAttribution", label: "FX Attribution (1Y)", value: FX_ATTRIBUTION_PCT, unit: "percent",
      directional: true,
      conclusionQuick: FX_ATTRIBUTION_PCT < 0 ? "Currency moves reduced your reporting-currency return this period." : "Currency moves added to your reporting-currency return this period.",
      explanationSimple: "How much of your total return came from the security's local-currency price move vs. the exchange rate between that currency and USD.",
      referencePoint: "HKD and CNY sleeves vs. USD reporting currency, trailing 1Y",
      // HG1 round 4 (methodology findings §4.5, §4.3) — corrected formula direction
      // (the prior text was the NEGATIVE of what the code computed) and the exact
      // exact identity now actually implemented, plus explicit scope exclusions.
      professionalDetail: "Portfolio-level FX effect = R_base,P − R_local,P (compounded), where R_local,P holds FX at the period-start (beginning-of-period) rate and R_base,P revalues at each date's own FX rate — exact by construction, no residual. Sleeve weights are beginning-of-period, reporting-currency weights. Per-sleeve local/FX/compounding-interaction/base breakdown is available via APP.data.getFxAttributionDetail().",
      caveat: "Decomposes local-market price return and currency return only; income (dividends), fees, and taxes are not attributed in V1 (this ledger records seven dividend transactions not reflected in this split). No single FX fixing time is modeled per market in this prototype — an open product decision (see methodology.fxAttribution known limitations).",
      methodologyId: "methodology.fxAttribution",
      i18n: { zh: {
        label: "汇率归因(1年)",
        conclusionQuick: FX_ATTRIBUTION_PCT < 0 ? "汇率变动降低了本期您以报告货币计的收益率。" : "汇率变动提高了本期您以报告货币计的收益率。",
        explanationSimple: "您的总收益中,有多少来自证券本币计价的价格变动,又有多少来自该货币与美元(USD)之间汇率的变动。",
        referencePoint: "港元(HKD)与人民币(CNY)板块相对于美元(USD)报告货币,过去一年",
        professionalDetail: "组合层面的汇率效应 = R_base,P − R_local,P(复利计算),其中 R_local,P 按期初汇率折算,R_base,P 按每日实际汇率重新折算——依构造精确成立,无残差。各板块权重为期初、报告货币权重。各板块的本币/汇率/复利交互/合计明细可通过 APP.data.getFxAttributionDetail() 获取。",
        caveat: "仅分解本币价格收益与汇率收益;股息、费用和税项未纳入本版本归因(本账本记录了七笔未反映在此拆分中的股息交易)。本原型未对各市场设定统一的汇率定盘时点——这是一项尚待产品决策的开放问题(见 methodology.fxAttribution 的已知限制)。"
      } }
    }),
    "metric.performanceAttribution": claim({
      id: "metric.performanceAttribution", label: "Performance Attribution", value: null, unit: "number",
      sufficiency: "AVAILABLE",
      formatted: "Local " + APP_fmtPct(PERIOD_RETURN_LOCAL) + " / FX " + APP_fmtPct(FX_ATTRIBUTION_PCT),
      conclusionQuick: "Your return decomposes into a local-market component and a currency component.",
      explanationSimple: "Local-market performance is how the securities themselves moved in their own currency (FX held at the start-of-period rate); the currency component is the separate, exact effect of exchange-rate movement, including its compounding interaction with the local move.",
      referencePoint: "Trailing 1Y, USD reporting currency",
      caveat: "Excludes income (dividends), fees, and taxes (see methodology.fxAttribution). The two legs shown sum exactly to Portfolio Return (1Y) by construction — no residual.",
      methodologyId: "methodology.fxAttribution",
      i18n: { zh: {
        label: "业绩归因",
        formatted: "本币 " + APP_fmtPct(PERIOD_RETURN_LOCAL) + " / 汇率 " + APP_fmtPct(FX_ATTRIBUTION_PCT),
        conclusionQuick: "您的收益可分解为本币市场部分与汇率部分。",
        explanationSimple: "本币市场表现指证券以其自身货币计算的价格变动(汇率固定在期初水平);汇率部分则是汇率变动本身带来的独立、精确的影响,包含其与本币变动之间的复利交互效应。",
        referencePoint: "过去一年,报告货币为美元(USD)",
        caveat: "不含股息、费用和税项(见 methodology.fxAttribution)。所示两部分之和依构造精确等于投资组合过去一年收益率——无残差。"
      } }
    }),
    "metric.beta": claim({
      id: "metric.beta", label: "Beta (vs. Benchmark)", value: BETA, unit: "ratio",
      sufficiency: "LIMITED",
      // HG1 round 4 (methodology findings §1.2/§1.3/§1.4, D1.1/D1.4) — replaces the
      // false "24 monthly-equivalent observations (36 preferred)" caveat, which
      // contradicted the Proof Packet's own `observations: 252` on the same screen
      // (D1.1), and which declared an unmeetable threshold under its own stated window
      // (D1.4). WINDOW_OBS_COUNT is the SAME variable (pr1y.length) the Evidence
      // packet's `observations` field reads (see registerEvidenceFor below) — the same
      // evidence object, not independently hardcoded, per PD-0014 §2.3 binding example 4.
      caveat: WINDOW_OBS_COUNT + " daily observations (" + WINDOW_START_DATE + " to " + WINDOW_END_DATE + "). " +
        "Cross-market default per PRD §14 is weekly (≥156 weekly [3Y] for AVAILABLE, 52–155 for LIMITED); " +
        "this implementation uses daily instead and records that deviation here rather than silently: " +
        "≥750 daily [3Y] for AVAILABLE, 250–749 for LIMITED, <250 for INSUFFICIENT_DATA. At " + WINDOW_OBS_COUNT +
        " daily observations this metric is LIMITED under its own, meetable, daily threshold.",
      // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.1-A.3). BINDING per the
      // ruling: caveat above is retained UNCHANGED (F4 — never rename/shorten in place;
      // the Proof Packet's thresholds_limits_if_used/limitations read it verbatim).
      // qualifierShort is an ADDED field, rendered in `.metric-qualifier` at every depth
      // instead of the ~430-char caveat. This is the ruling's INTERIM string (Ruling
      // 1(c), Part 3) — NOT the primary "252 daily obs · 3Y standard not met" form —
      // because the frequency-invariance condition the primary form depends on
      // currently FAILS on this fixture (F1: daily 252 obs -> LIMITED, but the
      // weekly-equivalent 49-50 obs -> INSUFFICIENT_DATA on the same window; the two
      // conventions disagree on which side of the sufficiency line this sits). The
      // interim string instead discloses THAT disagreement rather than a count the
      // weekly convention would not support. The calendar fix that would let the
      // primary form ship (adding market holidays so 252 trading days span ~365
      // calendar days) is F1/F3's fixture remedy, routed to methodology/engineering —
      // explicitly NOT this round's scope, per the ruling's own Part 4 and this
      // designer's instructions. DATES/every return series is UNCHANGED by this edit.
      qualifierShort: "limited (daily) · weekly default withholds",
      // HG1 Round 5, Phase 2 (PD-0012 §2 / S5) — a deterministic, magnitude-only
      // analogy, derived from the SAME BETA/BETA_WITHIN_TOLERANCE_BAND values
      // conclusionQuick/explanationSimple already use. This is the owner's own
      // counter-example, answered directly: beta is NOT restated as "N% less risk."
      analogyQuick: betaAnalogyQuick(BETA, BETA_WITHIN_TOLERANCE_BAND),
      conclusionQuick: betaDirectionConclusion(BETA, BETA_SE, WINDOW_OBS_COUNT, BETA_CI95),
      // HG1 round 4 (quant_analyst verification §6, threshold harmonized to 1.96 se) —
      // mirrors conclusionQuick's own tolerance-band decision rather than an
      // independent sign check, so the two fields can never disagree with each other
      // about whether beta is distinguishable from 1 (see js/selfcheck.js's binding1,
      // which checks both fields independently).
      explanationSimple: BETA_WITHIN_TOLERANCE_BAND
        ? "Moves in roughly the same direction and magnitude as the benchmark; at this sample size the estimate cannot be statistically distinguished from a beta of exactly 1 (moving one-for-one with the market)."
        : "Moves in the same direction as the benchmark, and historically " + (BETA < 1 ? "dampens" : "amplifies") +
          " benchmark moves by the beta factor, observed over this sample period — a difference from 1.0 larger than 1.96 standard errors of the estimate (95% confidence).",
      investorDetail: "Benchmark: MSCI ACWI. Window: trailing 1Y daily (" + WINDOW_OBS_COUNT + " observations, " + WINDOW_START_DATE + " to " + WINDOW_END_DATE + "). Standard error of the estimate: ±" + BETA_SE.toFixed(3) + " (95% CI [" + BETA_CI95[0].toFixed(4) + ", " + BETA_CI95[1].toFixed(4) + "]).",
      // HG1 ux_planning revision (review-07, P0 item 4) — this sentence previously
      // printed the internal constant NAME (`DIRECTIONAL_CLAIM_SE_MULTIPLIER`) verbatim
      // to the user, alongside a second, independently-hardcoded "1.96" literal that
      // could have silently drifted from the real constant. Mirrors the zh counterpart
      // below (which already states the threshold's VALUE and meaning without ever
      // naming the constant): the multiplier is interpolated from the SAME
      // DIRECTIONAL_CLAIM_SE_MULTIPLIER used above, never a second hardcoded number, and
      // the substantive disclosure (1.96 standard errors / 95% confidence) is kept in
      // full — only the internal identifier is removed. js/selfcheck.js's
      // beta.professionalDetailDirectionalThresholdParity assertion already checks this
      // sentence states the threshold multiplier (read from the same source value) and
      // the 95% confidence level in both locales; unchanged by this edit.
      professionalDetail: "OLS regression, daily returns, reporting-currency (FX-inclusive, HG1 round 4). se(β̂) = " + BETA_SE.toFixed(4) + "; |β̂−1| = " + BETA_SIGMAS_FROM_ONE.toFixed(3) + " standard errors. Directional-claim threshold: " + DIRECTIONAL_CLAIM_SE_MULTIPLIER.toFixed(2) + " standard errors (95% confidence), the same threshold used by the correlation classification-band guard. Full disclosure set in Methodology.",
      referencePoint: "MSCI ACWI, trailing 1Y daily",
      methodologyId: "methodology.beta",
      // HG1 round 4 (bilingual gap) — conclusionQuick/explanationSimple are DERIVED
      // (betaDirectionConclusion / the same BETA_WITHIN_TOLERANCE_BAND condition, lang
      // switched to "zh"), never a hand-translated snapshot of the English string.
      i18n: { zh: {
        label: "贝塔系数(相对基准)",
        caveat: WINDOW_OBS_COUNT + " 个交易日观测值(" + WINDOW_START_DATE + " 至 " + WINDOW_END_DATE + ")。" +
          "跨市场贝塔的默认频率为周频(PRD §14):周频≥156个观测值(3年)达到「可用」,52–155为「有限」;" +
          "本实现改用日频,并在此明确记录该偏离,而非默认沿用:日频≥750个观测值(3年)达到「可用」,250–749为「有限」,<250为「数据不足」。" +
          "本样本共 " + WINDOW_OBS_COUNT + " 个日频观测值,依其自身、可达成的日频阈值判定为「有限」。",
        qualifierShort: "有限(日频) · 周频默认将不予显示",
        analogyQuick: betaAnalogyQuick(BETA, BETA_WITHIN_TOLERANCE_BAND, "zh"),
        conclusionQuick: betaDirectionConclusion(BETA, BETA_SE, WINDOW_OBS_COUNT, BETA_CI95, "zh"),
        explanationSimple: BETA_WITHIN_TOLERANCE_BAND
          ? "与基准的方向和幅度大致相同;在本样本量下,该估计值无法与「贝塔恰好为1(与市场同步波动)」在统计上区分开。"
          : "与基准同向变动,且历史上" + (BETA < 1 ? "弱化" : "放大") + "了基准的波动幅度(按贝塔系数),该差异大于估计值自身的1.96个标准误(95%置信水平)。",
        investorDetail: "基准:MSCI ACWI。区间:过去一年,日频(" + WINDOW_OBS_COUNT + " 个观测值," + WINDOW_START_DATE + " 至 " + WINDOW_END_DATE + ")。估计值的标准误:±" + BETA_SE.toFixed(3) + "(95% 置信区间 [" + BETA_CI95[0].toFixed(4) + ", " + BETA_CI95[1].toFixed(4) + "])。",
        // HG1 ux_planning revision (review-06, B3) — restores the sentence the English
        // professionalDetail (above) carries and this zh counterpart previously dropped
        // in full: the directional-claim threshold itself (1.96 se / 95% confidence),
        // the SAME condition BETA_WITHIN_TOLERANCE_BAND (module scope, above) and every
        // other beta-direction string on this claim already gate on. Dropping this
        // sentence is a P3 violation (plainer wording may drop precision, never a
        // caveat that changes the conclusion) and a P9 violation (this claim's
        // Professional depth is the one place the threshold itself, not just its
        // consequence, is disclosed) — the reader of the zh Professional depth
        // previously had no way to learn WHY the direction claim above resolved the way
        // it did. `DIRECTIONAL_CLAIM_SE_MULTIPLIER` (the internal constant name) is
        // never exposed in either language's prose — both strings state its VALUE
        // (interpolated here, not a second hardcoded "1.96" literal) and its plain-
        // language meaning instead. js/selfcheck.js's
        // beta.professionalDetailDirectionalThresholdParity assertion checks this
        // sentence's semantic content (multiplier + confidence level) is present in
        // BOTH locales, not just that some string exists.
        professionalDetail: "OLS 回归,日频收益率,报告货币计价(含汇率影响,HG1 第四轮修正)。se(β̂) = " + BETA_SE.toFixed(4) + ";|β̂−1| = " + BETA_SIGMAS_FROM_ONE.toFixed(3) + " 个标准误。方向性结论判定阈值为" + DIRECTIONAL_CLAIM_SE_MULTIPLIER.toFixed(2) + "个标准误(95%置信水平),与相关性分类区间判定所使用的阈值相同。完整披露信息见方法论。",
        referencePoint: "基准 MSCI ACWI,过去一年,日频"
      } }
    }),
    "metric.alpha": claim({
      id: "metric.alpha", label: "Jensen's Alpha (annualized)", value: ALPHA_ANNUAL, unit: "percent",
      directional: true, // above/below the beta-implied return is a genuine directional result, unlike beta itself
      // HG1 round 4 (methodology findings §2.3) — "predict" is forecasting language for
      // a quantity that describes a closed historical window (P6); replaced verbatim
      // per the quant specification, mirrored symmetrically for the negative case.
      conclusionQuick: ALPHA_ANNUAL < 0
        ? "Over this window, the portfolio returned less than the benchmark relationship at this beta accounts for."
        : "Over this window, the portfolio returned more than the benchmark relationship at this beta accounts for.",
      explanationSimple: "After adjusting for how much market risk was taken (beta), the actual return fell short of (or exceeded) the model-implied return, in this specific historical window. This is a regression-based (arithmetic-mean, annualized) estimate — see metric.sml for how it compares to the ex-post market line's own vertical distance, a related but different quantity.",
      investorDetail: "Beta " + BETA.toFixed(2) + ", benchmark MSCI ACWI, risk-free rate " + (RF_ANNUAL * 100).toFixed(1) + "%.",
      professionalDetail: "Risk-free rate assumption 4.5% annualized; historical/model-based, not a universal measure of skill. OLS regression on arithmetic daily excess returns, annualized ×252 — not the same basis as a geometric-return difference (see metric.sml).",
      referencePoint: "MSCI ACWI, trailing 1Y, beta-adjusted",
      methodologyId: "methodology.alpha",
      i18n: { zh: {
        label: "詹森阿尔法(年化)",
        conclusionQuick: ALPHA_ANNUAL < 0
          ? "本区间内,投资组合的实际收益低于该贝塔水平下基准关系所能解释的部分。"
          : "本区间内,投资组合的实际收益高于该贝塔水平下基准关系所能解释的部分。",
        explanationSimple: "在调整了所承担的市场风险(贝塔)之后,本历史区间内实际收益低于(或高于)模型所隐含的收益。这是一个基于回归(算术平均、年化)的估计值——参见 metric.sml,了解它与事后证券市场线自身垂直距离(一个相关但不同的量)之间的关系。",
        investorDetail: "贝塔 " + BETA.toFixed(2) + ",基准 MSCI ACWI,无风险利率 " + (RF_ANNUAL * 100).toFixed(1) + "%。",
        professionalDetail: "无风险利率假设为年化4.5%;基于历史/模型估算,并非普遍适用的能力衡量指标。基于算术日超额收益的 OLS 回归,年化(×252)——与几何收益差异的计算基础不同(见 metric.sml)。",
        referencePoint: "基准 MSCI ACWI,过去一年,经贝塔调整"
      } }
    }),
    "metric.volatility": claim({
      id: "metric.volatility", label: "Annualized Volatility", value: ANNUAL_VOL, unit: "percent",
      conclusionQuick: volatilityConclusion(ANNUAL_VOL, BENCHMARK_ANNUAL_VOL),
      explanationSimple: "A measure of how much your portfolio's returns have swung around their average, annualized, over this period.",
      referencePoint: "MSCI ACWI annualized volatility: " + APP_fmtLevelPct(BENCHMARK_ANNUAL_VOL),
      methodologyId: "methodology.volatility",
      i18n: { zh: {
        label: "年化波动率",
        conclusionQuick: volatilityConclusion(ANNUAL_VOL, BENCHMARK_ANNUAL_VOL, "zh"),
        explanationSimple: "衡量您投资组合收益率在本期围绕其均值波动幅度的指标,已年化。",
        referencePoint: "基准 MSCI ACWI 年化波动率:" + APP_fmtLevelPct(BENCHMARK_ANNUAL_VOL)
      } }
    }),
    "metric.sharpe": claim({
      id: "metric.sharpe", label: "Sharpe Ratio", value: SHARPE, unit: "ratio",
      conclusionQuick: "Return earned per unit of total risk taken, historically.",
      explanationSimple: "Excess return over the risk-free rate, divided by volatility, over this period.",
      referencePoint: "Risk-free rate 4.5% annualized",
      methodologyId: "methodology.sharpe",
      i18n: { zh: {
        label: "夏普比率",
        conclusionQuick: "历史上,每承担一单位总风险所获得的收益。",
        explanationSimple: "本期超过无风险利率的超额收益,除以波动率。",
        referencePoint: "无风险利率年化4.5%"
      } }
    }),
    "metric.sortino": claim({
      id: "metric.sortino", label: "Sortino Ratio", value: null, unit: "ratio",
      sufficiency: "INSUFFICIENT_DATA",
      // HG1 round 4 (methodology findings §7.5) — the prior caveat asserted "fewer than
      // the minimum required downside-return observations," which was FALSE against
      // this file's own data (there are DOWNSIDE_DAY_COUNT downside days in the
      // window). The methodology findings are explicit that withholding this metric is
      // "a legitimate demonstration" of the INSUFFICIENT_DATA render path, but the
      // STATED REASON must not be a fabricated shortfall. No minimum-downside-
      // observation threshold has been set by quant_analyst yet (methodology findings
      // do not set one; only the ÷N denominator fix is specified) — not invented here.
      // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.4, finding F8): the
      // prior caveat's irreducible content was a SELF-NEGATION under T1 — most of its
      // length was spent un-saying the very insufficiency it demonstrates ("this is not
      // a claim that the current sample is actually insufficient"), which cannot simply
      // be compressed without keeping that same contradiction in a shorter form. Ruling:
      // "Delete, do not compress." Replaced with the ruling's own interim `.metric-reason`
      // string, which states the true, narrow reason (a demonstration render, no
      // threshold set yet) without asserting or denying a shortfall either way. This is
      // not a caveat-preservation exception like metric.beta's (F4) — the ruling
      // authorizes deleting this specific text, it does not forbid touching it.
      caveat: "Withheld to demo this state; no threshold set.",
      conclusionQuick: "Sortino Ratio is intentionally withheld in this prototype to demonstrate the INSUFFICIENT_DATA rendering path — see caveat.",
      referencePoint: "Risk-free rate 4.5% annualized",
      methodologyId: "methodology.sortino",
      i18n: { zh: {
        label: "索提诺比率",
        caveat: "为演示该状态而隐去;尚未设定阈值。",
        conclusionQuick: "本原型有意隐去索提诺比率(Sortino Ratio),以演示「数据不足」的渲染路径——详见说明。",
        referencePoint: "无风险利率年化4.5%"
      } }
    }),
    "metric.maxDrawdown": claim({
      id: "metric.maxDrawdown", label: "Max Drawdown (1Y)", value: MAX_DRAWDOWN, unit: "percent",
      conclusionQuick: "The largest peak-to-trough decline your portfolio experienced this period.",
      explanationSimple: "How far the portfolio fell from its highest point before recovering, historically — not a prediction of future declines (P6).",
      referencePoint: "Benchmark max drawdown: " + APP_fmtPct(BENCHMARK_MAX_DRAWDOWN_1Y),
      methodologyId: "methodology.drawdown",
      i18n: { zh: {
        label: "最大回撤(1年)",
        conclusionQuick: "本期您投资组合经历的最大峰值到谷值跌幅。",
        explanationSimple: "投资组合从最高点回落、直至企稳回升的历史幅度——并非对未来跌幅的预测(P6)。",
        referencePoint: "基准最大回撤:" + APP_fmtPct(BENCHMARK_MAX_DRAWDOWN_1Y)
      } }
    }),
    "metric.trackingError": claim({
      id: "metric.trackingError", label: "Tracking Error", value: TRACKING_ERROR, unit: "percent",
      conclusionQuick: "How closely your portfolio's returns have tracked the benchmark, historically.",
      referencePoint: "MSCI ACWI, trailing 1Y daily",
      methodologyId: "methodology.trackingError",
      i18n: { zh: {
        label: "跟踪误差",
        conclusionQuick: "历史上,您投资组合的收益率与基准的贴合程度。",
        referencePoint: "基准 MSCI ACWI,过去一年,日频"
      } }
    }),
    "metric.var95": claim({
      id: "metric.var95", label: "1-Day 95% VaR", value: VAR_95, unit: "percent",
      // HG1 round 4 (methodology findings §3.2/§3.3) — `value` stays the SIGNED return
      // quantile (registry quantity, composable with the return series / expected
      // shortfall); `formatted` overrides display with the non-negative magnitude
      // convention (no sign character, no directional colour — directional stays
      // false, below, unchanged from before this pass).
      // HG1 Round 5 micro-pass (Item 3) — PM-cited example ("1.6% of portfolio
      // value"). `formatted` is what `renderMetricValue`'s `.metric-number`
      // span actually displays (formatClaimValue reads `formatted` first, via
      // `APP.ui.localizeClaimField`); the English suffix below had no
      // `i18n.zh.formatted` counterpart at all, so it rendered unchanged in
      // `lang=zh` even though every OTHER field on this same claim was already
      // translated. Fixed via the same field, added to the i18n.zh block below.
      formatted: VAR_HAS_LOSS_THRESHOLD ? (APP_fmtMagnitudePct(VAR_MAGNITUDE) + " of portfolio value") : null,
      conclusionQuick: VAR_HAS_LOSS_THRESHOLD
        ? "A historical estimate: on 5% of days in this sample, the one-day change was worse than a " + APP_fmtMagnitudePct(VAR_MAGNITUDE) + " loss; " + VAR_EXCEEDANCE_COUNT + " of " + WINDOW_OBS_COUNT + " days (" + APP_fmtMagnitudePct(VAR_EXCEEDANCE_COUNT / WINDOW_OBS_COUNT) + ") were at or below that level. Describes this sample only — not a limit on future loss."
        : "No one-day loss threshold at 95% confidence in this sample — the worst 5% of days in this window were not losses.",
      investorDetail: "Historical simulation, " + WINDOW_OBS_COUNT + " daily returns (" + WINDOW_START_DATE + " to " + WINDOW_END_DATE + "). Realized exceedance: " + VAR_EXCEEDANCE_COUNT + " of " + WINDOW_OBS_COUNT + " days.",
      professionalDetail: "Historical simulation, lower order-statistic (no interpolation): q = sorted(r)[floor(0.05×(n−1))]. VaR₉₅ = −q for q<0. Not annualized (√h scaling forbidden for non-i.i.d. cross-border returns in V1). Reporting-currency returns including FX translation (HG1 round 4 — previously excluded currency risk, methodology findings §7.11).",
      referencePoint: "Historical simulation, " + WINDOW_OBS_COUNT + " daily returns (" + WINDOW_START_DATE + " to " + WINDOW_END_DATE + ")",
      methodologyId: "methodology.var",
      i18n: { zh: {
        label: "单日95%风险价值(VaR)",
        formatted: VAR_HAS_LOSS_THRESHOLD ? (APP_fmtMagnitudePct(VAR_MAGNITUDE) + "(占投资组合价值)") : null,
        conclusionQuick: VAR_HAS_LOSS_THRESHOLD
          ? "历史估计:本样本中5%的交易日,单日跌幅超过 " + APP_fmtMagnitudePct(VAR_MAGNITUDE) + " 的损失;" + WINDOW_OBS_COUNT + " 天中有 " + VAR_EXCEEDANCE_COUNT + " 天(" + APP_fmtMagnitudePct(VAR_EXCEEDANCE_COUNT / WINDOW_OBS_COUNT) + ")达到或超过该水平。仅描述本样本情况——并非对未来损失的限定。"
          : "本样本中95%置信水平下不存在单日损失阈值——本区间内表现最差的5%交易日并非亏损。",
        investorDetail: "历史模拟法," + WINDOW_OBS_COUNT + " 个日频收益率(" + WINDOW_START_DATE + " 至 " + WINDOW_END_DATE + ")。实际超出次数:" + WINDOW_OBS_COUNT + " 天中的 " + VAR_EXCEEDANCE_COUNT + " 天。",
        professionalDetail: "历史模拟法,下侧顺序统计量(不插值):q = sorted(r)[floor(0.05×(n−1))]。当 q<0 时,VaR₉₅ = −q。不进行年化(本版本禁止对非独立同分布的跨境收益率使用 √h 缩放)。报告货币收益率,含汇率折算(HG1 第四轮修正——此前不含汇率风险,见方法论发现 §7.11)。",
        referencePoint: "历史模拟法," + WINDOW_OBS_COUNT + " 个日频收益率(" + WINDOW_START_DATE + " 至 " + WINDOW_END_DATE + ")"
      } }
    }),
    "metric.concentration": claim({
      id: "metric.concentration", label: "Concentration (Top 5)", value: TOP5_SUM / TOTAL_HOLDINGS_VALUE, unit: "percent",
      conclusionQuick: (TOP5_SUM / TOTAL_HOLDINGS_VALUE > 0.5)
        ? "Your top five holdings make up a majority of invested value."
        : "Your top five holdings make up a significant, but not majority, share of invested value.",
      explanationSimple: "Effective N (" + EFFECTIVE_N.toFixed(1) + ") estimates how many equally-sized positions your portfolio behaves like, given its actual weight distribution.",
      investorDetail: "HHI: " + HHI.toFixed(3) + ". Effective N: " + EFFECTIVE_N.toFixed(1) + ".",
      referencePoint: "General diversification reference (no personal cap on file — see Portfolio Policy)",
      methodologyId: "methodology.concentration",
      i18n: { zh: {
        label: "集中度(前五大)",
        conclusionQuick: (TOP5_SUM / TOTAL_HOLDINGS_VALUE > 0.5)
          ? "您的前五大持仓占投资价值的多数。"
          : "您的前五大持仓占投资价值相当一部分,但未达多数。",
        explanationSimple: "有效持仓数(Effective N," + EFFECTIVE_N.toFixed(1) + ")估算的是:按您实际的权重分布,您的投资组合表现得相当于多少个等权重持仓。",
        investorDetail: "赫芬达尔指数(HHI):" + HHI.toFixed(3) + "。有效持仓数:" + EFFECTIVE_N.toFixed(1) + "。",
        referencePoint: "一般分散化参考基准(未设置个人上限——见投资组合政策)"
      } }
    }),
    "metric.correlation": claim({
      id: "metric.correlation", label: "Sleeve Correlation Matrix", value: null, unit: "number",
      formatted: "See matrix",
      conclusionQuick: CORR_CONCLUSION,
      // HG1 round 4 (quant_analyst verification §4.3) — the prior wording described all
      // five rows/columns as "local-currency sleeve returns," which is false for the
      // fifth (the benchmark, a USD reporting-currency series): this matrix mixes two
      // currency bases, not one. Numerically this barely matters here (max abs
      // difference between bases across the whole matrix: 0.0088; equity-pair ranking
      // identical either way — see methodology.correlation), so the label is fixed at
      // HG1; migrating the DISPLAYED matrix to one basis stays CP1.
      referencePoint: "Trailing 1Y daily returns, 5 series: four LOCAL-CURRENCY sleeve returns (US, HK, CN, Bonds) plus the benchmark (MSCI ACWI), which is a USD reporting-currency series — see methodology.correlation for the basis note.",
      caveat: "The benchmark row/column is a USD reporting-currency series while the four sleeve rows/columns are local-currency returns — this matrix mixes two currency bases. Correlations involving the benchmark (and only those) should be read with that in mind. Moving the whole matrix to one basis is planned but not yet implemented (CP1).",
      methodologyId: "methodology.correlation",
      i18n: { zh: {
        label: "板块相关性矩阵",
        formatted: "见矩阵",
        conclusionQuick: CORR_CONCLUSION_ZH,
        referencePoint: "过去一年日频收益率,共5个序列:四个本币计价的板块收益率(美股、港股、A股、债券),加上基准(MSCI ACWI,以美元报告货币计价)——计价基础说明见 methodology.correlation。",
        caveat: "基准所在行/列以美元(USD)报告货币计价,而其余四个板块行/列均为本币收益率——本矩阵混用了两种货币计价基础。涉及基准的相关系数(仅此部分)应结合这一点解读。将整个矩阵统一到同一计价基础的工作已规划但尚未实施(CP1)。"
      } }
    }),
    "metric.contributionToRisk": claim({
      id: "metric.contributionToRisk", label: "Contribution to Risk", value: null, unit: "number",
      formatted: "See breakdown",
      conclusionQuick: contributionRiskConclusion(CONTRIBUTION_TO_RISK),
      referencePoint: "Exact Euler (marginal-contribution-to-volatility) decomposition: weight × volatility × correlation-to-portfolio",
      // HG1 round 4 (methodology findings §7.7) — corrected from "simplified illustrative
      // approximation... NOT a certified risk-decomposition engine" (which understated
      // an exact method) to an accurate description, plus the labelled-remainder
      // disclosure the withheld segment requires.
      // HG1 round 4 (quant_analyst re-verification) — the AVAILABLE-segments' share
      // total is a LEVEL (a sum of shares), not a magnitude — APP_fmtLevelPct
      // preserves its sign (see contributionRiskConclusion's own comment for why a
      // hedge's genuinely-negative MCTR must never be abs()'d away).
      caveat: "Exact Euler decomposition of portfolio return volatility — not an approximation; the segments below sum exactly to total portfolio volatility. Computed on reporting-currency (FX-inclusive) sleeve returns, so Hong Kong and Mainland China currency risk is included. Excludes cash (no return risk in this model)." +
        (CONTRIB_WITHHELD.length ? " The displayed AVAILABLE segments' shares sum to " + APP_fmtLevelPct(CONTRIB_AVAILABLE_SUM) + ", not 100% — " + CONTRIB_WITHHELD.map(function (s) { return s.label; }).join(", ") + "'s contribution is withheld above; this is a labelled remainder, not a missing segment." : ""),
      methodologyId: "methodology.contributionToRisk",
      i18n: { zh: {
        label: "风险贡献",
        formatted: "见明细",
        conclusionQuick: contributionRiskConclusion(CONTRIBUTION_TO_RISK, "zh"),
        referencePoint: "精确的欧拉(边际波动率贡献)分解:权重 × 波动率 × 与组合的相关系数",
        caveat: "投资组合收益率波动率的精确欧拉分解——并非近似值;以下各板块之和精确等于组合总波动率。基于报告货币(含汇率影响)的板块收益率计算,因此香港和中国内地板块的汇率风险已被计入。不含现金(本模型中现金无收益风险)。" +
          (CONTRIB_WITHHELD.length ? "所示「可用」板块占比之和为 " + APP_fmtLevelPct(CONTRIB_AVAILABLE_SUM) + ",并非100%——" + CONTRIB_WITHHELD.map(function (s) { return sleeveNameZh(shortSleeveName(s.label)); }).join("、") + "的贡献已在上方隐去;这是一个已标注的余量,而非缺失的板块。" : "")
      } }
    }),
    "metric.sml": claim({
      // HG1 round 4 (methodology findings §2) — the chart's vertical-distance
      // annotation and the regression Jensen's alpha are different quantities
      // (concept 4 vs. concept 3); this claim's own text no longer conflates them, and
      // `formatted` now shows both, separately labelled, rather than one annotating
      // the other.
      id: "metric.sml", label: "SML / CAPM Position", value: null, unit: "number",
      formatted: "β " + BETA.toFixed(2) + " · Return " + APP_fmtPct(PERIOD_RETURN) + " · Line distance " + APP_fmtPct(SML_VERTICAL_DISTANCE) + " · α (regression) " + APP_fmtPct(ALPHA_ANNUAL),
      conclusionQuick: "Your portfolio's realized return sits " + (SML_VERTICAL_DISTANCE >= 0 ? "above" : "below") +
        " the ex-post market line implied by its beta, by " + APP_fmtPct(SML_VERTICAL_DISTANCE) + " over this window (a geometric-return distance). " +
        "The separately reported Jensen's alpha, " + APP_fmtPct(ALPHA_ANNUAL) + ", is a related but different quantity — an arithmetic-mean " +
        "regression estimate, annualized ×252 — and is not the same number as this line-distance; see Professional detail.",
      explanationSimple: "The line shows the return a portfolio at each beta would have needed, over this window, to match what the benchmark actually delivered relative to the risk-free rate. The distance from your point to the line (shown above) and the regression-based Jensen's alpha reported alongside it are two different quantities, computed on different bases (a geometric return difference vs. an arithmetic-mean regression estimate) — they are usually close but not identical, and neither is a forecast (P6).",
      investorDetail: "Benchmark: MSCI ACWI. Window: trailing 1Y daily (" + WINDOW_OBS_COUNT + " observations, " + WINDOW_START_DATE + " to " + WINDOW_END_DATE + ").",
      professionalDetail: "Line: y(β) = Rf + β×(realized benchmark return − Rf); realized benchmark return = " + APP_fmtPct(BENCHMARK_PERIOD_RETURN) + ", Rf = " + APP_fmtLevelPct(RF_ANNUAL) + ". This window's realized market premium is negative, so the line correctly slopes downward — a faithful description of what happened (P6), not an error, and must not be “corrected” toward a conventional upward slope. Line-distance is geometric (concept 4); Jensen's alpha (metric.alpha) is OLS on arithmetic daily excess returns ×252 (concept 3).",
      referencePoint: "MSCI ACWI, risk-free rate 4.5% annualized, trailing 1Y daily",
      caveat: "Reflects trailing-window historical returns only (P6) — the line and every point on it describe what happened in this sample, not a forecast of future position.",
      methodologyId: "methodology.sml",
      i18n: { zh: {
        label: "证券市场线/CAPM 头寸(事后)",
        formatted: "β " + BETA.toFixed(2) + " · 收益率 " + APP_fmtPct(PERIOD_RETURN) + " · 直线距离 " + APP_fmtPct(SML_VERTICAL_DISTANCE) + " · α(回归)" + APP_fmtPct(ALPHA_ANNUAL),
        conclusionQuick: "本区间内,您投资组合的实际收益率位于该贝塔水平所对应的事后市场线" + (SML_VERTICAL_DISTANCE >= 0 ? "之上" : "之下") +
          ",距离为 " + APP_fmtPct(SML_VERTICAL_DISTANCE) + "(一个几何收益率距离)。" +
          "另行报告的詹森阿尔法(Jensen's Alpha)为 " + APP_fmtPct(ALPHA_ANNUAL) + ",是一个相关但不同的量——基于算术平均的回归估计值(年化)——与此直线距离并非同一数字;详见「专业」层级说明。",
        // HG1 round 4 (quant_analyst re-verification, P6) — 本应 carries counterfactual
        // obligation ("ought to have") on its own, the same modal the quant vetoed in
        // the English at §2.3 ("would have needed... to match"); the trailing
        // 才能…相匹配 clause softens but does not remove it, and P6 has no lesser-instance
        // tier. Changed to 需要取得 ("would need to obtain"), matching the English's
        // "would have needed" without the counterfactual-obligation modal.
        explanationSimple: "该直线显示的是:在本区间内,处于各贝塔水平的投资组合需要取得多少收益,才能与基准相对于无风险利率的实际表现相匹配。您的点到直线的距离(如上)与同时报告的、基于回归的詹森阿尔法是两个不同的量,计算基础不同(几何收益率之差 vs. 算术平均回归估计)——二者通常接近但并不相同,且均非预测(P6)。",
        investorDetail: "基准:MSCI ACWI。区间:过去一年,日频(" + WINDOW_OBS_COUNT + " 个观测值," + WINDOW_START_DATE + " 至 " + WINDOW_END_DATE + ")。",
        professionalDetail: "直线方程:y(β) = Rf + β×(实际基准收益率 − Rf);实际基准收益率 = " + APP_fmtPct(BENCHMARK_PERIOD_RETURN) + ",Rf = " + APP_fmtLevelPct(RF_ANNUAL) + "。本区间的实际市场风险溢价为负,因此该直线正确地向下倾斜——这是对实际情况的如实描述(P6),并非错误,不应被「修正」为常规的向上倾斜。直线距离为几何量(概念4);詹森阿尔法(metric.alpha)为算术日超额收益的 OLS 回归结果,年化×252(概念3)。",
        referencePoint: "基准 MSCI ACWI,无风险利率年化4.5%,过去一年,日频",
        caveat: "仅反映本区间内的历史收益(P6)——该直线及线上每个点描述的都是本样本中实际发生的情况,并非对未来位置的预测。"
      } }
    }),
    // Exposure claims
    "exposure.assetClass": claim({ id: "exposure.assetClass", label: "Asset Class Exposure", value: null, formatted: "See breakdown", conclusionQuick: "Predominantly equities, with a fixed-income allocation via TLT.", methodologyId: "methodology.exposure",
      i18n: { zh: { label: "资产类别敞口", formatted: "见明细", conclusionQuick: "以股票为主,并通过 TLT 配置了固定收益资产。" } } }),
    "exposure.sector": claim({ id: "exposure.sector", label: "Sector Exposure", value: null, formatted: "See breakdown", conclusionQuick: "Information Technology is your largest sector exposure.", methodologyId: "methodology.exposure",
      i18n: { zh: { label: "行业敞口", formatted: "见明细", conclusionQuick: "信息技术是您最大的行业敞口。" } } }),
    "exposure.listingMarket": claim({ id: "exposure.listingMarket", label: "Listing-Market Exposure", value: null, formatted: "See breakdown", conclusionQuick: "By where securities are listed, US and Hong Kong dominate.", methodologyId: "methodology.exposure",
      i18n: { zh: { label: "上市地敞口", formatted: "见明细", conclusionQuick: "按证券上市地划分,美股与港股占主导。" } } }),
    "exposure.economicGeography": claim({ id: "exposure.economicGeography", label: "Economic-Geography Exposure", value: null, formatted: "See breakdown", conclusionQuick: "By where the underlying business actually sits, China is larger than the listing-market view suggests — several Hong Kong-listed holdings are China-domiciled businesses.", methodologyId: "methodology.exposure",
      i18n: { zh: { label: "经济地理敞口", formatted: "见明细", conclusionQuick: "按业务实际所在地划分,中国的敞口大于仅看上市地所显示的水平——多只港股持仓的业务主体位于中国内地。" } } }),
    "exposure.currency": claim({
      id: "exposure.currency", label: "Currency Exposure", value: null, formatted: "See breakdown",
      sufficiency: "LIMITED", reasonCode: "MISSING_FX_HISTORY",
      caveat: "This breakdown applies a single fixed illustrative FX snapshot rate to every conversion below, including CNY; a dated historical FX print for the most recent CNY activity (see the Transactions ledger) is not modeled separately in this prototype, so the CNY figure should be read as directionally illustrative, not reconciled to a specific rate date.",
      // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.4). "Safe to shorten, but
      // the placement is the real requirement" — the parent claim renders "See
      // breakdown" and carries no number, while the misleading figures are the CHILD
      // (per-currency) segments; a qualifier on the parent alone does not discharge the
      // disclosure for a reader looking at the CNY bar. BINDING: this exact string must
      // additionally render at every unit that displays a CNY-converted snapshot-rate
      // amount, not only here — see js/shell.js's APP.ui.renderQualifierNote, called
      // directly beside the currency bar chart in js/surfaces/overview.js and
      // js/surfaces/analytics.js (an exception in PLACEMENT, not length).
      qualifierShort: "limited · one illustrative FX snapshot rate",
      conclusionQuick: "USD, HKD, and CNY are all meaningfully represented.",
      methodologyId: "methodology.exposure",
      i18n: { zh: {
        label: "货币敞口",
        formatted: "见明细",
        qualifierShort: "有限 · 统一示例性汇率快照",
        conclusionQuick: "美元(USD)、港元(HKD)与人民币(CNY)均占有相当比重。",
        caveat: "本明细对以下所有换算(包括人民币)统一采用单一固定的示例性汇率快照;本原型未对最近的人民币相关活动(见交易记录)单独建模历史汇率,因此人民币相关数字应视为方向性示例,而非对应某一具体汇率日期的精确调节结果。"
      } }
    })
  };

  // Holdings-level per-position claims (cost basis / unrealized gain-loss, D1 Holdings item 3)
  //
  // NOTE (found during this pass's sweep, not fixed — out of this task's named scope,
  // flagged for follow-up): methodology findings §7.3 shows that `costBasisUSD` below
  // applies a single CURRENT snapshot FX rate to both cost basis and market value, so the
  // FX rate cancels identically out of every per-position gain/loss percentage — a
  // pure local-currency price return with the currency effect silently removed, and a
  // retroactive-FX-application pattern §8.3 forbids. Fixing this correctly requires a
  // historical FX rate AT EACH POSITION'S TRANSACTION DATE, which this file's FX model
  // (single snapshot rates) does not carry; implementing it is a real, non-trivial
  // methodology extension I did not want to invent unreviewed. See this worker's handoff.
  // ---------------------------------------------------------------------
  // D2 (Post-HG1 Checkpoint A, owner decision H3, designer-33; corrected in the
  // Post-HG1 Checkpoint A correction round, designer-34, F1/F3/F4/F5 — see this
  // file's CONTRACT.md addendum at the end for the full record) — closes the
  // Stage-0 baseline gap that every per-position unrealized G/L claim's
  // Professional rung rendered identically to Simple (no `professionalDetail`
  // existed at all). Bounded to: the position inputs already on `h`
  // (quantity — a neutral, unitless "Quantity: <n>" label, never "shares"/"股";
  // avg cost/current price in native currency; currency; listing market); the
  // claim's OWN existing sufficiency state and reason, restated in plain words
  // (never a new judgment, never a new threshold); and a truthful
  // methodology-availability statement. The claim's OWN existing reference
  // basis (`referencePoint`) is NOT separately restated in this text — its own
  // Reference line already renders directly above it at Simple and
  // Professional, so restating it here only duplicated it; the `referencePoint`
  // FIELD itself is never touched by this addition. NEVER FX,
  // currency-conversion, or reporting-currency content — that is a real,
  // separate, `quant_analyst` question (methodology findings §7.3; see the
  // comment above `HOLDING_CLAIMS` and Stage-0 baseline §6 item 1), not
  // decided or disclosed here. Every numeral is interpolated from `h` at
  // build time — never a typed literal — formatted to the same OUTPUT format
  // `APP.ui.formatCurrency` renders on the ledger ("$1,234.56" for USD,
  // "CODE 1,234.56" for every other currency — not a single uniform
  // "CODE 1,234.56" convention applied to USD too, which is what this text
  // previously said and what the code previously did); this is a small,
  // self-contained equivalent (not a cross-module call into js/shell.js) so
  // this module's own numerals never depend on load order beyond what it
  // already requires. Quantity is still rendered as a bare integer string
  // (`String(value)`), matching exactly how js/surfaces/portfolio.js's ledger
  // table renders the same field (`String(h.quantity)`, no thousands
  // separator) rather than diverging from it with a separately-formatted copy.
  // ---------------------------------------------------------------------
  function fmtNativeAmount(value, currency) {
    if (typeof value !== "number") return null;
    var sign = value < 0 ? "-" : "";
    var abs = Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return sign + (currency === "USD" ? "$" : currency + " ") + abs;
  }
  function fmtQty(value) {
    return String(value);
  }
  var PROFESSIONAL_DETAIL_METHODOLOGY_NOTE_EN = "The per-position methodology registry entry for this figure is not yet published (see Evidence & Methodology).";
  var PROFESSIONAL_DETAIL_METHODOLOGY_NOTE_ZH = "该数值对应的单一持仓层面方法论登记条目尚未发布(见证据与方法论)。";
  // F1: quantity is a unitless ledger field (never "shares"/"股" — 2800.HK is a
  // warrant-linked structured note, not an equity share count), so it is labeled with
  // the neutral token the ledger's own column header uses ("Quantity" / "数量").
  // F5: "listed on <market>" read as ungrammatical prose; replaced with the
  // "listing market: <market>" label form.
  function professionalPositionLineEn(h) {
    var avgCostText = (h.avgCost === null || h.avgCost === undefined)
      ? "not provided (transferred in-kind on " + h.addedDate + ")"
      : fmtNativeAmount(h.avgCost, h.currency);
    return "Position detail: Quantity: " + fmtQty(h.quantity) + ", listing market: " + h.listingMarket +
      ", currency " + h.currency + ". Average cost: " + avgCostText + ". Current price: " +
      fmtNativeAmount(h.price, h.currency) + ".";
  }
  function professionalPositionLineZh(h) {
    var avgCostText = (h.avgCost === null || h.avgCost === undefined)
      ? "未提供(已于" + h.addedDate + "以实物形式转入)"
      : fmtNativeAmount(h.avgCost, h.currency);
    // "上市地:" + code matches the existing inspector header convention
    // (Stage-0 baseline observed "账户:… · 上市地:CN · 经济地理:中国") rather than
    // inventing a second punctuation style for the same field. "数量:" (F1) matches
    // the ledger's own "数量" column header, replacing the prior "股" unit word.
    return "持仓明细:数量:" + fmtQty(h.quantity) + ",上市地:" + h.listingMarket + ",货币:" + h.currency +
      "。平均成本:" + avgCostText + "。现价:" + fmtNativeAmount(h.price, h.currency) + "。";
  }

  var HOLDING_CLAIMS = {};
  HOLDINGS.forEach(function (h) {
    var mv = marketValueUSD(h);
    if (h.costBasisState === "INSUFFICIENT_DATA") {
      HOLDING_CLAIMS[h.id] = claim({
        id: "holding." + h.id + ".unrealizedGL", label: h.name + " — Unrealized Gain/Loss",
        sufficiency: "INSUFFICIENT_DATA", reasonCode: "MISSING_COST_BASIS",
        caveat: "Transferred in-kind from a legacy custodian on " + h.addedDate + "; original cost basis was not provided by the sending broker.",
        conclusionQuick: "Cost basis is missing for this position, so unrealized gain/loss cannot be shown.",
        methodologyId: "methodology.unrealizedGainLoss",
        // HG1 Round 5 SECOND micro-pass (Defect 3) — the one Portfolio holding
        // note the micro-pass verification's own residual scan named directly
        // ("Transferred in-kind from a legacy custodian on 2026-…"). Uses the
        // SAME structural hook `caveat`'s own sibling fields already use
        // (js/shell.js's `APP.ui.localizeClaimField`, `claim.i18n.<lang>.<field>`)
        // rather than a new mechanism — this claim just had not been populated
        // yet. `h.addedDate` is concatenated identically into both languages
        // (a date is canonical, not prose — never translated), so only the
        // surrounding sentence differs between the two caveat strings.
        // HG1 ux_planning revision (review-07, P0 item 1) — `conclusionQuick` had no
        // zh counterpart at all (only `caveat` did), so a holding that hits this
        // branch — 600519.SS (贵州茅台, one of the five holdings with an established
        // Chinese name) is the concrete case in this dataset — showed this English
        // sentence in the inspector drawer even in zh mode. Added, not reworded.
        // D2 (Post-HG1 Checkpoint A) — see the block comment above
        // `HOLDING_CLAIMS` for the content boundary. No percentage/G-L figure
        // appears anywhere in this text (cost basis is missing; none is
        // estimated or shown), and the basis/methodology sentences restate
        // what this claim family already establishes elsewhere, never a new
        // claim.
        // F4(a): the "Measurement basis" sentence previously here duplicated the
        // claim's own Reference line (rendered directly above this text at Simple
        // and Professional); removed rather than restated a second time.
        professionalDetail: professionalPositionLineEn(h) +
          " Sufficiency: insufficient data — cost basis is missing, so no gain/loss figure is estimated or shown. " +
          PROFESSIONAL_DETAIL_METHODOLOGY_NOTE_EN,
        i18n: { zh: {
          caveat: "已于 " + h.addedDate + " 以实物形式从原托管机构转入本组合;原始成本基础未由转出券商提供。",
          conclusionQuick: "该持仓缺少成本基础,因此无法显示未实现盈亏。",
          professionalDetail: professionalPositionLineZh(h) +
            "数据充分性:数据不足——成本基础缺失,因此不估算也不显示盈亏数值。" + PROFESSIONAL_DETAIL_METHODOLOGY_NOTE_ZH
        } }
      });
    } else {
      var costBasisUSD = h.avgCost * h.quantity * FX_RATES[h.currency];
      var glPct = costBasisUSD > 0 ? mv / costBasisUSD - 1 : null;
      var fields = {
        id: "holding." + h.id + ".unrealizedGL", label: h.name + " — Unrealized Gain/Loss",
        value: glPct, unit: "percent", directional: true, // HG1 Condition 2 — a genuine per-position gain/loss sign
        conclusionQuick: glPct >= 0 ? "This position has an unrealized gain." : "This position has an unrealized loss.",
        referencePoint: "Average cost basis, native currency",
        methodologyId: "methodology.unrealizedGainLoss",
        // HG1 ux_planning revision (review-07, P0 item 1) — this claim previously had
        // NO i18n.zh at ALL outside the h.thinlyTraded branch below, so every
        // non-thinly-traded holding's inspector body (conclusionQuick AND
        // referencePoint) rendered in English regardless of language — "参考:
        // Average cost basis, native currency," the label chrome localized but the
        // value not. Same Chinese sentences the thinlyTraded branch already
        // established for this identical shape, now the base case every holding gets;
        // thinlyTraded below EXTENDS this same i18n.zh object rather than replacing it.
        i18n: { zh: {
          conclusionQuick: glPct >= 0 ? "该持仓存在未实现收益。" : "该持仓存在未实现亏损。",
          referencePoint: "平均成本基础,原始货币"
        } }
      };
      // D2 (Post-HG1 Checkpoint A) — base Professional-depth detail, common
      // to every holding that reaches this branch. Reads `fields.referencePoint`/
      // `fields.i18n.zh.referencePoint` (set immediately above) rather than a
      // second, independently-typed copy of the same basis string, so the two
      // can never drift. Overwritten below (not appended to) by the
      // thinlyTraded/UNSUPPORTED_ASSET branches where they apply, since each
      // holding has exactly one sufficiency state and this sentence should
      // name the ACTUAL one, not accumulate contradictory ones; the
      // methodology-availability note is appended once, at the end, after
      // every branch below has had a chance to run.
      // F4(a): no "Measurement basis" restatement — the claim's own Reference line
      // (fields.referencePoint) already renders directly above this text at Simple
      // and Professional; restating it here duplicated it.
      fields.professionalDetail = professionalPositionLineEn(h) + " Sufficiency: available.";
      // Post-HG1 Checkpoint A correction round 3 (F-2, designer-35) — was "充足", which
      // is not this application's canonical ZH term for AVAILABLE. The canonical set,
      // confirmed against existing i18n (js/shell.js's common.limited/common.
      // insufficientData zh values, and js/data.js's own pre-existing "「可用」"/"「有限」"/
      // "数据不足" methodology prose at ~line 1487-1488) is: AVAILABLE "可用", LIMITED
      // "有限", INSUFFICIENT_DATA "数据不足" (this file's own INSUFFICIENT_DATA
      // professionalDetail branch, ~line 1915, already used "数据不足" correctly — only
      // this AVAILABLE branch had drifted). Meaning unchanged; English unchanged; the
      // underlying AVAILABLE value/state/reason code is untouched.
      fields.i18n.zh.professionalDetail = professionalPositionLineZh(h) + "数据充分性:可用。";
      if (h.thinlyTraded) {
        fields.sufficiency = "LIMITED";
        // HG1 Round 5, Phase 2 (S4 — quant_analyst ruling, Part A.4, finding F7). The
        // prior wording ("widening the effective confidence band on this figure") named
        // a statistical construct that is not actually computed for a per-position
        // unrealized gain/loss — no confidence interval exists here to widen. Reworded
        // to describe the real consequence (fewer/less-frequent prints -> a less
        // reliable figure) without asserting a statistical quantity this claim doesn't
        // carry — corrected in caveatFull AND omitted from qualifierShort, per the
        // ruling. qualifierShort is the ruling's own recommended string, added
        // alongside caveat (never replacing it — F4's same "add, don't rename" pattern).
        fields.caveat = "Thinly traded A-share; recent price prints are sparse, which may make this figure less reliable than a security with regular trading.";
        fields.qualifierShort = "limited · thinly traded; price prints sparse";
        // HG1 ux_planning revision (review-07, P0 item 1) — extends the base fields.i18n.zh
        // object set above (same conclusionQuick/referencePoint strings, unchanged) rather
        // than constructing a second i18n.zh literal that could drift from it.
        fields.i18n.zh.caveat = "交易稀少的A股;近期成交价数据零散,可能使该数值的可靠性低于交易活跃的证券。";
        fields.i18n.zh.qualifierShort = "有限 · 交易稀少,价格数据零散";
        // D2 (Post-HG1 Checkpoint A) — replaces the base "Sufficiency: available"
        // sentence set above with this holding's ACTUAL state (LIMITED), same
        // reason already stated in `caveat`/`qualifierShort`, restated in plain
        // words rather than a new judgment.
        // F4(a): same removal as the base branch above — no "Measurement basis"
        // restatement of the Reference line already rendered directly above this text.
        fields.professionalDetail = professionalPositionLineEn(h) +
          " Sufficiency: limited — thinly traded, sparse price prints.";
        fields.i18n.zh.professionalDetail = professionalPositionLineZh(h) +
          "数据充分性:有限——交易稀少,价格数据零散。";
      }
      if (h.analyticsSupport === "UNSUPPORTED_ASSET") {
        fields.sufficiency = "AVAILABLE"; // market value is a fact regardless
        // D2 (Post-HG1 Checkpoint A) — the G/L claim itself stays AVAILABLE
        // (unchanged above); this only ADDS the true, separate fact that this
        // instrument's RISK claim (INSTRUMENT_RISK_CLAIMS, below) is
        // UNSUPPORTED_ASSET — never restating the G/L claim's own state as
        // anything other than available.
        fields.professionalDetail += " Risk analytics are not computed for this instrument.";
        fields.i18n.zh.professionalDetail += "本工具不计算风险分析指标。";
      }
      // D2 (Post-HG1 Checkpoint A) — the truthful methodology-availability
      // statement, appended once after every branch above, in both languages.
      fields.professionalDetail += " " + PROFESSIONAL_DETAIL_METHODOLOGY_NOTE_EN;
      fields.i18n.zh.professionalDetail += PROFESSIONAL_DETAIL_METHODOLOGY_NOTE_ZH;
      HOLDING_CLAIMS[h.id] = claim(fields);
    }
  });

  // Per-instrument risk-metric support flag (UNSUPPORTED_ASSET reason code demo)
  // HG1 Round 5 micro-pass (Item 3) — added `i18n.zh`, this claim's prior
  // missing translation (PM-cited example: "Structured/derivative instruments
  // are not yet supported..."). This claim renders through
  // `APP.ui.renderMetricValue`'s compact INSUFFICIENT_DATA path on THREE
  // routes — Overview's Major Holdings table, Analytics' unsupported-asset
  // note, and Portfolio's Holdings inspector — so this one addition, combined
  // with this pass's shell.js fix to that render path (it was reading
  // `claim.caveat` directly, bypassing localization even where an i18n.zh
  // block existed), closes the same gap everywhere this claim is shown.
  // Canonical security name ("CSOP Structured Note") kept verbatim in the
  // label per PD-0015 §2.1 ("a security may display a localized or common name
  // ... while retaining canonical identity"); only the descriptive suffix
  // translates.
  var INSTRUMENT_RISK_CLAIMS = {
    "2800.HK": claim({
      id: "holding.2800.HK.riskMetrics", label: "CSOP Structured Note — Risk Metrics",
      sufficiency: "INSUFFICIENT_DATA", reasonCode: "UNSUPPORTED_ASSET",
      caveat: "Structured/derivative instruments are not yet supported by this analytics engine's factor model.",
      conclusionQuick: "Beta, volatility, and correlation are not computed for this instrument.",
      methodologyId: "methodology.beta",
      i18n: { zh: {
        label: "CSOP Structured Note ——风险指标",
        caveat: "本分析引擎的因子模型尚不支持结构性/衍生品类工具。",
        conclusionQuick: "该工具不计算贝塔系数、波动率和相关性。"
      } }
    })
  };

  // Transaction-level FX-conversion claim (D1 Transactions item 4)
  // HG1 Round 5 micro-pass (Item 3) — added `i18n.zh` (PM-cited example: "No
  // USD/CNY rate is on file for 2026-09-02 yet..."). Renders on Portfolio's
  // Transactions table (Reporting-Currency Conversion column) through the SAME
  // compact render path fixed above.
  var TRANSACTION_FX_CLAIMS = {
    "tx-0029": claim({
      id: "transaction.tx-0029.fxConversion", label: "Reporting-Currency Conversion",
      sufficiency: "INSUFFICIENT_DATA", reasonCode: "MISSING_FX_HISTORY",
      caveat: "No USD/CNY rate is on file for 2026-09-02 yet; the reporting-currency amount is withheld, not estimated.",
      conclusionQuick: "This transaction's USD-equivalent amount cannot be shown yet.",
      methodologyId: "methodology.fxConversion",
      i18n: { zh: {
        label: "报告货币换算",
        caveat: "截至目前,尚无2026-09-02的USD/CNY汇率记录;报告货币金额予以隐去,而非估算。",
        conclusionQuick: "该交易的美元等值金额暂时无法显示。"
      } }
    })
  };

  // =======================================================================
  // 9. Methodology registry (§33, 15 fields) — HG1 round 4 adds/corrects the
  //    entries this pass's corrections depend on (methodology findings §8).
  //    Entries NOT touched here (methodology.drawdown, .trackingError,
  //    .correlation, .sharpe, .exposure, .unrealizedGainLoss, .fxConversion,
  //    .portfolioGainLoss, .totalPortfolioValue) remain deliberately
  //    unpopulated — a separate deliverable per the methodology findings'
  //    own closing statement, not an oversight of this pass.
  // =======================================================================
  var METHODOLOGY = {
    "methodology.portfolioReturn": {
      metricName: "Portfolio Return", definition: "Time-weighted return of total portfolio value in reporting currency.",
      formula: "TWR chain-linking of sub-period returns", annualizationConvention: "Not annualized for periods ≤ 1Y; geometric annualization beyond 1Y",
      dataInputs: "Daily position values, cash balances, cash flows", minimumObservations: "1 valuation per business day",
      frequency: "Daily", lookback: "Selected period", benchmarkDependency: "MSCI ACWI (display only, not part of formula)",
      riskFreeRateDependency: "None", missingDataHandling: "Carry-forward last valid price, flagged via freshness axis",
      // HG1 round 4 (methodology findings §8 corrections list) — the prior text ("Spot
      // conversion at each valuation date's FX fix") was aspirational and not what the
      // code did (§4.1). Now accurate to what is actually implemented.
      fxTreatment: "Each non-USD sleeve's daily local-currency return is combined multiplicatively with that sleeve's own daily FX return (R_base=(1+R_local)(1+R_fx)-1) before blending at fixed beginning-of-period sleeve weights. No single named fixing time is currently modeled per market — an open product decision (methodology findings §9.2).",
      corporateActionTreatment: "Adjusted at ex-date",
      knownLimitations: "Synthetic prototype data; not a certified return engine. No single FX fixing time is modeled per market yet (see fxTreatment).", implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.beta": {
      metricName: "Beta", definition: "Sensitivity of portfolio returns to benchmark returns.",
      formula: "OLS regression slope, portfolio returns on benchmark returns", annualizationConvention: "N/A (dimensionless ratio)",
      dataInputs: "Daily portfolio and benchmark returns (reporting-currency, FX-inclusive)",
      // HG1 round 4 (methodology findings §1.4, §8 corrections list) — replaces the
      // unmeetable "36 monthly-equivalent observations preferred" against a 1Y daily
      // window (which can contain at most 12 monthly-equivalents) with the quant-set
      // threshold table.
      minimumObservations: "Weekly (PRD §14 default): ≥156 weekly obs (3Y) → AVAILABLE; 52–155 → LIMITED; <52 → INSUFFICIENT_DATA. Daily (if the weekly default is deviated from, as here): ≥750 daily obs (3Y) → AVAILABLE; 250–749 → LIMITED; <250 → INSUFFICIENT_DATA.",
      frequency: "Daily", lookback: "Trailing 1 year", benchmarkDependency: "MSCI ACWI",
      riskFreeRateDependency: "None", missingDataHandling: "Excludes non-trading days for either series",
      fxTreatment: "Reporting currency (FX-inclusive, HG1 round 4 — previously local-only in effect since no FX was applied to portfolio returns at all).", corporateActionTreatment: "Adjusted at ex-date",
      knownLimitations: "Synthetic prototype data; sample is LIMITED under the daily threshold above (250–749). PRD §14 sets weekly as the default frequency for cross-market beta, to reduce non-synchronous-close (Epps effect) bias, which biases beta and cross-market correlation toward zero; this implementation uses daily and records that deviation here rather than silently. A move to weekly is a scheduling/product decision, not yet made (methodology findings §1.3/§9.1).",
      implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.alpha": {
      metricName: "Jensen's Alpha", definition: "Excess return beyond what beta and the benchmark relationship predict.",
      formula: "alpha = (Rp - Rf) - beta * (Rb - Rf)", annualizationConvention: "Daily alpha × 252",
      dataInputs: "Portfolio returns, benchmark returns, beta, risk-free rate", minimumObservations: "Same as Beta",
      frequency: "Daily", lookback: "Trailing 1 year", benchmarkDependency: "MSCI ACWI",
      riskFreeRateDependency: "4.5% annualized assumption", missingDataHandling: "Same as Beta",
      fxTreatment: "Reporting currency (FX-inclusive)", corporateActionTreatment: "Adjusted at ex-date",
      knownLimitations: "Historical/model-based; not a measure of manager skill. Regression (arithmetic-mean) estimate — not the same basis as the SML chart's own vertical-distance quantity (see methodology.sml).", implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.volatility": {
      metricName: "Annualized Volatility", definition: "Standard deviation of daily returns, annualized.",
      formula: "stdev(daily returns) × sqrt(252)", annualizationConvention: "sqrt(252) scaling",
      dataInputs: "Daily portfolio returns (reporting-currency, FX-inclusive)", minimumObservations: "60 daily observations preferred",
      frequency: "Daily", lookback: "Trailing 1 year", benchmarkDependency: "None (benchmark shown for comparison only)",
      riskFreeRateDependency: "None", missingDataHandling: "Carry-forward last valid price",
      fxTreatment: "Reporting currency (FX-inclusive)", corporateActionTreatment: "Adjusted at ex-date",
      knownLimitations: "Synthetic prototype data.", implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.concentration": {
      metricName: "Concentration (HHI / Effective N)", definition: "Herfindahl-Hirschman Index and its inverse over position weights.",
      formula: "HHI = sum(w_i^2); Effective N = 1/HHI", annualizationConvention: "N/A",
      dataInputs: "Position market values", minimumObservations: "N/A", frequency: "As of snapshot",
      lookback: "Point-in-time", benchmarkDependency: "None", riskFreeRateDependency: "None",
      missingDataHandling: "Excludes positions with no priceable value", fxTreatment: "Reporting currency",
      corporateActionTreatment: "N/A", knownLimitations: "Synthetic prototype data. Denominator is holdings-only (excludes cash, ~19% of total portfolio value) — a product decision, not yet reconciled with other surfaces that use a different denominator (methodology findings §7.8, not resolved in this pass). ETF look-through not applied — VOO is the largest single position at ~20% of holdings (methodology findings §9.6, out of V1 scope per §18.4).", implementationVersion: "hg1-prototype-v2.0"
    },
    // ---- HG1 round 4 additions (methodology findings §8) ----
    "methodology.var": {
      metricName: "1-day Value at Risk, 95% confidence",
      definition: "The one-day loss magnitude that was exceeded on 5% of days in the observation window.",
      formula: "q = sorted(r)[floor(0.05·(n−1))] (lower order-statistic, no interpolation); VaR₉₅ = −q, reported for q<0.",
      annualizationConvention: "None. VaR is not annualized — scaling by √h is forbidden in V1 (assumes i.i.d. returns the cross-border series do not satisfy).",
      dataInputs: "Daily reporting-currency portfolio returns, including FX translation.",
      minimumObservations: "Tail count k = floor((1−c)·n) ≥ 10 ⇒ AVAILABLE; 5≤k<10 ⇒ LIMITED; k<5 ⇒ INSUFFICIENT_DATA. At c=95%: n≥200, 100≤n<200, n<100.",
      frequency: "Daily", lookback: "Trailing 252 trading days", benchmarkDependency: "None", riskFreeRateDependency: "None",
      missingDataHandling: "A day missing a price on any constituent market is excluded from the sample entirely; never carried forward. Excluded-day count is a required disclosure.",
      fxTreatment: "Returns are reporting-currency returns; FX moves are inside the distribution, not stripped out.",
      corporateActionTreatment: "Adjusted at ex-date",
      knownLimitations: "Historical simulation reproduces only losses that occurred in the window; not a loss limit, not a maximum, not a forecast. With ~252 observations the estimate rests on ~13 tail points and moves visibly when one rolls out of the window. Displayed as a non-negative loss magnitude (no sign, no directional colour) — the internal, composable quantity is the signed quantile.",
      implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.fxAttribution": {
      metricName: "FX / Performance Attribution",
      definition: "Decomposes reporting-currency return into a local-market (price) component and a currency (FX) component.",
      formula: "Sleeve level: R_base = (1+R_local)(1+R_fx) − 1, interaction reported as R_local·R_fx. Portfolio level: FX effect = R_base,P − R_local,P, with R_local,P translated at the period-start rate — exact by construction, no residual.",
      annualizationConvention: "None — reported over the stated window only; annualizing the legs separately would break the identity.",
      dataInputs: "Daily local-currency sleeve returns and daily FX returns (HKD, CNY).",
      minimumObservations: "Requires a complete FX series over the window. Any date missing an FX print is excluded and the exclusion count disclosed; >5% of dates missing ⇒ LIMITED; >20% ⇒ INSUFFICIENT_DATA with MISSING_FX_HISTORY.",
      frequency: "Daily", lookback: "Trailing 1 year", benchmarkDependency: "None", riskFreeRateDependency: "None",
      missingDataHandling: "Same as above.",
      fxTreatment: "One fixing time for all three markets is required by this methodology but not yet chosen as a product decision — flagged, not resolved (methodology findings §9.2).",
      corporateActionTreatment: "Adjusted at ex-date",
      knownLimitations: "Decomposes price and currency only. Income (dividends), fees, and taxes are not attributed in V1. The compounding interaction term is real and is reported inside the FX leg at portfolio level and separately at sleeve level (see APP.data.getFxAttributionDetail()).",
      implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.sml": {
      metricName: "Security Market Line position (ex-post)",
      definition: "Portfolio and sleeve realized returns plotted against beta, alongside an ex-post market line built from the REALIZED (not expected) benchmark return over the same window.",
      formula: "Line: y(β) = Rf + β×(Rb_realized − Rf). Vertical-distance annotation (concept 4) = realized portfolio return − line-implied return at the portfolio's beta, a geometric-return quantity — DIFFERENT from Jensen's alpha (concept 3, reported separately as metric.alpha), an OLS regression intercept on arithmetic daily excess returns, annualized ×252.",
      annualizationConvention: "Line and vertical distance: geometric, not annualized beyond the stated window. Regression alpha (separate claim): arithmetic mean ×252.",
      dataInputs: "Portfolio, benchmark, and sleeve daily returns; beta; risk-free rate.",
      minimumObservations: "Same as Beta.", frequency: "Daily", lookback: "Trailing 1 year",
      benchmarkDependency: "MSCI ACWI", riskFreeRateDependency: "4.5% annualized assumption",
      missingDataHandling: "Same as Beta.",
      fxTreatment: "Reporting currency (USD); sleeve points use reporting-currency (FX-inclusive) sleeve returns.",
      corporateActionTreatment: "Adjusted at ex-date",
      knownLimitations: "This window's realized market premium is negative (benchmark return below the risk-free rate), so the ex-post line correctly slopes downward. That is a faithful description of what happened in this window (P6), not a modeling error, and must not be “corrected” toward a conventional upward slope. Describes this sample only; not a forecast (P6).",
      implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.benchmarkRelative": {
      metricName: "Benchmark-Relative Return", definition: "Difference between portfolio and benchmark realized returns over the same nominal window.",
      formula: "Portfolio period return − benchmark period return (geometric, compounded).",
      annualizationConvention: "Not annualized for periods ≤1Y.",
      dataInputs: "Portfolio and benchmark daily returns.", minimumObservations: "N/A (two full-window totals, not a regression).",
      frequency: "Daily", lookback: "Trailing 1 year", benchmarkDependency: "MSCI ACWI", riskFreeRateDependency: "None",
      missingDataHandling: "Excludes non-trading days for either series.", fxTreatment: "Reporting currency (FX-inclusive).",
      corporateActionTreatment: "Adjusted at ex-date",
      knownLimitations: "Two-leg comparison (PD-0014 Part 1): when a constituent market's leg is priced at a different effective instant than the benchmark's, the difference includes a timing gap that is not portfolio performance. This is a temporal-comparability limitation, disclosed on the metric's own freshness/comparability field — independent of session-based freshness sufficiency (a leg can be fully current under the session-aware rule and still sit across a comparability seam, because markets close at different local times).",
      implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.sortino": {
      metricName: "Sortino Ratio", definition: "Excess return over the risk-free rate, divided by downside deviation (target semideviation), annualized.",
      formula: "Downside deviation = sqrt(mean over ALL N observations of min(r−MAR,0)^2) — denominator is the FULL sample size N, not the count of downside observations. Sortino = (mean(r)−Rf_daily)/downside_deviation_daily × sqrt(252).",
      annualizationConvention: "sqrt(252) scaling of both numerator and denominator.",
      dataInputs: "Daily portfolio returns (reporting-currency), daily risk-free rate (used as MAR).",
      minimumObservations: "Not yet set by methodology — no minimum-downside-observation threshold has been established for this metric (flagged, not invented here).",
      frequency: "Daily", lookback: "Trailing 1 year", benchmarkDependency: "None", riskFreeRateDependency: "4.5% annualized assumption (MAR)",
      missingDataHandling: "Carry-forward last valid price.", fxTreatment: "Reporting currency (FX-inclusive).",
      corporateActionTreatment: "Adjusted at ex-date",
      knownLimitations: "A prior implementation divided by the count of downside observations only, inflating downside deviation by roughly 39% at this sample's mix of up/down days and understating Sortino by roughly a quarter; corrected here to divide by the full sample N. This metric is currently withheld (INSUFFICIENT_DATA) in this prototype to demonstrate that rendering path, not because a real threshold has been breached.",
      implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.contributionToRisk": {
      metricName: "Contribution to Risk (sleeve)", definition: "Exact marginal-contribution-to-volatility (Euler) decomposition of total portfolio return volatility by sleeve.",
      formula: "MCTR_i = w_i × σ_i × ρ(i,portfolio); Σ_i MCTR_i = σ_portfolio exactly, for a linear portfolio (Euler's theorem). NOT an approximation.",
      annualizationConvention: "Volatilities annualized by √252; this factor cancels in the normalized percent shares.",
      dataInputs: "Daily sleeve returns (reporting-currency, FX-inclusive for HK/CN) and daily portfolio returns.",
      minimumObservations: "Same as Volatility.", frequency: "Daily", lookback: "Trailing 1 year",
      benchmarkDependency: "None", riskFreeRateDependency: "None", missingDataHandling: "Same as Volatility.",
      fxTreatment: "Reporting currency (FX-inclusive) — currency risk in the Hong Kong and Mainland China sleeves is included in their contribution figures.",
      corporateActionTreatment: "Adjusted at ex-date",
      // HG1 round 4 (quant_analyst verification §5.3) — the withheld segment's gap is
      // its RISK-CONTRIBUTION share, not its capital weight; those are different
      // quantities and conflating them is exactly the distinction §18.3 exists to draw.
      // The claim's own caveat (metric.contributionToRisk.caveat) already stated this
      // correctly; only this registry sentence had the wrong word.
      knownLimitations: "Decomposes return volatility only (not VaR or drawdown). Excludes cash (no return risk in this model). When a segment's contribution is withheld (INSUFFICIENT_DATA), the displayed AVAILABLE segments' shares do not sum to 100% — the gap equals the withheld segment's own RISK-CONTRIBUTION share (not its capital weight — those are different quantities, per §18.3) and is disclosed on the metric, not a silently missing remainder.",
      implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.correlation": {
      // HG1 round 4 (quant_analyst verification §4.3, §8) — this entry was empty, which
      // is "the one place §33 requires the basis to be recorded," and its absence is how
      // the local/base basis question became ambiguous in the first place.
      metricName: "Sleeve Correlation Matrix",
      definition: "Pearson correlation of daily returns among portfolio sleeves and the benchmark.",
      formula: "Pearson correlation coefficient (population, ÷N), rounded to 2 decimal places before display.",
      annualizationConvention: "N/A (correlation is unitless and not annualized).",
      dataInputs: "Four LOCAL-CURRENCY sleeve daily return series (US, HK, CN, Bonds) plus the benchmark's USD reporting-currency daily return series.",
      minimumObservations: "Same as Beta (the §14 daily/weekly deviation applies identically to cross-market correlation).",
      frequency: "Daily", lookback: "Trailing 1 year",
      benchmarkDependency: "MSCI ACWI (one of the five series)", riskFreeRateDependency: "None",
      missingDataHandling: "Excludes non-trading days for either series.",
      fxTreatment: "MIXED BASIS — a known, flagged inconsistency (HG1 round-4 verification §4.3): the four sleeve series are LOCAL-CURRENCY returns; the benchmark series is a USD reporting-currency return. Asset-level co-movement independent of currency is a legitimate question, but it makes the benchmark row/column a cross-currency correlation with the currency stripped from only one side, and it is inconsistent with CORR_PORT_BENCH and every other statistic on this surface, which are computed on the reporting-currency (base) series. Migrating the whole matrix to one basis is CP1 work, tracked as such.",
      corporateActionTreatment: "Adjusted at ex-date",
      knownLimitations: "Maximum absolute difference between the local and reporting-currency (base) bases across this matrix is small (0.0088 in this dataset) and the equity-pair ranking is identical in both bases, so no currently-displayed conclusion changes — but the basis inconsistency is real and must not be read as a reporting-currency portfolio-diversification statement until the migration lands. Band-classification language (see correlationConclusion) is evaluated on the base basis specifically, per this entry's own fxTreatment note, even though the displayed matrix stays local-currency. The precision guard for asserting a band label requires the nearest boundary to be ≥1.96 standard errors away (95% confidence) — tightened from a bare 1 se after quant_analyst found the original se figure was mis-attributed (the US/HK row's, not HK/CN's), which had let the verdict flip depending on which basis was used to evaluate the same pair.",
      implementationVersion: "hg1-prototype-v2.0"
    },
    "methodology.scenarioImpactModel": {
      // HG1 round 4 (quant_analyst verification §7.4) — every scenario comparison claim
      // (volatility/beta/concentration/sharpe) previously pointed methodologyId at the
      // REAL metric's own registry entry, so a figure produced by e.g. ANNUAL_VOL * 0.91
      // resolved its Proof Packet to "stdev(daily returns) × sqrt(252)." It did not. A
      // wrong audit trail is more dangerous than a missing one (P9) because it looks
      // complete. This entry gives those claims an honest, dedicated methodology
      // instead — see SCENARIO_COMPARISON_META below, which now points here.
      metricName: "Scenario Impact Model (illustrative)",
      definition: "How a hypothetical scenario's stated modification is projected onto the volatility, beta, concentration, and Sharpe figures shown in Scenario Lab.",
      formula: "A fixed illustrative multiplier applied to the metric's current AVAILABLE value (e.g. ANNUAL_VOL * 0.91). No causal risk-propagation model connects the scenario's stated modification (a weight change) to the multiplier's size.",
      annualizationConvention: "Inherits the underlying metric's own convention where applicable; the multiplier itself is not annualized.",
      dataInputs: "The current actual metric value only — the scenario's own stated modification (e.g. \"-50% of the CN-listed sleeve\") is NOT an input to this multiplier.",
      minimumObservations: "N/A — not a statistical estimate.",
      frequency: "N/A", lookback: "N/A",
      benchmarkDependency: "Inherits the underlying metric's dependency where applicable.", riskFreeRateDependency: "None",
      missingDataHandling: "N/A", fxTreatment: "N/A", corporateActionTreatment: "N/A",
      knownLimitations: "This is an illustrative fixed multiplier, not an impact model, and must not be read as a projection of what the scenario's stated modification would actually do to this figure. P8 already marks the resulting value as hypothetical and non-forecast (stateType: SCENARIO); this entry exists so the Proof Packet's audit trail is honest about the multiplier's own (non-)basis rather than pointing at the real metric's registry entry, which described a computation that did not produce this number.",
      implementationVersion: "hg1-prototype-v2.0"
    }
    // methodology.drawdown, .trackingError, .sharpe, .exposure,
    // .unrealizedGainLoss, .fxConversion, .portfolioGainLoss, .totalPortfolioValue are
    // deliberately left unpopulated — getMethodology() returns null for these, and the
    // evidence overlay renders "not yet published", demonstrating that required state
    // exists alongside the populated ones (see CONTRACT.md's note on why both states
    // are shown). Populating the full registry is quant_analyst's separate deliverable
    // per the methodology findings' own closing statement, not reopened here.
  };

  // =======================================================================
  // 10. Insights (§20) with Proof-Packet-shaped evidence
  // =======================================================================
  var INSIGHTS = [
    {
      id: "insight.concentration.top5", severity: "WARNING", judgmentClass: "Interpretation",
      // HG1 round 4 (pm-01 live verification, owner's §6.3) — a top-5 concentration
      // SHARE is a static level, not a change; APP_fmtPct's unconditional "+" was
      // wrong here (it rendered "+75.1%"). APP_fmtLevelPct never adds the superfluous
      // sign.
      claim: "Your top 5 holdings represent " + APP_fmtLevelPct(TOP5_SUM / TOTAL_HOLDINGS_VALUE) + " of invested value.",
      relatedClaimId: "metric.concentration",
      // HG1 Round 5, Phase 2 correction pass (Blocker 3 — the "INSIGHTS / claim
      // prose on Overview" residual, reviews/gates/HG1_ROUND5_PHASE2_CORRECTION_
      // VERIFICATION.md §2's own example). i18n.zh.claim is read by
      // ui.localizeClaimField at both call sites already routed through it
      // (js/surfaces/overview.js buildBlockD, js/shell.js renderInsightsList — both
      // already anticipated this field, per their own comments) — no shell.js/
      // overview.js change needed. Reuses the SAME `APP_fmtLevelPct(TOP5_SUM /
      // TOTAL_HOLDINGS_VALUE)` call the English sentence uses, never a
      // second, independently-typed number — a language switch cannot make this
      // sentence disagree with its own English twin about what the value is.
      i18n: { zh: { claim: "您的前五大持仓占投资价值的 " + APP_fmtLevelPct(TOP5_SUM / TOTAL_HOLDINGS_VALUE) + "。" } }
    },
    {
      id: "insight.economicGeography.divergence", severity: "WARNING", judgmentClass: "Fact",
      claim: "Your economic exposure to China is larger than your Hong Kong-listing exposure alone suggests — several Hong Kong-listed holdings are China-domiciled businesses.",
      relatedClaimId: "exposure.economicGeography",
      // No numeric value in this sentence (a qualitative fact about the ADR/dual-
      // listing distinction) — nothing to derive, only to translate accurately.
      i18n: { zh: { claim: "您对中国内地的经济敞口大于仅从香港上市敞口所能看出的水平——多家在香港上市的持仓实际上是在中国内地注册经营的企业。" } }
    },
    {
      id: "insight.fx.drag", severity: "ATTENTION", judgmentClass: "Interpretation",
      // HG1 round 4 (pm-01 live verification) — the number here is a MAGNITUDE
      // following "by roughly"; direction is already carried by "reduced"/"added to"
      // in the sentence. APP_fmtMagnitudePct (already used for VaR) is the right
      // formatter — it never adds a sign, and already applies Math.abs() internally.
      claim: "Currency movement " + (FX_ATTRIBUTION_PCT < 0 ? "reduced" : "added to") + " your reporting-currency return by roughly " + APP_fmtMagnitudePct(FX_ATTRIBUTION_PCT) + " this period.",
      relatedClaimId: "metric.fxAttribution",
      // Same FX_ATTRIBUTION_PCT sign branch and the same APP_fmtMagnitudePct(...)
      // call as the English sentence above — the direction word and the magnitude
      // are both derived from the one value, in both languages.
      i18n: { zh: { claim: "汇率变动本期" + (FX_ATTRIBUTION_PCT < 0 ? "使您的报告货币收益率降低了约 " : "使您的报告货币收益率增加了约 ") + APP_fmtMagnitudePct(FX_ATTRIBUTION_PCT) + "。" } }
    },
    {
      id: "insight.drawdown.deeper", severity: "ATTENTION", judgmentClass: "Fact",
      // HG1 round 4 (methodology findings §7.1) — was hardcoded "deeper" regardless of
      // which series was actually deeper; now derived from the same two values it
      // interpolates.
      claim: drawdownConclusion(MAX_DRAWDOWN, BENCHMARK_MAX_DRAWDOWN_1Y),
      relatedClaimId: "metric.maxDrawdown",
      // drawdownConclusion already accepts a lang param and is already used for
      // metric.maxDrawdown's own i18n.zh.conclusionQuick — reused verbatim here,
      // the same function on the same two values, not a second translation.
      i18n: { zh: { claim: drawdownConclusion(MAX_DRAWDOWN, BENCHMARK_MAX_DRAWDOWN_1Y, "zh") } }
    },
    {
      id: "insight.correlation.hkCluster", severity: "OBSERVATION", judgmentClass: "Interpretation",
      // HG1 round 4 (Task 2, PD-0014 §2.3 binding example 3; methodology findings §7.1) —
      // was hardcoded "high...correlation" for the pair that is in fact the WEAKEST
      // equity-sleeve pair in the matrix. Derived from CORR_HK_CN directly.
      claim: "Your Hong Kong and Mainland China sleeves show the WEAKEST pairwise correlation among your equity sleeves in this sample (" + CORR_HK_CN.toFixed(2) + "), not a high one — diversification between them is stronger than a same-region assumption would suggest.",
      relatedClaimId: "metric.correlation",
      // Same CORR_HK_CN.toFixed(2) read as the English sentence — a plain decimal,
      // unaffected by language.
      i18n: { zh: { claim: "您的香港板块与中国内地板块,在本样本的股票板块两两相关性中呈现出最弱的相关性(" + CORR_HK_CN.toFixed(2) + "),而非较高的相关性——二者之间的分散化效果强于「同一地区」这一假设所暗示的水平。" } }
    },
    {
      id: "insight.freshness.cnStale", severity: "ATTENTION", judgmentClass: "Fact",
      // HG1 round 4 CORRECTION (owner) — a prior version of this string asserted
      // "a local market holiday, not staleness." That was false: 2026-09-03 was an
      // ordinary SSE/SZSE trading session (see FRESHNESS_AXES's comment for the full
      // correction record), so this print genuinely IS stale by CN_SESSIONS_ELAPSED
      // session(s), derived from the explicit session calendar rather than restated
      // as independent prose. Severity raised from OBSERVATION to ATTENTION to match
      // metric.maxDrawdown/insight.drawdown.deeper's own severity for a genuine,
      // named data-quality condition.
      claim: "Mainland China A-share prices are " + CN_SESSIONS_ELAPSED + " completed local trading session" +
        (CN_SESSIONS_ELAPSED === 1 ? "" : "s") + " stale — the last print is dated " + CN_PRINT_DATE +
        ", and SSE/SZSE has since traded normally on " + CN_ASOF_DATE + " with no update received. This is genuine staleness, not a market holiday — see the benchmark-relative comparability note.",
      relatedClaimId: "metric.benchmarkRelative",
      // Same CN_SESSIONS_ELAPSED / CN_PRINT_DATE / CN_ASOF_DATE reads as the English
      // sentence (dates rendered verbatim, unchanged by language — the same
      // convention this file already uses for WINDOW_START_DATE/WINDOW_END_DATE in
      // metric.beta's own zh investorDetail). Chinese has no singular/plural
      // inflection, so no count-based branch is needed here the way English needs
      // the trailing "s".
      i18n: { zh: { claim: "中国内地A股价格已滞后 " + CN_SESSIONS_ELAPSED + " 个已完成的本地交易日——最新报价日期为 " + CN_PRINT_DATE +
        ",而沪深交易所已于 " + CN_ASOF_DATE + " 正常交易,但尚未收到更新数据。这是真实的数据滞后,并非市场假期所致——详见基准可比性说明。" } }
    },
    {
      id: "insight.policy.noCapSet", severity: "OBSERVATION", judgmentClass: "Preference-dependent judgment",
      claim: "No single-position concentration policy is on file, so this observation uses a general reference point rather than a personal threshold.",
      relatedClaimId: "metric.concentration",
      i18n: { zh: { claim: "系统中未设置单一持仓集中度政策,因此本观察采用一般性参考基准,而非个人化阈值。" } }
    },
    {
      id: "insight.sortino.insufficientData", severity: "OBSERVATION", judgmentClass: "Fact",
      claim: "Sortino ratio is currently withheld (INSUFFICIENT_DATA) to demonstrate that rendering path; no minimum-downside-observation threshold has been set for it yet.",
      relatedClaimId: "metric.sortino",
      // "INSUFFICIENT_DATA" here is reader-facing prose, not a canonical state
      // token being stored/matched on — rendered as this app's own established
      // lowercase register (common.insufficientData: "insufficient data" / "数据
      // 不足"), the same word js/data.js's own metric.sortino.i18n.zh.caveat and
      // conclusionQuick already use, not a second name for the same state.
      i18n: { zh: { claim: "索提诺比率(Sortino Ratio)目前被隐去(数据不足)以演示该渲染路径;尚未为其设定最低下行观测数阈值。" } }
    }
  ];

  // Unified lookup by the claim's OWN id (not the map key it happens to live under —
  // HOLDING_CLAIMS/INSTRUMENT_RISK_CLAIMS/TRANSACTION_FX_CLAIMS are all keyed by
  // position/transaction id for convenient per-row lookup, but each claim's .id field is
  // a different, longer string; evidence must resolve by THAT id, since that's what
  // getEvidence(claimId) and every chip/evidence-control pass in).
  var ALL_CLAIMS_BY_ID = {};
  Object.keys(METRICS).forEach(function (id) { ALL_CLAIMS_BY_ID[METRICS[id].id] = METRICS[id]; });
  Object.keys(HOLDING_CLAIMS).forEach(function (posId) { var c = HOLDING_CLAIMS[posId]; ALL_CLAIMS_BY_ID[c.id] = c; });
  Object.keys(INSTRUMENT_RISK_CLAIMS).forEach(function (posId) { var c = INSTRUMENT_RISK_CLAIMS[posId]; ALL_CLAIMS_BY_ID[c.id] = c; });
  Object.keys(TRANSACTION_FX_CLAIMS).forEach(function (txId) { var c = TRANSACTION_FX_CLAIMS[txId]; ALL_CLAIMS_BY_ID[c.id] = c; });

  var EVIDENCE = {};
  function registerEvidenceFor(claimId, extra) {
    var c = ALL_CLAIMS_BY_ID[claimId] || null;
    EVIDENCE[claimId] = Object.assign({
      insight_id: null, insight_type: null, severity: null, claim: c ? c.conclusionQuick : "",
      judgment_class: null, metrics_used: [claimId], portfolio_snapshot_id: "snap-2026-09-03",
      scenario_id: c && c.scenarioId ? c.scenarioId : null, comparison_basis: c ? c.referencePoint : "", benchmark: "MSCI ACWI",
      period: "Trailing 1Y", frequency: "Daily", observations: pr1y.length,
      thresholds_limits_if_used: c && c.caveat ? c.caveat : null,
      source_data_timestamps: FRESHNESS_AXES.map(function (a) { return a.axis + "@" + a.asOf; }),
      methodology_versions: { engine: "hg1-prototype-v2.0" }, data_freshness: getFreshness(),
      confidence_availability_state: c ? c.sufficiency : "AVAILABLE",
      limitations: c && c.caveat ? c.caveat : "None recorded.",
      permitted_suggested_explorations: ["Open Methodology", "View on Analytics"],
      methodologyId: c ? c.methodologyId : null
    }, extra || {});
  }
  Object.keys(ALL_CLAIMS_BY_ID).forEach(function (claimId) { registerEvidenceFor(claimId); });
  // HG1 round 4 (quant_analyst verification §6) — "se(β̂) must be exposed in the Proof
  // Packet alongside the observation count §13.3 already requires," so a reader (and
  // js/selfcheck.js's binding1) can verify the directional-claim tolerance-band decision
  // from the SAME evidence object the claim itself is judged against, not a second,
  // independently-hardcoded number.
  EVIDENCE["metric.beta"] = Object.assign({}, EVIDENCE["metric.beta"], {
    standard_error: BETA_SE, confidence_interval_95: BETA_CI95, sigmas_from_reference: BETA_SIGMAS_FROM_ONE
  });
  INSIGHTS.forEach(function (ins) {
    EVIDENCE[ins.id] = Object.assign({}, EVIDENCE[ins.relatedClaimId] || {}, {
      insight_id: ins.id, insight_type: ins.judgmentClass, severity: ins.severity, claim: ins.claim, judgment_class: ins.judgmentClass
    });
  });

  // =======================================================================
  // 11. Scenario Lab definitions (P8 — SCENARIO stateType throughout)
  //
  //     NOT touched in this pass: the comparison multipliers below (e.g.
  //     ANNUAL_VOL * 0.91, BETA * 0.93) are hardcoded scaling factors with no stated
  //     model, flagged by the methodology findings (§11 "not verified... a real open
  //     methodology gap") as outside this round's five named questions. Left as-is —
  //     inventing a scenario-impact model is exactly the kind of methodology
  //     PD-0014 §3 reserves to quant_analyst, and it was not asked for here.
  // =======================================================================
  // HG1 round 4 (found by the visual-track designer, narrowed live by pm-01) — the
  // reduceCnExposure scenario declared "-50%" against a target string that mixed two
  // dimensions ("economicGeography:China (CN-listed only)") and computed a 0.85
  // multiplier that reconciled with NEITHER reading (not -50% of China economic
  // geography, not -50% of the CN-listed sleeve — the removed amount matched no
  // coherent base at all). Fixed below by deriving the removed dollar amount from one,
  // clearly named, single dimension (the CN-listed / "A-share" sleeve, matching this
  // scenario's own name and description) and applying it to the economicGeography
  // total that dimension actually feeds, with the relationship stated explicitly
  // rather than left for a reader to reverse-engineer. Guarded going forward by
  // js/selfcheck.js's scenario.*.reconciles assertions (PD-0014 §2.2 extended from
  // claims-about-metrics to claims-about-scenarios, per the coordinator's instruction).
  var CN_LISTED_HOLDINGS_VALUE = HOLDINGS.filter(function (h) { return h.listingMarket === "CN"; })
    .reduce(function (s, h) { return s + marketValueUSD(h); }, 0);
  var CN_LISTED_HALVED_REMOVAL = CN_LISTED_HOLDINGS_VALUE * 0.5;
  var HK_LISTING_CURRENT_VALUE = (EXPOSURE.listingMarket.filter(function (s) { return s.label === "HK"; })[0] || { value: 0 }).value;
  var HK_SHIFT_REMOVAL = HK_LISTING_CURRENT_VALUE * 0.10;

  var SCENARIOS = [
    {
      id: "scenario.reduceCnExposure", name: "Reduce Mainland China exposure by half",
      // HG1 round 4: description now states BOTH the acted-on dimension (the CN-listed
      // "A-share" sleeve) and why the DISPLAYED economic-geography total falls by less
      // than half — because that total also includes Hong Kong-listed, China-domiciled
      // holdings this scenario does not touch. Stating the relationship replaces
      // silently mixing the two dimensions in one label.
      description: "Halves the Mainland China A-share (CN-listed) sleeve's market value, reallocating proceeds to cash. Because every CN-listed holding is China-domiciled, this reduction flows one-for-one into the China total shown in the economic-geography breakdown below — but that breakdown also includes Hong Kong-listed, China-domiciled holdings (Tencent, China Mobile, Alibaba, Meituan, the CSOP note), which this scenario does NOT touch, so China's economic-geography total falls by less than half.",
      modifications: [{ action: "REDUCE_WEIGHT", target: "listingMarket:CN (Mainland China A-share sleeve)", amount: "-50% of the CN-listed sleeve's market value, reallocated to cash" }],
      comparison: {
        // China's economic-geography value drops by EXACTLY the dollar amount removed
        // from the CN-listed sleeve (CN_LISTED_HALVED_REMOVAL) — not an unrelated flat
        // multiplier. Every segment's pct is recomputed against the shrunk holdings
        // total (the removed amount now sits in cash, outside this holdings-only
        // breakdown), the same convention scenario.addTreasuryCash already uses in the
        // opposite direction (money entering holdings from cash).
        allocation: {
          current: EXPOSURE.economicGeography,
          scenario: (function () {
            var newTotal = TOTAL_HOLDINGS_VALUE - CN_LISTED_HALVED_REMOVAL;
            return EXPOSURE.economicGeography.map(function (e) {
              var newValue = e.label === "China" ? (e.value - CN_LISTED_HALVED_REMOVAL) : e.value;
              return Object.assign({}, e, { value: newValue, pct: newTotal ? newValue / newTotal : 0 });
            });
          })()
        },
        concentration: { current: TOP5_SUM / TOTAL_HOLDINGS_VALUE, scenario: (TOP5_SUM / TOTAL_HOLDINGS_VALUE) * 0.92 },
        volatility: { current: ANNUAL_VOL, scenario: ANNUAL_VOL * 0.91 },
        beta: { current: BETA, scenario: BETA * 0.93 },
        sharpe: {
          current: SHARPE, scenario: null, sufficiency: "INSUFFICIENT_DATA", reasonCode: "MISSING_BENCHMARK",
          caveat: "This scenario's hypothetical cash reallocation has no benchmark-relative convention defined yet for a partial-liquidation scenario."
        }
      },
      // NOT touched in this pass, and flagged again here so it is not mistaken for
      // resolved: concentration/volatility/beta/sharpe above remain hardcoded scaling
      // factors with no stated impact model (methodology findings §11) — a real,
      // separate, already-flagged methodology gap PD-0014 §3 reserves to quant_analyst,
      // not something a reconciliation pass over the ALLOCATION numbers can or should
      // invent a fix for.
      warnings: ["Hypothetical only — no ledger change occurs until you explicitly edit your actual portfolio."],
      // HG1 Round 5 correction pass (PD-0012 §3 — Scenario Lab named explicitly as
      // required bilingual coverage). Mirrors the claim.i18n.{lang}.{field} convention
      // already established throughout this file (see e.g. metric.beta above) — read
      // by scenario.js/ai.js via the SAME APP.ui.localizeClaimField helper, which does
      // not require its argument to be a `claim()`-wrapped object, only an object
      // carrying `.i18n[lang][field]`. Only name/description/warnings are translated
      // HERE (this SCENARIOS entry's own data); `modifications[]` itself
      // (the raw action/target/amount technical readout) stays untranslated
      // DATA and is presented at RENDER time instead — js/surfaces/
      // scenario.js's presentModificationLine (Post-HG1 Checkpoint A — D3,
      // 2026-09-15, `designer-33`, superseding this pass's own prior
      // judgment that `action` should reach the screen as untranslated
      // canonical enum syntax). `action` is now rendered as a human-readable
      // bilingual label there; `target`/`amount`/`from`/`to` continue through
      // translateModificationValue exactly as before. The raw `action`/
      // `target` VALUES in this array are never edited by that presentation
      // layer — only what a reader sees changes.
      i18n: { zh: {
        name: "将中国内地敞口减半",
        description: "将中国内地A股(CN上市)板块的市值减半,所得资金转为现金。由于每一笔CN上市持仓在业务归属上均为中国内地企业,此项削减会一对一地反映在下方「经济地理」明细的中国合计中——但该明细还包含港股上市、但业务归属中国内地的持仓(腾讯控股、中国移动、阿里巴巴、美团、CSOP票据),本情景并不触及这些持仓,因此中国的经济地理合计降幅会小于一半。",
        warnings: ["仅为假设情景——除非您明确编辑实际投资组合,否则不会发生任何账本变动。"]
      } }
    },
    {
      id: "scenario.addTreasuryCash", name: "Add $50,000 to US Treasury ETF (TLT)",
      description: "Models deploying additional cash into TLT, reducing overall equity weight.",
      modifications: [{ action: "ADD_HYPOTHETICAL_INSTRUMENT", target: "TLT", amount: "+$50,000" }],
      comparison: {
        allocation: { current: EXPOSURE.assetClass, scenario: EXPOSURE.assetClass.map(function (e) { return e.label.indexOf("Fixed Income") >= 0 ? Object.assign({}, e, { value: e.value + 50000, pct: (e.value + 50000) / (TOTAL_HOLDINGS_VALUE + 50000) }) : Object.assign({}, e, { pct: e.value / (TOTAL_HOLDINGS_VALUE + 50000) }); }) },
        concentration: { current: TOP5_SUM / TOTAL_HOLDINGS_VALUE, scenario: TOP5_SUM / (TOTAL_HOLDINGS_VALUE + 50000) },
        volatility: { current: ANNUAL_VOL, scenario: ANNUAL_VOL * 0.95 },
        beta: { current: BETA, scenario: BETA * 0.96 },
        sharpe: { current: SHARPE, scenario: SHARPE * 1.04 }
      },
      warnings: ["Hypothetical only — no ledger change occurs until you explicitly edit your actual portfolio."],
      i18n: { zh: {
        name: "向美国国债ETF(TLT)追加5万美元",
        description: "模拟将额外现金配置到TLT,从而降低整体股票权重。",
        warnings: ["仅为假设情景——除非您明确编辑实际投资组合,否则不会发生任何账本变动。"]
      } }
    },
    {
      id: "scenario.shiftHkToUs", name: "Shift 10% of Hong Kong equity weight to US equity",
      description: "Models rotating a tenth of the HK sleeve into the existing US equity mix, pro-rata.",
      modifications: [{ action: "SHIFT_EXPOSURE", from: "HK equity", to: "US equity", amount: "10% of HK sleeve" }],
      comparison: {
        // HG1 round 4 sweep: the prior US multiplier (1.06) was a rounded approximation
        // that did not reconcile exactly with 10% of HK's own value moving over
        // (1.0648 is the exact figure). Both sides now derive from the SAME
        // HK_SHIFT_REMOVAL dollar amount — a pure within-holdings reallocation, so the
        // total (and every other segment's pct denominator) is unchanged.
        allocation: { current: EXPOSURE.listingMarket, scenario: EXPOSURE.listingMarket.map(function (e) {
          if (e.label === "HK") return Object.assign({}, e, { value: e.value - HK_SHIFT_REMOVAL, pct: (e.value - HK_SHIFT_REMOVAL) / TOTAL_HOLDINGS_VALUE });
          if (e.label === "US") return Object.assign({}, e, { value: e.value + HK_SHIFT_REMOVAL, pct: (e.value + HK_SHIFT_REMOVAL) / TOTAL_HOLDINGS_VALUE });
          return e;
        }) },
        concentration: { current: TOP5_SUM / TOTAL_HOLDINGS_VALUE, scenario: (TOP5_SUM / TOTAL_HOLDINGS_VALUE) * 1.01 },
        volatility: { current: ANNUAL_VOL, scenario: ANNUAL_VOL * 0.97 },
        beta: { current: BETA, scenario: BETA * 0.98 },
        sharpe: { current: SHARPE, scenario: SHARPE * 1.01 }
      },
      warnings: ["Hypothetical only — no ledger change occurs until you explicitly edit your actual portfolio."],
      i18n: { zh: {
        name: "将10%的香港股票权重转移至美国股票",
        description: "模拟将港股板块十分之一的比例按比例转入现有的美股组合。",
        warnings: ["仅为假设情景——除非您明确编辑实际投资组合,否则不会发生任何账本变动。"]
      } }
    }
  ];

  // =======================================================================
  // 11A. Scenario-comparison claims (P8) — a shared, single-source claim
  // object for each SCENARIO-side comparison figure, added during
  // integration (designer-14) to close a real gap: scenario.js builds
  // composite claim ids (scenarioId + "." + key, and scenarioId +
  // ".allocation." + dimension) for its Evidence buttons, but nothing in
  // this file registered an EVIDENCE record for them, so those buttons
  // previously resolved to nothing (evidence.js's renderScenarioFallback
  // covered the resulting gap gracefully, but the underlying gap was real).
  // Centralizing the claim shape here — rather than each of scenario.js and
  // ai.js building its own local copy, as both did before this pass — means
  // both surfaces render the identical object, and evidence.js can resolve a
  // real Proof Packet for it via APP.data.getScenarioComparisonClaim(id).
  // stateType is always "SCENARIO" (P8), so the existing ACTUAL/SCENARIO
  // badge check in shell.js's renderClaim/evidence.js's renderKeyNumber marks
  // these unmistakably wherever they render — never as if they were an
  // actual-portfolio claim.
  // =======================================================================
  // HG1 round 4 (quant_analyst verification §7.4) — all four methodologyId fields below
  // now point at methodology.scenarioImpactModel, NOT at the real metric's own registry
  // entry (methodology.volatility/.beta/.concentration/.sharpe). Every SCENARIOS entry
  // above produces these four figures with a fixed illustrative multiplier (e.g.
  // ANNUAL_VOL * 0.91), not by recomputing stdev/regression/HHI/Sharpe on a hypothetical
  // series — pointing at the real method's registry entry made the Proof Packet WRONG
  // rather than absent, which is the more dangerous state (a reader following the
  // evidence path was actively misled). The scenario ALLOCATION claims (below, a
  // different code path) are unaffected: those figures are exact dollar reconciliations
  // against the real ledger, not illustrative multipliers, so they correctly keep
  // methodology.exposure.
  var SCENARIO_COMPARISON_META = {
    volatility: { label: "Annualized Volatility", unit: "percent", methodologyId: "methodology.scenarioImpactModel" },
    beta: { label: "Beta (vs. Benchmark)", unit: "ratio", methodologyId: "methodology.scenarioImpactModel" },
    concentration: { label: "Concentration (Top 5)", unit: "percent", methodologyId: "methodology.scenarioImpactModel" },
    sharpe: { label: "Sharpe Ratio", unit: "ratio", methodologyId: "methodology.scenarioImpactModel" }
  };
  // HG1 Round 5 micro-pass (Item 3) — zh labels reused VERBATIM from the real
  // metric claims' own already-established i18n.zh.label above (metric.
  // volatility/.beta/.concentration/.sharpe) — one translated name per concept,
  // not a second, independently-chosen one for its scenario-comparison twin
  // (PD-0014 §2.5).
  var SCENARIO_COMPARISON_META_ZH = {
    volatility: "年化波动率", beta: "贝塔系数(相对基准)", concentration: "集中度(前五大)", sharpe: "夏普比率"
  };
  // Which exposure dimension each scenario's `comparison.allocation` field represents.
  // Must stay identical to scenario.js's own (independently-inferred) mapping — both
  // read the same three SCENARIOS entries below, so both must name the same dimension.
  var SCENARIO_ALLOCATION_DIMENSION = {
    "scenario.reduceCnExposure": "economicGeography",
    "scenario.addTreasuryCash": "assetClass",
    "scenario.shiftHkToUs": "listingMarket"
  };
  var SCENARIO_ALLOCATION_DIMENSION_ZH = {
    economicGeography: "经济地理", assetClass: "资产类别", listingMarket: "上市地"
  };
  // HG1 Round 5 micro-pass (Item 3) — the one known scenario-comparison caveat
  // this fixture actually produces (scenario.reduceCnExposure's sharpe entry,
  // PM-cited example: "This scenario's hypothetical cash reallocation has..."),
  // translated by exact string rather than restructuring `comparison[key]`'s
  // shape — this is the only entry in this fixture that carries a caveat at
  // all. Falls through to the original English for any future caveat this map
  // does not name, same "never silently drop content" rule every other
  // translator function in this file already follows.
  var SCENARIO_CAVEAT_ZH = {
    "This scenario's hypothetical cash reallocation has no benchmark-relative convention defined yet for a partial-liquidation scenario.":
      "本情景假设的现金再配置,尚未针对部分清仓情景定义相对基准的换算规则。"
  };
  var SCENARIO_CLAIMS = {};
  SCENARIOS.forEach(function (scenario) {
    // HG1 Round 5 micro-pass (Item 3) — this whole SCENARIO_CLAIMS family
    // previously baked its label/conclusionQuick/referencePoint/caveat strings
    // as plain English at module-load time (this IIFE runs once, before any
    // language switch), with NO `i18n` field at all — a genuine gap distinct
    // from "not yet translated," since these strings could not respond to a
    // language switch by construction, regardless of dictionary completeness.
    // Fixed the same way every other claim family in this file is: an
    // `i18n.zh` block computed alongside the English fields, read by the SAME
    // `APP.ui.localizeClaimField` every renderer already calls.
    var scenarioNameZh = (scenario.i18n && scenario.i18n.zh && scenario.i18n.zh.name) || scenario.name;
    Object.keys(SCENARIO_COMPARISON_META).forEach(function (key) {
      var entry = scenario.comparison[key];
      if (!entry) return;
      var meta = SCENARIO_COMPARISON_META[key];
      var metaLabelZh = SCENARIO_COMPARISON_META_ZH[key] || meta.label;
      var hasSufficiency = Object.prototype.hasOwnProperty.call(entry, "sufficiency");
      var id = scenario.id + "." + key;
      var caveatEn = hasSufficiency ? (entry.caveat || "") : "";
      var caveatZh = caveatEn && SCENARIO_CAVEAT_ZH[caveatEn] ? SCENARIO_CAVEAT_ZH[caveatEn] : caveatEn;
      SCENARIO_CLAIMS[id] = claim({
        id: id, label: meta.label + " (Scenario)", unit: meta.unit, value: entry.scenario,
        stateType: "SCENARIO", scenarioId: scenario.id,
        sufficiency: hasSufficiency ? entry.sufficiency : "AVAILABLE",
        reasonCode: hasSufficiency ? (entry.reasonCode || null) : null,
        caveat: caveatEn,
        conclusionQuick: "Hypothetical " + meta.label.toLowerCase() + " under “" + scenario.name + "” — not a holding (P8).",
        referencePoint: "Compared against the actual current " + meta.label.toLowerCase() + "; a hypothetical scenario output, not a forecast (P6).",
        methodologyId: meta.methodologyId,
        i18n: { zh: {
          label: metaLabelZh + "(情景)",
          conclusionQuick: "假设情景「" + scenarioNameZh + "」下的" + metaLabelZh + "——并非实际持仓(P8)。",
          referencePoint: "与当前实际" + metaLabelZh + "相比较;为假设情景结果,并非预测(P6)。",
          caveat: caveatZh
        } }
      });
    });
    var dim = SCENARIO_ALLOCATION_DIMENSION[scenario.id];
    if (dim && scenario.comparison.allocation) {
      var dimZh = SCENARIO_ALLOCATION_DIMENSION_ZH[dim] || dim;
      var allocId = scenario.id + ".allocation." + dim;
      SCENARIO_CLAIMS[allocId] = claim({
        id: allocId, label: "Allocation by " + dim + " (Scenario)", unit: "number", formatted: "See breakdown",
        stateType: "SCENARIO", scenarioId: scenario.id,
        conclusionQuick: "Hypothetical allocation by " + dim + " under “" + scenario.name + "” — not a holding (P8).",
        referencePoint: "Compared against the actual current allocation by " + dim + "; a hypothetical scenario output, not a forecast (P6).",
        methodologyId: "methodology.exposure",
        i18n: { zh: {
          label: "按" + dimZh + "划分的配置(情景)",
          formatted: "见明细",
          conclusionQuick: "假设情景「" + scenarioNameZh + "」下按" + dimZh + "划分的配置——并非实际持仓(P8)。",
          referencePoint: "与当前实际按" + dimZh + "划分的配置相比较;为假设情景结果,并非预测(P6)。"
        } }
      });
    }
  });
  // Merge into the shared claim/evidence registries the same way every other
  // claim family does (§10 above) — registerEvidenceFor and ALL_CLAIMS_BY_ID
  // both already exist by this point in the IIFE.
  Object.keys(SCENARIO_CLAIMS).forEach(function (id) {
    ALL_CLAIMS_BY_ID[id] = SCENARIO_CLAIMS[id];
    registerEvidenceFor(id);
  });

  // =======================================================================
  // 12. Portfolio Policy (P7) — deliberately unset by default
  // =======================================================================
  var POLICY = { reportingCurrency: "USD", singlePositionCapPct: null, sectorCapPct: null, riskTolerance: null };

  // =======================================================================
  // 13. Ingestion fixtures — CSV import + simulated OCR, all seven states
  // =======================================================================
  var CSV_FIXTURE = {
    filename: "usbroker_export_2026-09.csv",
    columns: ["Date", "Symbol", "Action", "Quantity", "Price", "Account"],
    rows: [
      { raw: { Date: "2026-08-28", Symbol: "AAPL", Action: "Buy", Quantity: "25", Price: "230.10", Account: "US Broker Brokerage (US)" },
        mapped: { date: "2026-08-28", ticker: "AAPL", type: "BUY", quantity: 25, price: 230.10, accountId: "acct-us-1" }, status: "STAGED", issues: [] },
      { raw: { Date: "2026-08-29", Symbol: "TSMC", Action: "Buy", Quantity: "10", Price: "185.40", Account: "US Broker Brokerage (US)" },
        mapped: { date: "2026-08-29", ticker: "TSMC", type: "BUY", quantity: 10, price: 185.40, accountId: "acct-us-1" },
        status: "AMBIGUOUS_SECURITY", issues: ["\"TSMC\" matches both TSM (NYSE ADR) and 2330.TW (TWSE) — resolve before import."] },
      { raw: { Date: "2026-08-30", Symbol: "MSFT", Action: "Buy", Quantity: "", Price: "441.00", Account: "US Broker Brokerage (US)" },
        mapped: { date: "2026-08-30", ticker: "MSFT", type: "BUY", quantity: null, price: 441.00, accountId: "acct-us-1" },
        status: "MISSING_FIELD", issues: ["Quantity column was blank in the source file — left empty, not inferred."] },
      { raw: { Date: "2026-09-02", Symbol: "AAPL", Action: "Buy", Quantity: "40", Price: "146.80", Account: "US Broker Brokerage (US)" },
        mapped: { date: "2026-09-02", ticker: "AAPL", type: "BUY", quantity: 40, price: 146.80, accountId: "acct-us-1" },
        status: "POSSIBLE_DUPLICATE", issues: ["Matches existing transaction tx-0022 (same date, symbol, quantity, price)."] }
    ],
    importReport: { staged: 4, confirmed: 0, quarantined: 1 }
  };

  var OCR_FIXTURE = {
    documents: [
      {
        id: "ocr-doc-1", sourceType: "portfolio_screenshot", filename: "futu_hk_holdings.png", uploadedAt: "2026-09-03 21:10",
        overallStatus: "STAGED",
        fields: [
          { id: "f1", label: "Tencent Holdings (0700.HK) quantity", extractedValue: "800", confidence: "HIGH", status: "OK",
            region: { page: 1, x: 120, y: 240, w: 160, h: 22 } },
          { id: "f2", label: "China Mobile (0941.HK) average cost", extractedValue: "58.2", confidence: "HIGH", status: "OK",
            region: { page: 1, x: 120, y: 268, w: 160, h: 22 } },
          { id: "f3", label: "Row 7 security name", extractedValue: "9988", confidence: "LOW", status: "LOW_CONFIDENCE",
            region: { page: 1, x: 60, y: 402, w: 90, h: 20 },
            note: "Character recognition for the listing suffix was unclear; candidate readings: '9988.HK' or '9988.SS'." },
          { id: "f4", label: "Row 9 security name", extractedValue: "Alibaba", confidence: "LOW", status: "AMBIGUOUS_SECURITY",
            region: { page: 1, x: 60, y: 448, w: 140, h: 20 },
            candidates: ["9988.HK — Alibaba Group (HK listing)", "BABA — Alibaba Group (NYSE ADR)"] },
          { id: "f5", label: "Row 11 cost basis", extractedValue: null, confidence: null, status: "MISSING_FIELD",
            region: { page: 1, x: 260, y: 494, w: 90, h: 20 },
            note: "Field was blank/unreadable in the source image — left empty, not inferred (OCR-6/OCR-7)." },
          { id: "f6", label: "Row 12: Meituan (3690.HK), 300 sh @ HKD 102.00", extractedValue: "300 @ 102.00", confidence: "HIGH", status: "POSSIBLE_DUPLICATE",
            region: { page: 1, x: 60, y: 520, w: 220, h: 20 },
            note: "Matches existing transaction tx-0014 (same date range, symbol, quantity, price)." }
        ]
      },
      {
        id: "ocr-doc-2", sourceType: "brokerage_screenshot", filename: "futu_hk_holdings.png (reviewed)", uploadedAt: "2026-09-03 21:14",
        overallStatus: "REVIEWED",
        fields: [
          { id: "g1", label: "Row 7 security name (corrected)", extractedValue: "9988", correctedValue: "9988.HK", confidence: "LOW", status: "CORRECTED",
            region: { page: 1, x: 60, y: 402, w: 90, h: 20 }, correctedBy: "user", correctedAt: "2026-09-03 21:13" }
        ]
      },
      {
        id: "ocr-doc-3", sourceType: "statement", filename: "china_brokerage_statement_aug2026.pdf", uploadedAt: "2026-09-03 21:20",
        overallStatus: "CONFIRMED",
        fields: [
          { id: "h1", label: "CATL (300750.SZ) quantity", extractedValue: "500", confidence: "HIGH", status: "CONFIRMED",
            region: { page: 2, x: 90, y: 140, w: 100, h: 20 }, confirmedBy: "user", confirmedAt: "2026-09-03 21:19" }
        ]
      }
    ]
  };

  // =======================================================================
  // 14. Public accessor surface
  // =======================================================================
  APP.data = {
    meta: {
      asOf: END_DATE.toISOString().slice(0, 10), reportingCurrency: "USD", portfolioId: "portfolio-hg1-demo",
      // HG1 round 4 (quant_analyst verification §7.3) — additive field, documenting the
      // rule now applied to every FRESHNESS_AXES timestamp so this as-of date actually
      // bounds its inputs (§34/P12). This is quant_analyst's RECOMMENDATION, applied to
      // make the prototype internally consistent for HG1 review; the underlying
      // "what does 'as of' mean across three timezones" question is CP0 architecture
      // and belongs to the human product owner to confirm, not to this designer to
      // decide unilaterally.
      asOfDefinition: "The as-of date is the latest instant at or before which every required input has a print (quant_analyst recommendation, pending owner confirmation — see methodology/HG1_ROUND4_VERIFICATION.md §7.3)."
    },

    getAccounts: function () { return ACCOUNTS.slice(); },
    getCashBalances: function () { return CASH_BALANCES.slice(); },
    getTotalPortfolioValue: function () { return TOTAL_PORTFOLIO_VALUE; },

    getHoldings: function () {
      return HOLDINGS.map(function (h) {
        return Object.assign({}, h, { marketValueUSD: marketValueUSD(h), pctOfPortfolio: marketValueUSD(h) / TOTAL_HOLDINGS_VALUE });
      });
    },
    getHolding: function (id) { return APP.data.getHoldings().filter(function (h) { return h.id === id; })[0] || null; },
    getHoldingClaim: function (id) { return HOLDING_CLAIMS[id] || null; },
    getInstrumentRiskClaim: function (id) { return INSTRUMENT_RISK_CLAIMS[id] || null; },

    // HG1 ux_planning revision (review-07, P0 item 3) — TRANSACTIONS above is meant to
    // stay strictly ascending by date (tx-0001 .. tx-0029 are), but tx-0030 (appended
    // 2025-12-01, out of order after tx-0029's 2026-09-02) broke that invariant, and
    // js/surfaces/portfolio.js's render relied on it IMPLICITLY via `.slice().reverse()`
    // rather than sorting explicitly — so the one out-of-order row surfaced at the top
    // of the ledger, read as the most recent activity (a P9 violation: stale activity
    // presented as current). Fixed HERE, in the accessor every caller of transaction
    // data actually goes through (js/surfaces/portfolio.js's two call sites, both
    // unchanged by this edit), rather than by re-positioning tx-0030 in the array —
    // moving one row fixes today's data but not the invariant, and the array will be
    // appended to again (this designer's brief's own reasoning). A raw array insertion
    // order was never a contract a caller should have to trust; this makes the
    // chronological ordering the ACCESSOR's own guarantee instead, so no future append
    // at any position can silently resurface this defect. Sorted ascending by `date`
    // (ISO 8601 strings sort correctly as plain strings) with `id` as a deterministic
    // tiebreaker for same-date entries — never by array position — so
    // `.slice().reverse()` (descending) or direct ascending consumption both get a
    // correctly and deterministically ordered result regardless of source-array
    // position. `.filter()` already returns a new array, so `.sort()` on it does not
    // mutate TRANSACTIONS itself; the `.slice()` this replaced is no longer needed.
    // Transaction dates/amounts/types themselves are completely untouched by this
    // change — only the ORDER this accessor returns them in.
    getTransactions: function (filter) {
      filter = filter || {};
      return TRANSACTIONS.filter(function (t) {
        if (filter.accountId && t.accountId !== filter.accountId) return false;
        if (filter.type && t.type !== filter.type) return false;
        if (filter.from && t.date < filter.from) return false;
        if (filter.to && t.date > filter.to) return false;
        return true;
      }).sort(function (a, b) {
        if (a.date < b.date) return -1;
        if (a.date > b.date) return 1;
        return a.id < b.id ? -1 : (a.id > b.id ? 1 : 0);
      });
    },
    getTransactionFxClaim: function (id) { return TRANSACTION_FX_CLAIMS[id] || null; },

    // RULING 2(ii) (BINDING, HG1_M1_PERIOD_RETURN_BASE_CONVENTION_RULING.md) — emits the
    // BASE-ANCHORED array: sliced from periodWindow(range).baseIndex, not from
    // sliceRange(range) directly, so the chart's own `a[last]/a[0]-1`
    // (js/charts.js — UNCHANGED by this fix, RULING 2(iv)) lands on the same base the
    // engine uses for the identically-named metric/window. `window` is a NEW, additive
    // field carrying the declared convention (`baseRule`) plus the metadata a caller
    // needs to label the chart correctly — RULING 1(c): the WINDOW label stays the
    // declared `firstReturnIndex..lastIndex` span; the extra leading point is the anchor
    // ("base"), not a 253rd observation. Arrays gain exactly one leading element for
    // 1M/3M/6M/1Y and are unchanged for ALL (RULING 2, 3).
    getPortfolioSeries: function (opts) {
      opts = opts || {};
      var w = periodWindow(opts.range || "1Y");
      return {
        dates: DATES.slice(w.baseIndex),
        portfolio: portfolioIndex.slice(w.baseIndex),
        benchmark: benchmarkIndex.slice(w.baseIndex),
        window: w
      };
    },
    // RULING 1(d) (BINDING, scope limit) — drawdown and rolling volatility are STATE
    // series (a level read directly off the axis), not a ratio between two endpoints;
    // they carry no "base" and are deliberately NOT routed through periodWindow. Left
    // exactly as before this fix — do not anchor these to periodWindow's baseIndex.
    getDrawdownSeries: function (opts) {
      opts = opts || {};
      var start = sliceRange(opts.range || "1Y");
      return { dates: DATES.slice(start), portfolio: portfolioDrawdown.slice(start), benchmark: benchmarkDrawdown.slice(start) };
    },
    getRollingVolatilitySeries: function (opts) {
      opts = opts || {};
      var start = sliceRange(opts.range || "1Y");
      return { dates: DATES.slice(start), portfolio: rollingVolPortfolio.slice(start), benchmark: rollingVolBenchmark.slice(start) };
    },

    getMetric: function (id) { return METRICS[id] || null; },
    getMetrics: function (ids) { return ids.map(function (id) { return METRICS[id]; }).filter(Boolean); },
    listMetricIds: function () { return Object.keys(METRICS); },

    getExposure: function (dimension) { return { dimension: dimension, segments: EXPOSURE[dimension] || [], claim: METRICS["exposure." + dimension] || null }; },
    getConcentration: function () { return { topPositions: holdingsWithValue.slice(0, 5), hhi: HHI, effectiveN: EFFECTIVE_N, claim: METRICS["metric.concentration"] }; },
    getCorrelationMatrix: function () { return { labels: CORR_LABELS, matrix: CORR_MATRIX, claim: METRICS["metric.correlation"] }; },
    getContributionToRisk: function () { return { segments: CONTRIBUTION_TO_RISK, claim: METRICS["metric.contributionToRisk"] }; },
    // HG1 round 4 — `verticalDistance` (concept 4, §2 of this pass) is a NEW field,
    // additive and backward-compatible (existing readers of .points/.line are
    // unaffected). See this worker's handoff: js/surfaces/analytics.js's alphaCallout
    // currently wires metric.alpha.value (concept 3) into the chart's own vertical-
    // distance annotation and needs to be updated to read THIS field instead — outside
    // this designer's write path.
    getSMLPoints: function () { return { points: SML_POINTS, line: SML_LINE, verticalDistance: SML_VERTICAL_DISTANCE, claim: METRICS["metric.sml"] }; },
    // HG1 round 4 — NEW accessor (methodology findings §4.4 item 4: "a stated per-sleeve
    // breakdown at Investor depth or deeper" for HK/CN local/FX/interaction/base). Not
    // yet consumed by any surface file (outside this designer's write path to add) —
    // flagged in handoff.
    getFxAttributionDetail: function () {
      return {
        portfolio: { local: PERIOD_RETURN_LOCAL, fxEffect: FX_ATTRIBUTION_PCT, base: PERIOD_RETURN },
        sleeves: {
          hk: { local: hkLocalReturn, fx: hkFxReturn, interaction: hkInteraction, base: hkBaseSleeveReturn, weight: SLEEVE_WEIGHTS.hk },
          cn: { local: cnLocalReturn, fx: cnFxReturn, interaction: cnInteraction, base: cnBaseSleeveReturn, weight: SLEEVE_WEIGHTS.cn }
        },
        excludes: ["income (dividends)", "fees", "taxes"],
        fixingTimeNote: "No single FX fixing time is currently modeled per market in this prototype; this is an open product decision (methodology findings §9.2), not resolved here."
      };
    },

    getInsights: function (opts) {
      opts = opts || {};
      return INSIGHTS.filter(function (i) { return !opts.severity || i.severity === opts.severity; }).slice();
    },
    getInsight: function (id) { return INSIGHTS.filter(function (i) { return i.id === id; })[0] || null; },

    getEvidence: function (claimId) { return EVIDENCE[claimId] || null; },
    getMethodology: function (id) { return METHODOLOGY[id] || null; },

    getScenarios: function () { return SCENARIOS.slice(); },
    getScenario: function (id) { return SCENARIOS.filter(function (s) { return s.id === id; })[0] || null; },
    getScenarioComparisonClaim: function (claimId) { return SCENARIO_CLAIMS[claimId] || null; },

    getFreshness: getFreshness,
    getPolicy: function () { return Object.assign({}, POLICY); },

    getIngestionFixtures: function () { return { csv: CSV_FIXTURE, ocr: OCR_FIXTURE }; },

    // Internal, exposed for charts.js / debugging only — not part of the guaranteed
    // accessor contract in CONTRACT.md, but harmless to read. HG1 round 4 adds a few
    // fields here specifically so js/selfcheck.js can verify facts (like "sleeve
    // weights actually derive from holdings") without reaching into this closure.
    _internal: {
      DATES: DATES, portfolioReturns: portfolioReturns, benchmarkReturns: benchmarkReturns,
      sleeveWeights: SLEEVE_WEIGHTS, downsideDayCount: DOWNSIDE_DAY_COUNT,
      sortino: SORTINO, downsideDeviationAnnualized: DOWNSIDE_DEV_ANNUAL,
      windowStart: WINDOW_START_DATE, windowEnd: WINDOW_END_DATE, windowObservationCount: WINDOW_OBS_COUNT,
      // HG1 M1 fix — exposes the CANONICAL window/base-convention function itself (the
      // same one PERIOD_RETURN/getPortfolioSeries call, not a duplicate), plus a thin
      // wrapper around the SAME division PERIOD_RETURN/BENCHMARK_PERIOD_RETURN perform,
      // generalized to any of the five range selectors and either leg. Neither is a new
      // claim/metric (M1-F8: publishing a per-range return is a product-scope decision
      // left open); both exist so js/selfcheck.js's render/data-layer regression (RC-1,
      // RC-2) can reconcile a rendered quantity against the engine's OWN formula for a
      // range with no published metric.return.* fact, per RULING 5.
      periodWindow: periodWindow,
      enginePeriodReturn: function (range, leg) {
        var w = periodWindow(range);
        var idx = leg === "benchmark" ? benchmarkIndex : (leg === "local" ? portfolioIndexLocal : portfolioIndex);
        return enginePeriodReturnOn(idx, w);
      },
      // HG1 round 4 (quant_analyst verification §5.2) — exposed so js/selfcheck.js's
      // correlation.bandClassificationPrecision assertion can independently verify any
      // band-label claim without duplicating the correlation/standard-error arithmetic.
      correlationBandInfo: { hkCn: CORR_HK_CN_BAND_INFO },
      // HG1 round 4 (harmonized threshold) — exposed so js/selfcheck.js's binding1 can
      // read the SAME threshold beta's own directional claim is judged against,
      // rather than a separately hardcoded "1.96" that could silently drift from it.
      directionalClaimSeMultiplier: DIRECTIONAL_CLAIM_SE_MULTIPLIER,
      // HG1 round 4 (SSE calendar correction) — exposes the CANONICAL calendar
      // functions themselves (not a duplicate/parallel implementation) so
      // js/selfcheck.js's sseCalendar.* assertions can verify their behavior against
      // known reference facts (day-of-week is deterministic; specific holiday
      // membership is checkable data) without re-deriving the classification logic.
      // sseHolidayDates is the SAME mutable object sseSessionInfo/sseSessionsElapsed
      // close over, so a test can mutate it directly as a realistic negative-test
      // injector (a wrong calendar entry), not a separately-maintained copy.
      sseSessionInfo: sseSessionInfo,
      sseSessionsElapsed: sseSessionsElapsed,
      sseHolidayDates: SSE_HOLIDAY_DATES,
      cnSessionsElapsed: CN_SESSIONS_ELAPSED,
      cnPrintDate: CN_PRINT_DATE,
      cnAsOfDate: CN_ASOF_DATE
    }
  };

  // HG1 round 4 (Task 3, PD-0014 §2.2) — js/selfcheck.js is now loaded via a static
  // <script src="js/selfcheck.js"> tag in index.html (added by the visual-track
  // designer, who owns that file), so the dynamic <script> injection this file used
  // to carry as a workaround is removed. See CONTRACT.md's round-4 addendum for the
  // history of that workaround.
})();
