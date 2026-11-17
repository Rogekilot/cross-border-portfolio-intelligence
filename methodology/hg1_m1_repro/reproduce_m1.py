#!/usr/bin/env python3
"""
HG1 defect M1 — independent reproduction harness.

Purpose: reproduce, OUTSIDE the prototype, the return series that
`designs/hg1-prototype-v2/js/data.js` generates, so that the chart-vs-engine
discrepancy can be measured from first principles rather than read off a
running page (this role has no browser) or taken on trust from a bug report.

This is a READ-ONLY port. It reads nothing from the prototype at runtime; it
re-implements data.js sections 0-2 exactly (mulberry32 PRNG, Box-Muller
gaussian, the 504-weekday calendar, the factor model, the holdings-derived
sleeve weights, the FX combination, the cumulative index) and then evaluates
every candidate return convention over the trailing-1Y window.

Fidelity notes (stated so a reviewer can discount appropriately):
  * mulberry32 is exact integer arithmetic; Python reproduces it bit-for-bit.
  * Box-Muller uses log/cos/sqrt. Python and V8 both call the platform libm at
    double precision; agreement is to ~1 ulp per call, which cannot move a
    figure quoted to 0.01 pp.
  * No DOM, no charts.js: chart-side quantities are recomputed here from the
    SAME formulas charts.js uses, quoted by file:line in the ruling.

Run:  python3 methodology/hg1_m1_repro/reproduce_m1.py
"""

import math
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# data.js section 0 — deterministic PRNG (js/data.js:85-98)
# ---------------------------------------------------------------------------

MASK = 0xFFFFFFFF


def u32(x):
    return x & MASK


def i32(x):
    x = x & MASK
    return x - 0x100000000 if x >= 0x80000000 else x


def imul(a, b):
    """JS Math.imul."""
    return i32(u32(a) * u32(b))


def mulberry32(seed):
    state = {"s": i32(seed)}

    def _next():
        s = i32(state["s"])
        s = i32(s + 0x6D2B79F5)
        state["s"] = s
        t = imul(u32(s) ^ (u32(s) >> 15), i32(1 | s))
        t = i32(i32(t + imul(u32(t) ^ (u32(t) >> 7), i32(61 | t))) ^ t)
        return u32(u32(t) ^ (u32(t) >> 14)) / 4294967296.0

    return _next


rand = mulberry32(20260904)


def gaussian():
    u = max(rand(), 1e-9)
    v = max(rand(), 1e-9)
    return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v)


# ---------------------------------------------------------------------------
# data.js section 1 — calendar (js/data.js:196-208)
# ---------------------------------------------------------------------------

TRADING_DAYS = 504
END_DATE = date(2026, 9, 3)


def build_dates():
    out = []
    d = END_DATE
    while len(out) < TRADING_DAYS:
        # JS getUTCDay(): 0=Sun, 6=Sat.  Python weekday(): 0=Mon .. 6=Sun
        js_day = (d.weekday() + 1) % 7
        if js_day != 0 and js_day != 6:
            out.insert(0, d.isoformat())
        d = d - timedelta(days=1)
    return out


DATES = build_dates()

# ---------------------------------------------------------------------------
# data.js section 1.5 — holdings -> sleeve weights (js/data.js:238-289)
# ---------------------------------------------------------------------------

FX_RATES = {"USD": 1.0, "HKD": 0.1282, "CNY": 0.1406}

# (id, listingMarket, currency, assetClass, quantity, price)
HOLDINGS = [
    ("AAPL", "US", "USD", "Equity", 120, 231.55),
    ("MSFT", "US", "USD", "Equity", 60, 441.20),
    ("NVDA", "US", "USD", "Equity", 40, 118.40),
    ("VOO", "US", "USD", "Equity Fund", 85, 512.30),
    ("TLT", "US", "USD", "Fixed Income Fund", 150, 88.10),
    ("0700.HK", "HK", "HKD", "Equity", 800, 398.20),
    ("0941.HK", "HK", "HKD", "Equity", 2000, 82.60),
    ("9988.HK", "HK", "HKD", "Equity", 600, 91.40),
    ("3690.HK", "HK", "HKD", "Equity", 300, 128.90),
    ("2800.HK", "HK", "HKD", "Derivative", 2000, 3.85),
    ("600519.SS", "CN", "CNY", "Equity", 20, 1542.00),
    ("300750.SZ", "CN", "CNY", "Equity", 500, 221.80),
    ("601318.SS", "CN", "CNY", "Equity", 300, 49.90),
]


def market_value_usd(h):
    return h[4] * h[5] * FX_RATES[h[2]]


def sleeve_key(h):
    if h[3] == "Fixed Income Fund":
        return "bond"
    return {"US": "us", "HK": "hk", "CN": "cn"}.get(h[1])


TOTAL_HOLDINGS_VALUE = sum(market_value_usd(h) for h in HOLDINGS)
SLEEVE_MARKET_VALUE = {"us": 0.0, "hk": 0.0, "cn": 0.0, "bond": 0.0}
for _h in HOLDINGS:
    _k = sleeve_key(_h)
    if _k:
        SLEEVE_MARKET_VALUE[_k] += market_value_usd(_h)

SLEEVE_WEIGHTS = {k: v / TOTAL_HOLDINGS_VALUE for k, v in SLEEVE_MARKET_VALUE.items()}

# ---------------------------------------------------------------------------
# data.js section 2 — factor model (js/data.js:296-351)
# PRNG consumption order is load-bearing and reproduced verbatim.
# ---------------------------------------------------------------------------

RF_ANNUAL = 0.045
RF_DAILY = RF_ANNUAL / 252

marketFactor = [gaussian() * 0.0075 + 0.00030 for _ in DATES]


def sleeve_returns(loading, idio_sigma, drift_adj=0.0):
    return [loading * marketFactor[i] + gaussian() * idio_sigma + drift_adj
            for i in range(len(DATES))]


benchmarkReturns = list(marketFactor)
usEquitySleeve = sleeve_returns(1.05, 0.0065, 0.00005)
hkEquitySleeve = sleeve_returns(1.15, 0.0110, -0.00005)
cnEquitySleeve = sleeve_returns(0.85, 0.0140, -0.00015)
bondSleeve = sleeve_returns(0.15, 0.0035, 0.00002)

portfolioReturnsLocal = [
    SLEEVE_WEIGHTS["us"] * usEquitySleeve[i] + SLEEVE_WEIGHTS["hk"] * hkEquitySleeve[i]
    + SLEEVE_WEIGHTS["cn"] * cnEquitySleeve[i] + SLEEVE_WEIGHTS["bond"] * bondSleeve[i]
    for i in range(len(DATES))
]

fxHKD = [gaussian() * 0.0009 for _ in DATES]
fxCNY = [gaussian() * 0.0022 - 0.00006 for _ in DATES]


def combine_local_fx(r_local, r_fx):
    return (1 + r_local) * (1 + r_fx) - 1


usEquitySleeveBase = usEquitySleeve
bondSleeveBase = bondSleeve
hkEquitySleeveBase = [combine_local_fx(r, fxHKD[i]) for i, r in enumerate(hkEquitySleeve)]
cnEquitySleeveBase = [combine_local_fx(r, fxCNY[i]) for i, r in enumerate(cnEquitySleeve)]

portfolioReturns = [
    SLEEVE_WEIGHTS["us"] * usEquitySleeveBase[i] + SLEEVE_WEIGHTS["hk"] * hkEquitySleeveBase[i]
    + SLEEVE_WEIGHTS["cn"] * cnEquitySleeveBase[i] + SLEEVE_WEIGHTS["bond"] * bondSleeveBase[i]
    for i in range(len(DATES))
]


def cumulative_index(returns, base=100.0):
    out = [base]
    for r in returns:
        out.append(out[-1] * (1 + r))
    return out[1:]


portfolioIndex = cumulative_index(portfolioReturns)
portfolioIndexLocal = cumulative_index(portfolioReturnsLocal)
benchmarkIndex = cumulative_index(benchmarkReturns)


def slice_range(rng):
    n = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252, "ALL": TRADING_DAYS}.get(rng, 252)
    return max(0, len(DATES) - n)


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------

def pct(x):
    return "%+8.4f%%" % (x * 100)


def engine_period_return(index, i):
    """js/data.js:391 — base at i-1, clamped at 0."""
    return index[-1] / index[i - 1 if i - 1 >= 0 else 0] - 1


def chart_period_return(index, i):
    """js/charts.js:476/497 — a[last]/a[0]-1 over the SLICED array."""
    sl = index[i:]
    return sl[-1] / sl[0] - 1


def main():
    print("=" * 78)
    print("HG1 M1 — independent reproduction of the chart/engine trailing-1Y gap")
    print("=" * 78)
    print()
    print("Calendar")
    print("  len(DATES)              = %d" % len(DATES))
    print("  DATES[0]                = %s" % DATES[0])
    print("  DATES[-1]               = %s" % DATES[-1])
    i1y = slice_range("1Y")
    print("  sliceRange('1Y')  i1y   = %d" % i1y)
    print("  DATES[i1y-1]            = %s   <- engine base date" % DATES[i1y - 1])
    print("  DATES[i1y]              = %s   <- chart first plotted date" % DATES[i1y])
    print("  displayed points        = %d" % len(DATES[i1y:]))
    print()

    print("Sleeve weights (derived from HOLDINGS)")
    for k in ("us", "hk", "cn", "bond"):
        print("  %-5s = %.6f" % (k, SLEEVE_WEIGHTS[k]))
    print()

    print("Single-day returns at the seam (index %d = %s)" % (i1y, DATES[i1y]))
    print("  portfolio r[i1y]        = %s" % pct(portfolioReturns[i1y]))
    print("  benchmark r[i1y]        = %s" % pct(benchmarkReturns[i1y]))
    print()

    e_p = engine_period_return(portfolioIndex, i1y)
    c_p = chart_period_return(portfolioIndex, i1y)
    e_b = engine_period_return(benchmarkIndex, i1y)
    c_b = chart_period_return(benchmarkIndex, i1y)
    e_pl = engine_period_return(portfolioIndexLocal, i1y)
    c_pl = chart_period_return(portfolioIndexLocal, i1y)

    print("Trailing 1Y — PORTFOLIO (base currency, FX-inclusive)")
    print("  engine PERIOD_RETURN            (base idx %d) = %s" % (i1y - 1, pct(e_p)))
    print("  chart  a[last]/a[0]-1           (base idx %d) = %s" % (i1y, pct(c_p)))
    print("  delta (chart - engine)                        = %s" % pct(c_p - e_p))
    print()
    print("Trailing 1Y — PORTFOLIO (local-currency, FX held at start)")
    print("  engine PERIOD_RETURN_LOCAL      (base idx %d) = %s" % (i1y - 1, pct(e_pl)))
    print("  chart-convention on local index (base idx %d) = %s" % (i1y, pct(c_pl)))
    print()
    print("Trailing 1Y — BENCHMARK")
    print("  engine BENCHMARK_PERIOD_RETURN  (base idx %d) = %s" % (i1y - 1, pct(e_b)))
    print("  chart  b[last]/b[0]-1           (base idx %d) = %s" % (i1y, pct(c_b)))
    print()
    print("Trailing 1Y — RELATIVE (arithmetic difference of simple returns)")
    print("  engine metric.benchmarkRelative = PERIOD_RETURN - BENCHMARK_PERIOD_RETURN")
    print("                                                = %s" % pct(e_p - e_b))
    print("  chart  relDiff = retAAll - retBAll            = %s" % pct(c_p - c_b))
    print("  delta (chart - engine)                        = %s" % pct((c_p - c_b) - (e_p - e_b)))
    print()

    print("Does the one-day base offset ALONE explain both gaps?")
    kp = 1 + portfolioReturns[i1y]
    kb = 1 + benchmarkReturns[i1y]
    print("  identity check portfolio: (1+chart)*(1+r[i1y]) - 1 = %s   engine = %s   residual = %.3e"
          % (pct((1 + c_p) * kp - 1), pct(e_p), ((1 + c_p) * kp - 1) - e_p))
    print("  identity check benchmark: (1+chart)*(1+r[i1y]) - 1 = %s   engine = %s   residual = %.3e"
          % (pct((1 + c_b) * kb - 1), pct(e_b), ((1 + c_b) * kb - 1) - e_b))
    print()

    print("Counterfactual: is the gap FX-related? (compare FX-inclusive vs local)")
    print("  chart-convention base-ccy   = %s" % pct(c_p))
    print("  chart-convention local-ccy  = %s" % pct(c_pl))
    print("  engine base-ccy             = %s" % pct(e_p))
    print("  engine local-ccy            = %s" % pct(e_pl))
    print()

    print("All selector periods — chart convention vs engine convention (portfolio)")
    print("  %-5s %-4s %-12s %-12s %-12s %-10s" % ("range", "i", "start(chart)", "chart ret", "engine ret", "delta pp"))
    for rng in ("1M", "3M", "6M", "1Y", "ALL"):
        i = slice_range(rng)
        c = chart_period_return(portfolioIndex, i)
        e = engine_period_return(portfolioIndex, i)
        print("  %-5s %-4d %-12s %-12s %-12s %-10.4f"
              % (rng, i, DATES[i], pct(c).strip(), pct(e).strip(), (c - e) * 100))
    print()

    print("Semantic-bucket consequence (returnAnalogyQuick branches at pct >= 5)")
    for name, v in (("engine PERIOD_RETURN", e_p), ("chart end label", c_p)):
        print("  %-22s = %6.2f%%  -> bucket %s"
              % (name, v * 100, "'>=5 meaningful'" if v * 100 >= 5 else "'<5 flat/near-breakeven'"))
    print()

    print("Rounding note — how each figure is DISPLAYED")
    print("  APP_fmtPct(engine PERIOD_RETURN) = %s" % ("%+.1f%%" % (e_p * 100)))
    print("  chart pctText(chart return)      = ~%s (see js/charts.js pctText)" % ("%+.1f%%" % (c_p * 100)))
    print()

    print("Closed-form error identity:  R_engine - R_chart == (1 + R_chart) * r[i]")
    for rng in ("1M", "3M", "6M", "1Y", "ALL"):
        i = slice_range(rng)
        c = chart_period_return(portfolioIndex, i)
        e = engine_period_return(portfolioIndex, i)
        pred = (1 + c) * portfolioReturns[i]
        print("  %-5s r[i]=%s  observed(e-c)=%s  predicted=%s  residual=%.3e"
              % (rng, pct(portfolioReturns[i]).strip(), pct(e - c).strip(), pct(pred).strip(), (e - c) - pred))
    print("  (ALL is the exception: i=0 has no prior close, so the clamp makes")
    print("   engine == chart and BOTH silently drop r[0].)")
    print()

    print("Relative-gap decomposition: the small -0.14pp is a NEAR-CANCELLATION")
    print("  portfolio base-offset error (chart - engine) = %s" % pct(c_p - e_p))
    print("  benchmark base-offset error (chart - engine) = %s" % pct(c_b - e_b))
    print("  their difference                             = %s" % pct((c_p - e_p) - (c_b - e_b)))
    print("  observed relative delta                      = %s" % pct((c_p - c_b) - (e_p - e_b)))
    print()

    print("The ALL boundary — what r[0] is worth")
    true_all = portfolioIndex[-1] / 100.0 - 1
    cur_all = engine_period_return(portfolioIndex, 0)
    print("  r[0] (return dated %s)                 = %s" % (DATES[0], pct(portfolioReturns[0])))
    print("  ALL as currently computed (503 returns)      = %s" % pct(cur_all))
    print("  ALL over all 504 returns from the 100 origin = %s" % pct(true_all))
    print("  difference                                   = %s" % pct(true_all - cur_all))
    print()

    print("PROPOSED CANONICAL CONVENTION (see ruling): base at index i-1,")
    print("i.e. the last close BEFORE the window, for every selector period.")
    for rng in ("1M", "3M", "6M", "1Y", "ALL"):
        i = slice_range(rng)
        base_i = i - 1 if i - 1 >= 0 else 0
        n_obs = (len(DATES) - i) if i > 0 else (len(DATES) - 1)
        first_ret_date = DATES[i] if i > 0 else DATES[1]
        print("  %-5s base idx %-4d base date %s  return obs=%d  first return dated %s  ret=%s"
              % (rng, base_i, DATES[base_i], n_obs, first_ret_date,
                 pct(engine_period_return(portfolioIndex, i)).strip()))
    print()
    print("Post-fix reconciliation: accessor returns index.slice(base_i), chart keeps")
    print("a[last]/a[0]-1 unchanged. Check that the two are then bit-identical:")
    for rng in ("1M", "3M", "6M", "1Y", "ALL"):
        i = slice_range(rng)
        base_i = i - 1 if i - 1 >= 0 else 0
        sl = portfolioIndex[base_i:]
        chart_after = sl[-1] / sl[0] - 1
        eng = engine_period_return(portfolioIndex, i)
        print("  %-5s chart_after=%.17g  engine=%.17g  identical=%s"
              % (rng, chart_after, eng, chart_after == eng))
    print()
    print("Post-fix relative callout vs engine metric.benchmarkRelative (1Y only,")
    print("since the engine publishes benchmarkRelative for the 1Y window alone):")
    i = slice_range("1Y")
    b_i = i - 1
    pa, pb = portfolioIndex[b_i:], benchmarkIndex[b_i:]
    rel_after = (pa[-1] / pa[0] - 1) - (pb[-1] / pb[0] - 1)
    print("  chart relDiff after fix = %.17g" % rel_after)
    print("  engine benchmarkRelative= %.17g" % (e_p - e_b))
    print("  identical               = %s" % (rel_after == (e_p - e_b)))
    print()

    # ---- adjacent observation, RAISED NOT RULED: MAX_DRAWDOWN's anchor ----
    def drawdown_series(idx):
        run_max, out = float("-inf"), []
        for v in idx:
            run_max = max(run_max, v)
            out.append(v / run_max - 1)
        return out

    dd_full = drawdown_series(portfolioIndex)
    md_as_implemented = min(dd_full[i1y:])          # js/data.js:410, running max over ALL history
    dd_window = drawdown_series(portfolioIndex[i1y:])
    md_window_only = min(dd_window)                  # peak-to-trough WITHIN the window
    peak_idx = max(range(i1y + 1), key=lambda k: portfolioIndex[k])
    print("ADJACENT, RAISED NOT RULED — MAX_DRAWDOWN's peak anchor (js/data.js:410)")
    print("  as implemented (running max over ALL history, restricted to window) = %s" % pct(md_as_implemented))
    print("  peak-to-trough WITHIN the 1Y window only                           = %s" % pct(md_window_only))
    print("  running max at window start was attained on %s (index %d), %s the window"
          % (DATES[peak_idx], peak_idx, "INSIDE" if peak_idx >= i1y else "OUTSIDE"))
    print("  the two conventions %s here."
          % ("DISAGREE" if abs(md_as_implemented - md_window_only) > 1e-12 else "coincide"))


if __name__ == "__main__":
    main()
