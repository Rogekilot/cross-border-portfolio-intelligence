"""Independent calculator for cp4_golden part 4 (1.0-part4, risk/1.9: the risk-free quote at instant t in Current
mode, and the default view of a benchmark-relative statistic).

Author: quant-analyst, 2026-10-03. Convention set: risk/1.9, on performance/1.12 and market-data/1.14.

A CALCULATOR for CP4_GOLDEN_PART4_DERIVATION.md, written from methodology/CP4_RISK_CONVENTIONS.md. It is not an
engine and reads no engine output:

- standard library only; it imports nothing from src/. It reuses the part-3 calculator (which reuses parts 2 and
  1) and adds what part 4 needs:
  - risk Ruling 5.8 items 4, 5 and 7 for the risk-free leg: in Current mode at t, a quote is used for a period only
    if it is published at or before t AND its file is in M_t; a publication date in (f_k, g_{k-1}] counts as missed
    only if it is due at t (published at or before t), whether or not its file has arrived;
  - the declared files of market_data.retrieval (one coverage interval and retrieval time per file);
- it reads the fixture's INPUT blocks and recomputes every expected item from them in exact rationals.

Usage (read-only; it writes no file):
  python3 cp4_part4_calculator.py FIXTURE.json               print every derived result as JSON
  python3 cp4_part4_calculator.py FIXTURE.json --check       compare with the fixture's expect items
  python3 cp4_part4_calculator.py FIXTURE.json --mutations   every mutation changes EXACTLY the items naming it
  python3 cp4_part4_calculator.py FIXTURE.json --retrieval   the declared files against market-data Ruling 3.1, and
                                                             late_rows against M_t at every Current-mode instant
"""

import datetime as dt
import importlib.util
import json
import os
import sys
from fractions import Fraction
from zoneinfo import ZoneInfo

_spec = importlib.util.spec_from_file_location("cp4p3", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                     "cp4_part3_calculator.py"))
P3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P3)
P2, P1 = P3.P2, P3.P1
D, St, frac = P1.D, P1.St, P1.frac
UTC = dt.timezone.utc

CATALOG = {
    "M-D1": "Current mode reads the risk-free quote by date, ignoring t and M_t (the historical rule at D_c(t))",
    "M-D2": "a quote that is due at t but whose file is not yet in M_t is not counted as missed",
    "M-D3": "a quote not yet due at t (published after t) is counted as missed",
    "M-D4": "Current mode applies the publication test to the risk-free quote but not M_t (a file retrieved after t is "
            "read)",
    "M-D5": "the risk-free return of a period uses the latest quote on or before the period's END g_k, not its start "
            "g_{k-1} (Ruling 4.3's rejected alternative)",
    "M-D6": "the default view falls back on ANY INSUFFICIENT_DATA default request, benchmark-side causes included",
    "M-D7": "the default view never falls back for a benchmark-relative statistic (the fallback applied to single-leg "
            "metrics only)",
    "M-D8": "a request whose base is before inception is answered from inception under the requested label, not "
            "refused (Rulings 2.3 and 7.2)",
    "M-D9": "a MAX_AVAILABLE result of a benchmark-relative statistic omits max_available_start from its effective "
            "window (Ruling 2.3)",
    "M-D10": "a benchmark level missing before the series' first calculation day is back-filled with the first level, "
             "not refused (Ruling 5.2)",
}
MUT = set()
CTX4 = {"cal": None, "files": None}


def ts(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def available(cal, d):
    """The availability instant of row d on calendar cal: scheduled close, or publication (ECB, risk-free)."""
    if cal["kind"] == "EXCHANGE_SESSIONS":
        t = cal["close"]["default"]
    elif cal["kind"] == "ECB_FIXINGS":
        t = cal["fixing"]["publication"]
    else:
        t = cal["publication"]["time"]
    h, m = map(int, t.split(":"))
    return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=ZoneInfo(cal["timezone"])).astimezone(UTC)


def retrieved(series, d):
    """The retrieval time of the file holding row d of the series (None: no file covers d)."""
    for f in CTX4["files"]:
        if f["series"] == series and D(f["coverage"][0]) <= d <= D(f["coverage"][1]):
            return ts(f["retrieval_time"])
    return None


# ---- risk Ruling 4.3 / 4.4 with Ruling 5.8 items 4, 5, 7 -------------------------------------------------------
def period4(self, a, b):
    """rf for (a, b] and its state, quote date f and missed count m."""
    t = None if "M-D1" in MUT else P3.CTX["t"]
    k = b if "M-D5" in MUT else a                       # Ruling 4.3: the quote known when the period starts
    cal = CTX4["cal"][self.cal.id]
    pub = lambda x: available(cal, x)
    in_mt = lambda x: (retrieved(self.s["series_id"], x) or dt.datetime.max.replace(tzinfo=UTC)) <= t

    def usable(x):                                      # item 4 (published) and item 7 (in M_t)
        return t is None or (pub(x) <= t and ("M-D4" in MUT or in_mt(x)))

    def missed(y):                                      # item 5: not yet due is not missed; due but late is missed
        if t is None or "M-D3" in MUT:
            return True
        if pub(y) > t:
            return False
        return not ("M-D2" in MUT and not in_mt(y))

    qs = [x for x in self.row_days if x <= k and usable(x)]
    if not qs:
        return None, St([("INSUFFICIENT_DATA", None, "RISK_FREE_UNAVAILABLE")]), None, None
    f = qs[-1]
    assert self.cal.lo <= f and k <= self.cal.hi, ("CALENDAR_COVERAGE_GAP", self.cal.id)
    m = sum(1 for y in self.cal.days if f < y <= k and missed(y))
    st = P1.fresh(m, "RF")
    if st.level() == 2:
        return None, st, f, m
    return self.per_day(self.rows[f]) * (b - a).days, st, f, m


P1.RiskFree.period = period4


# ---- the other mutations of part 4 --------------------------------------------------------------------------------
_window3 = P1.window


def window4(port, req, freq, E):
    out = _window3(port, req, freq, E)
    if "M-D8" in MUT and "refusal" in out and "WINDOW_BEFORE_INCEPTION" in out["refusal"].details():
        pts = [d for d in P1.daterange(port.I0, E) if P1.on_grid(freq, d)]
        if len(pts) >= 2:
            return {"requested_base": out["requested_base"], "points": pts}
    return out


P1.window = window4

_bench_at = P3.Bench3.at


def bench_at4(self, g):
    L, st, e, m = _bench_at(self, g)
    if "M-D10" in MUT and L is None and "BENCHMARK_NOT_COVERING_WINDOW" in st.details() and self.row_days:
        e0 = self.row_days[0]
        return self.rows[e0], St(), e0, 0
    return L, st, e, m


P3.Bench3.at = bench_at4

_item = P3.item_result


def item4(w, p, item, E, version):
    res = _item(w, p, item, E, version)
    if "M-D9" in MUT and item["kind"] in P2.TWO_LEG and res.get("effective_window"):
        res["effective_window"].pop("max_available_start", None)
    return res


P3.item_result = item4

_default_view = P3.default_view


def default_view4(w, p, port, item, E, version):
    """Ruling 7.7 (1.6) is P3.default_view; M-D6 and M-D7 force or forbid its fallback."""
    saved = P3.MUT
    try:
        res = _default_view(w, p, port, item, E, version)
        if "M-D6" in MUT and not res["fallback"] and res["shown"]["state"] == "INSUFFICIENT_DATA":
            P3.MUT = {"M-C12"}
            res = _default_view(w, p, port, item, E, version)
        if "M-D7" in MUT and res["fallback"] and item["metric"] in P2.STATISTICS:
            P3.MUT = {"M-C13"}
            res = _default_view(w, p, port, item, E, version)
    finally:
        P3.MUT = saved
    return res


P3.default_view = default_view4


# ---- derive, check, mutations, retrieval ----------------------------------------------------------------------------
def derive(fx):
    md = fx["market_data"]
    CTX4["cal"] = {c["calendar_id"]: c for c in md["calendars"]}
    CTX4["files"] = md["retrieval"]["files"]
    P3.MUT = set()
    return P3.derive(fx)


def changed(a, b):
    """A result differs: any compared field (P3.diff), or its own risk detail names. The fixture asserts
    details_include, so a mutation that only adds or drops a detail (M-D2, M-D3 on a Sharpe item) must count."""
    own = lambda r: {x for x in r.get("details", []) if x in P3.RISK_DETAILS}      # a set, as details_include is
    return bool(P3.diff(a, b)) or own(a) != own(b)


def mutations(fx):
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
        moved = {(aid, i) for aid, i, e in items if changed(base[aid][i], mut[aid][i])}
        named = {(aid, i) for aid, i, e in items if mid in e.get("bites", [])}
        ok = moved == named
        bad += not ok
        print(("ok  " if ok else "BAD ") + f"{mid}: changes {len(moved)} item(s); fixture names {len(named)}"
              + ("" if ok else f"  unnamed={sorted(moved - named)} not-bitten={sorted(named - moved)}"))
    MUT = set()
    if sorted(CATALOG) != sorted(fx["mutation_catalog"]):
        bad += 1
        print("BAD  the fixture's mutation_catalog and the calculator's differ")
    print("MUTATIONS", "AGREE" if not bad else "DISAGREE")
    return bad


def retrieval_check(fx):
    """(a) every file is retrieved at or after the availability instant of each row it holds (market-data Ruling 3.1);
    (b) the files of one series have disjoint coverage and cover every row; (c) at each Current-mode instant t, the
    rows due at t but not in M_t are exactly the declared late_rows, and no row is in M_t before it is due."""
    md = fx["market_data"]
    CTX4["files"] = md["retrieval"]["files"]
    cals = {c["calendar_id"]: c for c in md["calendars"]}
    objs = {c["calendar_id"]: P1.Calendar(c) for c in md["calendars"]}
    series = {}
    for s in md["prices"]["series"]:
        series[s["listing_id"]] = (s["calendar"], D(s["first"]), D(s["last"]))
    for b in md["benchmarks"]:
        series[b["benchmark_id"]] = (b["calendar"], D(b["first"]), D(b["last"]))
    for r in md["risk_free"]["series"]:
        series[r["series_id"]] = (r["calendar"], D(r["first"]), D(r["last"]))
    ecb = [c for c in md["calendars"] if c["kind"] == "ECB_FIXINGS"][0]["calendar_id"]
    series["ECB"] = (ecb, D(md["fx"]["first"]), D(md["fx"]["last"]))
    instants = [ts(a["instant"]) for p in fx["portfolios"] for a in p["assertions"] if a.get("valuation_mode") == "CURRENT"]
    declared = {(ts(x["instant"]), x["series"], D(r)) for x in md["retrieval"]["late_rows"] for r in x["rows"]}
    bad, rows, late = 0, 0, set()
    for sid, (cid, first, last) in series.items():
        files = sorted((f for f in CTX4["files"] if f["series"] == sid), key=lambda f: f["coverage"][0])
        for f, g in zip(files, files[1:]):
            if D(g["coverage"][0]) <= D(f["coverage"][1]):
                bad += 1
                print(f"BAD  {sid}: files {f['file']} and {g['file']} overlap")
        for d in objs[cid].days:
            if not first <= d <= last:
                continue
            rows += 1
            a, r = available(cals[cid], d), retrieved(sid, d)
            if r is None:
                bad += 1
                print(f"BAD  {sid} {d}: no file holds the row")
                continue
            if r < a:
                bad += 1
                print(f"BAD  {sid} {d}: retrieved {r} before it is available {a} (market-data Ruling 3.1)")
            for t in instants:
                if a <= t < r:
                    late.add((t, sid, d))
    for x in sorted(late ^ declared):
        bad += 1
        print(f"BAD  late row {x[1]} {x[2]} at {x[0]}: {'not declared' if x in late else 'declared but not late'}")
    print(f"RETRIEVAL {'CONSISTENT' if not bad else 'INCONSISTENT'} - {rows} rows, {len(instants)} Current-mode "
          f"instant(s), {len(late)} late row(s) as declared, {bad} problem(s)")
    return bad


if __name__ == "__main__":
    fixture = json.load(open(sys.argv[1]))
    results = derive(fixture)
    status = 0
    if "--mutations" in sys.argv:
        status |= 1 if mutations(fixture) else 0
    if "--check" in sys.argv:
        status |= 1 if P3.check(fixture, results) else 0
    if "--retrieval" in sys.argv:
        status |= 1 if retrieval_check(fixture) else 0
    if not any(x in sys.argv for x in ("--check", "--mutations", "--retrieval")):
        print(json.dumps(results, indent=1, default=lambda x: frac(x) if isinstance(x, Fraction) else str(x)))
    sys.exit(status)
