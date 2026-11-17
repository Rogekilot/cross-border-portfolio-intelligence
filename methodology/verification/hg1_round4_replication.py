#!/usr/bin/env python3
"""
Independent replication of designs/hg1-prototype-v2/js/data.js's synthetic generator.

PURPOSE. This is *verification tooling*, not a golden fixture. It re-implements the
prototype's PRNG and return-generation chain in a second language so that the numbers
the Analytics surface displays can be quantified and reasoned about without executing
the prototype's own code (no JS runtime is available in this environment, and reading a
value off the implementation is not evidence about the method anyway).

WHAT IT IS NOT. Nothing here may be promoted to methodology/fixtures/. A golden fixture
states expected values derived by hand or from an independent authority; this file
derives values from a restatement of the same generator, which proves only that the two
restatements agree. It is used here to answer questions of the form "how large is the
term the prototype drops?", which is a legitimate use.

Authored by quant-01 (role quant_analyst) for HG1 round 4 methodology findings.
Run:  python3 methodology/verification/hg1_round4_replication.py
"""
import math

M32 = 0xFFFFFFFF


def to_int32(x):
    x &= M32
    return x - 0x100000000 if x & 0x80000000 else x


def imul(a, b):
    return to_int32((to_int32(a) * to_int32(b)) & M32)


class Mulberry32:
    """Bit-exact restatement of data.js:22-30 mulberry32."""

    def __init__(self, seed):
        self.seed = to_int32(seed)

    def __call__(self):
        s = to_int32(self.seed)
        s = to_int32(s + 0x6D2B79F5)
        self.seed = s
        u = s & M32                      # ToUint32, for JS >>>
        t = imul(to_int32(s ^ (u >> 15)), to_int32(1 | s))
        tu = t & M32
        t = to_int32(to_int32(t + imul(to_int32(t ^ (tu >> 7)), to_int32(61 | t))) ^ t)
        tu = t & M32
        return ((tu ^ (tu >> 14)) & M32) / 4294967296.0


rand = Mulberry32(20260904)


def gaussian():
    u = max(rand(), 1e-9)
    v = max(rand(), 1e-9)
    return math.sqrt(-2 * math.log(u)) * math.cos(2 * math.pi * v)


def mean(a):
    return sum(a) / len(a)


def variance(a):
    m = mean(a)
    return mean([(x - m) ** 2 for x in a])


def stdev(a):
    return math.sqrt(variance(a))


def covariance(a, b):
    ma, mb = mean(a), mean(b)
    return sum((a[i] - ma) * (b[i] - mb) for i in range(len(a))) / len(a)


def pearson(a, b):
    sa, sb = stdev(a), stdev(b)
    return 0 if sa == 0 or sb == 0 else covariance(a, b) / (sa * sb)


def downside_dev_code(rs, mar):
    """data.js:52-56 — denominator is the COUNT OF DOWNSIDE OBSERVATIONS."""
    downs = [(r - mar) ** 2 for r in rs if r < mar]
    return 0 if not downs else math.sqrt(mean(downs))


def downside_dev_standard(rs, mar):
    """Sortino/Satchell target semideviation — denominator is the FULL SAMPLE N."""
    return math.sqrt(mean([min(r - mar, 0.0) ** 2 for r in rs]))


def percentile(a, p):
    """data.js:58-62 — floor index, no interpolation."""
    s = sorted(a)
    return s[int(math.floor(p * (len(s) - 1)))]


def cumindex(rs, base=100.0):
    out, v = [], base
    for r in rs:
        v *= (1 + r)
        out.append(v)
    return out


def drawdowns(idx):
    rm, out = -1e18, []
    for v in idx:
        rm = max(rm, v)
        out.append(v / rm - 1)
    return out


# ---------------------------------------------------------------- generation
N = 504
RF_ANNUAL = 0.045
RF_DAILY = RF_ANNUAL / 252

marketFactor = [gaussian() * 0.0075 + 0.00030 for _ in range(N)]


def sleeve(loading, idio, drift=0.0):
    return [loading * marketFactor[i] + gaussian() * idio + drift for i in range(N)]


benchmarkReturns = marketFactor[:]
us = sleeve(1.05, 0.0065, 0.00005)
hk = sleeve(1.15, 0.0110, -0.00005)
cn = sleeve(0.85, 0.0140, -0.00015)
bond = sleeve(0.15, 0.0035, 0.00002)

W = {"us": 0.40, "hk": 0.30, "cn": 0.20, "bond": 0.10}
portfolioReturns = [W["us"] * us[i] + W["hk"] * hk[i] + W["cn"] * cn[i] + W["bond"] * bond[i]
                    for i in range(N)]

fxHKD = [gaussian() * 0.0009 for _ in range(N)]
fxCNY = [gaussian() * 0.0022 - 0.00006 for _ in range(N)]

portfolioIndex = cumindex(portfolioReturns)
benchmarkIndex = cumindex(benchmarkReturns)
pdd, bdd = drawdowns(portfolioIndex), drawdowns(benchmarkIndex)

i1y = N - 252
pr1y, br1y = portfolioReturns[i1y:], benchmarkReturns[i1y:]

PERIOD_RETURN = portfolioIndex[-1] / portfolioIndex[i1y - 1] - 1
BENCH_RETURN = benchmarkIndex[-1] / benchmarkIndex[i1y - 1] - 1
ANNUAL_VOL = stdev(pr1y) * math.sqrt(252)
BENCH_VOL = stdev(br1y) * math.sqrt(252)
BETA = covariance(pr1y, br1y) / variance(br1y)
ALPHA_ANNUAL = (mean(pr1y) - RF_DAILY - BETA * (mean(br1y) - RF_DAILY)) * 252
SHARPE = (mean(pr1y) - RF_DAILY) / stdev(pr1y) * math.sqrt(252)
MAXDD, BENCH_MAXDD = min(pdd[i1y:]), min(bdd[i1y:])
TE = stdev([pr1y[i] - br1y[i] for i in range(252)]) * math.sqrt(252)
VAR95 = percentile(pr1y, 0.05)

print("== A. headline values (cross-check against the rendered surface) ==")
print("PERIOD_RETURN   %.6f  -> %+.1f%%" % (PERIOD_RETURN, PERIOD_RETURN * 100))
print("BENCH_RETURN    %.6f  -> %+.2f%%" % (BENCH_RETURN, BENCH_RETURN * 100))
print("BETA            %.6f" % BETA)
print("ALPHA_ANNUAL    %.6f  -> %+.1f%%" % (ALPHA_ANNUAL, ALPHA_ANNUAL * 100))
print("ANNUAL_VOL      %.6f   BENCH_VOL %.6f" % (ANNUAL_VOL, BENCH_VOL))
print("SHARPE          %.6f   TRACKING_ERROR %.6f" % (SHARPE, TE))
print("VAR95           %.6f  -> %+.1f%%" % (VAR95, VAR95 * 100))
print("MAXDD           %.6f   BENCH_MAXDD %.6f" % (MAXDD, BENCH_MAXDD))
print("vs.benchmark    %.6f  -> %+.2f%%" % (PERIOD_RETURN - BENCH_RETURN,
                                            (PERIOD_RETURN - BENCH_RETURN) * 100))

print()
print("== B. Q1/Q2 — estimation bases and the two distinct 'alpha' quantities ==")
print("beta/alpha estimator sample: %d DAILY observations (= %.1f months)"
      % (len(pr1y), len(pr1y) / 21.0))
print("full generated dataset:      %d DAILY observations (= %.1f months)" % (N, N / 21.0))
print("mean(pr1y) daily %.8f ; arithmetic x252 = %+.6f (vs geometric %+.6f)"
      % (mean(pr1y), mean(pr1y) * 252, PERIOD_RETURN))
print("mean(br1y) daily %.8f ; arithmetic x252 = %+.6f (vs geometric %+.6f)"
      % (mean(br1y), mean(br1y) * 252, BENCH_RETURN))
SLOPE, INTERCEPT = BENCH_RETURN - RF_ANNUAL, RF_ANNUAL
implied = INTERCEPT + BETA * SLOPE
print("SML_LINE intercept=%.6f slope=%.6f  (geometric-return space)" % (INTERCEPT, SLOPE))
print("CAPM-implied return at beta %.4f = %+.6f" % (BETA, implied))
print("(1) vertical gap on the chart  = %+.6f (%+.2f%%)"
      % (PERIOD_RETURN - implied, (PERIOD_RETURN - implied) * 100))
print("(2) regression Jensen alpha    = %+.6f (%+.2f%%)" % (ALPHA_ANNUAL, ALPHA_ANNUAL * 100))
print("    (2)-(1) = %+.6f  (%.2f pp) -- the chart annotation and the cell disagree"
      % (ALPHA_ANNUAL - (PERIOD_RETURN - implied),
         (ALPHA_ANNUAL - (PERIOD_RETURN - implied)) * 100))
for nm, s in (("US", us), ("HK", hk), ("CN", cn)):
    b = pearson(s[i1y:], br1y) * (stdev(s[i1y:]) * math.sqrt(252)) / BENCH_VOL
    r = cumindex(s[i1y:])[-1] / 100 - 1
    print("  %s sleeve point: beta %.4f  ret %+.4f  implied %+.4f  gap %+.4f"
          % (nm, b, r, INTERCEPT + b * SLOPE, r - (INTERCEPT + b * SLOPE)))

print()
print("== C. Q3 — VaR estimator ==")
srt = sorted(pr1y)
k = int(math.floor(0.05 * 251))
h = 0.05 * (252 - 1)
lo = int(math.floor(h))
print("index = floor(0.05*(252-1)) = %d -> the %d-th smallest of 252" % (k, k + 1))
print("neighbours srt[11]=%.6f srt[12]=%.6f srt[13]=%.6f" % (srt[11], srt[12], srt[13]))
print("observations <= VAR95: %d  (%.2f%% of the sample)"
      % (len([r for r in pr1y if r <= VAR95]), 100.0 * len([r for r in pr1y if r <= VAR95]) / 252))
print("linear-interpolated (type-7) 5%% quantile = %.6f  (difference %.6f)"
      % (srt[lo] + (h - lo) * (srt[lo + 1] - srt[lo]),
         (srt[lo] + (h - lo) * (srt[lo + 1] - srt[lo])) - VAR95))
print("expected shortfall (mean of the %d worst) = %.6f" % (k + 1, mean(srt[:k + 1])))

print()
print("== D. Q4 — FX decomposition and the interaction term ==")
hkLocal = cumindex(hk[i1y:])[-1] / 100 - 1
hkFx = cumindex(fxHKD[i1y:])[-1] / 100 - 1
cnLocal = cumindex(cn[i1y:])[-1] / 100 - 1
cnFx = cumindex(fxCNY[i1y:])[-1] / 100 - 1
FX_ATTR = W["hk"] * hkFx + W["cn"] * cnFx
print("hkLocal %+.6f  hkFx %+.6f" % (hkLocal, hkFx))
print("cnLocal %+.6f  cnFx %+.6f" % (cnLocal, cnFx))
print("FX_ATTRIBUTION_PCT = .30*hkFx + .20*cnFx = %+.6f (%+.3f%%)" % (FX_ATTR, FX_ATTR * 100))
for nm, loc, fx, w in (("HK", hkLocal, hkFx, W["hk"]), ("CN", cnLocal, cnFx, W["cn"])):
    print("%s  arith %+.6f | geometric %+.6f | interaction local*fx %+.8f (%.4f pp) | weighted %+.8f (%.4f pp)"
          % (nm, loc + fx, (1 + loc) * (1 + fx) - 1, loc * fx, loc * fx * 100,
             w * loc * fx, w * loc * fx * 100))
tot_inter = W["hk"] * hkLocal * hkFx + W["cn"] * cnLocal * cnFx
print("TOTAL weighted interaction term = %+.8f  (%.4f pp)" % (tot_inter, tot_inter * 100))
print("prototype local leg = PERIOD_RETURN - FX_ATTR = %+.6f (%+.2f%%)"
      % (PERIOD_RETURN - FX_ATTR, (PERIOD_RETURN - FX_ATTR) * 100))
rc = [W["us"] * us[i] + W["bond"] * bond[i]
      + W["hk"] * ((1 + hk[i]) * (1 + fxHKD[i]) - 1)
      + W["cn"] * ((1 + cn[i]) * (1 + fxCNY[i]) - 1) for i in range(N)]
rcidx = cumindex(rc)
RC = rcidx[-1] / rcidx[i1y - 1] - 1
print("an actually FX-translated reporting-currency return would be %+.6f (%+.2f%%)" % (RC, RC * 100))
print("difference vs the PERIOD_RETURN on screen = %+.6f (%.2f pp)"
      % (RC - PERIOD_RETURN, (RC - PERIOD_RETURN) * 100))

print()
print("== E. Sortino denominator ==")
dc, ds = downside_dev_code(pr1y, RF_DAILY), downside_dev_standard(pr1y, RF_DAILY)
nd = len([r for r in pr1y if r < RF_DAILY])
print("downside observations below daily rf: %d of %d" % (nd, len(pr1y)))
print("data.js downside deviation (/n_down) %.6f -> annualized %.6f" % (dc, dc * math.sqrt(252)))
print("standard target semideviation (/N)   %.6f -> annualized %.6f" % (ds, ds * math.sqrt(252)))
print("Sortino with data.js DD = %.4f ; with standard DD = %.4f ; ratio %.4f"
      % ((mean(pr1y) - RF_DAILY) / dc * math.sqrt(252),
         (mean(pr1y) - RF_DAILY) / ds * math.sqrt(252), ds and dc / ds))

print()
print("== F. risk contribution: is it really an approximation? ==")
vols = {k2: stdev({"us": us, "hk": hk, "cn": cn, "bond": bond}[k2][i1y:]) * math.sqrt(252) for k2 in W}
cors = {k2: pearson({"us": us, "hk": hk, "cn": cn, "bond": bond}[k2][i1y:], pr1y) for k2 in W}
raw = {k2: W[k2] * vols[k2] * cors[k2] for k2 in W}
tot = sum(raw.values())
print("sum_i w_i*sigma_i*rho_iP = %.8f ; portfolio annualized vol = %.8f ; ratio %.10f"
      % (tot, ANNUAL_VOL, tot / ANNUAL_VOL))
for k2 in ("us", "hk", "cn", "bond"):
    print("  %-4s w=%.2f vol=%.4f corr=%.4f share=%.4f" % (k2, W[k2], vols[k2], cors[k2], raw[k2] / tot))
print("three displayed shares sum to %.4f ; withheld CN share = %.4f"
      % ((raw["us"] + raw["hk"] + raw["bond"]) / tot, raw["cn"] / tot))

print()
print("== G. stated sleeve weights vs actual holdings weights ==")
FXR = {"USD": 1.0, "HKD": 0.1282, "CNY": 0.1406}
H = [("AAPL", "US", "USD", 120, 231.55), ("MSFT", "US", "USD", 60, 441.20),
     ("NVDA", "US", "USD", 40, 118.40), ("VOO", "US", "USD", 85, 512.30),
     ("TLT", "US", "USD", 150, 88.10), ("0700.HK", "HK", "HKD", 800, 398.20),
     ("0941.HK", "HK", "HKD", 2000, 82.60), ("9988.HK", "HK", "HKD", 600, 91.40),
     ("3690.HK", "HK", "HKD", 300, 128.90), ("2800.HK", "HK", "HKD", 2000, 3.85),
     ("600519.SS", "CN", "CNY", 20, 1542.00), ("300750.SZ", "CN", "CNY", 500, 221.80),
     ("601318.SS", "CN", "CNY", 300, 49.90)]
mv = {h[0]: h[3] * h[4] * FXR[h[2]] for h in H}
TOTH = sum(mv.values())
bym = {}
for h in H:
    bym[h[1]] = bym.get(h[1], 0) + mv[h[0]]
print("total holdings USD %.2f" % TOTH)
for k2, v in sorted(bym.items(), key=lambda x: -x[1]):
    print("  %s market weight %.4f" % (k2, v / TOTH))
print("  US ex-TLT %.4f (SLEEVE_WEIGHTS.us 0.40) ; TLT %.4f (SLEEVE_WEIGHTS.bond 0.10)"
      % ((bym["US"] - mv["TLT"]) / TOTH, mv["TLT"] / TOTH))
CASH = [("USD", 18400.32), ("USD", 4200.00), ("HKD", 62500.00), ("CNY", 38000.00),
        ("USD", 12000.00), ("HKD", 15000.00), ("CNY", 9000.00)]
TOTC = sum(a * FXR[c] for c, a in CASH)
srtmv = sorted(mv.items(), key=lambda x: -x[1])
hhi = sum((v / TOTH) ** 2 for v in mv.values())
print("cash USD %.2f = %.2f%% of total portfolio value %.2f"
      % (TOTC, 100 * TOTC / (TOTH + TOTC), TOTH + TOTC))
print("top5 %s -> %.4f of HOLDINGS (%.4f of TOTAL incl. cash)"
      % ([k2 for k2, _ in srtmv[:5]], sum(v for _, v in srtmv[:5]) / TOTH,
         sum(v for _, v in srtmv[:5]) / (TOTH + TOTC)))
print("HHI %.4f  EffectiveN %.2f  (holdings-only denominator)" % (hhi, 1 / hhi))
print("2800.HK (UNSUPPORTED_ASSET for risk metrics) weight of holdings = %.4f" % (mv["2800.HK"] / TOTH))

print()
print("== H. max drawdown: does the 1Y figure use a peak from inside the window? ==")
print("data.js MAXDD (peak carried in from the full 504-day history) = %.6f" % MAXDD)
win_dd = drawdowns(portfolioIndex[i1y:])
print("peak reset at window start (true trailing-1Y max drawdown)    = %.6f" % min(win_dd))
print("difference = %.6f (%.2f pp)" % (MAXDD - min(win_dd), (MAXDD - min(win_dd)) * 100))
bwin_dd = drawdowns(benchmarkIndex[i1y:])
print("benchmark: data.js %.6f vs window-reset %.6f" % (BENCH_MAXDD, min(bwin_dd)))
print("data.js comparison says portfolio %s than benchmark; window-reset says %s"
      % ("deeper" if MAXDD < BENCH_MAXDD else "shallower",
         "deeper" if min(win_dd) < min(bwin_dd) else "shallower"))

print()
print("== J. hardcoded conclusion strings vs the values they sit beside ==")
labels = ["US", "HK", "CN", "BOND", "BENCH"]
series = [us[i1y:], hk[i1y:], cn[i1y:], bond[i1y:], br1y]
print("  1Y daily correlation matrix:")
for i2, a in enumerate(series):
    print("    %-5s %s" % (labels[i2], " ".join("%5.2f" % pearson(a, b) for b in series)))
print('  metric.beta   says "moved MORE than the market"      -> beta = %.4f  => %s'
      % (BETA, "TRUE" if BETA > 1 else "FALSE, beta < 1"))
print('  insight.drawdown.deeper says portfolio DEEPER than benchmark -> %.4f vs %.4f => %s'
      % (MAXDD, BENCH_MAXDD, "TRUE" if MAXDD < BENCH_MAXDD else "FALSE, portfolio is SHALLOWER"))
print('  insight.correlation.hkCluster says HK/CN "high correlation"  -> rho(HK,CN) = %.3f'
      % pearson(hk[i1y:], cn[i1y:]))
print('  metric.contributionToRisk says HK and CN "contribute the most" -> shares:')
_v = {"us": stdev(us[i1y:]), "hk": stdev(hk[i1y:]), "cn": stdev(cn[i1y:]), "bond": stdev(bond[i1y:])}
_c = {"us": pearson(us[i1y:], pr1y), "hk": pearson(hk[i1y:], pr1y),
      "cn": pearson(cn[i1y:], pr1y), "bond": pearson(bond[i1y:], pr1y)}
_r = {k2: W[k2] * _v[k2] * _c[k2] for k2 in W}
_t = sum(_r.values())
print("      " + "  ".join("%s %.1f%%" % (k2.upper(), 100 * _r[k2] / _t) for k2 in ("us", "hk", "cn", "bond")))
print('  metric.volatility says portfolio varied MORE than benchmark -> %.4f vs %.4f => %s'
      % (ANNUAL_VOL, BENCH_VOL, "TRUE" if ANNUAL_VOL > BENCH_VOL else "FALSE"))
print('  metric.sortino says "fewer than minimum downside observations" -> %d of 252 are downside'
      % len([r for r in pr1y if r < RF_DAILY]))

print()
print("== I. how large is a local x fx cross term at realistic cross-border magnitudes? ==")
for loc, fx in ((0.10, 0.02), (0.20, 0.05), (0.30, 0.08), (-0.25, 0.10), (0.15, -0.07)):
    print("  local %+6.1f%% x fx %+5.1f%%  -> cross term %+7.2f bp   (arith %+.4f vs geometric %+.4f)"
          % (loc * 100, fx * 100, loc * fx * 10000, loc + fx, (1 + loc) * (1 + fx) - 1))
