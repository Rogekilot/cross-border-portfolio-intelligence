"""Independent calculator for cp3_golden part 3 (FIFO lots, realized and unrealized gains).

Author: quant-analyst, 2026-10-01. Conventions: ledger-replay/1.5 (FIFO mode, sections 0.5 and
0.6), performance/1.6, market-data/1.10, lot relief FIFO/1. (1.1-part3 adds acquired_on: kind
RECORDED, and P20.)

This is a CALCULATOR for CP3_GOLDEN_PART3_DERIVATION.md. It is not the engine and it reads no
engine output:

- standard library only (fractions, decimal); it imports nothing from src/;
- the FIFO fold below is written from ledger-replay/1.4 section 0.5 alone. It handles only what
  part 3 exercises (BUY, SELL, SPLIT, OPENING_POSITION, external TRANSFER_IN, internal transfer
  pairs, REVERSAL). Flags, opaque lots and same-day cycles are not exercised and not implemented;
  the fold asserts that none occurs;
- prices and FX are the fixture's synthetic step series, typed in by hand.

Re-run with `python3 methodology/fixtures/cp3_golden/derivation/cp3_part3_calculator.py`.
Exact values print as reduced fractions; presented values follow performance Ruling 2.2
(ROUND_HALF_UP to the minor unit; ratios to 1e-12).
"""

from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction as F


# ---------------------------------------------------------------------------- presentation
def frac(x):
    if x is None:
        return "None"
    return f"{x.numerator}/{x.denominator}" if x.denominator != 1 else str(x.numerator)


def _dec(x):
    with localcontext() as c:
        c.prec = 200
        return Decimal(x.numerator) / Decimal(x.denominator)


def pm(x):
    return str(_dec(x).quantize(Decimal("0.01"), ROUND_HALF_UP))


def pr(x):
    return str(_dec(x).quantize(Decimal("1e-12"), ROUND_HALF_UP))


def show(label, x, kind="money"):
    if x is None:
        print(f"  {label:66s} INSUFFICIENT")
        return
    print(f"  {label:66s} exact {frac(x):>22s}  presented {pm(x) if kind == 'money' else pr(x)}")


def apportion(total, parts):
    """performance Ruling 2.4 item 3: largest remainder, ties in line order. Money, 2 dp."""
    q = F(1, 100)
    t_hat = F(int(_dec(total).quantize(Decimal('0.01'), ROUND_HALF_UP) * 100), 100)
    floors = []
    for p in parts:
        n = p / q
        fl = n.numerator // n.denominator
        floors.append(F(fl) * q)
    short = int((t_hat - sum(floors)) / q)
    order = sorted(range(len(parts)), key=lambda i: (-(parts[i] - floors[i]), i))
    out = list(floors)
    for i in order[:short]:
        out[i] += q
    assert sum(out) == t_hat
    return t_hat, out


# ---------------------------------------------------------------------------- FX (ECB synthetic)
# Period A: fixings to 2025-03-31; period B: from 2025-04-01 (part 1 market_data).
ECB = {"A": {"USD": F("1.0400"), "HKD": F("8.1120"), "CNY": F("7.4880")},
       "B": {"USD": F("1.0880"), "HKD": F("8.5000"), "CNY": F("7.8880")}}


FIRST_FIXING = "2025-01-02"  # the synthetic ECB file starts here; no observation before it


def X(c, r, date):
    """Units of r per unit of c on a date (market-data Ruling 1.3/1.6: latest fixing <= date);
    X(r->r) = 1; None when M holds no observation at or before the date (MISSING_FX_HISTORY)."""
    if c == r:
        return F(1)
    if date < FIRST_FIXING:
        return None
    per = "A" if date <= "2025-03-31" else "B"
    return ECB[per][r] / ECB[per][c]


assert X("HKD", "USD", "2025-01-08") == F(5, 39) and X("HKD", "USD", "2025-04-02") == F(16, 125)
assert X("HKD", "CNY", "2025-04-01") == F(116, 125)


# ---------------------------------------------------------------------------- the FIFO fold
def fold(events, D, L):
    """ledger-replay/1.4 section 0.5 (FIFO/1) for the event shapes part 3 uses.

    events: dicts with seq, id, acct, type, date, and as needed listing, qty, amount, ccy,
    cost_basis, cp (counterparty), rev (reversed id), split (n, o).
    Returns (books, reliefs): books[(acct, listing)] = list of lots; reliefs[event_id] = list of
    portions. A lot / portion is a dict: origin, path (tuple of hop tuples
    (from_acct, out_id, in_id, date)), a, kind, k, c (unit cost or None), u (units).
    """
    inv = [e for e in events if e["seq"] <= L]
    reversed_ids = {e["rev"] for e in inv if e["type"] == "REVERSAL"}
    live = [e for e in inv if e["type"] != "REVERSAL" and e["id"] not in reversed_ids]
    inc = sorted((e for e in live if e["date"] <= D),
                 key=lambda e: (e["date"], 0 if e["type"] == "SPLIT" else 1, e["seq"]))
    books, reliefs = {}, {}
    days = sorted({e["date"] for e in inc})
    for d in days:
        today = [e for e in inc if e["date"] == d]
        # 0.5.7: a split rescales every start-of-day lot (rank 0, the start of its date).
        for e in today:
            if e["type"] == "SPLIT":
                n, o = e["split"]
                key = (e["acct"], e["listing"])
                q0 = sum((l["u"] for l in books.get(key, [])), F(0))
                assert (q0 * n / o).denominator == 1, "non-integral split not exercised"
                books[key] = [dict(l, u=l["u"] * n / o, c=None if l["c"] is None else l["c"] * o / n)
                              for l in books.get(key, [])]
        # Pairing (0.5.6): within each matching group, in ascending event_id order.
        outs = sorted((e for e in today if e["type"] == "TRANSFER_OUT" and e.get("cp")), key=lambda e: e["id"])
        ins = sorted((e for e in today if e["type"] == "TRANSFER_IN" and e.get("cp")), key=lambda e: e["id"])
        pair, used = {}, set()
        for o_ in outs:
            for i_ in ins:
                if i_["id"] in used:
                    continue
                if (i_["acct"] == o_["cp"] and i_["cp"] == o_["acct"] and i_["listing"] == o_["listing"]
                        and i_["qty"] == o_["qty"] and i_["ccy"] == o_["ccy"]):
                    pair[o_["id"]] = i_
                    used.add(i_["id"])
                    break
        assert len(used) == len(ins) == len(outs), "every internal leg is paired in part 3"
        keys = sorted({(e["acct"], e["listing"]) for e in today if e.get("listing") and e["type"] != "SPLIT"})
        acq = {k: [] for k in keys}
        dep = {k: [] for k in keys}
        need_src = {k: set() for k in keys}
        for e in today:
            k = (e["acct"], e.get("listing"))
            t = e["type"]
            if t == "BUY":
                acq[k].append(dict(origin=e["id"], path=(), a=d, kind="TRADE", k=e["ccy"],
                                   c=e["amount"] / e["qty"], u=e["qty"]))
            elif t in ("OPENING_POSITION",) or (t == "TRANSFER_IN" and not e.get("cp")):
                cb = e.get("cost_basis")
                ao = e.get("acquired_on")  # ledger-replay/1.5 Ruling 0.6
                acq[k].append(dict(origin=e["id"], path=(), a=ao or d, kind="RECORDED" if ao else "ENTRY",
                                   k=None if cb is None else e["ccy"],
                                   c=None if cb is None else cb / e["qty"], u=e["qty"]))
            elif t in ("SELL",) or (t == "TRANSFER_OUT"):
                dep[k].append(e)
            elif t == "TRANSFER_IN":
                need_src[k].add((e["cp"], e["listing"]))
        carried_in = {k: [] for k in keys}
        done = set()
        pending = list(keys)
        while pending:
            ready = [k for k in pending if all(s in done or s not in pending for s in need_src[k])]
            assert ready, "same-day cycle not exercised in part 3"
            k = ready[0]
            pending.remove(k)
            done.add(k)
            cand = books.get(k, []) + acq[k] + carried_in[k]
            q_dep = sum((e["qty"] for e in dep[k]), F(0))
            U = sum((l["u"] for l in cand), F(0))
            assert q_dep <= U, "negative quantity not exercised"
            if q_dep == 0:
                books[k] = cand
                continue
            # 0.5.4: groups by acquisition date ascending; pro rata within a group.
            relieved, remaining, needv = [], [], q_dep
            for a in sorted({l["a"] for l in cand}):
                group = [l for l in cand if l["a"] == a]
                ug = sum((l["u"] for l in group), F(0))
                if needv >= ug:
                    relieved += [dict(l) for l in group]
                    needv -= ug
                elif needv > 0:
                    for l in group:
                        take = needv * l["u"] / ug
                        relieved.append(dict(l, u=take))
                        remaining.append(dict(l, u=l["u"] - take))
                    needv = F(0)
                else:
                    remaining += [dict(l) for l in group]
            # 0.5.5: each depleting event gets q_e / q_dep of every relieved portion.
            for e in dep[k]:
                share = e["qty"] / q_dep
                portions = [dict(p, u=p["u"] * share) for p in relieved]
                reliefs[e["id"]] = portions
                if e["type"] == "TRANSFER_OUT" and e.get("cp"):
                    in_leg = pair[e["id"]]
                    hop = (e["acct"], e["id"], in_leg["id"], d)
                    rk = (in_leg["acct"], in_leg["listing"])
                    carried_in[rk] += [dict(p, path=p["path"] + (hop,)) for p in portions]
            books[k] = [l for l in remaining if l["u"] != 0]
    return books, reliefs


def basis(lots):
    if any(l["c"] is None for l in lots):
        return None
    return sum((l["u"] * l["c"] for l in lots), F(0))


def native_basis(lots):
    out = {}
    for l in lots:
        if l["c"] is None:
            return None
        out[l["k"]] = out.get(l["k"], F(0)) + l["u"] * l["c"]
    return out


def show_lots(label, lots, names):
    print(f"  {label}")
    for l in sorted(lots, key=lambda l: (l["a"], l["origin"], l["path"])):
        hops = " ".join(f"[{names.get(h[1], h[1])}->{names.get(h[2], h[2])} {h[3]}]" for h in l["path"])
        b = None if l["c"] is None else l["u"] * l["c"]
        print(f"     {names.get(l['origin'], l['origin']):8s} a={l['a']} {l['kind']:5s} k={l['k']} "
              f"u={frac(l['u']):>7s} c={frac(l['c']):>7s} basis={frac(b):>8s} {hops}")


def c_R(l, R):
    """performance Ruling 3.7: reporting-currency unit cost, or None with a cause."""
    if l["c"] is None:
        return None, "UNKNOWN_BASIS"
    if l["kind"] in ("TRADE", "RECORDED"):  # performance 3.7 / 3.7a
        x = X(l["k"], R, l["a"])
        if x is None:
            return None, "MISSING_FX_HISTORY"
        return l["c"] * x, None
    if l["k"] == R:
        return l["c"], None
    return None, "ACQUISITION_DATE_UNKNOWN"


def _cause(rs):
    """Reason by performance Ruling 1.5 (MISSING_COST_BASIS before MISSING_FX_HISTORY), with details."""
    ws = sorted({w for c, w in rs if c is None})
    code = "MISSING_COST_BASIS" if any(w != "MISSING_FX_HISTORY" for w in ws) else "MISSING_FX_HISTORY"
    return code + "/" + "+".join(ws)


def rg(sale, portions, R):
    """performance Ruling 3.8: (native or cause, reporting or cause)."""
    A, ce, d = sale["amount"], sale["ccy"], sale["date"]
    known = [p for p in portions if p["c"] is not None]
    if len(known) < len(portions):
        nat = "MISSING_COST_BASIS"
    elif any(p["k"] != ce for p in known):
        nat = "UNSUPPORTED_ASSET/MIXED_CURRENCY_BASIS"
    else:
        nat = A - sum((p["u"] * p["c"] for p in portions), F(0))
    rs = [c_R(p, R) for p in portions]
    if any(c is None for c, _ in rs):
        rep = _cause(rs)
    else:
        rep = A * X(ce, R, d) - sum((p["u"] * c for p, (c, _) in zip(portions, rs)), F(0))
    return nat, rep


def ug(lots, price, listing_ccy, R, D):
    """performance Ruling 3.9: (MV_R, native UG or cause, reporting UG or cause)."""
    u = sum((l["u"] for l in lots), F(0))
    mv_c = u * price
    mv_R = mv_c * X(listing_ccy, R, D)
    nb = native_basis(lots)
    if nb is None:
        nat = "MISSING_COST_BASIS"
    elif set(nb) != {listing_ccy}:
        nat = "UNSUPPORTED_ASSET/MIXED_CURRENCY_BASIS"
    else:
        nat = mv_c - nb[listing_ccy]
    rs = [c_R(l, R) for l in lots]
    if any(c is None for c, _ in rs):
        rep = _cause(rs)
    else:
        rep = mv_R - sum((l["u"] * c for l, (c, _) in zip(lots, rs)), F(0))
    return mv_R, nat, rep


def ev(seq, id_, acct, type_, date, **kw):
    d = dict(seq=seq, id=id_, acct=acct, type=type_, date=date)
    for k_, v in kw.items():
        d[k_] = F(v) if k_ in ("qty", "amount", "cost_basis") and v is not None else v
    return d


def report_rg(label, sale, portions, R):
    nat, rep = rg(sale, portions, R)
    for nm, v in (("native", nat), ("R", rep)):
        if isinstance(v, str):
            print(f"  RG {label} {nm:6s}: {v}")
        else:
            show(f"RG {label} {nm}", v)


# ============================================================================ P1 (USD)
print("=== P1 (cp1_golden P1, L = 25; reporting USD) ===")
A1, A2, A3 = "A1", "A2", "A3"
AAPL, T0700, MSFT = "AAPL", "0700", "MSFT"
P1 = [
    ev(2, "E2", A1, "BUY", "2025-01-06", listing=AAPL, qty=50, amount=7500, ccy="USD"),
    ev(4, "E4", A2, "BUY", "2025-01-08", listing=T0700, qty=500, amount=17500, ccy="HKD"),
    ev(5, "E5", A1, "SPLIT", "2025-02-03", listing=AAPL, split=(4, 1)),
    ev(8, "E7", A1, "SELL", "2025-03-03", listing=AAPL, qty=50, amount=2250, ccy="USD"),
    ev(9, "E8", A1, "TRANSFER_IN", "2025-03-10", listing=MSFT, qty=10, ccy="USD", cost_basis=None),
    ev(12, "X3", A1, "BUY", "2025-04-02", listing=T0700, qty=200, amount=7000, ccy="HKD"),
    ev(13, "X4", A3, "BUY", "2025-05-05", listing=MSFT, qty=5, amount=2000, ccy="USD"),
    ev(19, "X10", A3, "BUY", "2025-06-03", listing=MSFT, qty=5, amount=2100, ccy="USD"),
    ev(20, "X11", A3, "SELL", "2025-06-10", listing=MSFT, qty=4, amount=1720, ccy="USD"),
    ev(21, "X12", A1, "SELL", "2025-06-16", listing=AAPL, qty=40, amount=2000, ccy="USD"),
    ev(22, "X13", A1, "TRANSFER_OUT", "2025-06-16", listing=AAPL, qty=110, ccy="USD", cp=A3),
    ev(23, "X14", A3, "TRANSFER_IN", "2025-06-16", listing=AAPL, qty=110, ccy="USD", cp=A1),
]
names = {e["id"]: e["id"] for e in P1}
b, r = fold(P1, "2025-03-04", 25)
show_lots("lot book A1 AAPL at 03-04", b[(A1, AAPL)], names)
show("relief E7 basis", basis(r["E7"]))
report_rg("E7", P1[3], r["E7"], "USD")
show("remaining basis A1 AAPL 03-04", basis(b[(A1, AAPL)]))
show("UG A1 AAPL 03-04 (150 x 45)", 150 * F(45) - basis(b[(A1, AAPL)]))

b, r = fold(P1, "2025-06-30", 25)
show_lots("lot book A3 AAPL at 06-30", b[(A3, AAPL)], names)
show_lots("lot book A3 MSFT at 06-30", b[(A3, MSFT)], names)
show_lots("lot book A1 MSFT at 06-30", b[(A1, MSFT)], names)
print("  A1 AAPL lots at 06-30:", b.get((A1, AAPL)))
show("relief X11", basis(r["X11"]))
show("relief X12", basis(r["X12"]))
show("relief X13 (carried)", basis(r["X13"]))
report_rg("X11", P1[8], r["X11"], "USD")
report_rg("X12", P1[9], r["X12"], "USD")
d630 = "2025-06-30"
prices630 = {AAPL: F(50), MSFT: F(430), T0700: F(37)}
ccy = {AAPL: "USD", MSFT: "USD", T0700: "HKD"}
included, mv_all, mv_ex = F(0), F(0), F(0)
for key in [(A1, T0700), (A1, MSFT), (A2, T0700), (A3, AAPL), (A3, MSFT)]:
    mv_R, nat, rep = ug(b[key], prices630[key[1]], ccy[key[1]], "USD", d630)
    show(f"MV_R {key}", mv_R)
    print(f"     UG native {key}: {nat if isinstance(nat, str) else frac(nat) + ' -> ' + pm(nat)}")
    print(f"     UG R      {key}: {rep if isinstance(rep, str) else frac(rep) + ' -> ' + pm(rep)}")
    lots = b[key]
    nb = native_basis(lots)
    rb = [c_R(l, "USD") for l in lots]
    print(f"     remaining basis native {key}: {None if nb is None else {k: frac(v) for k, v in nb.items()}}; "
          f"R: {None if any(c is None for c, _ in rb) else frac(sum(l['u'] * c for l, (c, _) in zip(lots, rb)))}")
    mv_all += abs(mv_R)
    if isinstance(rep, str):
        mv_ex += abs(mv_R)
    else:
        included += rep
show("P1 UG total (included)", included)
show("P1 UG total excluded weight", mv_ex / mv_all, "ratio")
show("P1 RG total SI (E7 + X11 + X12)", F(375) + 120 + 500)
show("P1 RG total (03-31, 06-30] (X11 + X12)", F(120) + 500)
# Since-acquisition (performance Ruling 9.7) for the two HKD lots at 06-30.
for key, origin in [((A2, T0700), "E4"), ((A1, T0700), "X3")]:
    lot = [l for l in b[key] if l["origin"] == origin][0]
    V, K = lot["u"] * F(37), lot["u"] * lot["c"]
    Xa, XD = X("HKD", "USD", lot["a"]), X("HKD", "USD", d630)
    parts = [(V - K) * Xa, K * (XD - Xa), (V - K) * (XD - Xa)]
    tot = V * XD - K * Xa
    assert sum(parts) == tot
    t_hat, app = apportion(tot, parts)
    print(f"  since-acq {key} lot {origin}: total {frac(tot)} -> {pm(tot)}; parts "
          + ", ".join(f"{frac(p)} ({pm(p)})" for p in parts) + "; apportioned " + ", ".join(str(_dec(a)) for a in app))
# I-7 on A3 MSFT: RG + UG = proceeds + MV - costs.
assert F(120) + (6 * 430 - 2500) == 1720 + 6 * 430 - 4100

# ============================================================================ P2 (HKD, snapshot)
print("=== P2 (cp1_golden P2, L = 3; reporting HKD) ===")
P2 = [ev(1, "S-POS", "B1", "OPENING_POSITION", "2025-06-30", listing=T0700, qty=500, ccy="HKD", cost_basis=None),
      ev(3, "S-SELL", "B1", "SELL", "2025-07-02", listing=T0700, qty=200, amount=7400, ccy="HKD")]
b, r = fold(P2, "2025-07-31", 3)
show_lots("lot book B1 0700 at 07-31", b[("B1", T0700)], {})
show_lots("relief S-SELL", r["S-SELL"], {})
report_rg("S-SELL", P2[1], r["S-SELL"], "HKD")
mv_R, nat, rep = ug(b[("B1", T0700)], F(38), "HKD", "HKD", "2025-07-31")
print("  UG 07-31:", nat, rep)

# ============================================================================ P3 (CNY), seq 8-13
print("=== P3 (part 1 P3 seq 1-7 + part 3 seq 8-13, L = 13; reporting CNY) ===")
C1, C2, SYNA, NOP1 = "C1", "C2", "SYNA", "NOP1"
P3 = [
    ev(2, "P3-2", C1, "BUY", "2025-03-03", listing=SYNA, qty=2000, amount=20000, ccy="CNY"),
    ev(3, "P3-3", C1, "BUY", "2025-03-04", listing=T0700, qty=1000, amount=32400, ccy="CNY"),
    ev(7, "P3-7", C2, "BUY", "2025-03-25", listing=NOP1, qty=100, amount=1000, ccy="HKD"),
    ev(8, "P3-8", C2, "BUY", "2025-04-01", listing=T0700, qty=200, amount=7200, ccy="HKD"),
    ev(9, "P3-9", C1, "TRANSFER_OUT", "2025-04-02", listing=T0700, qty=1000, ccy="HKD", cp=C2),
    ev(10, "P3-10", C2, "TRANSFER_IN", "2025-04-02", listing=T0700, qty=1000, ccy="HKD", cp=C1),
    ev(11, "P3-11", C2, "TRANSFER_IN", "2025-04-03", listing=T0700, qty=100, ccy="HKD", cost_basis=3000),
    ev(12, "P3-12", C2, "SELL", "2025-04-10", listing=T0700, qty=1100, amount=39600, ccy="HKD"),
    ev(13, "P3-13", C2, "SELL", "2025-04-15", listing=T0700, qty=150, amount=5400, ccy="HKD"),
]
b, r = fold(P3, "2025-04-01", 13)
mv_R, nat, rep = ug(b[(C1, T0700)], F(36), "HKD", "CNY", "2025-04-01")
show("C1 0700 at 04-01: MV_R", mv_R)
print("  C1 0700 at 04-01: UG native", nat, "; UG R", frac(rep), pm(rep))
b, r = fold(P3, "2025-04-03", 13)
show_lots("lot book C2 0700 at 04-03", b[(C2, T0700)], {})
print("  native basis by currency:", {k: frac(v) for k, v in native_basis(b[(C2, T0700)]).items()})
b, r = fold(P3, "2025-04-30", 13)
show_lots("relief P3-12", r["P3-12"], {})
report_rg("P3-12", P3[7], r["P3-12"], "CNY")
show_lots("relief P3-13", r["P3-13"], {})
report_rg("P3-13", P3[8], r["P3-13"], "CNY")
show_lots("lot book C2 0700 at 04-30", b[(C2, T0700)], {})
mv_R, nat, rep = ug(b[(C2, T0700)], F(36), "HKD", "CNY", "2025-04-30")
print("  C2 0700 at 04-30: UG native", frac(nat), "; UG R", rep)
mv_R, nat, rep = ug(b[(C1, SYNA)], F(11), "CNY", "CNY", "2025-04-30")
print("  C1 SYNA at 04-30: UG native", frac(nat), "; UG R", frac(rep))
p12 = F(39600) * X("HKD", "CNY", "2025-04-10")
p13 = F(5400) * X("HKD", "CNY", "2025-04-15")
show("P3 RG total (03-31, 04-30] (P3-12 only)", F(1008))
show("P3 RG total excluded weight", p13 / (p12 + p13), "ratio")

# ============================================================================ P14 and P15 (USD)
for name, order in (("P14", ["S80", "B100", "B50"]), ("P15", ["B50", "B100", "S80"])):
    print(f"=== {name} (same-day buys and a sale; 03-05 entered as {order}) ===")
    day = {"S80": dict(type_="SELL", qty=80, amount=880), "B100": dict(type_="BUY", qty=100, amount=1040),
           "B50": dict(type_="BUY", qty=50, amount=580)}
    evs = [ev(2, "L0", "F1", "BUY", "2025-03-03", listing="SYNF", qty=30, amount=270, ccy="USD")]
    for i, nm in enumerate(order):
        x = day[nm]
        evs.append(ev(3 + i, nm, "F1", x["type_"], "2025-03-05", listing="SYNF", qty=x["qty"],
                      amount=x["amount"], ccy="USD"))
    evs.append(ev(6, "S40", "F1", "SELL", "2025-03-10", listing="SYNF", qty=40, amount=480, ccy="USD"))
    b, r = fold(evs, "2025-03-05", 6)
    show_lots("lot book at 03-05", b[("F1", "SYNF")], {})
    show_lots("relief S80", r["S80"], {})
    show("relief S80 basis", basis(r["S80"]))
    show("RG S80", F(880) - basis(r["S80"]))
    show("lot book basis at 03-05", basis(b[("F1", "SYNF")]))
    b, r = fold(evs, "2025-03-31", 6)
    show_lots("relief S40", r["S40"], {})
    show("RG S40", F(480) - basis(r["S40"]))
    show_lots("lot book at 03-31", b[("F1", "SYNF")], {})
    show("remaining basis 03-31", basis(b[("F1", "SYNF")]))
    show("UG 03-31 (60 x 13)", 60 * F(13) - basis(b[("F1", "SYNF")]))
    show("RG total (03-02, 03-31]", F(880) - F(810) + F(480) - F(432))
    assert (F(70) + 48) + (780 - basis(b[("F1", "SYNF")])) == 880 + 480 + 780 - (270 + 1040 + 580)

# ============================================================================ P16 (USD)
print("=== P16 (partial internal move from two lots; receiver FIFO; sale + move same day) ===")
T1, T2 = "T1", "T2"
P16 = [
    ev(3, "16-3", T1, "BUY", "2025-03-03", listing="SYNF", qty=100, amount=900, ccy="USD"),
    ev(4, "16-4", T1, "BUY", "2025-03-05", listing="SYNF", qty=100, amount=1100, ccy="USD"),
    ev(5, "16-5", T2, "BUY", "2025-03-06", listing="SYNF", qty=100, amount=1120, ccy="USD"),
    ev(6, "16-6", T1, "TRANSFER_OUT", "2025-03-07", listing="SYNF", qty=150, ccy="USD", cp=T2),
    ev(7, "16-7", T2, "TRANSFER_IN", "2025-03-07", listing="SYNF", qty=150, ccy="USD", cp=T1),
    ev(8, "16-8", T2, "SELL", "2025-03-10", listing="SYNF", qty=120, amount=1440, ccy="USD"),
    ev(9, "16-9", T2, "SELL", "2025-03-12", listing="SYNF", qty=40, amount=520, ccy="USD"),
    ev(10, "16-10", T2, "TRANSFER_OUT", "2025-03-12", listing="SYNF", qty=50, ccy="USD", cp=T1),
    ev(11, "16-11", T1, "TRANSFER_IN", "2025-03-12", listing="SYNF", qty=50, ccy="USD", cp=T2),
    ev(12, "16-12", T1, "SELL", "2025-03-14", listing="SYNF", qty=60, amount=780, ccy="USD"),
]
for D in ("2025-03-07", "2025-03-10", "2025-03-12", "2025-03-14", "2025-03-31"):
    b, r = fold(P16, D, 12)
    print(f"  -- as of {D}")
    show_lots("T1", b.get((T1, "SYNF"), []), {})
    show_lots("T2", b.get((T2, "SYNF"), []), {})
    show("T1 basis", basis(b.get((T1, "SYNF"), [])))
    show("T2 basis", basis(b.get((T2, "SYNF"), [])))
b, r = fold(P16, "2025-03-31", 12)
for sid, amt in (("16-6", None), ("16-8", 1440), ("16-9", 520), ("16-10", None), ("16-12", 780)):
    show_lots(f"relief {sid}", r[sid], {})
    show(f"relief {sid} basis", basis(r[sid]))
    if amt is not None:
        show(f"RG {sid}", F(amt) - basis(r[sid]))
rg_tot = (F(1440) - basis(r["16-8"])) + (F(520) - basis(r["16-9"])) + (F(780) - basis(r["16-12"]))
ug_t1 = 40 * F(13) - basis(b[(T1, "SYNF")])
ug_t2 = 40 * F(13) - basis(b[(T2, "SYNF")])
show("RG total (03-02, 03-31]", rg_tot)
show("UG T1 03-31", ug_t1)
show("UG T2 03-31", ug_t2)
show("UG total 03-31", ug_t1 + ug_t2)
assert rg_tot + ug_t1 + ug_t2 == (1440 + 520 + 780) + 80 * F(13) - (900 + 1100 + 1120)  # I-7, portfolio level

# ============================================================================ P17 (USD; taint)
print("=== P17 (carried split taint; FIFO relieves the tainted lot first) ===")
V1, V2 = "V1", "V2"
P17 = [
    ev(2, "17-2", V1, "BUY", "2025-02-03", listing="SYNT", qty=100, amount=8000, ccy="USD"),
    ev(4, "17-4", V2, "BUY", "2025-03-04", listing="SYNT", qty=100, amount=1950, ccy="USD"),
    ev(5, "17-5", V1, "TRANSFER_OUT", "2025-03-05", listing="SYNT", qty=40, ccy="USD", cp=V2),
    ev(6, "17-6", V2, "TRANSFER_IN", "2025-03-05", listing="SYNT", qty=40, ccy="USD", cp=V1),
    ev(7, "17-7", V2, "SELL", "2025-03-10", listing="SYNT", qty=40, amount=800, ccy="USD"),
]
for D in ("2025-03-07", "2025-03-10", "2025-03-11"):
    b, r = fold(P17, D, 7)
    tainted = [l for l in b[(V2, "SYNT")] if any(h[0] == V1 and h[3] >= "2025-03-03" for h in l["path"])]
    print(f"  -- as of {D}: V2 end-of-day lot book holds a tainted unit: {bool(tainted)}")
    show_lots("V2", b[(V2, "SYNT")], {})
    show_lots("V1", b[(V1, "SYNT")], {})
show_lots("relief 17-5 (out-leg)", r["17-5"], {})
show_lots("relief 17-7 (sale)", r["17-7"], {})
show("V2 value at 03-10 / 03-11 (100 x 20.00)", 100 * F(20))
show("V2 UG at 03-11", 100 * F(20) - basis(b[(V2, "SYNT")]))

# ============================================================================ P18 (USD; snapshot)
print("=== P18 (opening lots with recorded basis, USD and HKD) ===")
O1 = "O1"
P18 = [
    ev(1, "18-1", O1, "OPENING_POSITION", "2025-03-31", listing="SYNF", qty=50, ccy="USD", cost_basis=400),
    ev(2, "18-2", O1, "OPENING_POSITION", "2025-03-31", listing=T0700, qty=1000, ccy="HKD", cost_basis=30000),
    ev(4, "18-4", O1, "BUY", "2025-04-02", listing="SYNF", qty=50, amount=650, ccy="USD"),
    ev(5, "18-5", O1, "SELL", "2025-04-03", listing="SYNF", qty=60, amount=780, ccy="USD"),
    ev(6, "18-6", O1, "SELL", "2025-04-07", listing=T0700, qty=400, amount=14400, ccy="HKD"),
]
b, r = fold(P18, "2025-04-30", 6)
show_lots("relief 18-5", r["18-5"], {})
report_rg("18-5", P18[3], r["18-5"], "USD")
show_lots("relief 18-6", r["18-6"], {})
report_rg("18-6", P18[4], r["18-6"], "USD")
mv_f, nat_f, rep_f = ug(b[(O1, "SYNF")], F("12.50"), "USD", "USD", "2025-04-30")
mv_h, nat_h, rep_h = ug(b[(O1, T0700)], F(36), "HKD", "USD", "2025-04-30")
show("SYNF MV_R 04-30", mv_f)
show("SYNF UG R 04-30", rep_f)
show("SYNF remaining basis R", basis(b[(O1, "SYNF")]))
show("0700 MV_R 04-30", mv_h)
show("0700 UG native 04-30", nat_h)
print("  0700 UG R:", rep_h, "; remaining native", {k: frac(v) for k, v in native_basis(b[(O1, T0700)]).items()})
show("UG total (SYNF only)", rep_f)
show("UG total excluded weight", mv_h / (mv_h + mv_f), "ratio")
pr_f = F(780)
pr_h = F(14400) * X("HKD", "USD", "2025-04-07")
show("RG total (03-31, 04-30] (18-5 only)", F(780) - basis(r["18-5"]))
show("RG total excluded weight", pr_h / (pr_f + pr_h), "ratio")

# ============================================================================ P19 (USD; reversal)
print("=== P19 (a purchase reversed and re-dated: FIFO recomputed per (D, L)) ===")
P19 = [
    ev(2, "19-2", "R1", "BUY", "2025-03-03", listing="SYNF", qty=100, amount=900, ccy="USD"),
    ev(3, "19-3", "R1", "BUY", "2025-03-05", listing="SYNF", qty=100, amount=1100, ccy="USD"),
    ev(4, "19-4", "R1", "SELL", "2025-03-10", listing="SYNF", qty=100, amount=1200, ccy="USD"),
    ev(5, "19-5", "R1", "REVERSAL", "2025-03-20", rev="19-2"),
    ev(6, "19-6", "R1", "BUY", "2025-03-06", listing="SYNF", qty=100, amount=1120, ccy="USD"),
]
for D, L in (("2025-03-05", 4), ("2025-03-05", 6), ("2025-03-31", 4), ("2025-03-31", 6)):
    b, r = fold(P19, D, L)
    print(f"  -- (D, L) = ({D}, {L})")
    show_lots("R1", b[("R1", "SYNF")], {})
    show("basis", basis(b[("R1", "SYNF")]))
    if "19-4" in r:
        show_lots("relief 19-4", r["19-4"], {})
        show("RG 19-4", F(1200) - basis(r["19-4"]))
        show("UG at 03-31 (100 x 13)", 100 * F(13) - basis(b[("R1", "SYNF")]))

# ============================================================================ P20 (USD; acquired_on)
print("=== P20 (opening lots with acquired_on: RECORDED; S = 2025-03-31) ===")
Q1, Q2 = "Q1", "Q2"
P20 = [
    ev(1, "O1", Q1, "OPENING_POSITION", "2025-03-31", listing=T0700, qty=400, ccy="HKD", cost_basis=14000, acquired_on="2025-01-04"),
    ev(2, "O2", Q1, "OPENING_POSITION", "2025-03-31", listing=T0700, qty=600, ccy="HKD", cost_basis=18000, acquired_on="2025-01-08"),
    ev(3, "O3", Q1, "OPENING_POSITION", "2025-03-31", listing=T0700, qty=200, ccy="HKD", cost_basis=7600),
    ev(4, "O4", Q1, "OPENING_POSITION", "2025-03-31", listing=T0700, qty=100, ccy="HKD", cost_basis=3200, acquired_on="2024-12-16"),
    ev(5, "O5", Q1, "OPENING_POSITION", "2025-03-31", listing="SYNF", qty=50, ccy="USD", cost_basis=400, acquired_on="2024-11-01"),
    ev(7, "S7", Q1, "SELL", "2025-04-07", listing=T0700, qty=450, amount=16200, ccy="HKD"),
    ev(8, "S8", Q1, "SELL", "2025-04-10", listing=T0700, qty=250, amount=9000, ccy="HKD"),
    ev(9, "M9", Q1, "TRANSFER_OUT", "2025-04-15", listing=T0700, qty=100, ccy="HKD", cp=Q2),
    ev(10, "M10", Q2, "TRANSFER_IN", "2025-04-15", listing=T0700, qty=100, ccy="HKD", cp=Q1),
]
b, r = fold(P20, "2025-03-31", 10)
show_lots("Q1 0700 at 03-31", b[(Q1, T0700)], {})
show_lots("Q1 SYNF at 03-31", b[(Q1, "SYNF")], {})
for l in b[(Q1, T0700)]:
    print("     c_R", l["origin"], c_R(l, "USD"))
b, r = fold(P20, "2025-04-30", 10)
show_lots("relief S7", r["S7"], {})
report_rg("S7", P20[5], r["S7"], "USD")
show_lots("relief S8", r["S8"], {})
report_rg("S8", P20[6], r["S8"], "USD")
show_lots("relief M9 (out-leg)", r["M9"], {})
show_lots("Q1 0700 at 04-30", b[(Q1, T0700)], {})
show_lots("Q2 0700 at 04-30", b[(Q2, T0700)], {})
d430 = "2025-04-30"
mv1, n1, r1 = ug(b[(Q1, T0700)], F(36), "HKD", "USD", d430)
mv2, n2, r2 = ug(b[(Q2, T0700)], F(36), "HKD", "USD", d430)
mv3, n3, r3 = ug(b[(Q1, "SYNF")], F("12.50"), "USD", "USD", d430)
print("  Q1 0700: MV_R", frac(mv1), "UG native", frac(n1), "UG R", r1)
print("  Q2 0700: MV_R", frac(mv2), "UG native", frac(n2), "UG R", frac(r2), pm(r2))
print("  Q1 SYNF: MV_R", frac(mv3), "UG R", frac(r3), pm(r3))
show("Q2 remaining basis R", sum(l["u"] * c_R(l, "USD")[0] for l in b[(Q2, T0700)]))
for key, lots in (("Q1 O2", [l for l in b[(Q1, T0700)] if l["origin"] == "O2"]), ("Q2 O2'", b[(Q2, T0700)]),
                  ("Q1 O5 SYNF", b[(Q1, "SYNF")])):
    lot = lots[0]
    price, lc = (F("12.50"), "USD") if lot["k"] == "USD" else (F(36), "HKD")
    V, K = lot["u"] * price, lot["u"] * lot["c"]
    Xa, XD = X(lot["k"], "USD", lot["a"]), X(lc, "USD", d430)
    parts = [(V - K) * Xa, K * (XD - Xa), (V - K) * (XD - Xa)]
    tot = V * XD - K * Xa
    assert sum(parts) == tot
    t_hat, app = apportion(tot, parts)
    print(f"  since-acq {key}: total {frac(tot)} -> {pm(tot)}; parts " + ", ".join(frac(p) for p in parts)
          + "; apportioned " + ", ".join(str(_dec(a)) for a in app))
p7, p8 = F(16200) * X("HKD", "USD", "2025-04-07"), F(9000) * X("HKD", "USD", "2025-04-10")
show("RG total (03-31, 04-30] (S8 only)", r_s8 := (p8 - sum(p["u"] * c_R(p, "USD")[0] for p in r["S8"])))
show("RG total excluded weight", p7 / (p7 + p8), "ratio")
show("UG total (Q2 0700 + SYNF)", r2 + r3)
show("UG total excluded weight", mv1 / (mv1 + mv2 + mv3), "ratio")
print("done")
