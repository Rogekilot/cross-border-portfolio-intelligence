"""Independent calculator for cp3_golden part 1 (valuation, TWR, annualization).

Author: quant-analyst, 2026-10-01. Convention set: performance/1.1, market-data/1.8,
ledger-replay/1.3.

This is a CALCULATOR for the hand derivation in CP3_GOLDEN_PART1_DERIVATION.md. It is not an
engine and it reads no engine output:

- it imports nothing from src/ (stdlib only: fractions, decimal);
- the holdings at each date are typed in by hand from the ledger events (the derivation document
  lists the events behind each line), not replayed;
- prices and FX are the fixture's synthetic step series, typed in by hand.

A reviewer re-runs it with `python3 methodology/fixtures/cp3_golden/derivation/cp3_part1_calculator.py`
and compares its printout with the fixture JSON. Exact values are printed as reduced fractions,
presented values per performance/1.1 Ruling 2.2 (ROUND_HALF_UP to the minor unit; returns to 1e-12).
"""

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction as F

# ---- FX (performance/1.1 notation X(c->R)); ECB EUR quotes, synthetic --------------------------
# Period A: fixings 2025-01-02 .. 2025-03-31.  Period B: fixings from 2025-04-01.
ECB_A = {"USD": F("1.0400"), "HKD": F("8.1120"), "CNY": F("7.4880")}
ECB_B = {"USD": F("1.0880"), "HKD": F("8.5000"), "CNY": F("7.8880")}


def X(ecb, c, r):
    """Units of r per one unit of c: x_r / x_c (market-data Ruling 1.3); X(r->r) = 1."""
    if c == r:
        return F(1)
    return ecb[r] / ecb[c]


def present_money(x):
    if x is None:
        return None
    with localcontext() as ctx:
        ctx.prec = 200
        d = Decimal(x.numerator) / Decimal(x.denominator)
        return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def present_ratio(x):
    with localcontext() as ctx:
        ctx.prec = 200
        d = Decimal(x.numerator) / Decimal(x.denominator)
        return str(d.quantize(Decimal("1e-12"), rounding=ROUND_HALF_UP))


def frac(x):
    return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)


def value(items, ecb, r):
    """items: list of (native amount, currency). Returns the exact total in r."""
    return sum((F(a) * X(ecb, c, r) for a, c in items), F(0))


def show(label, x, kind="money"):
    p = present_money(x) if kind == "money" else present_ratio(x)
    print(f"{label:58s} exact {frac(x):>32s}  presented {p}")


# ================================ P1 (USD) =====================================================
print("=== P1 (reporting USD) ===")
R = "USD"
# Holdings typed from the ledger (see derivation §3). Prices: AAPL 150 (to 01-31), 37.50 (02-03),
# 45 (03-03), 50 (06-16); 0700 35 (01-02), 36 (04-01), 37 (06-02), 38 (07-15);
# MSFT 400 (01-02), 420 (06-02), 430 (06-10).
P1 = {
    "2025-01-01": ([], ECB_A),
    "2025-01-02": ([(10000, "USD")], ECB_A),
    "2025-01-05": ([(10000, "USD")], ECB_A),
    "2025-01-06": ([(2500, "USD"), (50 * 150, "USD"), (20000, "HKD")], ECB_A),
    "2025-01-31": ([(2500, "USD"), (50 * 150, "USD"), (2500, "HKD"), (500 * 35, "HKD")], ECB_A),
    "2025-03-09": ([(3750, "USD"), (150 * 45, "USD"), (1000, "USD"), (500 * 35, "HKD"), (2500, "HKD")], ECB_A),
    "2025-03-10": ([(3750, "USD"), (150 * 45, "USD"), (10 * 400, "USD"), (1000, "USD"),
                    (500 * 35, "HKD"), (2500, "HKD")], ECB_A),
    "2025-03-31": ([(3750, "USD"), (150 * 45, "USD"), (10 * 400, "USD"), (1000, "USD"),
                    (500 * 35, "HKD"), (2500, "HKD")], ECB_A),
    "2025-04-02": ([(2748, "USD"), (750, "HKD"), (200 * 36, "HKD"), (150 * 45, "USD"), (10 * 400, "USD"),
                    (1000, "USD"), (500 * 36, "HKD"), (2500, "HKD")], ECB_B),
    "2025-05-07": ([(2748, "USD"), (750, "HKD"), (200 * 36, "HKD"), (150 * 45, "USD"), (10 * 400, "USD"),
                    (-1000, "USD"), (5 * 400, "USD"), (500 * 36, "HKD"), (2500, "HKD")], ECB_B),
    "2025-05-08": ([(2748, "USD"), (750, "HKD"), (200 * 36, "HKD"), (150 * 45, "USD"), (10 * 400, "USD"),
                    (0, "USD"), (5 * 400, "USD"), (500 * 36, "HKD"), (2500, "HKD")], ECB_B),
    "2025-06-01": ([(2748, "USD"), (750, "HKD"), (200 * 36, "HKD"), (150 * 45, "USD"), (10 * 400, "USD"),
                    (F("-3.50"), "USD"), (5 * 400, "USD"), (500 * 36, "HKD"), (2500, "HKD")], ECB_B),
    "2025-06-02": ([(2748, "USD"), (750, "HKD"), (200 * 37, "HKD"), (150 * 45, "USD"), (10 * 420, "USD"),
                    (F("4996.50"), "USD"), (5 * 420, "USD"), (500 * 37, "HKD"), (2500, "HKD")], ECB_B),
    "2025-06-30": ([(4748, "USD"), (750, "HKD"), (200 * 37, "HKD"), (10 * 430, "USD"),
                    (F("4616.50"), "USD"), (6 * 430, "USD"), (110 * 50, "USD"),
                    (500 * 37, "HKD"), (2500, "HKD")], ECB_B),
    "2026-01-31": ([(4748, "USD"), (750, "HKD"), (200 * 38, "HKD"), (10 * 430, "USD"),
                    (F("4616.50"), "USD"), (6 * 430, "USD"), (110 * 50, "USD"),
                    (500 * 38, "HKD"), (2500, "HKD")], ECB_B),
}
V = {d: value(items, ecb, R) for d, (items, ecb) in P1.items()}
for d in sorted(V):
    show(f"V({d})", V[d])

# Flows (Ruling 4.1/4.2): cash inflows BOD; in-kind inflows EOD at the close.
IC_0102 = F(10000)
IC_0106 = F(20000) * X(ECB_A, "HKD", "USD")
IK_0310 = F(10 * 400)
IC_0508 = F(1000)
IC_0602 = F(5000)
show("I^C 2025-01-06 (20,000 HKD)", IC_0106)

# Segment form (Ruling 5.2). Days with V_{D-1} and V_D both listed.
f_0102 = V["2025-01-02"] / (V["2025-01-01"] + IC_0102)
f_0106 = V["2025-01-06"] / (V["2025-01-05"] + IC_0106)
run_0107_0309 = V["2025-03-09"] / V["2025-01-06"]
f_0310 = (V["2025-03-10"] - IK_0310) / V["2025-03-09"]
run_0311_0507 = V["2025-05-07"] / V["2025-03-10"]
f_0508 = V["2025-05-08"] / (V["2025-05-07"] + IC_0508)
run_0509_0601 = V["2025-06-01"] / V["2025-05-08"]
f_0602 = V["2025-06-02"] / (V["2025-06-01"] + IC_0602)
run_0603_0630 = V["2025-06-30"] / V["2025-06-02"]
for n, x in [("f 01-02", f_0102), ("f 01-06", f_0106), ("run 01-07..03-09", run_0107_0309),
             ("f 03-10", f_0310), ("run 03-11..05-07", run_0311_0507), ("f 05-08", f_0508),
             ("run 05-09..06-01", run_0509_0601), ("f 06-02", f_0602), ("run 06-03..06-30", run_0603_0630)]:
    print(f"   factor {n:22s} {frac(x)}")

twr_si = f_0102 * f_0106 * run_0107_0309 * f_0310 * run_0311_0507 * f_0508 * run_0509_0601 * f_0602 * run_0603_0630 - 1
show("TWR SI (2025-01-01, 2025-06-30]", twr_si, "ratio")
G_si = V["2025-06-30"] - V["2025-01-01"] - (IC_0102 + IC_0106 + IK_0310 + IC_0508 + IC_0602)
show("G SI (2025-01-01, 2025-06-30]", G_si)

twr_3m = (V["2025-05-07"] / V["2025-03-31"]) * f_0508 * run_0509_0601 * f_0602 * run_0603_0630 - 1
show("TWR 3M (2025-03-31, 2025-06-30]", twr_3m, "ratio")
G_3m = V["2025-06-30"] - V["2025-03-31"] - (IC_0508 + IC_0602)
show("G 3M (2025-03-31, 2025-06-30]", G_3m)

run_0701_260131 = V["2026-01-31"] / V["2025-06-30"]
twr_1y = (V["2025-03-09"] / V["2025-01-31"]) * f_0310 * run_0311_0507 * f_0508 * run_0509_0601 * f_0602 \
    * run_0603_0630 * run_0701_260131 - 1
show("TWR 1Y (2025-01-31, 2026-01-31]", twr_1y, "ratio")
twr_si2 = (twr_si + 1) * run_0701_260131 - 1
show("TWR SI (2025-01-01, 2026-01-31]", twr_si2, "ratio")
G_si2 = V["2026-01-31"] - (IC_0102 + IC_0106 + IK_0310 + IC_0508 + IC_0602)
show("G SI (2025-01-01, 2026-01-31]", G_si2)

Y = F(12, 12) + F(30, 365)
print(f"   Y(2025-01-01, 2026-01-31) = {frac(Y)}")
with localcontext() as ctx:
    ctx.prec = 60
    ctx.rounding = ROUND_HALF_EVEN
    g = Decimal((twr_si2 + 1).numerator) / Decimal((twr_si2 + 1).denominator)
    ann = (g.ln() * Decimal(Y.denominator) / Decimal(Y.numerator)).exp() - 1
    print(f"   annualized SI = {ann}  presented {ann.quantize(Decimal('1e-12'), rounding=ROUND_HALF_UP)}")
# Certified cross-check: ann_hi/lo bracket by integer bisection on (1+R)^(73/79)
lo, hi = F(1), F(2)
target = (twr_si2 + 1) ** 73  # (1+a)^79 = (1+R)^73
for _ in range(200):
    mid = (lo + hi) / 2
    if mid ** 79 <= target:
        lo = mid
    else:
        hi = mid
print(f"   certified bracket width {float(hi - lo):.3e}; lo-1 = {present_ratio(lo - 1)}, hi-1 = {present_ratio(hi - 1)}")

# Stale-share / presentation checks for P1 components at 03-09
show("P1 03-09 holding A2 0700 reporting (17,500 HKD)", F(17500) * X(ECB_A, "HKD", "USD"))
show("P1 03-09 cash A2 HKD reporting (2,500 HKD)", F(2500) * X(ECB_A, "HKD", "USD"))
show("P1 01-06 cash A2 HKD reporting (20,000 HKD)", F(20000) * X(ECB_A, "HKD", "USD"))

# ================================ P2 (HKD, snapshot) ===========================================
print("=== P2 (reporting HKD) ===")
V2 = {"2025-06-30": F(500 * 37 + 3000), "2025-07-02": F(300 * 37 + 10400), "2025-07-31": F(300 * 38 + 10400)}
for d in sorted(V2):
    show(f"V({d})", V2[d])
show("TWR (2025-06-30, 2025-07-31]", V2["2025-07-31"] / V2["2025-06-30"] - 1, "ratio")
show("G (2025-06-30, 2025-07-31]", V2["2025-07-31"] - V2["2025-06-30"])

# ================================ P3 (CNY) =====================================================
print("=== P3 (reporting CNY) ===")
R = "CNY"
# SYNA: 10.00 (03-03), 10.50 (03-04), gap 03-17..03-19, 11.00 (03-20). 0700: 35 (to 03-31).
P3 = {
    "2025-03-02": [],
    "2025-03-03": [(80000, "CNY"), (2000 * 10, "CNY")],
    "2025-03-04": [(47600, "CNY"), (F("2000") * F("10.50"), "CNY"), (1000 * 35, "HKD")],
    "2025-03-05": [(47600, "CNY"), (F("2000") * F("10.50"), "CNY"), (1000 * 35, "HKD"), (5000, "USD"), (10000, "HKD")],
    "2025-03-17": [(47600, "CNY"), (F("2000") * F("10.50"), "CNY"), (1000 * 35, "HKD"), (5000, "USD"), (10000, "HKD")],
    "2025-03-19": [(47600, "CNY"), (F("2000") * F("10.50"), "CNY"), (1000 * 35, "HKD"), (5000, "USD"), (10000, "HKD")],
    "2025-03-20": [(47600, "CNY"), (2000 * 11, "CNY"), (1000 * 35, "HKD"), (5000, "USD"), (10000, "HKD")],
}
V3 = {d: value(items, ECB_A, R) for d, items in P3.items()}
for d in sorted(V3):
    show(f"V({d})", V3[d])
IC3_0303 = F(100000)
IC3_0305 = F(5000) * X(ECB_A, "USD", "CNY") + F(10000) * X(ECB_A, "HKD", "CNY")
show("I^C 2025-03-05 (5,000 USD + 10,000 HKD)", IC3_0305)
f3_0303 = V3["2025-03-03"] / (V3["2025-03-02"] + IC3_0303)
run3_0304 = V3["2025-03-04"] / V3["2025-03-03"]
f3_0305 = V3["2025-03-05"] / (V3["2025-03-04"] + IC3_0305)
print(f"   factors 03-03 {frac(f3_0303)}, run 03-04 {frac(run3_0304)}, 03-05 {frac(f3_0305)}")
twr3_0320 = f3_0303 * run3_0304 * f3_0305 * (V3["2025-03-20"] / V3["2025-03-05"]) - 1
twr3_0319 = f3_0303 * run3_0304 * f3_0305 * (V3["2025-03-19"] / V3["2025-03-05"]) - 1
show("TWR (2025-03-02, 2025-03-20]", twr3_0320, "ratio")
show("TWR (2025-03-02, 2025-03-19] (LIMITED)", twr3_0319, "ratio")
show("G (2025-03-02, 2025-03-20]", V3["2025-03-20"] - IC3_0303 - IC3_0305)
stale = F("2000") * F("10.50") / V3["2025-03-19"]
show("stale share 03-19 (SYNA / gross total)", stale, "ratio")
show("holding 0700 C1 reporting (35,000 HKD)", F(35000) * X(ECB_A, "HKD", "CNY"))
show("cash C2 USD reporting (5,000 USD)", F(5000) * X(ECB_A, "USD", "CNY"))
show("cash C2 HKD reporting (10,000 HKD)", F(10000) * X(ECB_A, "HKD", "CNY"))
# 03-21: CNH 3,000 arrives (unvalued). 03-25: NOP1 bought for 1,000 HKD (unpriced).
priced_0321 = value(P3["2025-03-20"], ECB_A, R)
priced_0325 = value([(47600, "CNY"), (2000 * 11, "CNY"), (1000 * 35, "HKD"), (5000, "USD"), (9000, "HKD")], ECB_A, R)
show("priced holdings 03-21 (excludes CNH cash)", priced_0321)
show("priced holdings 03-25 (excludes CNH cash, NOP1)", priced_0325)
show("cash C2 HKD reporting 03-25 (9,000 HKD)", F(9000) * X(ECB_A, "HKD", "CNY"))

# ================================ P4 (USD), non-positive base ==================================
print("=== P4 (reporting USD) ===")
V4 = {"2025-01-07": F(0), "2025-01-08": F(10 * 101 - 1000), "2025-01-09": F(10 * 101), "2025-01-10": F(10 * 102)}
for d in sorted(V4):
    show(f"V({d})", V4[d])
print("   run 01-08..01-08: V(01-08)/V(01-07) = 10/0 -> NON_POSITIVE_BASE")
twr4 = (V4["2025-01-09"] / (V4["2025-01-08"] + 1000)) * (V4["2025-01-10"] / V4["2025-01-09"]) - 1
show("TWR (2025-01-08, 2025-01-10]", twr4, "ratio")
show("G (2025-01-07, 2025-01-10]", V4["2025-01-10"] - V4["2025-01-07"] - 1000)

# ================================ P5 (USD), zero-capital run ===================================
print("=== P5 (reporting USD) ===")
print("   01-02 factor 1000/(0+1000)=1; 01-03 factor (0+1000)/1000=1; run 01-04..01-06 0/0 -> 1 (ZERO_CAPITAL_RUN);")
print("   01-07 factor 500/(0+500)=1; run 01-08..01-10 500/500=1; TWR = 0; G = 500 - (1000 - 1000 + 500) = 0")

# ================================ P6 (HKD) =====================================================
print("=== P6 (reporting HKD) ===")
R = "HKD"
items = [(550, "USD"), (10 * 45, "USD"), (1000, "CNY")]
V6a = value(items, ECB_A, R)
V6b = value(items, ECB_B, R)
show("V(2025-03-31)", V6a)
show("V(2025-04-30)", V6b)
show("cash USD 550 at 03-31", F(550) * X(ECB_A, "USD", "HKD"))
show("holding AAPL 450 USD at 03-31", F(450) * X(ECB_A, "USD", "HKD"))
show("cash CNY 1,000 at 03-31", F(1000) * X(ECB_A, "CNY", "HKD"))
show("cash USD 550 at 04-30", F(550) * X(ECB_B, "USD", "HKD"))
show("holding AAPL 450 USD at 04-30", F(450) * X(ECB_B, "USD", "HKD"))
show("cash CNY 1,000 at 04-30", F(1000) * X(ECB_B, "CNY", "HKD"))
IC6 = F(1000) * X(ECB_A, "USD", "HKD") + F(1000) * X(ECB_A, "CNY", "HKD")
V6_0303 = V6a
twr6 = (V6_0303 / (0 + IC6)) * (V6b / V6_0303) - 1
show("TWR (2025-03-02, 2025-04-30]", twr6, "ratio")
show("G (2025-03-02, 2025-04-30]", V6b - IC6)
