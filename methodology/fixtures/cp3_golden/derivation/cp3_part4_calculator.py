"""Independent calculator for cp3_golden part 4 (attribution: the eight exact daily lines, Carino linking).

Author: quant-analyst, 2026-10-01. Conventions: performance/1.6 (Rulings 5.1, 8.1, 8.5, 9.1-9.6, 2.4), ledger-replay/1.5,
market-data/1.10.

A CALCULATOR for CP3_GOLDEN_PART4_DERIVATION.md, not an engine. Standard library only; imports nothing from src/.
It implements performance Ruling 9.1 directly from the portfolio-level events of each day:

- state = positions per listing (internal transfers do not change portfolio-level positions, so they are not modelled),
  cash per currency, accrued dividend receivables;
- every calendar day of the window is evaluated; the eight lines are computed from the start-of-day state, the day's
  prices and fixings, and the day's events; the end-of-day value is computed from the end state;
- identity I-4 (sum of lines = g_D) is asserted on every day; I-3 (sum g_D = G) and I-2 (product of daily factors = the
  TWR given in parts 1-3) are asserted per window;
- Carino linking (Ruling 9.4) uses Decimal at prec 50 for the logarithms; everything else is exact Fraction.

Prices and FX are the fixtures' synthetic step series, typed in by hand. Re-run with
`python3 methodology/fixtures/cp3_golden/derivation/cp3_part4_calculator.py`.
"""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal, getcontext, localcontext
from fractions import Fraction as F

LINES = ["1 attr.price", "2 attr.fx", "3 attr.price_fx_interaction", "4 attr.income", "5 attr.fees",
         "6 attr.taxes", "7 attr.financing", "8 attr.conversion"]  # performance/1.7 Ruling 9.2 identifiers

# ---------------------------------------------------------------- FX: ECB synthetic steps (part 1), latest fixing <= D
ECB = {"A": {"USD": F("1.0400"), "HKD": F("8.1120"), "CNY": F("7.4880")},
       "B": {"USD": F("1.0880"), "HKD": F("8.5000"), "CNY": F("7.8880")}}


def X(c, r, d):
    if c == r:
        return F(1)
    p = "A" if d <= dt.date(2025, 3, 31) else "B"
    return ECB[p][r] / ECB[p][c]


# ---------------------------------------------------------------- prices: RAW step series (parts 1-4), close of s(D)
STEPS = {
    "AAPL": [("2025-01-02", "150.00"), ("2025-02-03", "37.50"), ("2025-03-03", "45.00"), ("2025-06-16", "50.00")],
    "0700": [("2025-01-02", "35.00"), ("2025-04-01", "36.00"), ("2025-06-02", "37.00"), ("2025-07-15", "38.00")],
    "MSFT": [("2025-01-02", "400.00"), ("2025-06-02", "420.00"), ("2025-06-10", "430.00")],
    "SYNA": [("2025-03-03", "10.00"), ("2025-03-04", "10.50"), ("2025-03-20", "11.00")],
    "SYNH": [("2025-03-31", "390.00"), ("2025-04-01", "400.00")],
    "SYNF": [("2025-03-03", "9.00"), ("2025-03-05", "11.00"), ("2025-03-10", "12.00"), ("2025-03-12", "13.00"),
             ("2025-04-15", "12.50")],
    "SYNG": [("2025-03-03", "10.00"), ("2025-03-17", "11.00")],
}
CCY = {"AAPL": "USD", "0700": "HKD", "MSFT": "USD", "SYNA": "CNY", "SYNH": "HKD", "SYNF": "USD", "SYNG": "USD"}


def P(listing, d):
    """Step close in force on d (holidays and gaps carry the last close; staleness is handled by the caller)."""
    out = None
    for s, c in STEPS[listing]:
        if dt.date.fromisoformat(s) <= d:
            out = F(c)
    assert out is not None, (listing, d)
    return out


def D_(s):
    return dt.date.fromisoformat(s)


# ---------------------------------------------------------------- the daily decomposition (Ruling 9.1)
def value(state, d, R):
    pos, cash, recv = state
    v = sum((q * P(l, d) * X(CCY[l], R, d) for l, q in pos.items() if q != 0), F(0))
    v += sum((a * X(c, R, d) for c, a in cash.items()), F(0))
    v += sum((a * X(c, R, d) for (c, a) in recv.values()), F(0))
    return v


def day(state, events, d, R):
    """Return (lines[8], IC, IK, O, new_state, components) for calendar day d. components: FX by component."""
    pos, cash, recv = dict(state[0]), dict(state[1]), dict(state[2])
    y = d - dt.timedelta(days=1)
    L = [F(0)] * 8
    comp = {}
    sigma = {e[1]: F(e[2], e[3]) for e in events if e[0] == "SPLIT"}
    for l, q in pos.items():
        if q == 0:
            continue
        s = sigma.get(l, F(1))
        q0, P0, P1 = q * s, P(l, y) / s, P(l, d)
        X0, X1 = X(CCY[l], R, y), X(CCY[l], R, d)
        L[0] += q0 * (P1 - P0) * X0
        L[1] += q0 * P0 * (X1 - X0)
        L[2] += q0 * (P1 - P0) * (X1 - X0)
        comp[("position", l)] = q0 * P0 * (X1 - X0)
        comp[("price", l)] = comp.get(("price", l), F(0)) + q0 * (P1 - P0) * X0
        pos[l] = q0
    for c, m in cash.items():
        L[1] += m * (X(c, R, d) - X(c, R, y))
        comp[("cash", c)] = m * (X(c, R, d) - X(c, R, y))
    for k, (c, a) in recv.items():
        L[1] += a * (X(c, R, d) - X(c, R, y))
        comp[("receivable", k)] = a * (X(c, R, d) - X(c, R, y))
    IC = IK = O = F(0)
    for e in events:
        t = e[0]
        if t == "SPLIT":
            continue
        if t == "DEP":
            _, c, a = e; a = F(a); cash[c] = cash.get(c, 0) + a; IC += a * X(c, R, d)
        elif t == "WDR":
            _, c, a = e; a = F(a); cash[c] = cash.get(c, 0) - a; O += a * X(c, R, d)
        elif t in ("BUY", "SELL"):
            _, l, q, a, c = e; q, a = F(q), F(a)
            sgn = 1 if t == "BUY" else -1
            pos[l] = pos.get(l, 0) + sgn * q
            cash[c] = cash.get(c, 0) - sgn * a
            tr = sgn * (q * P(l, d) * X(CCY[l], R, d) - a * X(c, R, d))
            L[0] += tr
            comp[("price", l)] = comp.get(("price", l), F(0)) + tr
        elif t == "INK":
            _, l, q = e; q = F(q); pos[l] = pos.get(l, 0) + q; IK += q * P(l, d) * X(CCY[l], R, d)
        elif t == "DIV":       # cash basis
            _, a, c = e; a = F(a); cash[c] = cash.get(c, 0) + a; L[3] += a * X(c, R, d)
        elif t == "ACCRUE":    # on the ex-date (Ruling 8.1)
            _, k, a, c = e; a = F(a); recv[k] = (c, a); L[3] += a * X(c, R, d)
        elif t == "SETTLE":    # on the pay date: receivable becomes cash at equal value
            _, k = e; c, a = recv.pop(k); cash[c] = cash.get(c, 0) + a
        elif t in ("TAX", "FEE", "FIN"):
            _, a, c = e; a = F(a); cash[c] = cash.get(c, 0) - a
            L[{"FEE": 4, "TAX": 5, "FIN": 6}[t]] -= a * X(c, R, d)
        elif t == "CONV":
            _, cs, s_, cb, b_ = e; s_, b_ = F(s_), F(b_)
            cash[cs] = cash.get(cs, 0) - s_; cash[cb] = cash.get(cb, 0) + b_
            L[7] += -s_ * X(cs, R, d) + b_ * X(cb, R, d)
        else:
            raise ValueError(t)
    return L, IC, IK, O, (pos, cash, recv), comp


def ln(x):
    return x.ln()


def run(name, events_by_date, B, E, R, twr_expected=None, g_expected=None, groups=None):
    """Evaluate every calendar day of (B, E]; the state at the end of B is built by running from the first event."""
    print(f"=== {name}: window ({B}, {E}], reporting {R} ===")
    first = min(D_(k) for k in events_by_date)
    state = ({}, {}, {})
    d = first
    while d <= D_(B):
        _, _, _, _, state, _ = day(state, events_by_date.get(d.isoformat(), []), d, R)
        d += dt.timedelta(days=1)
    Vb = value(state, D_(B), R)
    tot = [F(0)] * 8
    one_plus = F(1)
    G = F(0)
    days = []
    comp_tot = {}
    d = D_(B) + dt.timedelta(days=1)
    V_prev = Vb
    while d <= D_(E):
        L, IC, IK, O, state, comp = day(state, events_by_date.get(d.isoformat(), []), d, R)
        V = value(state, d, R)
        beta = V_prev + IC
        g = V + O - IK - beta
        assert sum(L) == g, (name, d, sum(L), g)          # I-4, every day
        if beta == 0:
            assert g == 0, (name, d, "non-positive base")
            r = F(0)
        else:
            assert beta > 0, (name, d, "non-positive base")
            r = g / beta
        one_plus *= 1 + r
        G += g
        if any(x != 0 for x in L):
            days.append((d, beta, r, L))
            print(f"  {d}  beta {frac(beta)}  g {frac(g)}  r {frac(r)}")
            print("        lines " + ", ".join(f"{i + 1}:{frac(x)}" for i, x in enumerate(L) if x != 0))
        for k, v in comp.items():
            comp_tot[k] = comp_tot.get(k, F(0)) + v
        tot = [a + b for a, b in zip(tot, L)]
        V_prev = V
        d += dt.timedelta(days=1)
    twr = one_plus - 1
    assert sum(tot) == G                                    # I-4 over the window and I-3 below
    if twr_expected is not None:
        assert twr == F(twr_expected), (name, frac(twr), twr_expected)   # I-2: daily product = parts' segment TWR
    if g_expected is not None:
        assert G == F(g_expected), (name, frac(G), g_expected)
    print(f"  TWR {frac(twr)} -> {pr(twr)};  G {frac(G)} -> {pm(G)}")
    t_hat, app = apportion(G, tot)
    for i, x in enumerate(tot):
        print(f"    line {LINES[i]:34s} exact {frac(x):>24s}  apportioned {app[i]}")
    print(f"    apportioned sum {sum(Decimal(a) for a in app)} = total {t_hat}")
    C = carino(days, twr)
    for i, c in enumerate(C):
        print(f"    C_{i + 1} {LINES[i]:34s} {pr_dec(c)}")
    with localcontext() as ctx:
        ctx.prec = 50
        diff = sum(C, Decimal(0)) - Decimal(twr.numerator) / Decimal(twr.denominator)
    print(f"    Carino sum - TWR (internal) = {diff:.3E};  presented C sum {sum(Decimal(pr_dec(c)) for c in C)}"
          f" vs TWR {pr(twr)}")
    if groups:
        for gname, (line_idx, keys) in groups.items():
            parts = [comp_tot.get(k, F(0)) for k in keys]
            assert sum(parts) == tot[line_idx], (name, gname)          # Ruling 9.6: the grouping sums to the line
            shown = [(k, p) for k, p in zip(keys, parts) if p != 0]      # 9.6 (1.9) item 4: zero parts omitted
            app_parts = apportion_to(app[line_idx], [p for _, p in shown])  # item 2: to the line's display value
            print(f"    breakdown {gname} (line {line_idx + 1}, displayed {app[line_idx]}): "
                  + ", ".join(f"{k}={frac(p)} -> {a}" for (k, p), a in zip(shown, app_parts)))
    return twr, G, tot, C


def apportion_to(display_total, parts):
    """performance Ruling 9.6 (1.9) item 2 with Ruling 2.4 item 3: apportion exact parts (given in the 9.6 order, which
    breaks ties) to an already-displayed total (2 dp)."""
    q = F(1, 100)
    t_hat = F(Decimal(display_total))
    floors = []
    for p in parts:
        n = p / q
        floors.append(F(n.numerator // n.denominator) * q)
    short = int((t_hat - sum(floors)) / q)
    assert 0 <= short <= len(parts)
    order = sorted(range(len(parts)), key=lambda i: (-(parts[i] - floors[i]), i))
    out = list(floors)
    for i in order[:short]:
        out[i] += q
    assert sum(out) == t_hat
    return [str(_d(o).quantize(Decimal("0.01"))) for o in out]


def carino(days, twr):
    """Ruling 9.4 with Decimal prec 50: C_k = (1/kappa) sum_D kappa_D m_kD / beta_D."""
    with localcontext() as ctx:
        ctx.prec = 50
        def dec(x):
            return Decimal(x.numerator) / Decimal(x.denominator)
        def kap(r):
            return Decimal(1) if r == 0 else (Decimal(1) + dec(r)).ln() / dec(r)
        k = kap(twr)
        C = [Decimal(0)] * 8
        for (_, beta, r, L) in days:
            kd = kap(r)
            for i in range(8):
                if L[i] != 0:
                    C[i] += kd * dec(L[i] / beta)
        return [c / k for c in C]


# ---------------------------------------------------------------- presentation helpers
def frac(x):
    return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)


def _d(x):
    with localcontext() as c:
        c.prec = 200
        return Decimal(x.numerator) / Decimal(x.denominator)


def pm(x):
    return str(_d(x).quantize(Decimal("0.01"), ROUND_HALF_UP))


def pr(x):
    return str(_d(x).quantize(Decimal("1e-12"), ROUND_HALF_UP))


def pr_dec(x):
    return str(x.quantize(Decimal("1e-12"), ROUND_HALF_UP))


def apportion(total, parts):
    """Ruling 2.4 item 3, money at 2 dp: floors toward -inf, shortfall to the largest remainders, ties in line order."""
    q = F(1, 100)
    t_hat = F(int(_d(total).quantize(Decimal("0.01"), ROUND_HALF_UP) * 100), 100)
    floors = []
    for p in parts:
        n = p / q
        floors.append(F(n.numerator // n.denominator) * q)
    short = int((t_hat - sum(floors)) / q)
    order = sorted(range(len(parts)), key=lambda i: (-(parts[i] - floors[i]), i))
    out = list(floors)
    for i in order[:short]:
        out[i] += q
    assert sum(out) == t_hat
    return pm(t_hat), [str(_d(o).quantize(Decimal("0.01"))) for o in out]


def evs(*pairs):
    out = {}
    for date, e in pairs:
        out.setdefault(date, []).append(e)
    return out


# ================================================================ P12 (Example W re-dated: W')
P12 = evs(("2025-03-31", ("DEP", "USD", 10000)), ("2025-03-31", ("CONV", "USD", 5000, "HKD", 38800)),
          ("2025-03-31", ("BUY", "SYNH", 100, 38000, "HKD")), ("2025-03-31", ("FEE", 10, "HKD")),
          ("2025-04-01", ("WDR", "USD", 1000)),
          ("2025-04-02", ("DIV", 200, "HKD")), ("2025-04-02", ("TAX", 20, "HKD")))
run("P12 (W')", P12, "2025-03-30", "2025-04-02", "USD", twr_expected="2776451/112562500", g_expected="6104/25")
run("P12 day 2 only", P12, "2025-03-31", "2025-04-01", "USD")

# ================================================================ P1 since inception (cp1_golden P1, L = 25)
P1 = evs(("2025-01-02", ("DEP", "USD", 10000)),
         ("2025-01-06", ("BUY", "AAPL", 50, 7500, "USD")), ("2025-01-06", ("DEP", "HKD", 20000)),
         ("2025-01-08", ("BUY", "0700", 500, 17500, "HKD")),
         ("2025-02-03", ("SPLIT", "AAPL", 4, 1)),
         ("2025-03-03", ("SELL", "AAPL", 50, 2250, "USD")),
         ("2025-03-10", ("INK", "MSFT", 10)),
         ("2025-04-02", ("CONV", "USD", 1000, "HKD", 7750)), ("2025-04-02", ("FEE", 2, "USD")),
         ("2025-04-02", ("BUY", "0700", 200, 7000, "HKD")),
         ("2025-05-05", ("BUY", "MSFT", 5, 2000, "USD")), ("2025-05-08", ("DEP", "USD", 1000)),
         ("2025-05-31", ("FIN", "3.50", "USD")), ("2025-06-02", ("DEP", "USD", 5000)),
         ("2025-06-03", ("BUY", "MSFT", 5, 2100, "USD")), ("2025-06-10", ("SELL", "MSFT", 4, 1720, "USD")),
         ("2025-06-16", ("SELL", "AAPL", 40, 2000, "USD")))
run("P1 since inception", P1, "2025-01-01", "2025-06-30", "USD",
    twr_expected="14849541313483073959/79734639592304900000", g_expected="1135523/390")

# ================================================================ P6 (HKD; FX only)
P6 = evs(("2025-03-03", ("DEP", "USD", 1000)), ("2025-03-03", ("DEP", "CNY", 1000)),
         ("2025-03-03", ("BUY", "AAPL", 10, 450, "USD")))
run("P6 since inception", P6, "2025-03-02", "2025-04-30", "HKD", twr_expected="47/61828", g_expected="1175/174",
    groups={"FX by component": (1, [("position", "AAPL"), ("cash", "CNY"), ("cash", "USD")])})

# ================================================================ P3 (CNY; Southbound) -- before the CNH deposit
P3 = evs(("2025-03-03", ("DEP", "CNY", 100000)), ("2025-03-03", ("BUY", "SYNA", 2000, 20000, "CNY")),
         ("2025-03-04", ("BUY", "0700", 1000, 32400, "CNY")),
         ("2025-03-05", ("DEP", "USD", 5000)), ("2025-03-05", ("DEP", "HKD", 10000)))
run("P3 to 03-16", P3, "2025-03-02", "2025-03-16", "CNY", twr_expected="59/6500", g_expected="11800/13",
    groups={"price by listing": (0, [("price", "0700"), ("price", "SYNA")])})
run("P3 to 03-20 (LIMITED: SYNA 2-3 sessions stale on 03-18/19)", P3, "2025-03-02", "2025-03-20", "CNY",
    twr_expected="35242/2205125", g_expected="24800/13")

# ================================================================ P21 (USD; FX on a dividend receivable)
P21 = evs(("2025-03-26", ("DEP", "HKD", 40000)), ("2025-03-26", ("BUY", "0700", 1000, 35000, "HKD")),
          ("2025-03-28", ("ACCRUE", "div", 2000, "HKD")),
          ("2025-04-03", ("SETTLE", "div")), ("2025-04-03", ("TAX", 200, "HKD")))
run("P21 since inception", P21, "2025-03-25", "2025-04-03", "USD", twr_expected="1067/15625", g_expected="68288/195",
    groups={"FX by component": (1, [("position", "0700"), ("cash", "HKD"), ("receivable", "div")])})

# ================================================================ P22 (USD; five-session gap) -- values only
P22 = evs(("2025-03-03", ("DEP", "USD", 1000)), ("2025-03-03", ("BUY", "SYNG", 100, 1000, "USD")))
print("=== P22: TWR and G use only V(03-02), V(03-03) and V(03-31) (Ruling 5.2) ===")
s = ({}, {}, {})
for dd in ("2025-03-03",):
    _, _, _, _, s, _ = day(s, P22[dd], D_(dd), "USD")
V0303, V0331 = value(s, D_("2025-03-03"), "USD"), value(s, D_("2025-03-31"), "USD")
print(f"  V(03-03) {frac(V0303)}  V(03-31) {frac(V0331)}  TWR {frac(V0331 / F(1000) - 1)}  G {frac(V0331 - 1000)}")
print("  sessions 03-10..03-14 have no SYNG print: on 03-14 (and 03-15, 03-16) s = 5 -> holding INSUFFICIENT_DATA "
      "+ STALE_DATA (market-data 5.2), so V_D is missing and the attribution is INSUFFICIENT_DATA + STALE_DATA.")

# ================================================================ P14 (USD; everything in R)
P14 = evs(("2025-03-03", ("DEP", "USD", 10000)), ("2025-03-03", ("BUY", "SYNF", 30, 270, "USD")),
          ("2025-03-05", ("SELL", "SYNF", 80, 880, "USD")), ("2025-03-05", ("BUY", "SYNF", 100, 1040, "USD")),
          ("2025-03-05", ("BUY", "SYNF", 50, 580, "USD")), ("2025-03-10", ("SELL", "SYNF", 40, 480, "USD")))
run("P14 since inception (all USD)", P14, "2025-03-02", "2025-03-31", "USD", twr_expected="1/40", g_expected="250")
print("done")
