#!/usr/bin/env python3
"""
Independent replication of the CORRECTED designs/hg1-prototype-v2/js/data.js
(designer-19 HG1 round-4 analytical-truth pass).

Companion to hg1_round4_replication.py, which replicated the PRE-correction build. That
file is kept unchanged for provenance: the two together show what moved and why.

Verification tooling, not a golden fixture. See the header of the companion file.

Authored by quant-01 (role quant_analyst).
Run:  python3 methodology/verification/hg1_round4_postfix_replication.py
"""
import math
from datetime import date, timedelta

M32 = 0xFFFFFFFF


def to_int32(x):
    x &= M32
    return x - 0x100000000 if x & 0x80000000 else x


def imul(a, b):
    return to_int32((to_int32(a) * to_int32(b)) & M32)


class Mulberry32:
    def __init__(self, seed):
        self.seed = to_int32(seed)

    def __call__(self):
        s = to_int32(self.seed)
        s = to_int32(s + 0x6D2B79F5)
        self.seed = s
        u = s & M32
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


def downside_dev_N(rs, mar):
    """CORRECTED form now in data.js: denominator is the full sample N."""
    return math.sqrt(sum(min(r - mar, 0.0) ** 2 for r in rs) / len(rs))


def percentile(a, p):
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


# ------------------------------------------------- calendar (matches data.js DATES)
N = 504
DATES = []
d = date(2026, 9, 3)
while len(DATES) < N:
    if d.weekday() < 5:
        DATES.insert(0, d.isoformat())
    d -= timedelta(days=1)

# ------------------------------------------------- holdings -> derived sleeve weights
FXR = {"USD": 1.0, "HKD": 0.1282, "CNY": 0.1406}
# id, listingMarket, currency, qty, price, assetClass
H = [
    ("AAPL", "US", "USD", 120, 231.55, "Equity"),
    ("MSFT", "US", "USD", 60, 441.20, "Equity"),
    ("NVDA", "US", "USD", 40, 118.40, "Equity"),
    ("VOO", "US", "USD", 85, 512.30, "Equity Fund"),
    ("TLT", "US", "USD", 150, 88.10, "Fixed Income Fund"),
    ("0700.HK", "HK", "HKD", 800, 398.20, "Equity"),
    ("0941.HK", "HK", "HKD", 2000, 82.60, "Equity"),
    ("9988.HK", "HK", "HKD", 600, 91.40, "Equity"),
    ("3690.HK", "HK", "HKD", 300, 128.90, "Equity"),
    ("2800.HK", "HK", "HKD", 2000, 3.85, "Derivative"),
    ("600519.SS", "CN", "CNY", 20, 1542.00, "Equity"),
    ("300750.SZ", "CN", "CNY", 500, 221.80, "Equity"),
    ("601318.SS", "CN", "CNY", 300, 49.90, "Equity"),
]
mv = {h[0]: h[3] * h[4] * FXR[h[2]] for h in H}
TOTH = sum(mv.values())


def sleeve_key(h):
    if h[5] == "Fixed Income Fund":
        return "bond"
    return {"US": "us", "HK": "hk", "CN": "cn"}.get(h[1])


SMV = {"us": 0.0, "hk": 0.0, "cn": 0.0, "bond": 0.0}
for h in H:
    SMV[sleeve_key(h)] += mv[h[0]]
W = {k: SMV[k] / TOTH for k in SMV}

# ------------------------------------------------- generation (PRNG order unchanged)
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

portfolioReturnsLocal = [W["us"] * us[i] + W["hk"] * hk[i] + W["cn"] * cn[i] + W["bond"] * bond[i]
                         for i in range(N)]

fxHKD = [gaussian() * 0.0009 for _ in range(N)]
fxCNY = [gaussian() * 0.0022 - 0.00006 for _ in range(N)]

usBase, bondBase = us, bond
hkBase = [(1 + hk[i]) * (1 + fxHKD[i]) - 1 for i in range(N)]
cnBase = [(1 + cn[i]) * (1 + fxCNY[i]) - 1 for i in range(N)]

portfolioReturns = [W["us"] * usBase[i] + W["hk"] * hkBase[i] + W["cn"] * cnBase[i] + W["bond"] * bondBase[i]
                    for i in range(N)]

portfolioIndex = cumindex(portfolioReturns)
portfolioIndexLocal = cumindex(portfolioReturnsLocal)
benchmarkIndex = cumindex(benchmarkReturns)
pdd, bdd = drawdowns(portfolioIndex), drawdowns(benchmarkIndex)

i1y = N - 252
pr1y = portfolioReturns[i1y:]
pr1yLocal = portfolioReturnsLocal[i1y:]
br1y = benchmarkReturns[i1y:]

PERIOD_RETURN = portfolioIndex[-1] / portfolioIndex[i1y - 1] - 1
PERIOD_RETURN_LOCAL = portfolioIndexLocal[-1] / portfolioIndexLocal[i1y - 1] - 1
BENCH_RETURN = benchmarkIndex[-1] / benchmarkIndex[i1y - 1] - 1
ANNUAL_VOL = stdev(pr1y) * math.sqrt(252)
BENCH_VOL = stdev(br1y) * math.sqrt(252)
BETA = covariance(pr1y, br1y) / variance(br1y)
ALPHA_ANNUAL = (mean(pr1y) - RF_DAILY - BETA * (mean(br1y) - RF_DAILY)) * 252
SHARPE = (mean(pr1y) - RF_DAILY) / stdev(pr1y) * math.sqrt(252)
DD = downside_dev_N(pr1y, RF_DAILY)
SORTINO = (mean(pr1y) - RF_DAILY) / DD * math.sqrt(252)
DOWNSIDE_DAYS = len([r for r in pr1y if r < RF_DAILY])
MAXDD, BENCH_MAXDD = min(pdd[i1y:]), min(bdd[i1y:])
TE = stdev([pr1y[i] - br1y[i] for i in range(252)]) * math.sqrt(252)
VAR95 = percentile(pr1y, 0.05)
VAR_EXC = len([r for r in pr1y if r <= VAR95])
CORR_PB = pearson(pr1y, br1y)
FX_ATTR = PERIOD_RETURN - PERIOD_RETURN_LOCAL

print("== A. derived sleeve weights (must match exposure surfaces) ==")
for k in ("us", "hk", "cn", "bond"):
    print("  %-4s %.6f  (%.2f%%)" % (k, W[k], W[k] * 100))
print("  sum = %.10f" % sum(W.values()))

print()
print("== B. corrected headline values ==")
print("WINDOW  obs=%d  start=%s  end=%s   (price base date = %s)"
      % (len(pr1y), DATES[i1y], DATES[-1], DATES[i1y - 1]))
print("PERIOD_RETURN (base/FX-incl) %.6f  -> %+.2f%%" % (PERIOD_RETURN, PERIOD_RETURN * 100))
print("PERIOD_RETURN_LOCAL          %.6f  -> %+.2f%%" % (PERIOD_RETURN_LOCAL, PERIOD_RETURN_LOCAL * 100))
print("FX_ATTRIBUTION_PCT           %.6f  -> %+.3f%%" % (FX_ATTR, FX_ATTR * 100))
print("  identity local+fx-base = %.3e  (must be 0)" % (PERIOD_RETURN_LOCAL + FX_ATTR - PERIOD_RETURN))
print("BENCH_RETURN                 %.6f  -> %+.2f%%" % (BENCH_RETURN, BENCH_RETURN * 100))
print("BETA                         %.6f" % BETA)
print("ALPHA_ANNUAL                 %.6f  -> %+.2f%%" % (ALPHA_ANNUAL, ALPHA_ANNUAL * 100))
print("ANNUAL_VOL                   %.6f   BENCH_VOL %.6f" % (ANNUAL_VOL, BENCH_VOL))
print("SHARPE                       %.6f   TRACKING_ERROR %.6f" % (SHARPE, TE))
print("VAR95 (signed quantile)      %.6f   magnitude %.4f%%  exceedances %d/%d = %.2f%%"
      % (VAR95, -VAR95 * 100, VAR_EXC, len(pr1y), 100.0 * VAR_EXC / len(pr1y)))
print("MAXDD %.6f   BENCH_MAXDD %.6f" % (MAXDD, BENCH_MAXDD))
print("CORR(portfolio_base, bench)  %.6f" % CORR_PB)
print("vs.benchmark                 %.6f -> %+.2f%%"
      % (PERIOD_RETURN - BENCH_RETURN, (PERIOD_RETURN - BENCH_RETURN) * 100))
print("downside days %d of %d ; DD(/N) daily %.6f ann %.6f ; Sortino %.4f"
      % (DOWNSIDE_DAYS, len(pr1y), DD, DD * math.sqrt(252), SORTINO))

print()
print("== C. SML: line, vertical distance (concept 4) vs regression alpha (concept 3) ==")
SLOPE, INTERCEPT = BENCH_RETURN - RF_ANNUAL, RF_ANNUAL
implied = INTERCEPT + BETA * SLOPE
VD = PERIOD_RETURN - implied
print("line: intercept %.6f slope %.6f ; implied at beta %.4f = %+.6f" % (INTERCEPT, SLOPE, BETA, implied))
print("SML_VERTICAL_DISTANCE (concept 4) = %+.6f (%+.2f%%)" % (VD, VD * 100))
print("ALPHA_ANNUAL          (concept 3) = %+.6f (%+.2f%%)" % (ALPHA_ANNUAL, ALPHA_ANNUAL * 100))
print("difference = %+.6f (%.2f pp) -- must be reported as two quantities, not one"
      % (ALPHA_ANNUAL - VD, (ALPHA_ANNUAL - VD) * 100))
for nm, s in (("US", usBase), ("HK", hkBase), ("CN", cnBase)):
    b = pearson(s[i1y:], br1y) * (stdev(s[i1y:]) * math.sqrt(252)) / BENCH_VOL
    r = cumindex(s[i1y:])[-1] / 100 - 1
    print("  %s sleeve (base): beta %.4f  ret %+.4f  implied %+.4f  gap %+.4f"
          % (nm, b, r, INTERCEPT + b * SLOPE, r - (INTERCEPT + b * SLOPE)))

print()
print("== D. FX attribution detail (getFxAttributionDetail equivalents) ==")
hkLocal = cumindex(hk[i1y:])[-1] / 100 - 1
hkFx = cumindex(fxHKD[i1y:])[-1] / 100 - 1
cnLocal = cumindex(cn[i1y:])[-1] / 100 - 1
cnFx = cumindex(fxCNY[i1y:])[-1] / 100 - 1
for nm, loc, fx, w in (("hk", hkLocal, hkFx, W["hk"]), ("cn", cnLocal, cnFx, W["cn"])):
    base = (1 + loc) * (1 + fx) - 1
    print("  %s local %+.6f fx %+.6f interaction %+.8f (%+.2f bp) base %+.6f  weight %.4f"
          % (nm, loc, fx, loc * fx, loc * fx * 10000, base, w))
    print("     identity (1+l)(1+f)-1 - base = %.3e" % (((1 + loc) * (1 + fx) - 1) - base))
print("  portfolio: local %+.6f  fxEffect %+.6f  base %+.6f" % (PERIOD_RETURN_LOCAL, FX_ATTR, PERIOD_RETURN))
print("  NOTE the portfolio fxEffect is NOT the weighted sum of sleeve fx returns:")
print("       weighted sleeve fx sum = %+.6f  vs exact portfolio fx effect = %+.6f  (diff %.2f bp)"
      % (W["hk"] * hkFx + W["cn"] * cnFx, FX_ATTR,
         (W["hk"] * hkFx + W["cn"] * cnFx - FX_ATTR) * 10000))

print()
print("== E. contribution to risk on BASE sleeves — Euler exactness ==")
basemap = {"us": usBase, "hk": hkBase, "cn": cnBase, "bond": bondBase}
vols = {k: stdev(basemap[k][i1y:]) * math.sqrt(252) for k in W}
cors = {k: pearson(basemap[k][i1y:], pr1y) for k in W}
raw = {k: W[k] * vols[k] * cors[k] for k in W}
tot = sum(raw.values())
print("  sum w*sigma*rho = %.10f ; portfolio ann vol = %.10f ; ratio %.12f" % (tot, ANNUAL_VOL, tot / ANNUAL_VOL))
for k in ("us", "hk", "cn", "bond"):
    print("   %-4s weight %.4f  vol %.4f  corr %.4f  share %.4f" % (k, W[k], vols[k], cors[k], raw[k] / tot))
avail = (raw["us"] + raw["hk"] + raw["bond"]) / tot
print("  displayed AVAILABLE shares sum = %.4f ; withheld CN risk share = %.4f ; CN CAPITAL weight = %.4f"
      % (avail, raw["cn"] / tot, W["cn"]))
print("  ranked available: %s" % sorted([(k, raw[k] / tot) for k in ("us", "hk", "bond")],
                                        key=lambda x: -x[1]))

print()
print("== F. correlation matrix: local basis (as implemented) vs base basis ==")
labels = ["US", "HK", "CN", "BOND", "BENCH"]
loc_series = [us[i1y:], hk[i1y:], cn[i1y:], bond[i1y:], br1y]
base_series = [usBase[i1y:], hkBase[i1y:], cnBase[i1y:], bondBase[i1y:], br1y]
print("  LOCAL basis (what metric.correlation currently shows):")
for i, a in enumerate(loc_series):
    print("    %-5s %s" % (labels[i], " ".join("%5.2f" % pearson(a, b) for b in loc_series)))
print("  BASE (reporting-currency) basis:")
for i, a in enumerate(base_series):
    print("    %-5s %s" % (labels[i], " ".join("%5.2f" % pearson(a, b) for b in base_series)))
print("  max abs difference across the matrix = %.4f"
      % max(abs(pearson(loc_series[i], loc_series[j]) - pearson(base_series[i], base_series[j]))
            for i in range(5) for j in range(5)))
eq = [(0, 1), (0, 2), (1, 2)]
names = {(0, 1): "US/HK", (0, 2): "US/CN", (1, 2): "HK/CN"}
for basis, ser in (("local", loc_series), ("base", base_series)):
    ranked = sorted(eq, key=lambda p: -pearson(ser[p[0]], ser[p[1]]))
    print("  %-5s equity-pair ranking: %s" % (basis, " > ".join(
        "%s(%.3f)" % (names[p], pearson(ser[p[0]], ser[p[1]])) for p in ranked)))
print("  bonds: rho(HK,BOND) local %.3f base %.3f ; rho(CN,BOND) local %.3f base %.3f ; rho(HK,CN) local %.3f base %.3f"
      % (pearson(loc_series[1], loc_series[3]), pearson(base_series[1], base_series[3]),
         pearson(loc_series[2], loc_series[3]), pearson(base_series[2], base_series[3]),
         pearson(loc_series[1], loc_series[2]), pearson(base_series[1], base_series[2])))

print()
print("== G. claim strings that must now be derived — what the derivation should produce ==")
print("  beta %.4f -> '%s'" % (BETA, "moved LESS than the market" if BETA < 1 else "moved MORE"))
print("  vol  %.4f vs bench %.4f -> '%s'" % (ANNUAL_VOL, BENCH_VOL,
                                             "varied MORE" if ANNUAL_VOL > BENCH_VOL else "varied LESS"))
print("  drawdown %.4f vs bench %.4f -> '%s'" % (MAXDD, BENCH_MAXDD,
                                                 "DEEPER" if MAXDD < BENCH_MAXDD else "SHALLOWER"))
top5 = sum(v for _, v in sorted(mv.items(), key=lambda x: -x[1])[:5])
print("  top5 %.4f of holdings -> '%s'" % (top5 / TOTH, "majority" if top5 / TOTH > 0.5 else "not majority"))

print()
print("== I. estimator precision: are the DERIVED directional claims supportable? ==")
# OLS slope standard error: se(b) = sigma_resid / (sigma_bench * sqrt(n))
resid = [pr1y[i] - (mean(pr1y) + BETA * (br1y[i] - mean(br1y))) for i in range(252)]
sd_resid_d = math.sqrt(sum(r * r for r in resid) / (252 - 2))
se_beta = sd_resid_d / (stdev(br1y) * math.sqrt(252))
print("  BETA = %.6f ; residual daily sd = %.6f ; se(beta) = %.6f" % (BETA, sd_resid_d, se_beta))
print("  |beta - 1| = %.6f = %.3f standard errors" % (abs(BETA - 1), abs(BETA - 1) / se_beta))
print("  95%% CI for beta: [%.4f, %.4f]  -> 1.0 %s inside"
      % (BETA - 1.96 * se_beta, BETA + 1.96 * se_beta,
         "IS" if BETA - 1.96 * se_beta < 1 < BETA + 1.96 * se_beta else "is NOT"))
print("  => the claim 'moved LESS than the market' rests on a %.3f-sigma difference from 1.0"
      % (abs(BETA - 1) / se_beta))
print()
print("  other derived comparisons, for boundary proximity:")
print("   volatility   %.4f vs %.4f  gap %+.4f (%.1f%% relative) -- well separated"
      % (ANNUAL_VOL, BENCH_VOL, ANNUAL_VOL - BENCH_VOL, 100 * (ANNUAL_VOL / BENCH_VOL - 1)))
print("   max drawdown %.4f vs %.4f  gap %+.4f" % (MAXDD, BENCH_MAXDD, MAXDD - BENCH_MAXDD))
print("   risk contrib top two: US %.4f vs HK %.4f  gap %.4f (sentence names BOTH, so order-robust)"
      % (raw["us"] / tot, raw["hk"] / tot, raw["us"] / tot - raw["hk"] / tot))


def se_corr(r, n):
    return (1 - r * r) / math.sqrt(n - 1)


p1 = pearson(loc_series[0], loc_series[1])
p2 = pearson(loc_series[0], loc_series[2])
p3 = pearson(loc_series[1], loc_series[2])
print("   equity-pair correlations US/HK %.3f (se~%.3f), US/CN %.3f, HK/CN %.3f" %
      (p1, se_corr(p1, 252), p2, p3))
print("     strongest-vs-second gap %.3f = %.1f se ; second-vs-weakest gap %.3f = %.1f se"
      % (p1 - p2, (p1 - p2) / se_corr(p1, 252), p2 - p3, (p2 - p3) / se_corr(p2, 252)))

print()
print("== J. correlation band precision guard (verification section 5.2) ==")
BOUNDS = [0.80, 0.60, 0.35, 0.15]


def band(r):
    if r >= 0.80:
        return "almost identical"
    if r >= 0.60:
        return "strongly co-moving"
    if r >= 0.35:
        return "moderately co-moving"
    if r >= 0.15:
        return "weakly co-moving"
    return "largely independent"


def se_rho(r, n):
    return (1 - r * r) / math.sqrt(n - 1)


def nearest_boundary(r):
    return min(abs(r - b) for b in BOUNDS)


CPAIRS = [("US/HK", 0, 1), ("US/CN", 0, 2), ("HK/CN", 1, 2),
          ("HK/BOND", 1, 3), ("CN/BOND", 2, 3), ("US/BOND", 0, 3)]
for basis, ser in (("LOCAL (displayed)", loc_series), ("BASE (classification basis)", base_series)):
    print("  %s:" % basis)
    for nm, i, j in CPAIRS:
        r = pearson(ser[i], ser[j])
        s = se_rho(r, 252)
        dd = nearest_boundary(r)
        print("    %-8s rho=%.4f se=%.4f nearestBoundaryDist=%.4f = %.3f se -> %-10s [%s]"
              % (nm, r, s, dd, dd / s, "ASSERTABLE" if dd >= s else "rank-only", band(r)))

r_hkcn_base = pearson(base_series[1], base_series[2])
r_hkcn_loc = pearson(loc_series[1], loc_series[2])
print()
print("  HK/CN is the pair the product actually talks about:")
for nm, r in (("local", r_hkcn_loc), ("base", r_hkcn_base)):
    s, dd = se_rho(r, 252), nearest_boundary(r)
    print("    %-5s rho=%.6f se=%.6f dist=%.6f margin(dist-se)=%+.6f -> %s"
          % (nm, r, s, dd, dd - s, "ASSERTABLE" if dd >= s else "rank-only"))
print("  => the verdict FLIPS between bases; on the base basis it clears by %.6f in rho units"
      % (nearest_boundary(r_hkcn_base) - se_rho(r_hkcn_base, 252)))
print("     = %.2f%% of one standard error. At a 1.96-se guard, BOTH bases are rank-only."
      % (100 * (nearest_boundary(r_hkcn_base) - se_rho(r_hkcn_base, 252)) / se_rho(r_hkcn_base, 252)))

print()
print("== H. still-open items: unchanged figures ==")
CASH = [("USD", 18400.32), ("USD", 4200.00), ("HKD", 62500.00), ("CNY", 38000.00),
        ("USD", 12000.00), ("HKD", 15000.00), ("CNY", 9000.00)]
TOTC = sum(a * FXR[c] for c, a in CASH)
TPV = TOTH + TOTC
print("  total portfolio value %.2f (holdings %.2f + cash %.2f = %.2f%% cash)"
      % (TPV, TOTH, TOTC, 100 * TOTC / TPV))
gl = TPV * PERIOD_RETURN / (1 + PERIOD_RETURN)
print("  metric.pl.absolute = %.2f  -> implied start value %.2f" % (gl, TPV - gl))
print("  in-window contributions: CNY 800000 = $%.2f (2025-09-09), $3000, $5000  => total $%.2f"
      % (800000 * FXR["CNY"], 800000 * FXR["CNY"] + 8000))
print("  top5 %.4f of holdings vs %.4f of total incl. cash" % (top5 / TOTH, top5 / TPV))
hhi = sum((v / TOTH) ** 2 for v in mv.values())
print("  HHI %.4f  EffectiveN %.2f (holdings-only denominator, unchanged)" % (hhi, 1 / hhi))
