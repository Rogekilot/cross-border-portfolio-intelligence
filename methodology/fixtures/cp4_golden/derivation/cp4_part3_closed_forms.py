"""Closed-form cross-checks for cp4_golden part 3 (1.1-part3, risk/1.3): a SECOND derivation, independent of the calculator.

Author: quant-analyst, 2026-10-02. Companion to CP4_GOLDEN_PART3_DERIVATION.md section 13.

cp4_part3_calculator.py replays the ledger and the market data day by day. This file does not: it writes each
portfolio's periodic returns directly from the four-week cycles of the fixture's inputs (the cycle levels below
are copied from the fixture's market_data block by hand), with the one perturbation each portfolio has, and
computes the statistics from the formulas of risk Rulings 6.7-6.11 and 3.2. It shares no code with the calculator
or with src/. It reads the fixture only to compare its own results with the expected values.

Usage (read-only): python3 cp4_part3_closed_forms.py ../cp4_golden_part3.json
"""

import datetime as dt
import json
import sys
from fractions import Fraction as F

D = dt.date.fromisoformat
ONE_DAY = dt.timedelta(days=1)
J0 = D("2023-01-06")                       # cycle index 0 (every cycle of the fixture starts here)

S21 = [F(100), F(104), F(101), F(98)]      # SYN21 (and SYN43 before its split), USD
S42 = [F(100), F(103), F(99), F(101)]      # SYN42, USD
S31 = [F(50), F(51), F("50.5"), F("49.5")] # SYN31 and SYN32 (the ETFs), USD
S22 = [F(100), F(105), F(100), F(95)]      # SYN22, HKD
BUS = [F(1000), F(1030), F(1010), F(990)]  # SYN4_BM_US_TR (and both sources of _TR2), USD
BCN = [F(5000), F(5100), F(5050), F(4950)] # SYN4_BM_CN_TR, CNY


def phase(d):
    """Phase of the level in force on date d: Monday to Thursday repeat the previous Friday's level."""
    k = (d - J0).days
    return 0 if k < 0 else (k // 7) % 4


def parity(d):
    k = (d - J0).days
    return 0 if k < 0 else (k // 7) % 2


def at(cycle, d):
    return cycle[phase(d)]


def dates(a, b, keep):
    out, d = [], a
    while d < b:
        d += ONE_DAY
        if keep(d):
            out.append(d)
    return out


def fridays(a, b):
    return dates(a, b, lambda d: d.weekday() == 4)


def weekdays(a, b):
    return dates(a, b, lambda d: d.weekday() < 5)


def month_ends(a, b):
    return dates(a, b, lambda d: (d + ONE_DAY).day == 1)


def rets(f, grid):
    return [f(y) / f(x) - 1 for x, y in zip(grid, grid[1:])]


def stats(r, b):
    n = len(r)
    mr, mb = sum(r) / n, sum(b) / n
    a = [x - y for x, y in zip(r, b)]
    ma = sum(a) / n
    return dict(n=n, mr=mr,
                srr=sum((x - mr) ** 2 for x in r),
                sbb=sum((y - mb) ** 2 for y in b),
                srb=sum((x - mr) * (y - mb) for x, y in zip(r, b)),
                saa=sum((x - ma) ** 2 for x in a))


def beta(s):
    return s["srb"] / s["sbb"]


def var_ann(A, s, key):
    """A x s^2 (divisor n - 1): the square of an annualized dispersion (Ruling 3.2)."""
    return A * s[key] / (s["n"] - 1)


E = D("2026-01-02")
FIX = json.load(open(sys.argv[1]))
BAD = [0]


def expected(aid, k, field):
    for p in FIX["portfolios"]:
        for a in p["assertions"]:
            if a["id"] == aid:
                return F(a["expect"][k][field])
    raise KeyError(aid)


def check(label, got, aid, k, field="exact"):
    ok = got == expected(aid, k, field)
    BAD[0] += not ok
    print(("ok  " if ok else "BAD ") + f"{aid}[{k}].{field}  {label} = {got}")


# R1: the flat benchmark. b_k = 0, so a_k = r_k: TE = volatility; IR = A rbar / (sqrt(A) s(r)).
g = [D("2025-01-03")] + fridays(D("2025-01-03"), E)
s = stats(rets(lambda d: at(S21, d), g), [F(0)] * 52)
check("TE^2 = 52 S_rr / 51", var_ann(52, s, "srr"), "R1-F1", 3, "exact_square")
check("IR^2 = 52 rbar^2 / (S_rr / 51)", 52 * s["mr"] ** 2 / (s["srr"] / 51), "R1-F1", 4, "exact_square")

# R2: SYN42 has no print on Friday 2025-06-13 (phase 3), so that date is valued at Thursday's close, which is the
# phase-2 level 99: the period ending 06-13 returns 0 (not 2/99) and the next one 100/99 - 1 = 1/99 (not -1/101).
MISS = D("2025-06-13")
g = [D("2023-01-06")] + fridays(D("2023-01-06"), E)
s = stats(rets(lambda d: at(S42, d - ONE_DAY if d == MISS else d), g), rets(lambda d: at(BUS, d), g))
check("beta = S_rb / S_bb", beta(s), "R2-L1", 0)
check("TE^2 = 52 S_aa / 155", var_ann(52, s, "saa"), "R2-L1", 1, "exact_square")
g = [D("2025-01-03")] + fridays(D("2025-01-03"), E)          # 1.1-part3, R2-L2: the same perturbation over 1Y
s = stats(rets(lambda d: at(S42, d - ONE_DAY if d == MISS else d), g), rets(lambda d: at(BUS, d), g))
check("1Y beta", beta(s), "R2-L2", 0)
check("1Y TE^2 = 52 S_aa / 51", var_ann(52, s, "saa"), "R2-L2", 1, "exact_square")
check("1Y volatility^2 = 52 S_rr / 51", var_ann(52, s, "srr"), "R2-L2", 2, "exact_square")


# R3: the CN index translated into USD at the ECB fixing: X(CNY->USD) = 1.08 / 7.8000 (even index) or 1.08 / 7.8390
# (odd). CNY has no quote on 03-13 and 03-14, so Friday 03-14 (index 114, even: 7.8000) is translated at the
# 03-12 rate, which is Friday 03-07's (index 113, odd: 7.8390).
def x_cny(d):
    while d in (D("2025-03-13"), D("2025-03-14")):
        d -= ONE_DAY
    return F("1.08") / (F("7.8000") if parity(d) == 0 else F("7.8390"))


g = [D("2025-01-03")] + fridays(D("2025-01-03"), E)
s = stats(rets(lambda d: at(S21, d), g), rets(lambda d: at(BCN, d) * x_cny(d), g))
check("beta", beta(s), "R3-X1", 0)
check("TE^2", var_ann(52, s, "saa"), "R3-X1", 1, "exact_square")
check("benchmark return (01-10 -> 01-02)", at(BCN, E) * x_cny(E) / (at(BCN, D("2025-01-10")) * x_cny(D("2025-01-10"))) - 1,
      "R3-X1", 3)

# R5: the ETF proxy of SYN31: TR_t = TR_prev (P_t + d_t) / P_prev on every weekday; d = 0.50 ex Monday 2025-03-03
# (after a phase-0 Friday) and 0.40 ex Tuesday 2025-09-02 (after a phase-2 Friday).
DIVS = {D("2025-03-03"): F("0.50"), D("2025-09-02"): F("0.40")}


def tr_ratio(a, b):
    f, prev = F(1), a
    for d in weekdays(a, b):
        f *= (at(S31, d) + DIVS.get(d, 0)) / at(S31, prev)
        prev = d
    return f


g = [D("2025-01-03")] + fridays(D("2025-01-03"), E)
s = stats(rets(lambda d: at(S21, d), g), [tr_ratio(x, y) - 1 for x, y in zip(g, g[1:])])
check("beta", beta(s), "R5-E1", 0)
check("TE^2", var_ann(52, s, "saa"), "R5-E1", 1, "exact_square")
check("benchmark return = (50/51)(101/100)(509/505) - 1", tr_ratio(D("2025-01-10"), E) - 1, "R5-E1", 3)

# R6: DAILY (every weekday; 53 non-zero returns, on the Fridays) and MONTHLY (month-ends).
g = [D("2025-01-02")] + weekdays(D("2025-01-02"), E)
s = stats(rets(lambda d: at(S21, d), g), rets(lambda d: at(BUS, d), g))
check("daily beta", beta(s), "R6-D1", 0)
check("daily TE^2 = 260 S_aa / 260", var_ann(260, s, "saa"), "R6-D1", 1, "exact_square")
for k, base in ((2, D("2023-01-02")), (4, D("2025-01-02"))):
    g = month_ends(base, E)
    print(f"     monthly grid from {g[0]}: phases {''.join(str(phase(x)) for x in g)}")
    s = stats(rets(lambda d: at(S21, d), g), rets(lambda d: at(BUS, d), g))
    check("monthly beta", beta(s), "R6-D1", k)
    if k == 2:
        check("monthly TE^2 = 12 S_aa / 34", var_ann(12, s, "saa"), "R6-D1", 3, "exact_square")

# R7: HKD reporting. X(USD->HKD) = 8.4000 / 1.08 (even) or 8.4420 / 1.08 (odd). In Current mode at 2026-01-09 09:00
# UTC the last period's benchmark end point is Thursday 01-08 (level and fixing = Friday 01-02's), so that period's
# benchmark return is 0; historically it is 1030 x 8.442 / (1000 x 8.4) - 1 = 703/20000.
def x_hkd(d):
    return (F("8.4000") if parity(d) == 0 else F("8.4420")) / F("1.08")


E7 = D("2026-01-09")
g = [D("2025-01-10")] + fridays(D("2025-01-10"), E7)
r = rets(lambda d: at(S22, d), g)
b_hist = rets(lambda d: at(BUS, d) * x_hkd(d), g)
b_curr = b_hist[:-1] + [F(0)]
check("Current-mode beta (last benchmark return 0)", beta(stats(r, b_curr)), "R7-C1", 0)
check("historical beta (last benchmark return 703/20000)", beta(stats(r, b_hist)), "R7-H1", 0)


# R8, portfolio scope: 100 SYN21 and 10,100 USD idle in A2 until Wednesday 2025-06-11, then 200 SYN21 (the internal
# transfer and the buy at 101.00 are neutral at portfolio scope). 22 diluted periods, then 30 of SYN21's.
def v8(d):
    return 100 * at(S21, d) + 10100 if d < D("2025-06-11") else 200 * at(S21, d)


g = [D("2025-01-03")] + fridays(D("2025-01-03"), E)
s = stats(rets(v8, g), rets(lambda d: at(BUS, d), g))
check("portfolio beta", beta(s), "R8-K1", 5)
check("portfolio volatility^2", var_ann(52, s, "srr"), "R8-K1", 6, "exact_square")


# R10: the snapshot, 100 SYN21 and 500 USD from 2024-11-29: r = (P' - P) / (P + 5).
def v10(d):
    return 100 * at(S21, d) + 500


for k, g0 in ((1, D("2025-01-03")), (2, D("2024-11-29"))):
    g = [g0] + fridays(g0, E)
    s = stats(rets(v10, g), [F(0)] * (len(g) - 1))
    check(f"volatility^2 from {g0} (n = {s['n']})", var_ann(52, s, "srr"), "R10-S1", k, "exact_square")
g = [D("2024-11-29")] + fridays(D("2024-11-29"), E)
check("MAX_AVAILABLE beta", beta(stats(rets(v10, g), rets(lambda d: at(BUS, d), g))), "R10-S1", 3)

print("CLOSED FORMS", "AGREE" if not BAD[0] else "DISAGREE")
sys.exit(1 if BAD[0] else 0)
