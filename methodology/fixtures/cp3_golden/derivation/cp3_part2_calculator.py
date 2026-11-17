"""Independent calculator for cp3_golden part 2 (MWR, income, fees, taxes, financing, conversion result,
dividend receivables, a synthetic split suppression).

Author: quant-analyst, 2026-10-01. Conventions: performance/1.3, market-data/1.9, ledger-replay/1.3.

A CALCULATOR for CP3_GOLDEN_PART2_DERIVATION.md, not an engine. Standard library only; imports nothing from
src/; holdings and flows are typed in by hand from the events (the derivation lists them); prices and FX are
the fixture's synthetic steps. Re-run with
`python3 methodology/fixtures/cp3_golden/derivation/cp3_part2_calculator.py`.

The MWR is solved twice, independently:
  (1) performance Ruling 6.2 as written: Decimal (prec 60), bracket by doubling/halving from g = 1, bisection;
  (2) the exact variant of Ruling 6.2 (1.1): with tau_i = k_i / n and y = g^(1/n), the sign of
      sum CF_i y^(-k_i) is evaluated in exact Fraction arithmetic, and y is bisected.
Both must give the same 12-decimal presented value. The uniqueness test (Ruling 6.3) is run at the root.
"""

from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction as F

A = F("1.0400") / F("8.1120")   # USD per HKD, fixings 2025-01-02 .. 03-31 (= 5/39)
B = F("1.0880") / F("8.5000")   # USD per HKD, fixings from 2025-04-01 (= 16/125)
assert A == F(5, 39) and B == F(16, 125)


def frac(x):
    return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)


def pm(x):  # presented money, half away from zero, 2 dp
    with localcontext() as c:
        c.prec = 200
        return str((Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.01"), ROUND_HALF_UP))


def pr(d):  # presented ratio (Decimal or Fraction), 12 dp
    if isinstance(d, F):
        with localcontext() as c:
            c.prec = 200
            d = Decimal(d.numerator) / Decimal(d.denominator)
    return str(d.quantize(Decimal("1e-12"), ROUND_HALF_UP))


def show(label, x, kind="money"):
    print(f"{label:62s} exact {frac(x):>30s}  presented {pm(x) if kind == 'money' else pr(x)}")


# ---------------- MWR solvers ------------------------------------------------------------------------------
def mwr_decimal(cfs, n):
    """cfs: list of (k, amount Fraction) with tau = k/n. Ruling 6.2 with Decimal prec 60."""
    agg = {}
    for k, a in cfs:
        agg[k] = agg.get(k, F(0)) + a
    items = sorted((k, a) for k, a in agg.items() if a != 0)
    if not items:
        return None, "NO_CAPITAL"
    if items[0][1] >= 0 or not any(a > 0 for _, a in items):
        return None, "IRR_NOT_DEFINED"
    with localcontext() as c:
        c.prec = 60
        c.rounding = ROUND_HALF_EVEN

        def D(x):
            return Decimal(x.numerator) / Decimal(x.denominator)

        def f(g):
            lg = g.ln()
            return sum(D(a) * (-(Decimal(k) / Decimal(n)) * lg).exp() for k, a in items)

        G = sum(a for _, a in items)
        if G == 0:
            g = Decimal(1)
        else:
            lo = hi = Decimal(1)
            if G > 0:
                hi = Decimal(2)
                while f(hi) > 0:
                    hi *= 2
            else:
                lo = Decimal("0.5")
                while f(lo) < 0:
                    lo /= 2
            it = 0
            while hi - lo > Decimal("1e-30") * hi and it < 400:
                mid = (lo + hi) / 2
                if f(mid) > 0:
                    lo = mid
                else:
                    hi = mid
                it += 1
            g = (lo + hi) / 2
        # uniqueness (Ruling 6.3): running balance at g, all flows but the last
        lg = g.ln()
        K = None
        prev = None
        for k, a in items[:-1]:
            K = -D(a) if K is None else K * ((Decimal(k - prev) / Decimal(n)) * lg).exp() - D(a)
            prev = k
            if K < 0:
                return g - 1, "IRR_UNIQUENESS_NOT_ESTABLISHED"
        return g - 1, None


def mwr_exact(cfs, n, width=F(1, 10 ** 22)):
    """Exact variant: y = g^(1/n); bisect y with exact Fraction sign tests; returns a bracket for g - 1."""
    agg = {}
    for k, a in cfs:
        agg[k] = agg.get(k, F(0)) + a
    items = sorted((k, a) for k, a in agg.items() if a != 0)
    kmax = max(k for k, _ in items)

    def h(y):  # y^kmax * f = sum a * y^(kmax - k); same sign as f for y > 0
        return sum(a * y ** (kmax - k) for k, a in items)

    G = sum(a for _, a in items)
    if G == 0:
        return F(0), F(0)
    lo, hi = F(1), F(1)
    if G > 0:
        hi = F(2)
        while h(hi) > 0:
            hi *= 2
    else:
        lo = F(1, 2)
        while h(lo) < 0:
            lo /= 2
    # bisect until g = y^n is bracketed within `width`
    while hi ** n - lo ** n > width:
        mid = (lo + hi) / 2
        if h(mid) > 0:
            lo = mid
        else:
            hi = mid
        # keep numbers small: snap to a dyadic with bounded bits (still a valid bracket)
    return lo ** n - 1, hi ** n - 1


def report_mwr(label, cfs, n):
    rho, status = mwr_decimal(cfs, n)
    if rho is None or status:
        print(f"{label:62s} MWR state: {status}  (decimal root {rho})")
        return rho, status
    lo, hi = mwr_exact(cfs, n)
    print(f"{label:62s} MWR presented {pr(rho)}   exact-bracket presents {pr(lo)} .. {pr(hi)}")
    return rho, status


def annualize(rho, Y):
    with localcontext() as c:
        c.prec = 60
        return ((1 + rho).ln() * Decimal(Y.denominator) / Decimal(Y.numerator)).exp() - 1


# ================================ P1 (USD) =====================================================
print("=== P1 MWR ===")
V0630, V260131 = F(254757, 10), F(255653, 10)
I_E3 = F(20000) * A
p1 = [(0, F(-10000)), (4, -I_E3), (68, F(-4000)), (126, F(-1000)), (151, F(-5000))]
r1, _ = report_mwr("P1 MWR (2025-01-01, 2025-06-30] n=180", p1 + [(180, V0630)], 180)
r1b, _ = report_mwr("P1 MWR (2025-01-01, 2026-01-31] n=395", p1 + [(395, V260131)], 395)
print("   annualized SI MWR (Y=79/73):", pr(annualize(r1b, F(79, 73))))
print("   G check P1 to 06-30:", frac(V0630 - (F(10000) + I_E3 + 4000 + 1000 + 5000)))
print("=== P1 cost/income lines (2025-01-01, 2025-06-30] ===")
show("fees (X2 FEE 2 USD)", F(-2))
show("financing (X6 INTEREST_CHARGED 3.50 USD)", F("-3.50"))
show("conversion result X8: -1000 USD + 7750 HKD x 16/125", -1000 + F(7750) * B)

# ================================ P2 (HKD) =====================================================
print("=== P2 MWR ===")
report_mwr("P2 MWR (2025-06-30, 2025-07-31] n=31 (I-6: = TWR 3/215)", [(0, F(-21500)), (31, F(21800))], 31)

# ================================ P4 (USD) =====================================================
print("=== P4 MWR (TWR there is NON_POSITIVE_BASE) ===")
r4, _ = report_mwr("P4 MWR (2025-01-07, 2025-01-10] n=3", [(1, F(-1000)), (3, F(1020))], 3)
with localcontext() as c:
    c.prec = 60
    print("   closed form 1.02^(3/2) - 1 =", pr((Decimal("1.02").ln() * Decimal("1.5")).exp() - 1))

# ================================ P5 (USD) =====================================================
print("=== P5 window (2025-01-03, 2025-01-06]: V_B = 0, no flows ===")
report_mwr("P5 MWR", [(0, F(0)), (3, F(0))], 3)

# ================================ P8 closed form ===============================================
print("=== P8 closed form (2025-01-01, 2026-01-01] n=365 ===")
report_mwr("P8 MWR (one deposit 4,000; V_E 10 x 430 = 4,300)", [(0, F(-4000)), (365, F(4300))], 365)
print("   exact: 4300/4000 - 1 =", frac(F(4300, 4000) - 1))

# ================================ P9 (M-3) =====================================================
print("=== P9 (Example M-3 realized) window (2025-03-03, 2025-03-06] n=3 ===")
V9 = {"03-03": F(1800), "03-04": F(6300 - 6050), "03-05": F(250), "03-06": F(250 + 6750 - 7000) + 2000 * F("1.25")}
print("   V:", {k: frac(v) for k, v in V9.items()})
report_mwr("P9 MWR", [(0, -V9["03-03"]), (1, F(6050)), (2, F(-6750)), (3, V9["03-06"])], 3)
twr9 = ((V9["03-04"] + 6050) / V9["03-03"]) * (V9["03-05"] / V9["03-04"]) * (V9["03-06"] / (V9["03-05"] + 6750)) - 1
show("P9 TWR", twr9, "ratio")
show("P9 G", V9["03-06"] - V9["03-03"] - (6750 - 6050))

# ================================ P10 (M-2) ====================================================
print("=== P10 (Example M-2 realized) window (2025-03-10, 2025-03-14] n=4 ===")
V10 = {"03-10": F(10000), "03-11": F(1000) * F("10.50"), "03-12": 800 * F(11) + 200, "03-13": 800 * F(11) + 200,
       "03-14": 800 * F(11) + 200 + 3000}
print("   V:", {k: frac(v) for k, v in V10.items()})
report_mwr("P10 MWR", [(0, -V10["03-10"]), (2, F(2000)), (3, F(-3000)), (4, V10["03-14"])], 4)
twr10 = (V10["03-11"] / V10["03-10"]) * ((V10["03-12"] + 2000) / V10["03-11"]) * (V10["03-13"] / V10["03-12"]) \
    * (V10["03-14"] / (V10["03-13"] + 3000)) - 1
show("P10 TWR", twr10, "ratio")
show("P10 G", V10["03-14"] - V10["03-10"] - (3000 - 2000))

# ================================ P11 (USD) ====================================================
print("=== P11 (BUY 10 SYNU for 1,020 on 01-08; DEPOSIT 1,020 on 01-10) ===")
V11 = {"01-07": F(0), "01-08": F(1010 - 1020), "01-09": F(1010 - 1020), "01-10": F(1020)}
print("   V:", {k: frac(v) for k, v in V11.items()})
report_mwr("P11 MWR custom (2025-01-08, 2025-01-10] n=2", [(0, -V11["01-08"]), (1, F(-1020)), (2, V11["01-10"])], 2)
report_mwr("P11 MWR SI (2025-01-07, 2025-01-10] n=3", [(0, F(0)), (2, F(-1020)), (3, V11["01-10"])], 3)
show("P11 G custom", V11["01-10"] - V11["01-08"] - 1020)

# ================================ P12 (Example W') =============================================
print("=== P12 (Example W re-dated: 03-31 at 5/39, 04-01 and 04-02 at 16/125) ===")
V12 = {"03-30": F(0),
       "03-31": F(5000) + (F(790) + 100 * F(390)) * A,
       "04-01": F(4000) + (F(790) + 100 * F(400)) * B,
       "04-02": F(4000) + (F(970) + 100 * F(400)) * B}
for k, v in V12.items():
    show(f"V12({k})", v)
twr12 = (V12["03-31"] / (V12["03-30"] + 10000)) * ((V12["04-01"] + 1000) / V12["03-31"]) * (V12["04-02"] / V12["04-01"]) - 1
show("P12 TWR (2025-03-30, 2025-04-02]", twr12, "ratio")
report_mwr("P12 MWR (2025-03-30, 2025-04-02] n=3", [(0, F(-10000)), (2, F(1000)), (3, V12["04-02"])], 3)
show("P12 G", V12["04-02"] - 9000)
show("P12 income (200 HKD x 16/125)", F(200) * B)
show("P12 taxes (-20 HKD x 16/125)", F(-20) * B)
show("P12 fees (-10 HKD x 5/39)", F(-10) * A)
show("P12 conversion result (-5000 + 38800 x 5/39)", -5000 + F(38800) * A)

# ================================ P7 (USD; dividends) ==========================================
print("=== P7 (reporting USD; SYNP HKD; dividends, interest, stamp duty, fee, CNH dividend) ===")
cash = {"04-01": F(100000) - 50000 - 50 - 30}
V7 = {
    "03-31": F(0),
    "04-01": (cash["04-01"] + 1000 * F(50)) * B,
    "05-05": (cash["04-01"] + 1000 * F(52)) * B,                 # HK holiday: 05-02 close 52
    "05-06": (cash["04-01"] + 1000 * F(50) + 2000) * B,          # ex-date: price 50, receivable 2,000
    "05-19": (cash["04-01"] + 1000 * F(50) + 2000) * B,
    "05-20": (cash["04-01"] + 2000 - 200 + 1000 * F(50)) * B,    # paid; withholding 200
    "06-26": (cash["04-01"] + 2000 - 200 + 1000 + F("12.34") + 1000 * F(51)) * B,
}
for k, v in V7.items():
    show(f"V7({k})", v)
show("receivable 2,000 HKD on 05-06..05-19", F(2000) * B)
IC7 = F(100000) * B
twr7 = (V7["04-01"] / IC7) * (V7["06-26"] / V7["04-01"]) - 1
show("P7 TWR (2025-03-31, 2025-06-26]", twr7, "ratio")
report_mwr("P7 MWR (2025-03-31, 2025-06-26] n=87 (I-6: = TWR)", [(0, -IC7), (87, V7["06-26"])], 87)
show("P7 G (2025-03-31, 2025-06-26]", V7["06-26"] - IC7)
show("P7 income (03-31, 06-26]: (2000 + 1000 + 12.34) HKD", (F(2000) + 1000 + F("12.34")) * B)
show("P7 taxes (03-31, 06-26]: -(50 + 200) HKD", F(-250) * B)
show("P7 fees  (03-31, 06-26]: -30 HKD", F(-30) * B)
show("P7 income (05-05, 05-31]: ex-date 05-06 inside", F(2000) * B)
show("P7 income (05-06, 05-31]: ex-date is the base, outside", F(0))
show("P7 taxes (05-06, 05-31]: withholding 05-20", F(-200) * B)

# ================================ P13 (synthetic split) ========================================
print("=== P13 (synthetic corroborated split 4:1 ex 2025-03-03 missing from the ledger) ===")
show("V13(2025-02-28): cash 2,000 + 100 x 80.00", F(2000) + 100 * 80)
show("priced holdings 2025-03-03 (cash only; SYNS excluded)", F(2000))
