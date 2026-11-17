"""Independent calculator for cp4_golden part 1 (risk/1.0: the series spine and single-series metrics).

Author: quant-analyst, 2026-10-02. Convention set: risk/1.0, on performance/1.12 and market-data/1.11.

This is a CALCULATOR for the derivation in CP4_GOLDEN_PART1_DERIVATION.md, written from the text of
methodology/CP4_RISK_CONVENTIONS.md (risk/1.0) and the performance/market-data rulings it cites. It is
not an engine, and it reads no engine output:

- it imports nothing from src/ (standard library only: json, datetime, calendar, fractions, decimal,
  math);
- it reads the fixture's INPUT blocks (market data, listings, ledger events, assertion requests) and
  recomputes every expected value from them in exact rational arithmetic;
- it never reads an 'expect' value to compute another one. In --check mode it compares its own results
  with the fixture's expect items, field by field, and exits non-zero on any difference.

Usage (read-only; it writes no file):
  python3 cp4_part1_calculator.py FIXTURE.json            print every derived result as JSON
  python3 cp4_part1_calculator.py FIXTURE.json --check    compare with the fixture's expect items
  python3 cp4_part1_calculator.py FIXTURE.json --closed   also re-derive P3/P5 from the closed forms
  python3 cp4_part1_calculator.py --counts                 re-count N1/N3 (Ruling 7.1) over 2001-2029

Scope: the ledger event types part 1 uses (DEPOSIT, BUY, external in-kind TRANSFER_IN). Anything else
raises, so the calculator cannot silently mis-handle an event it was not written for.
"""

import calendar as _cal
import datetime as dt
import json
import sys
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction as F
from math import isqrt

D = dt.date.fromisoformat
ONE = dt.timedelta(days=1)

# ---- risk/1.0 constants -----------------------------------------------------------------------
A = {"DAILY": 260, "WEEKLY": 52, "MONTHLY": 12}            # Ruling 3.1: periods per year
N1 = {"DAILY": 259, "WEEKLY": 51, "MONTHLY": 11}           # Ruling 7.1: INSUFFICIENT_DATA below
N3 = {"DAILY": 781, "WEEKLY": 155, "MONTHLY": 35}          # Ruling 7.1: AVAILABLE from
PRIORITY = ["CALCULATION_ERROR", "LEDGER_INCONSISTENT", "NOT_RECONSTRUCTABLE", "SOURCE_CONFLICT",
            "UNRESOLVED_CONVENTION", "UNSUPPORTED_ASSET", "MISSING_BENCHMARK", "MISSING_COST_BASIS",
            "MISSING_PRICE_HISTORY", "MISSING_FX_HISTORY", "STALE_DATA"]   # performance Ruling 1.5
RANK = {"AVAILABLE": 0, "LIMITED": 1, "INSUFFICIENT_DATA": 2}


# ---- dates (performance Ruling 5.4) -----------------------------------------------------------
def last_dom(y, m):
    return _cal.monthrange(y, m)[1]


def add_months(x, m):
    """The end-of-month rule of performance Ruling 5.4."""
    y = x.year + (x.month - 1 + m) // 12
    mo = (x.month - 1 + m) % 12 + 1
    if x.day == last_dom(x.year, x.month):
        return dt.date(y, mo, last_dom(y, mo))
    return dt.date(y, mo, min(x.day, last_dom(y, mo)))


def on_grid(freq, d):
    """risk/1.0 Ruling 2.2: weekdays, Fridays, last calendar day of the month."""
    if freq == "DAILY":
        return d.weekday() < 5
    if freq == "WEEKLY":
        return d.weekday() == 4
    if freq == "MONTHLY":
        return d.day == last_dom(d.year, d.month)
    raise ValueError(freq)


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += ONE


def frac(x):
    return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)


# ---- causes and states ------------------------------------------------------------------------
class St:
    """A state built from causes (level, reason code or None, detail name)."""

    def __init__(self, causes=()):
        self.causes = list(causes)

    def level(self):
        return max((RANK[c[0]] for c in self.causes), default=0)

    def state(self):
        return {0: "AVAILABLE", 1: "LIMITED", 2: "INSUFFICIENT_DATA"}[self.level()]

    def reason(self):
        """performance Ruling 1.5 (1.1): only causes at the result's own level compete."""
        lv = self.level()
        codes = [c[1] for c in self.causes if RANK[c[0]] == lv and c[1]]
        if lv == 0:
            codes = [c for c in codes if c == "STALE_DATA"]
        for p in PRIORITY:
            if p in codes:
                return p
        return None

    def details(self):
        out = []
        for c in self.causes:
            if c[2] and c[2] not in out:
                out.append(c[2])
        return out

    def add(self, other):
        self.causes += other.causes
        return self


def fresh(count, kind):
    """market-data Rulings 5.2 and 1.6, and risk/1.0 Ruling 4.4, on a missed count."""
    if count == 0:
        return St()
    detail = {"PRICE": "PRICE_STALE", "FX": "FX_STALE", "RF": "RISK_FREE_STALE"}[kind]
    if count == 1:
        return St([("AVAILABLE", "STALE_DATA", detail)])
    if count <= 4:
        return St([("LIMITED", "STALE_DATA", detail)])
    code = "MISSING_FX_HISTORY" if kind == "FX" else "STALE_DATA"
    return St([("INSUFFICIENT_DATA", code, detail)])


# ---- market data ------------------------------------------------------------------------------
class Calendar:
    def __init__(self, c):
        self.id = c["calendar_id"]
        self.lo, self.hi = D(c["coverage"]["from"]), D(c["coverage"]["to"])
        closed = {D(x) for x in c["closed_weekdays"]}
        assert c["sessions_rule"].startswith("every Monday to Friday"), c["sessions_rule"]
        self.days = sorted(d for d in daterange(self.lo, self.hi) if d.weekday() < 5 and d not in closed)

    def count_between(self, a, b):
        """Number of listed dates d with a < d <= b. The interval must lie inside coverage."""
        assert self.lo <= a + ONE and b <= self.hi, ("CALENDAR_COVERAGE_GAP", self.id, a, b)
        return sum(1 for d in self.days if a < d <= b)


def expand_steps(steps, cycle, key):
    """Explicit steps plus an optional cycle (format 'cycle'); returns sorted (from, value)."""
    out = {D(s["from"]): F(s[key]) for s in steps}
    if cycle:
        start, every, until = D(cycle["from"]), cycle["every_days"], D(cycle["until"])
        vals = cycle["closes"] if key == "close" else cycle["rates"]
        j = 0
        while start + dt.timedelta(days=every * j) <= until:
            out[start + dt.timedelta(days=every * j)] = F(vals[j % len(vals)])
            j += 1
    return sorted(out.items())


def step_at(steps, d):
    v = None
    for f, x in steps:
        if f <= d:
            v = x
        else:
            break
    return v


class Prices:
    def __init__(self, s, cal):
        self.cal = cal
        steps = expand_steps(s["steps"], s.get("cycle"), "close")
        gaps = {D(x) for x in s["gaps"]}
        first, last = D(s["first"]), D(s["last"])
        self.rows = {d: step_at(steps, d) for d in cal.days if first <= d <= last and d not in gaps}
        self.row_days = sorted(self.rows)

    def at(self, d):
        """(close, state, print date, missed sessions) for valuation date d (market-data 2.1, 5.2)."""
        prints = [x for x in self.row_days if x <= d]
        if not prints:
            return None, St([("INSUFFICIENT_DATA", "MISSING_PRICE_HISTORY", "NO_PRINT")]), None, None
        p = prints[-1]
        m = self.cal.count_between(p, d)
        return self.rows[p], fresh(m, "PRICE"), p, m


class FX:
    def __init__(self, fx, cal):
        self.cal = cal
        first, last = D(fx["first"]), D(fx["last"])
        self.rows = {}
        for c, steps in fx["steps"].items():
            st = expand_steps(steps, fx.get("cycles", {}).get(c), "rate")
            gaps = {D(x) for x in fx.get("gaps_by_currency", {}).get(c, [])}
            self.rows[c] = {d: step_at(st, d) for d in cal.days if first <= d <= last and d not in gaps}

    def X(self, c, r, d):
        """Units of r per one c at date d (market-data Rulings 1.3 and 1.6): (rate, state)."""
        if c == r:
            return F(1), St()
        common = [x for x in self.cal.days if x <= d and x in self.rows[c] and x in self.rows[r]]
        if not common:
            return None, St([("INSUFFICIENT_DATA", "MISSING_FX_HISTORY", "NO_FIXING")])
        u = common[-1]
        st = fresh(self.cal.count_between(u, d), "FX")
        if st.level() == 2:
            return None, st
        return self.rows[r][u] / self.rows[c][u], st


class RiskFree:
    def __init__(self, s, cal):
        self.s, self.cal = s, cal
        steps = expand_steps(s["steps"], None, "rate")
        gaps = {D(x) for x in s["gaps"]}
        first, last = D(s["first"]), D(s["last"])
        self.rows = {d: step_at(steps, d) for d in cal.days if first <= d <= last and d not in gaps}
        self.row_days = sorted(self.rows)

    def per_day(self, q):
        """risk/1.0 Ruling 4.3: the simple rate per calendar day of a quote given in percent."""
        y = q / 100
        if self.s["quote_type"] == "SIMPLE_YIELD":
            return y / self.s["day_count_basis"]
        if self.s["quote_type"] == "BANK_DISCOUNT":
            return y / (360 - y * self.s["tenor_days"])
        raise ValueError(self.s["quote_type"])

    def period(self, a, b):
        """rf for (a, b]: the quote at the latest publication <= a, accrued simply over (b - a) days."""
        qs = [x for x in self.row_days if x <= a]
        if not qs:
            return None, St([("INSUFFICIENT_DATA", None, "RISK_FREE_UNAVAILABLE")]), None, None
        f = qs[-1]
        m = self.cal.count_between(f, a)
        st = fresh(m, "RF")
        if st.level() == 2:
            return None, st, f, m
        return self.per_day(self.rows[f]) * (b - a).days, st, f, m


class World:
    def __init__(self, fx):
        md = fx["market_data"]
        self.cals = {c["calendar_id"]: Calendar(c) for c in md["calendars"]}
        ecb = [c for c in md["calendars"] if c["kind"] == "ECB_FIXINGS"][0]["calendar_id"]
        self.fx = FX(md["fx"], self.cals[ecb])
        self.prices = {s["listing_id"]: Prices(s, self.cals[s["calendar"]]) for s in md["prices"]["series"]}
        self.rf = {s["currency"]: RiskFree(s, self.cals[s["calendar"]]) for s in md["risk_free"]["series"]}
        self.listing_ccy = {l["listing_id"]: l["trading_currency"] for l in fx["listings"]}


# ---- the portfolio (performance Rulings 1.4, 4.1-4.4, 5.1-5.3) ---------------------------------
class Portfolio:
    def __init__(self, p, w):
        self.w, self.R = w, p["reporting_currency"]
        self.events = [e["event"] for e in sorted(p["events"], key=lambda e: e["ledger_seq"])]
        self.I0 = min(D(e["event_date"]) for e in self.events) - ONE      # Ruling 4.4 (no snapshot here)

    def holdings(self, d):
        cash, qty = {}, {}
        for e in self.events:
            if D(e["event_date"]) > d:
                continue
            t = e["event_type"]
            if t == "DEPOSIT":
                cash[e["currency"]] = cash.get(e["currency"], F(0)) + F(e["amount"]["amount"])
            elif t == "BUY":
                c = e["amount"]["currency"]
                cash[c] = cash.get(c, F(0)) - F(e["amount"]["amount"])
                qty[e["listing_id"]] = qty.get(e["listing_id"], F(0)) + F(e["quantity"])
            elif t == "TRANSFER_IN" and "listing_id" in e and "counterparty_account_id" not in e:
                qty[e["listing_id"]] = qty.get(e["listing_id"], F(0)) + F(e["quantity"])
            else:
                raise ValueError(f"event type not handled by this calculator: {t}")
        return cash, qty

    def V(self, d):
        """TV_R(d) and its state; None when INSUFFICIENT_DATA. Quantity-zero positions are not priced."""
        if d <= self.I0:
            return F(0), St()
        cash, qty = self.holdings(d)
        total, st = F(0), St()
        for c, a in cash.items():
            if a == 0:
                continue
            x, s = self.w.fx.X(c, self.R, d)
            st.add(s)
            if x is not None:
                total += a * x
        for l, q in qty.items():
            if q == 0:
                continue
            p, s, _, _ = self.w.prices[l].at(d)
            x, s2 = self.w.fx.X(self.w.listing_ccy[l], self.R, d)
            st.add(s).add(s2)
            if p is not None and x is not None:
                total += q * p * x
        return (None if st.level() == 2 else total), st

    def flows(self, d):
        """(I^C, I^K, O) dated d in R. Part 1 has no outflow."""
        ic, ik, st = F(0), F(0), St()
        for e in self.events:
            if D(e["event_date"]) != d:
                continue
            if e["event_type"] == "DEPOSIT":
                x, s = self.w.fx.X(e["currency"], self.R, d)
                st.add(s)
                ic += F(e["amount"]["amount"]) * (x if x is not None else 0)
            elif e["event_type"] == "TRANSFER_IN" and "listing_id" in e:
                p, s, _, _ = self.w.prices[e["listing_id"]].at(d)
                x, s2 = self.w.fx.X(self.w.listing_ccy[e["listing_id"]], self.R, d)
                st.add(s).add(s2)
                ik += F(e["quantity"]) * p * x
        return ic, ik, F(0), st

    def twr(self, a, b):
        """TWR factor over (a, b], segment form (performance Ruling 5.2), with its inputs' state."""
        flow_days = sorted({D(e["event_date"]) for e in self.events
                            if e["event_type"] in ("DEPOSIT", "TRANSFER_IN") and a < D(e["event_date"]) <= b})
        st, vals = St(), {}

        def v(d):
            if d not in vals:
                x, s = self.V(d)
                st.add(s)
                vals[d] = x
            return vals[d]

        def ratio(num, den):
            if num is None or den is None:
                return None
            if den == 0:
                if num == 0:
                    return F(1)                          # ZERO_CAPITAL_RUN
                raise ValueError("NON_POSITIVE_BASE")
            return num / den

        factor, prev = F(1), a
        for fd in flow_days:
            if fd - ONE != prev:                         # a non-empty run before the flow day
                r = ratio(v(fd - ONE), v(prev))
                factor = None if (factor is None or r is None) else factor * r
            ic, ik, o, s = self.flows(fd)
            st.add(s)
            vb, ve = v(fd - ONE), v(fd)
            r = ratio(None if ve is None else ve + o - ik, None if vb is None else vb + ic)
            factor = None if (factor is None or r is None) else factor * r
            prev = fd
        if prev != b:
            r = ratio(v(b), v(prev))
            factor = None if (factor is None or r is None) else factor * r
        return (None if st.level() == 2 else factor), st


# ---- window and series (risk/1.0 Rulings 2.1-2.5) ---------------------------------------------
def window(port, req, freq, E):
    rule = req["rule"]
    if rule == "TRAILING_MONTHS":
        B = add_months(E, -req["months"])
    elif rule == "CUSTOM":
        B = D(req["base"])
    elif rule in ("SINCE_INCEPTION", "MAX_AVAILABLE"):
        B = port.I0
    else:
        raise ValueError(rule)
    out = {"requested_base": B}
    if B < port.I0:
        out["refusal"] = St([("INSUFFICIENT_DATA", None, "WINDOW_BEFORE_INCEPTION")])
        return out
    pts = [d for d in daterange(B, E) if on_grid(freq, d)]
    if len(pts) < 2:
        out["refusal"] = St([("INSUFFICIENT_DATA", None, "NO_FULL_PERIOD")])
        return out
    out["points"] = pts
    return out


def build(port, req, freq, E):
    w = window(port, req, freq, E)
    if "refusal" in w:
        return w, None
    pts = w["points"]
    s = []
    for a, b in zip(pts, pts[1:]):
        f, st = port.twr(a, b)
        s.append({"start": a, "end": b, "r": (None if f is None else f - 1), "st": st})
    if req["rule"] == "MAX_AVAILABLE":
        bad = [i for i, x in enumerate(s) if x["st"].level() == 2]
        w["max_available_start"] = "AFTER_INSUFFICIENT_PERIOD" if bad else "INCEPTION"
        if bad:
            k = bad[-1]
            w["points"], s = pts[k + 1:], s[k + 1:]
            if not s:
                w["refusal"] = St([("INSUFFICIENT_DATA", None, "NO_FULL_PERIOD")])
                return w, None
    return w, s


def series_state(s):
    st = St()
    bad = [x for x in s if x["st"].level() == 2]
    lim = [x for x in s if x["st"].level() == 1]
    stale = [x for x in s if x["st"].level() == 0 and x["st"].reason() == "STALE_DATA"]
    for x in bad:
        st.causes += [c for c in x["st"].causes if RANK[c[0]] == 2]
    if bad:
        st.causes.append(("INSUFFICIENT_DATA", None, "PERIOD_INSUFFICIENT"))
    if lim:
        st.causes.append(("LIMITED", "STALE_DATA", "STALE_PERIODS"))
    if stale:
        st.causes.append(("AVAILABLE", "STALE_DATA", "STALE_PERIODS"))
    return st, len(lim)


def count_state(n, freq):
    if n < N1[freq]:
        return St([("INSUFFICIENT_DATA", None, "INSUFFICIENT_OBSERVATIONS")])
    if n < N3[freq]:
        return St([("LIMITED", None, "OBSERVATIONS_BELOW_STANDARD")])
    return St()


# ---- statistics (risk/1.0 Ruling 6) and presentation (Ruling 3.4) ---------------------------------
def mean(xs):
    return sum(xs, F(0)) / len(xs)


def svar(xs):
    m = mean(xs)
    return sum(((x - m) ** 2 for x in xs), F(0)) / (len(xs) - 1)


def present_rational(x):
    """performance Ruling 2.2: ROUND_HALF_UP to 1e-12, written with exactly 12 decimals."""
    with localcontext() as ctx:
        ctx.prec = 200
        d = Decimal(x.numerator) / Decimal(x.denominator)
        return format(d.quantize(Decimal("1e-12"), rounding=ROUND_HALF_UP), "f")


def present_sqrt(sign, Q):
    """ROUND_HALF_UP to 1e-12 of sign*sqrt(Q), certified with integers only (no float, no Decimal sqrt).

    With N = Q*10^24 and k = floor(sqrt(N)) = isqrt(floor(N)), |value|*10^12 = sqrt(N) rounds up to k+1
    exactly when sqrt(N) >= k + 1/2, i.e. 4N >= (2k+1)^2: an exact rational comparison.

    Also returns a LOWER BOUND on the distance |sqrt(N) - (k + 1/2)|, in quanta (units of 1e-12): since
    sqrt(N) + k + 1/2 <= 2k + 3/2, the distance is at least |4N - (2k+1)^2| / (4 (2k + 3/2)). It is the
    certificate that an independent Decimal implementation at prec 50 must present the same value."""
    if Q == 0 or sign == 0:
        return "0.000000000000", None
    N = Q * 10 ** 24
    k = isqrt(N.numerator // N.denominator)
    m = k + 1 if 4 * N >= (2 * k + 1) ** 2 else k
    s = ("-" if sign < 0 else "") + str(m // 10 ** 12) + "." + str(m % 10 ** 12).zfill(12)
    return s, abs(4 * N - (2 * k + 1) ** 2) / (4 * (2 * k + F(3, 2)))


def mdd(rs):
    """risk/1.0 Ruling 1.1: W_0 = 1 at the base; running peak over the window INCLUDING the base."""
    W = [F(1)]
    for r in rs:
        W.append(W[-1] * (1 + r))
    best, trough, M = F(0), None, W[0]
    for k, w in enumerate(W):
        M = max(M, w)
        dd = w / M - 1
        if dd < best:
            best, trough = dd, k
    if trough is None:
        return F(0), None, None, None
    Mt = max(W[: trough + 1])
    peak = max(j for j in range(trough + 1) if W[j] == Mt)
    rec = next((j for j in range(trough + 1, len(W)) if W[j] >= Mt), None)
    return best, peak, trough, rec


def metric(port, kind, freq, req, E):
    w, s = build(port, req, freq, E)
    res = {"kind": kind, "frequency": freq, "request": req, "requested_base": w["requested_base"].isoformat()}
    if s is None:
        st = w["refusal"]
        res.update(state=st.state(), reason=st.reason(), details=st.details(), value=None, effective_window=None)
        return res
    pts, n = w["points"], len(s)
    res["effective_window"] = {"base_date": pts[0].isoformat(), "last_period_end": pts[-1].isoformat(),
                               "observation_count": n, "stub_start_days": (pts[0] - w["requested_base"]).days,
                               "stub_end_days": (E - pts[-1]).days}
    if "max_available_start" in w:
        res["effective_window"]["max_available_start"] = w["max_available_start"]
    sst, nlim = series_state(s)
    st = St().add(sst)
    if kind == "return_series":
        res["returns"] = [{"period_end": x["end"].isoformat(), "exact": None if x["r"] is None else frac(x["r"]),
                           "state": x["st"].state()} for x in s]
        res.update(state=st.state(), reason=st.reason(), details=st.details())
        return res
    r = [x["r"] for x in s]
    rf = None
    if kind in ("downside_deviation", "sharpe", "sortino", "risk_free_rates"):
        if port.R not in port.w.rf:
            st.causes.append(("INSUFFICIENT_DATA", None, "NO_RISK_FREE_SOURCE"))
        else:
            rf = [port.w.rf[port.R].period(x["start"], x["end"]) for x in s]
            for q in rf:
                st.add(q[1])
    if kind == "risk_free_rates":
        res["rates"] = [{"period_start": x["start"].isoformat(), "period_end": x["end"].isoformat(),
                         "quote_date": q[2].isoformat(), "missed_publications": q[3],
                         "exact": None if q[0] is None else frac(q[0])} for x, q in zip(s, rf)]
        res.update(state=st.state(), reason=st.reason(), details=st.details())
        return res
    if kind != "max_drawdown":
        st.add(count_state(n, freq))
        res["thresholds"] = {"insufficient_below": N1[freq], "available_from": N3[freq]}
    else:
        res["thresholds"] = None
    if nlim:
        res["stale_period_count"] = nlim
    value = None
    if st.level() < 2:
        a = A[freq]
        if kind == "volatility":
            value = ("sqrt", 1, a * svar(r))
        elif kind == "max_drawdown":
            v, pk, tr, rc = mdd(r)
            value = ("rational", v)
            res["peak_date"] = None if pk is None else pts[pk].isoformat()
            res["trough_date"] = None if tr is None else pts[tr].isoformat()
            res["recovery_date"] = None if rc is None else pts[rc].isoformat()
        else:
            d = [ri - q[0] for ri, q in zip(r, rf)]
            dbar = mean(d)
            sgn = (dbar > 0) - (dbar < 0)
            down = sum((min(F(0), x) ** 2 for x in d), F(0))
            if kind == "downside_deviation":
                value = ("sqrt", 1, a * down / n)
            elif svar(r) == 0:
                st.causes.append(("INSUFFICIENT_DATA", None, "ZERO_VOLATILITY"))
            elif kind == "sharpe":
                value = ("sqrt", sgn, a * dbar ** 2 / svar(r))
            elif down == 0:
                st.causes.append(("INSUFFICIENT_DATA", None, "NO_DOWNSIDE_OBSERVATIONS"))
            else:
                value = ("sqrt", sgn, a * dbar ** 2 * n / down)
    if st.level() == 2:
        value = None
    res.update(state=st.state(), reason=st.reason(), details=st.details())
    if value is None:
        res.update(value=None, exact=None)
    elif value[0] == "rational":
        res.update(value=present_rational(value[1]), exact=frac(value[1]))
    else:
        sgn, Q = value[1], value[2]
        txt, gap = present_sqrt(sgn, Q)
        res.update(value=txt, exact=None, exact_square=frac(Q), sign=(sgn if Q != 0 else 0))
        res["_boundary_distance_quanta"] = gap      # not a fixture field; summarised by --check
    return res


def derive(fx):
    w = World(fx)
    out = {}
    for p in fx["portfolios"]:
        port = Portfolio(p, w)
        for a in p["assertions"]:
            E = D(a["as_of"])
            out[a["id"]] = [metric(port, x["kind"], x["frequency"], x["request"], E) for x in a["expect"]]
    return out


# ---- closed forms for P3 and P5 (the hand derivation, re-done here as a second route) ------------
def closed_forms():
    """Re-derives P3-A1, P3-A3 and P5-M1 from the counts stated in the derivation document."""
    u, w_ = F(1, 25), F(-1, 26)
    rf1, rf2 = F(7, 10000), F(14, 10000)
    out = {}
    # P3-A1: 156 periods; up/down by rf regime: regime 1 (130 starts): 65 up, 65 down; regime 2 (26): 13/13
    n = 156
    rbar = F(1, 1300)
    s2 = F(156, 155) * F(51, 1300) ** 2
    out["P3-A1 volatility^2"] = 52 * s2
    dbar = rbar - (130 * rf1 + 26 * rf2) / n
    down = 65 * (w_ - rf1) ** 2 + 13 * (w_ - rf2) ** 2
    out["P3-A1 downside^2"] = 52 * down / n
    out["P3-A1 sharpe^2"] = 52 * dbar ** 2 / s2
    out["P3-A1 sortino^2"] = 52 * dbar ** 2 * n / down
    # P3-A3: 52 periods from 2025-01-03 (level 104): 26 up, 26 down; regime 1: 26 starts (13/13), regime 2: 26 (13/13)
    n = 52
    s2 = F(52, 51) * F(51, 1300) ** 2
    out["P3-A3 volatility^2"] = 52 * s2
    dbar = rbar - (26 * rf1 + 26 * rf2) / n
    down = 13 * (w_ - rf1) ** 2 + 13 * (w_ - rf2) ** 2
    out["P3-A3 downside^2"] = 52 * down / n
    out["P3-A3 sharpe^2"] = 52 * dbar ** 2 / s2
    out["P3-A3 sortino^2"] = 52 * dbar ** 2 * n / down
    # P5-M1: 52 periods alternating +1/200 (first) and -1/201; 13/13 in each rf regime
    up, dn = F(1, 200), F(-1, 201)
    rbar = (up + dn) / 2
    s2 = F(52, 51) * ((up - dn) / 2) ** 2
    out["P5-M1 volatility^2"] = 52 * s2
    dbar = rbar - (26 * rf1 + 26 * rf2) / 52
    down = 13 * (dn - rf1) ** 2 + 13 * (dn - rf2) ** 2
    out["P5-M1 downside^2"] = 52 * down / 52
    out["P5-M1 sharpe^2"] = 52 * dbar ** 2 / s2
    out["P5-M1 sortino^2"] = 52 * dbar ** 2 * 52 / down
    return out


COMPARED = ["state", "reason", "value", "exact", "exact_square", "sign", "requested_base",
            "effective_window", "thresholds", "peak_date", "trough_date", "recovery_date", "returns", "rates",
            "stale_period_count"]


def check(fx, out):
    bad = 0
    for p in fx["portfolios"]:
        for a in p["assertions"]:
            if len(a["expect"]) != len(out[a["id"]]):
                bad += 1
                print(f"MISMATCH {a['id']}: item count")
            for exp, got in zip(a["expect"], out[a["id"]]):
                for k in COMPARED:
                    if (k in exp or k in got) and exp.get(k) != got.get(k):
                        bad += 1
                        print(f"MISMATCH {a['id']} {exp['kind']} {exp['frequency']} {k}: "
                              f"fixture={exp.get(k)!r} calculator={got.get(k)!r}")
                for name in exp.get("details_include", []):
                    if name not in got["details"]:
                        bad += 1
                        print(f"MISMATCH {a['id']} {exp['kind']} {exp['frequency']}: details lack {name}")
                own = [x for x in got["details"] if x in RISK_DETAILS]
                if sorted(own) != sorted(exp.get("details_include", [])):
                    bad += 1
                    print(f"MISMATCH {a['id']} {exp['kind']} {exp['frequency']}: risk/1.0 details "
                          f"fixture={sorted(exp.get('details_include', []))} calculator={sorted(own)}")
    gaps = [g for items in out.values() for it in items
            for g in [it.get("_boundary_distance_quanta")] if g is not None]
    if gaps:
        lo = min(gaps)
        print("smallest distance of a square-root value from a rounding boundary:",
              present_rational(lo), "quanta (", "OK" if lo > F(1, 10 ** 18) else "TOO CLOSE", "; need > 1e-18 )")
        bad += 0 if lo > F(1, 10 ** 18) else 1
    print("CHECK", "FAILED" if bad else "PASSED", "-", bad, "difference(s)")
    return bad


#: the lineage detail names risk/1.0 defines (Ruling 7.4); the fixture asserts exactly these
RISK_DETAILS = {"INSUFFICIENT_OBSERVATIONS", "OBSERVATIONS_BELOW_STANDARD", "WINDOW_BEFORE_INCEPTION",
                "NO_FULL_PERIOD", "ZERO_VOLATILITY", "NO_DOWNSIDE_OBSERVATIONS", "NO_RISK_FREE_SOURCE",
                "RISK_FREE_UNAVAILABLE", "RISK_FREE_STALE", "PERIOD_INSUFFICIENT", "STALE_PERIODS"}


def check_closed(out):
    cf = closed_forms()
    pick = {"P3-A1": (0, 5), "P3-A3": (0, 5), "P5-M1": (0, 5)}
    names = ["volatility", "downside", "max_drawdown", "sharpe", "sortino"]
    bad = 0
    for aid in pick:
        for i, name in enumerate(names):
            key = f"{aid} {name}^2"
            if key not in cf:
                continue
            got = F(out[aid][i]["exact_square"])
            ok = got == cf[key]
            bad += not ok
            print(("ok  " if ok else "BAD ") + key, frac(cf[key]))
    print("CLOSED FORMS", "AGREE" if not bad else "DISAGREE")
    return bad


def window_counts():
    """risk/1.0 Ruling 7.1: min and max observations of every full 1-, 3- and 5-year window, over
    every end date 2001-01-01 .. 2029-12-31 (a full 28-year weekday/leap cycle)."""
    print("months freq min max   (N1 = min at 12 months, N3 = min at 36 months)")
    for months in (12, 36, 60):
        for f in ("DAILY", "WEEKLY", "MONTHLY"):
            lo, hi, E = None, None, dt.date(2001, 1, 1)
            while E <= dt.date(2029, 12, 31):
                B = add_months(E, -months)
                n = sum(1 for d in daterange(B, E) if on_grid(f, d)) - 1
                lo = n if lo is None else min(lo, n)
                hi = n if hi is None else max(hi, n)
                E += ONE
            print(months, f, lo, hi)
            if months == 12:
                assert lo == N1[f], (f, lo)
            if months == 36:
                assert lo == N3[f], (f, lo)
    print("N1 and N3 AGREE with the full-window minima")


if __name__ == "__main__":
    if sys.argv[1] == "--counts":
        window_counts()
        sys.exit(0)
    fixture = json.load(open(sys.argv[1]))
    if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
        fixture["portfolios"] = json.load(open(sys.argv[2]))      # authoring aid: inputs split in two files
    results = derive(fixture)
    status = 0
    if "--closed" in sys.argv:
        status |= 1 if check_closed(results) else 0
    if "--check" in sys.argv:
        status |= 1 if check(fixture, results) else 0
    else:
        print(json.dumps(results, indent=1, default=lambda x: frac(x) if isinstance(x, F) else str(x)))
    sys.exit(status)
