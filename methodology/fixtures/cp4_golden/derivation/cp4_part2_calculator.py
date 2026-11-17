"""Independent calculator for cp4_golden part 2 (risk/1.1: benchmark-relative metrics, comparability, selections).

Author: quant-analyst, 2026-10-02. Convention set: risk/1.1, on performance/1.12 and market-data/1.11.

A CALCULATOR for CP4_GOLDEN_PART2_DERIVATION.md, written from methodology/CP4_RISK_CONVENTIONS.md. It is not an
engine and reads no engine output:

- standard library only (json, datetime, zoneinfo, fractions, decimal, math, importlib, os); it imports nothing
  from src/. It reuses the part-1 calculator in this directory for the valuation layer (calendars, prices, FX,
  risk-free quotes, the TWR in segment form, windows, part-1 metrics);
- it reads the fixture's INPUT blocks and recomputes every expected item from them in exact rationals;
- it never reads an 'expect' value to compute another one.

Usage (read-only; it writes no file):
  python3 cp4_part2_calculator.py FIXTURE.json               print every derived result as JSON
  python3 cp4_part2_calculator.py FIXTURE.json --check       compare with the fixture's expect items
  python3 cp4_part2_calculator.py FIXTURE.json --mutations   run every mutation of the catalog and verify that it
                                                             changes EXACTLY the items whose 'bites' name it
  python3 cp4_part2_calculator.py FIXTURE.json --closed      re-derive Q1, Q2 and Q4 from the closed forms
"""

import datetime as dt
import importlib.util
import json
import os
import sys
from fractions import Fraction as F
from zoneinfo import ZoneInfo

_spec = importlib.util.spec_from_file_location("cp4p1", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                     "cp4_part1_calculator.py"))
P1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P1)

D, ONE, St, frac = P1.D, P1.ONE, P1.St, P1.frac
UTC = dt.timezone.utc

#: the mutation catalog (each one a single deliberate departure from risk/1.1; see the derivation, section 10)
CATALOG = {
    "M-B1": "benchmark not translated into R (native levels)",
    "M-B2": "benchmark translated at the previous calendar day's fixing, not the portfolio's u(g)",
    "M-B3": "beta and R-squared from the excess-return regression instead of the total-return market model",
    "M-B4": "active return geometric: (1 + TWR_p)/(1 + R_b) - 1",
    "M-B5": "tracking error with divisor n instead of n - 1",
    "M-B6": "a PRICE_RETURN benchmark accepted",
    "M-B7": "window facts (active and benchmark return) read the benchmark at every grid date, not only g_0 and g_n",
    "M-B8": "information ratio = window active return / tracking error",
    "M-B9": "a BANK_DISCOUNT quote read as a simple yield on ACT/360",
    "M-B10": "the FIRST selection record of the pinned log version is used instead of the latest",
    "M-B11": "the seam test ignores the ECB fixing (exchange calendars only)",
    "M-B12": "no LAGGED test",
    "M-B13": "an empty portfolio instant set (cash in R only) counts as a seam",
    "M-B14": "beta = S_rb / S_rr (regression the wrong way round)",
    "M-B15": "R-squared adjusted for degrees of freedom",
    "M-B16": "alpha = A * (mean(r) - beta * mean(b)) (market-model intercept, no risk-free rate)",
    "M-B17": "the USD risk-free series used for any reporting currency",
    "M-B19": "benchmark staleness does not degrade the state",
    "M-B20": "a missing benchmark suppresses every metric, benchmark-independent ones included",
    "M-B21": "R-squared reported as 0 when the portfolio's variance is 0 (instead of undefined)",
    "M-B22": "with no selection in force, the engine defaults to the first benchmark in M",
    "M-B23": "the benchmark leg of a window fact measured from the requested base B instead of g_0",
}
MUT = set()

TWO_LEG = {"beta", "r_squared", "alpha_jensen", "tracking_error", "information_ratio", "active_return"}
STATISTICS = {"beta", "r_squared", "alpha_jensen", "tracking_error", "information_ratio"}
WINDOW_FACTS = {"active_return", "benchmark_return"}
RISK_DETAILS = P1.RISK_DETAILS | {"NO_BENCHMARK_SELECTED", "BENCHMARK_SERIES_UNAVAILABLE", "BENCHMARK_NOT_TOTAL_RETURN",
                                  "BENCHMARK_NOT_COVERING_WINDOW", "BENCHMARK_STALE", "ZERO_BENCHMARK_VARIANCE",
                                  "ZERO_PORTFOLIO_VARIANCE", "ZERO_TRACKING_ERROR"}


# ---- market data beyond part 1 -------------------------------------------------------------------
class Bench:
    def __init__(self, b, cal):
        self.b, self.cal, self.ccy, self.basis = b, cal, b["currency"], b["return_basis"]
        steps = P1.expand_steps(b["steps"], b.get("cycle"), "level")
        gaps = {D(x) for x in b["gaps"]}
        first, last = D(b["first"]), D(b["last"])
        self.rows = {d: P1.step_at(steps, d) for d in cal.days if first <= d <= last and d not in gaps}
        self.row_days = sorted(self.rows)

    def at(self, g):
        """risk/1.1 Ruling 5.2: (level, state, effective calculation day, missed calculation days)."""
        prior = [x for x in self.row_days if x <= g]
        if not prior:
            return None, St([("INSUFFICIENT_DATA", "MISSING_BENCHMARK", "BENCHMARK_NOT_COVERING_WINDOW")]), None, None
        e = prior[-1]
        m = self.cal.count_between(e, g)
        st = St() if m == 0 else St([({1: "AVAILABLE"}.get(m, "LIMITED" if m <= 4 else "INSUFFICIENT_DATA"),
                                      "STALE_DATA", "BENCHMARK_STALE")])
        if "M-B19" in MUT:
            st = St()
        return (None if st.level() == 2 else self.rows[e]), st, e, m


def _patch_expand_steps():
    """Benchmarks use key 'level' and cycle field 'levels'; extend part 1's helper without changing its behaviour."""
    orig = P1.expand_steps

    def expand(steps, cycle, key):
        if key != "level":
            return orig(steps, cycle, key)
        out = {D(s["from"]): F(s["level"]) for s in steps}
        if cycle:
            start, every, until = D(cycle["from"]), cycle["every_days"], D(cycle["until"])
            j = 0
            while start + dt.timedelta(days=every * j) <= until:
                out[start + dt.timedelta(days=every * j)] = F(cycle["levels"][j % len(cycle["levels"])])
                j += 1
        return sorted(out.items())
    P1.expand_steps = expand


_patch_expand_steps()


class World2(P1.World):
    def __init__(self, fx):
        super().__init__(fx)
        md = fx["market_data"]
        self.cal_json = {c["calendar_id"]: c for c in md["calendars"]}
        self.ecb_id = [c for c in md["calendars"] if c["kind"] == "ECB_FIXINGS"][0]["calendar_id"]
        self.listing_cal = {s["listing_id"]: s["calendar"] for s in md["prices"]["series"]}
        self.bench = {b["benchmark_id"]: Bench(b, self.cals[b["calendar"]]) for b in md["benchmarks"]}

    def fx_fixing(self, c, r, g):
        """(rate, state, fixing date u, missed fixings) for X(c->r, g); c == r needs nothing."""
        if c == r:
            return F(1), St(), None, 0
        days = [x for x in self.fx.cal.days if x <= g and x in self.fx.rows[c] and x in self.fx.rows[r]]
        x, st = self.fx.X(c, r, g)
        if not days:
            return x, st, None, None
        return x, st, days[-1], self.fx.cal.count_between(days[-1], g)

    def instant(self, calendar_id, day):
        """The scheduled close (or the ECB fixing) of `day` on that calendar, as a UTC datetime (Ruling 8.3)."""
        c = self.cal_json[calendar_id]
        if c["kind"] == "ECB_FIXINGS":
            t = c["fixing"]["time"]
        else:
            over = {o["date"]: o["time"] for o in c["close"]["overrides"]}
            t = over.get(day.isoformat(), c["close"]["default"])
        h, m = map(int, t.split(":"))
        return dt.datetime(day.year, day.month, day.day, h, m, tzinfo=ZoneInfo(c["timezone"])).astimezone(UTC)


# ---- the benchmark in force (Ruling 5.6) ------------------------------------------------------------
def selection(port_json, version):
    recs = sorted((r for r in port_json.get("benchmark_selections", []) if r["seq"] <= version), key=lambda r: r["seq"])
    if not recs:
        return None
    return recs[0] if "M-B10" in MUT else recs[-1]


def resolve_benchmark(w, port_json, version):
    """(Bench or None, lineage dict, St of the refusal or empty)."""
    rec = selection(port_json, version)
    if "M-B22" in MUT and (rec is None or rec["benchmark_id"] is None):
        rec = {"benchmark_id": next(iter(w.bench)), "selection_id": "DEFAULTED"}
    if rec is None or rec["benchmark_id"] is None:
        return None, {"benchmark_id": None, "selection_id": None if rec is None else rec["selection_id"]}, \
            St([("INSUFFICIENT_DATA", "MISSING_BENCHMARK", "NO_BENCHMARK_SELECTED")])
    lin = {"benchmark_id": rec["benchmark_id"], "selection_id": rec["selection_id"]}
    b = w.bench.get(rec["benchmark_id"])
    if b is None:
        return None, lin, St([("INSUFFICIENT_DATA", "MISSING_BENCHMARK", "BENCHMARK_SERIES_UNAVAILABLE")])
    lin.update(return_basis=b.basis, currency=b.ccy, currency_treatment=(
        "NONE (benchmark already in R)" if b.ccy == port_json["reporting_currency"] else "TRANSLATED_UNHEDGED (ECB fixing u(g))"))
    if b.basis == "PRICE_RETURN" and "M-B6" not in MUT:
        return None, lin, St([("INSUFFICIENT_DATA", "MISSING_BENCHMARK", "BENCHMARK_NOT_TOTAL_RETURN")])
    return b, lin, St()


def bench_R(w, b, R, g):
    """L_R(g) and its state, with the benchmark leg's lag (Ruling 5.3)."""
    L, st, e, m = b.at(g)
    if "M-B1" in MUT:
        x, sx, u, mx = F(1), St(), None, 0
    else:
        gx = g - P1.ONE if "M-B2" in MUT else g
        x, sx, u, mx = w.fx_fixing(b.ccy, R, gx)
    st = St().add(st).add(sx)
    val = None if (L is None or x is None or st.level() == 2) else L * x
    lag = max(m if m is not None else 0, mx if (mx is not None and b.ccy != R) else 0)
    return val, st, e, u, lag


# ---- comparability (Ruling 8.2, 8.3 as of risk/1.1) -------------------------------------------------
def portfolio_inputs(w, port, g):
    """Calendars of listings held at g, whether any translation is needed at g, and the leg's lag at g."""
    cash, qty = port.holdings(g)
    cals, needs_fx, lag, listing_days = set(), False, 0, []
    for l, q in qty.items():
        if q == 0:
            continue
        cals.add(w.listing_cal[l])
        _, _, p, m = w.prices[l].at(g)
        lag = max(lag, m or 0)
        listing_days.append((w.listing_cal[l], p))
        c = w.listing_ccy[l]
        if c != port.R:
            needs_fx = True
            lag = max(lag, w.fx_fixing(c, port.R, g)[3] or 0)
    for c, a in cash.items():
        if a != 0 and c != port.R:
            needs_fx = True
            lag = max(lag, w.fx_fixing(c, port.R, g)[3] or 0)
    return cals, needs_fx, lag, listing_days


def comparability(w, port, b, dates):
    p_set, b_set, points = set(), set(), []
    for g in dates:
        cals, fxp, lp, _ = portfolio_inputs(w, port, g)
        p_set |= cals | ({w.ecb_id} if fxp and "M-B11" not in MUT else set())
        _, _, _, _, lb = bench_R(w, b, port.R, g)
        b_set |= {b.cal.id} | ({w.ecb_id} if b.ccy != port.R and "M-B11" not in MUT else set())
        points.append({"date": g.isoformat(), "portfolio_lag": lp, "benchmark_lag": lb})
    seam = None
    if (p_set or "M-B13" in MUT) and p_set != b_set:
        gn = dates[-1]
        cals, fxp, _, listing_days = portfolio_inputs(w, port, gn)
        p_inst = [w.instant(c, d) for c, d in listing_days]
        if fxp:
            p_inst.append(w.instant(w.ecb_id, _u_any(w, port, gn)))
        _, _, e, u, _ = bench_R(w, b, port.R, gn)
        b_inst = [w.instant(b.cal.id, e)] + ([w.instant(w.ecb_id, u)] if b.ccy != port.R and u else [])
        off = max((abs((p - q).total_seconds()) // 60 for p in p_inst for q in b_inst), default=None)
        seam = {"portfolio_calendars": sorted(p_set), "benchmark_calendars": sorted(b_set),
                "max_offset_minutes_at_last_grid_date": None if off is None else int(off)}
    lagged = [pt for pt in points if pt["portfolio_lag"] != pt["benchmark_lag"]]
    if "M-B12" in MUT:
        lagged = []
    return {"class": "LIMITED" if (seam or lagged) else "FULL", "seam": seam,
            "lagged": {"count": len(lagged), "of": len(points), "points": lagged}}


def _u_any(w, port, g):
    """The ECB fixing date the portfolio uses at g (the latest fixing day <= g with every needed quote)."""
    cash, qty = port.holdings(g)
    ccys = {c for c, a in cash.items() if a != 0 and c != port.R} | \
           {w.listing_ccy[l] for l, q in qty.items() if q != 0 and w.listing_ccy[l] != port.R}
    us = [w.fx_fixing(c, port.R, g)[2] for c in ccys]
    return min(us)


# ---- decomposition view (Ruling 6.9 as of risk/1.1; performance Ruling 2.4 item 3) ------------------
Q12 = 10 ** 12


def _half_up_quanta(x):
    k = x * Q12
    s = 1 if k >= 0 else -1
    return s * int(abs(k) + F(1, 2))


def _q(n):
    s = "-" if n < 0 else ""
    n = abs(n)
    return f"{s}{n // Q12}.{str(n % Q12).zfill(12)}"


def decomposition(total, parts):
    """Largest remainder: parts floored to the quantum, the shortfall to the largest remainders, ties in order."""
    T = _half_up_quanta(total)
    fl = [(p * Q12).__floor__() for p in parts]
    rem = [p * Q12 - f for p, f in zip(parts, fl)]
    short = T - sum(fl)
    order = sorted(range(len(parts)), key=lambda i: (-rem[i], i))
    for i in order[:short]:
        fl[i] += 1
    return _q(T), [_q(x) for x in fl]


# ---- the metrics -------------------------------------------------------------------------------------
def metric2(w, port, pj, item, E, version):
    kind, freq, req = item["kind"], item["frequency"], item["request"]
    if kind in ("volatility", "downside_deviation", "max_drawdown", "sharpe", "sortino", "return_series", "risk_free_rates") \
            and kind != "risk_free_rates":
        res = P1.metric(port, kind, freq, req, E)
        if "M-B20" in MUT and resolve_benchmark(w, pj, version)[2].level() == 2:
            res.update(state="INSUFFICIENT_DATA", reason="MISSING_BENCHMARK", value=None, exact=None)
            res.pop("exact_square", None), res.pop("sign", None)
        return res
    if kind == "risk_free_rates":
        if "M-B9" in MUT:
            _orig = P1.RiskFree.per_day
            P1.RiskFree.per_day = lambda self, q: (q / 100) / 360 if self.s["quote_type"] == "BANK_DISCOUNT" else _orig(self, q)
            try:
                return P1.metric(port, kind, freq, req, E)
            finally:
                P1.RiskFree.per_day = _orig
        return P1.metric(port, kind, freq, req, E)

    wnd, s = P1.build(port, req, freq, E)
    res = {"kind": kind, "frequency": freq, "request": req, "requested_base": wnd["requested_base"].isoformat()}
    b, lin, bst = resolve_benchmark(w, pj, version)
    res["benchmark"] = lin
    st = St().add(bst)
    if s is None:
        st.add(wnd["refusal"])
        res.update(state=st.state(), reason=st.reason(), details=st.details(), value=None, effective_window=None,
                   comparability=None)
        return res
    pts, n = wnd["points"], len(s)
    res["effective_window"] = {"base_date": pts[0].isoformat(), "last_period_end": pts[-1].isoformat(),
                               "observation_count": n, "stub_start_days": (pts[0] - wnd["requested_base"]).days,
                               "stub_end_days": (E - pts[-1]).days}
    if "max_available_start" in wnd:      # (cp4_golden/1.9-part3) the MAX_AVAILABLE lineage, as for every metric
        res["effective_window"]["max_available_start"] = wnd["max_available_start"]
    value = None
    used = pts if (kind in STATISTICS or "M-B7" in MUT) else [pts[0], pts[-1]]
    if b is not None:
        LR = {}
        for g in used:
            v, sg, _, _, _ = bench_R(w, b, port.R, g)
            st.add(sg)
            LR[g] = v
    if kind in STATISTICS:
        sst, nlim = P1.series_state(s)
        st.add(sst).add(P1.count_state(n, freq))
        res["thresholds"] = {"insufficient_below": P1.N1[freq], "available_from": P1.N3[freq]}
        if nlim:
            res["stale_period_count"] = nlim
    else:
        f, tst = port.twr(pts[0], pts[-1])
        st.add(St([c for c in tst.causes]))
        res["thresholds"] = None
    rf = None
    if kind == "alpha_jensen":
        R = "USD" if "M-B17" in MUT else port.R
        if R not in w.rf:
            st.causes.append(("INSUFFICIENT_DATA", None, "NO_RISK_FREE_SOURCE"))
        else:
            if "M-B9" in MUT:
                _orig = P1.RiskFree.per_day
                P1.RiskFree.per_day = lambda self, q: (q / 100) / 360 if self.s["quote_type"] == "BANK_DISCOUNT" else _orig(self, q)
            try:
                rf = [w.rf[R].period(x["start"], x["end"]) for x in s]
            finally:
                if "M-B9" in MUT:
                    P1.RiskFree.per_day = _orig
            for q in rf:
                st.add(q[1])
    if st.level() < 2 and b is not None:
        A = P1.A[freq]
        if kind in STATISTICS:
            r = [x["r"] for x in s]
            bb = [LR[g1] / LR[g0] - 1 for g0, g1 in zip(pts, pts[1:])]
            a = [x - y for x, y in zip(r, bb)]
            if kind in ("beta", "r_squared", "alpha_jensen") and "M-B3" in MUT:
                rr = [x - q for x, q in zip(r, [w.rf[port.R].period(x["start"], x["end"])[0] for x in s])]
                bx = [y - q for y, q in zip(bb, [w.rf[port.R].period(x["start"], x["end"])[0] for x in s])]
            else:
                rr, bx = r, bb
            mr, mb = P1.mean(rr), P1.mean(bx)
            Srb = sum(((x - mr) * (y - mb) for x, y in zip(rr, bx)), F(0))
            Sbb = sum(((y - mb) ** 2 for y in bx), F(0))
            Srr = sum(((x - mr) ** 2 for x in rr), F(0))
            if kind in ("beta", "r_squared", "alpha_jensen") and Sbb == 0:
                st.causes.append(("INSUFFICIENT_DATA", None, "ZERO_BENCHMARK_VARIANCE"))
            elif kind == "r_squared" and Srr == 0 and "M-B21" in MUT:
                value = ("rational", F(0))
            elif kind == "r_squared" and Srr == 0:
                st.causes.append(("INSUFFICIENT_DATA", None, "ZERO_PORTFOLIO_VARIANCE"))
            elif kind in ("beta", "r_squared", "alpha_jensen"):
                beta = Srb / Srr if ("M-B14" in MUT and Srr != 0) else Srb / Sbb
                if kind == "beta":
                    value = ("rational", beta)
                    res["v_beta"] = frac((Srr - beta * Srb) / ((n - 2) * Sbb))
                elif kind == "r_squared":
                    r2 = Srb ** 2 / (Sbb * Srr)
                    if "M-B15" in MUT:
                        r2 = 1 - (1 - r2) * (n - 1) / (n - 2)
                    value = ("rational", r2)
                else:
                    if "M-B16" in MUT:
                        value = ("rational", A * (P1.mean(r) - beta * P1.mean(bb)))
                    else:
                        dbar = P1.mean([x - q[0] for x, q in zip(r, rf)])
                        xbar = P1.mean([y - q[0] for y, q in zip(bb, rf)])
                        value = ("rational", A * (dbar - beta * xbar))
            else:
                ma = P1.mean(a)
                va = sum(((x - ma) ** 2 for x in a), F(0)) / (n if "M-B5" in MUT else n - 1)
                if kind == "tracking_error":
                    value = ("sqrt", 1, A * va)
                elif va == 0:
                    st.causes.append(("INSUFFICIENT_DATA", None, "ZERO_TRACKING_ERROR"))
                elif "M-B8" in MUT:
                    tw = (port.twr(pts[0], pts[-1])[0] - 1) - (LR[pts[-1]] / LR[pts[0]] - 1)
                    value = ("sqrt", (tw > 0) - (tw < 0), tw ** 2 / (A * va))
                else:
                    value = ("sqrt", (ma > 0) - (ma < 0), A * ma ** 2 / va)
        else:
            P = port.twr(pts[0], pts[-1])[0] - 1
            base_level = bench_R(w, b, port.R, wnd["requested_base"])[0] if "M-B23" in MUT else LR[pts[0]]
            B = LR[pts[-1]] / base_level - 1
            if kind == "benchmark_return":
                value = ("rational", B)
            else:
                AR = (1 + P) / (1 + B) - 1 if "M-B4" in MUT else P - B
                value = ("rational", AR)
                tot, (vb, va_) = decomposition(P, [B, AR])
                res["decomposition_view"] = {"portfolio_twr": tot, "benchmark_return": vb, "active_return": va_}
    if st.level() == 2:
        value = None
        res.pop("decomposition_view", None)
        res.pop("v_beta", None)
    res.update(state=st.state(), reason=st.reason(), details=st.details())
    if value is None:
        res.update(value=None, exact=None)
    elif value[0] == "rational":
        res.update(value=P1.present_rational(value[1]), exact=frac(value[1]))
    else:
        txt, gap = P1.present_sqrt(value[1], value[2])
        res.update(value=txt, exact=None, exact_square=frac(value[2]), sign=(value[1] if value[2] != 0 else 0))
        res["_boundary_distance_quanta"] = gap
    if kind in TWO_LEG:
        res["comparability"] = None if (st.level() == 2 or b is None) else comparability(w, port, b, used)
    return res


def derive(fx):
    w = World2(fx)
    out = {}
    for p in fx["portfolios"]:
        port = P1.Portfolio(p, w)
        for a in p["assertions"]:
            out[a["id"]] = [metric2(w, port, p, x, D(a["as_of"]), a.get("selection_log_version", 0)) for x in a["expect"]]
    return out


COMPARED = ["state", "reason", "value", "exact", "exact_square", "sign", "requested_base", "effective_window", "thresholds",
            "benchmark", "comparability", "v_beta", "decomposition_view", "stale_period_count", "rates",
            "peak_date", "trough_date", "recovery_date"]


def diff(exp, got):
    out = [k for k in COMPARED if (k in exp or k in got) and exp.get(k) != got.get(k)]
    own = sorted(x for x in got.get("details", []) if x in RISK_DETAILS)
    if "details_include" in exp and own != sorted(exp["details_include"]):
        out.append("details_include")
    return out


BENCHMARK_KINDS = TWO_LEG | {"benchmark_return"}


def expected(a, e):
    """An item's expectation, with the assertion-level 'benchmark_expected' applied to benchmark-dependent kinds."""
    if e["kind"] in BENCHMARK_KINDS and "benchmark" not in e and "benchmark_expected" in a:
        return dict(e, benchmark=a["benchmark_expected"])
    return e


def check(fx, out, quiet=False):
    bad = 0
    for p in fx["portfolios"]:
        for a in p["assertions"]:
            if len(a["expect"]) != len(out[a["id"]]):
                bad += 1
                print(f"MISMATCH {a['id']}: item count")
            for exp, got in zip((expected(a, e) for e in a["expect"]), out[a["id"]]):
                for k in diff(exp, got):
                    bad += 1
                    if not quiet:
                        print(f"MISMATCH {a['id']} {exp['kind']} {exp['frequency']} {k}: fixture={exp.get(k)!r} calculator={got.get(k)!r}")
    if not quiet:
        gaps = [g for items in out.values() for it in items for g in [it.get("_boundary_distance_quanta")] if g is not None]
        if gaps:
            lo = min(gaps)
            print("smallest distance of a square-root value from a rounding boundary:", P1.present_rational(lo),
                  "quanta (", "OK" if lo > F(1, 10 ** 18) else "TOO CLOSE", "; need > 1e-18 )")
            bad += 0 if lo > F(1, 10 ** 18) else 1
        print("CHECK", "FAILED" if bad else "PASSED", "-", bad, "difference(s)")
    return bad


def mutations(fx):
    """Each mutation must change EXACTLY the items that name it in 'bites' (and every item must name one)."""
    global MUT
    MUT = set()
    base = derive(fx)
    bad = 0
    items = [(a["id"], i, e) for p in fx["portfolios"] for a in p["assertions"] for i, e in enumerate(a["expect"])]
    for aid, i, e in items:
        if not e.get("bites"):
            bad += 1
            print(f"NO MUTATION NAMED for {aid}[{i}] {e['kind']}")
    for mid in CATALOG:
        MUT = {mid}
        mut = derive(fx)
        changed = {(aid, i) for aid, i, e in items if diff(base[aid][i], mut[aid][i])}
        named = {(aid, i) for aid, i, e in items if mid in e.get("bites", [])}
        ok = changed == named
        bad += not ok
        print(("ok  " if ok else "BAD ") + f"{mid}: changes {len(changed)} item(s); fixture names {len(named)}"
              + ("" if ok else f"  unnamed={sorted(changed - named)} not-bitten={sorted(named - changed)}"))
    MUT = set()
    print("MUTATIONS", "AGREE" if not bad else "DISAGREE")
    return bad


def closed_forms(out):
    """Q1 (US benchmark, constant rate), Q2-T1 (identity) and Q4 (cash) from the cycle sums of the derivation, section 3."""
    r = [F(1, 25), F(-3, 104), F(-3, 101), F(1, 49)]
    b = [F(3, 100), F(-2, 103), F(-2, 101), F(1, 99)]
    c = F(7, 10000)
    mr, mb = sum(r) / 4, sum(b) / 4
    srb = sum((x - mr) * (y - mb) for x, y in zip(r, b))
    sbb = sum((y - mb) ** 2 for y in b)
    srr = sum((x - mr) ** 2 for x in r)
    beta = srb / sbb
    want = {("Q1-B1", 0): beta, ("Q1-B1", 1): srb ** 2 / (sbb * srr), ("Q1-B1", 2): 52 * ((mr - c) - beta * (mb - c)),
            ("Q1-B2", 0): beta, ("Q1-B2", 1): srb ** 2 / (sbb * srr), ("Q1-B2", 2): 52 * ((mr - c) - beta * (mb - c)),
            ("Q2-T1", 0): F(1), ("Q2-T1", 1): F(1), ("Q2-T1", 2): F(0),
            ("Q4-C1", 0): F(0), ("Q4-C1", 2): 52 * (-c)}
    a = [-y for y in b]
    ma = sum(a) / 4
    want_sq = {("Q1-B1", 3): 52 * 13 * sum((x - y - (mr - mb)) ** 2 for x, y in zip(r, b)) / 51,
               ("Q1-B2", 3): 52 * 39 * sum((x - y - (mr - mb)) ** 2 for x, y in zip(r, b)) / 155,
               ("Q4-C1", 3): 52 * 13 * sum((x - ma) ** 2 for x in a) / 51}
    bad = 0
    for (aid, i), v in want.items():
        ok = F(out[aid][i]["exact"]) == v
        bad += not ok
        print(("ok  " if ok else "BAD ") + f"{aid}[{i}] {out[aid][i]['kind']} = {frac(v)}")
    for (aid, i), v in want_sq.items():
        ok = F(out[aid][i]["exact_square"]) == v
        bad += not ok
        print(("ok  " if ok else "BAD ") + f"{aid}[{i}] {out[aid][i]['kind']}^2 = {frac(v)}")
    print("CLOSED FORMS", "AGREE" if not bad else "DISAGREE")
    return bad


if __name__ == "__main__":
    fixture = json.load(open(sys.argv[1]))
    if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
        fixture["portfolios"] = json.load(open(sys.argv[2]))      # authoring aid: inputs split in two files
    results = derive(fixture)
    status = 0
    if "--closed" in sys.argv:
        status |= 1 if closed_forms(results) else 0
    if "--mutations" in sys.argv:
        status |= 1 if mutations(fixture) else 0
    if "--check" in sys.argv:
        status |= 1 if check(fixture, results) else 0
    if not any(x in sys.argv for x in ("--check", "--mutations", "--closed")):
        print(json.dumps(results, indent=1, default=lambda x: frac(x) if isinstance(x, F) else str(x)))
    sys.exit(status)
