"""Closed forms for cp4_golden/1.0-part4 (risk/1.9): the hand derivation of every expected value, as arithmetic.

Author: quant-analyst, 2026-10-03. Companion to CP4_GOLDEN_PART4_DERIVATION.md.

This file is the SECOND derivation, independent of cp4_part4_calculator.py. It does not replay a ledger or read
market-data files. It writes the periodic returns and the risk-free returns from the fixture's two weekly cycles
(the levels below are copied from the fixture's market_data block by hand) and evaluates the formulas of risk
Rulings 4.3, 6.5 and 6.7 directly. It shares no code with the calculators or with src/. It reads the fixture only to
compare its own results with the expected values.

Usage (read-only): python3 cp4_part4_closed_forms.py ../cp4_golden_part4.json
"""

import datetime as dt
import json
import sys
from fractions import Fraction as F
from math import isqrt

D = dt.date.fromisoformat
DAY = dt.timedelta(days=1)
J0 = D("2022-01-03")                               # Monday; every cycle of the fixture starts here
PX = [F(100), F(104)]                              # SYN51, USD: the level changes each Monday
BM = [F(1000), F(1010), F(1000), F(1020)]          # SYN5_BM_US_TR (and SYN5_BM_YOUNG where it exists), USD


def level(cycle, d):
    """The level in force on date d: set on Monday, kept Tuesday to Sunday."""
    k = (d - J0).days
    return cycle[0] if k < 0 else cycle[(k // 7) % len(cycle)]


def grid(a, b, keep):
    """Grid dates g with a <= g <= b."""
    out, d = [], a
    while d <= b:
        if keep(d):
            out.append(d)
        d += DAY
    return out


def rets(v, g):
    return [v(y) / v(x) - 1 for x, y in zip(g, g[1:])]


def svar(xs):
    m = sum(xs, F(0)) / len(xs)
    return sum(((x - m) ** 2 for x in xs), F(0)) / (len(xs) - 1)


def present_sqrt(sign, q):
    """ROUND_HALF_UP of sign * sqrt(q) to 12 decimals, with integers only."""
    n = q * 10 ** 24
    k = isqrt(n.numerator // n.denominator)
    m = k + 1 if 4 * n >= (2 * k + 1) ** 2 else k
    return ("-" if sign < 0 else "") + f"{m // 10 ** 12}.{str(m % 10 ** 12).zfill(12)}"


def frac(x):
    return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)


FIX = json.load(open(sys.argv[1]))
ITEMS = {a["id"]: a["expect"] for p in FIX["portfolios"] for a in p["assertions"]}
BAD = [0]


def check(label, got, want):
    ok = got == want
    BAD[0] += not ok
    print(("ok  " if ok else "BAD ") + f"{label}: closed form {got!r}" + ("" if ok else f", fixture {want!r}"))


# ---- 1. R41-C1, R41-C2, R41-C3: the DAILY Sharpe ratio at E = D_c(t) = Thursday 2025-11-27 -----------------------------
# Window TRAILING_MONTHS 12: B = 2024-11-27 (a Wednesday, on the DAILY grid), so g_0 = B and the periods are the 261
# weekdays of (2024-11-27, 2025-11-27]. 100 SYN51 and no cash, so r_k is SYN51's own price return.
E = D("2025-11-27")
g = grid(D("2024-11-27"), E, lambda d: d.weekday() < 5)
r = rets(lambda d: level(PX, d), g)
n = len(r)
mondays = [y for x, y, rk in zip(g, g[1:], r) if rk != 0]
print(f"n = {n}; non-zero returns = {len(mondays)} (all on Mondays); up = {sum(1 for x in r if x > 0)}, "
      f"down = {sum(1 for x in r if x < 0)}; sum r = {frac(sum(r, F(0)))}")
# The risk-free return of (g_{k-1}, g_k] is rho x (g_k - g_{k-1}) days with rho = 0.0365/365 = 1/10000 (3.65 %),
# except the LAST period (11-26, 11-27] when the 11-26 quote (7.30 %, rho = 2/10000) is in force at t.
days = [(y - x).days for x, y in zip(g, g[1:])]
assert sum(days) == 365
rho_old, rho_new = F("0.0365") / 365, F("0.0730") / 365
rf_old = [rho_old * k for k in days]                         # the 11-25 quote for the last period (C2, C3)
rf_new = rf_old[:-1] + [rho_new * days[-1]]                  # the 11-26 quote for the last period (C1)
s2 = svar(r)
for aid, rf in (("R41-C1", rf_new), ("R41-C2", rf_old), ("R41-C3", rf_old)):
    dbar = sum((a - b for a, b in zip(r, rf)), F(0)) / n
    q = 260 * dbar ** 2 / s2
    print(f"{aid}: sum rf = {frac(sum(rf, F(0)))}, mean excess = {frac(dbar)}, Sharpe^2 = {frac(q)}")
    item = ITEMS[aid][1]
    check(f"{aid} Sharpe exact_square", frac(q), item["exact_square"])
    check(f"{aid} Sharpe value", present_sqrt(1 if dbar > 0 else -1, q), item["value"])
    check(f"{aid} n", n, item["effective_window"]["observation_count"])
    # the risk-free rates of the last two periods (CUSTOM base 2025-11-25)
    rates = ITEMS[aid][0]["rates"]
    check(f"{aid} rf of (11-25, 11-26]", frac(rho_old * 1), rates[0]["exact"])
    check(f"{aid} rf of (11-26, 11-27]", frac(rf[-1]), rates[1]["exact"])
print("Sharpe ratio C1 / C3 =", frac(F(34, 35)), "exactly (the mean excess returns are 34 and 35 / 2,610,000)")

# ---- 2. R41-V1: the 3Y WEEKLY beta falls back to MAX_AVAILABLE (as of Friday 2025-11-28) ------------------------------
# P41's first event is 2024-11-01, so I_0 = 2024-10-31 and the MAX_AVAILABLE grid is the Fridays 2024-11-01 ..
# 2025-11-28: 57 points, 56 periods, 14 whole four-week benchmark cycles.
E2 = D("2025-11-28")
g = grid(D("2024-10-31"), E2, lambda d: d.weekday() == 4)
r = rets(lambda d: level(PX, d), g)
b = rets(lambda d: level(BM, d), g)
n = len(r)
mr, mb = sum(r, F(0)) / n, sum(b, F(0)) / n
srb = sum(((x - mr) * (y - mb) for x, y in zip(r, b)), F(0))
sbb = sum(((y - mb) ** 2 for y in b), F(0))
srr = sum(((x - mr) ** 2 for x in r), F(0))
beta = srb / sbb
v_beta = (srr - beta * srb) / ((n - 2) * sbb)
print(f"R41-V1: n = {n}, first four (r, b) = {[(frac(x), frac(y)) for x, y in zip(r[:4], b[:4])]}")
print(f"        S_rb = {frac(srb)}, S_bb = {frac(sbb)}, S_rr = {frac(srr)}")
mx = ITEMS["R41-V1"][2]
check("R41-V1 MAX_AVAILABLE beta exact", frac(beta), mx["exact"])
check("R41-V1 v_beta", frac(v_beta), mx["v_beta"])
check("R41-V1 n", n, mx["effective_window"]["observation_count"])
check("R41-V1 default view shows the same beta", frac(beta), ITEMS["R41-V1"][0]["shown"]["exact"])

print("CLOSED FORMS", "AGREE" if not BAD[0] else "DISAGREE")
sys.exit(1 if BAD[0] else 0)
