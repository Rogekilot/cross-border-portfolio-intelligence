"""Independent calculator for cp4_golden part 3 (1.9-part3, risk/1.9, market-data/1.14: selection-log reversals, sources, proxies, Current mode, scope, snapshots,
zero-capital periods, split suppression, daily and monthly benchmark statistics, the default view).

Author: quant-analyst, 2026-10-02. Convention set: risk/1.9, on performance/1.12 and market-data/1.14.

A CALCULATOR for CP4_GOLDEN_PART3_DERIVATION.md, written from methodology/CP4_RISK_CONVENTIONS.md and the
performance and market-data rulings it cites. It is not an engine and reads no engine output:

- standard library only; it imports nothing from src/. It reuses the part-2 calculator (which reuses the part-1
  calculator) in this directory and extends it here: the ledger event types of part 3 (WITHDRAWAL, internal
  TRANSFER_IN/OUT, OPENING_POSITION, OPENING_CASH, SPLIT), account scope, snapshots, zero-capital periods,
  corroborated-split suppression (market-data Ruling 6.4 item 2, single-account form), two benchmark sources,
  ETF proxies, Current mode (performance Ruling 1.7 (1.12) and risk Ruling 5.8) and the default view (Ruling 7.7);
- it reads the fixture's INPUT blocks and recomputes every expected item from them in exact rationals.

Usage (read-only; it writes no file):
  python3 cp4_part3_calculator.py FIXTURE.json               print every derived result as JSON
  python3 cp4_part3_calculator.py FIXTURE.json --check       compare with the fixture's expect items
  python3 cp4_part3_calculator.py FIXTURE.json --mutations   every mutation changes EXACTLY the items naming it
  python3 cp4_part3_calculator.py FIXTURE.json --closed      metamorphic cross-checks (derivation section 13)
  python3 cp4_part3_calculator.py FIXTURE.json --retrieval   the declared file vintages against market-data Ruling 3.1
                                                             and M_t at every Current-mode instant (fixture 1.1-part3)
  python3 cp4_part3_calculator.py FIXTURE.json --release     the release-build cases RB-1..RB-5 and their mutations
                                                             (market-data Ruling 0.1 (1.12); fixture 1.3-part3)
"""

import datetime as dt
import importlib.util
import json
import os
import sys
from fractions import Fraction as F
from zoneinfo import ZoneInfo

_spec = importlib.util.spec_from_file_location("cp4p2", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                                     "cp4_part2_calculator.py"))
P2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P2)
P1 = P2.P1
D, St, frac, ONE = P1.D, P1.St, P1.frac, P1.ONE
UTC = dt.timezone.utc

CATALOG = {
    "M-C1": "Current mode reads the benchmark level and its FX fixing by date, ignoring the instant t",
    "M-C2": "Current mode resolves the as-of date to UTC-date(t), without the close and publication test",
    "M-C3": "the second source of a benchmark is ignored (primary only)",
    "M-C4": "when two benchmark sources disagree, the primary's level is used",
    "M-C5": "the ETF proxy ignores dividends (a price-return proxy)",
    "M-C6": "the ETF proxy uses CORROBORATED dividends only (SINGLE_SOURCE dropped)",
    "M-C7": "the ETF proxy takes the feed amount when feed and filing disagree",
    "M-C8": "no suppression for a corroborated split missing from the ledger",
    "M-C9": "a period with no capital is counted as a zero return",
    "M-C10": "internal transfers are not flows at account scope",
    "M-C11": "a window before a snapshot is accepted",
    "M-C12": "the default view always falls back to MAX_AVAILABLE",
    "M-C13": "the default view never falls back",
    "M-C14": "beta, R-squared and alpha reported as 0 when the benchmark did not move (undefined shown as 0)",
    "M-C15": "the portfolio leg's lag ignores price staleness",
    "M-C16": "the benchmark leg's lag ignores FX staleness",
    "M-C17": "tracking error with divisor n",
    "M-C18": "beta = S_rb / S_rr",
    "M-C19": "volatility with divisor n",
    "M-C20": "the benchmark is not translated into R (native levels)",
    "M-C21": "a disputed dividend suppresses the whole proxy series, not only from its ex-date",
    "M-C22": "the benchmark leg of a window fact measured from the requested base B instead of g_0",
    "M-C23": "a ledger SPLIT event does not change the quantity held",
    "M-C24": "the reason code is chosen among the causes at every level (the performance 1.0 wording), not only at the "
             "result's own level",
    "M-C25": "a REVERSAL is ignored: the reversed record still counts",
    "M-C26": "after a REVERSAL, no selection is in force (NONE) instead of the latest remaining record",
    "M-C27": "a pinned version that cuts a correction pair (a REVERSAL without its replacement) is accepted",
    "M-C28": "the EARLIEST live record is in force instead of the latest",
    "M-C29": "a replacement is ordered by its own sequence number, not by the position of the record it corrects",
    "M-C30": "the active return over a window containing a ZERO_CAPITAL_PERIOD takes the TWR's factor-1 value (AVAILABLE)",
    "M-C31": "a refused window suppresses the window-independent benchmark causes (no selection: reason none, not "
             "MISSING_BENCHMARK)",
    "M-C32": "a disputed proxy dividend suppresses every proxy level from its ex-date on (the 1.2 reading), not only the "
             "ratios that span it",
    "M-C33": "a disputed ETF print withholds that print and every later one (no chain around it)",
    "M-C34": "a disputed ETF print is treated as a missing print (the previous print used, counted stale), not as "
             "SOURCE_CONFLICT",
    "M-C35": "the default view does not fall back when an active return is refused by its portfolio leg TWR(g_0, g_n]",
    "M-C36": "two dividend statements of different sides that share no date are two dividends, both applied, however "
             "close their ex-dates (no linking window)",
    "M-C37": "any two unpaired dividend statements of different sides are one disputed dividend, however far apart",
    "M-C38": "a proxy dividend declared in another currency is added to the price unconverted (CP4F-12)",
    "M-C39": "a proxy dividend is converted at the ECB fixing of its PAY date, not its ex-date",
    "M-C40": "the freshness of a proxy dividend's conversion is ignored",
    "M-C41": "an amount the issuer states as paid in the price currency is ignored (ECB conversion used instead)",
    "M-C42": "a proxy dividend in another currency is refused: the proxy is unavailable from its ex-date (the interim order)",
    "M-C43": "a paid amount stated by one side only makes the dividend a DISAGREEMENT (market-data Ruling 4.5 (1.14) "
             "compares paid fields only when both sides state them)",
    "M-C44": "a multi-source benchmark with no declared precision is reconciled anyway (precision inferred, not declared)",
    "M-C45": "a benchmark source's precision is inferred as the most decimals any of its level texts shows (CP4F-13), not "
             "declared",
    "M-C46": "when the declared dividend is corroborated, only the first (FEED) statement's paid fields are kept: a "
             "FILING-only payment is ignored and two different payments are not a DISAGREEMENT (CP4F-15)",
}
MUT = set()
CTX = {"t": None}
FALLBACK_DETAILS = {"WINDOW_BEFORE_INCEPTION", "WINDOW_BEFORE_SNAPSHOT", "PERIOD_INSUFFICIENT", "ZERO_CAPITAL_PERIOD"}
RISK_DETAILS = P2.RISK_DETAILS | {"ZERO_CAPITAL_PERIOD", "WINDOW_BEFORE_SNAPSHOT", "BENCHMARK_SOURCE_CONFLICT"}
CONFLICT = object()


# ---- step expansion: several cycles per series ---------------------------------------------------------
_orig_expand = P1.expand_steps


def _expand(steps, cycle, key):
    if isinstance(cycle, list):
        out = dict(_orig_expand(steps, None, key))
        for c in cycle:
            out.update(dict(_orig_expand([], c, key)))
        return sorted(out.items())
    return _orig_expand(steps, cycle, key)


P1.expand_steps = _expand


# ---- the identity of a cash dividend across sources, for an ETF proxy (risk Ruling 5.5 (1.7)) -------------
LINK_WINDOW = 20


def identify_dividends(cas, listing, cal):
    """Returns [(status, [statements])], status CORROBORATED | SINGLE_SOURCE | DISAGREEMENT. A statement is one record
    (side FEED or FILING) of a CASH_DIVIDEND entry: its ex-date, pay date, record date (if stated) and amount.
      1. Equal statements across the two sides pair one-to-one: CORROBORATED.
      2. Of the rest, a FEED and a FILING statement sharing the record date, the ex-date or the pay date are about the
         same dividend; each connected group of such statements is a DISAGREEMENT (they are not equal).
      3. Of the rest, a FEED and a FILING statement whose ex-dates are at most LINK_WINDOW sessions apart may be one
         dividend stated with different dates: each connected group is a DISAGREEMENT (fail closed, not a double count).
      4. What is left: SINGLE_SOURCE, applied."""
    st = []
    for ca in cas:
        if ca["listing_id"] != listing or ca["type"] != "CASH_DIVIDEND":
            continue
        for r in ca["records"]:
            st.append({"side": r["side"], "ex": D(ca["ex_date"]), "pay": ca.get("pay_date"), "rec": ca.get("record_date"),
                       "amount": F(r["amount"]), "ccy": ca.get("currency"),
                       "paid": (r["paid_currency"], F(r["paid_amount"])) if "paid_currency" in r else None})
    st.sort(key=lambda s: (s["ex"], s["side"], s["amount"]))
    key = lambda s: (s["ex"], s["pay"], s["rec"], s["amount"], s["ccy"])
    paid_ok = lambda a, b: "M-C46" in MUT or a["paid"] == b["paid"] or (
        "M-C43" not in MUT and (a["paid"] is None or b["paid"] is None))
    # market-data 4.5 (1.14): paid fields compared only when both sides state them
    out, used = [], set()
    for i, a in enumerate(st):                                    # 1. exact pairs
        if i in used or a["side"] != "FEED":
            continue
        j = next((j for j, b in enumerate(st) if j not in used and b["side"] == "FILING" and key(b) == key(a)
                  and paid_ok(a, b)), None)
        if j is not None:
            used |= {i, j}
            merged = dict(a, paid=a["paid"] if "M-C46" in MUT else (a["paid"] or st[j]["paid"]))
            # a one-sided paid amount is used as stated, whichever side states it (M-C46: the first statement's only)
            out.append(("CORROBORATED", [merged, st[j]]))

    def sessions(x, y):
        lo, hi = min(x, y), max(x, y)
        return sum(1 for d in cal.days if lo < d <= hi)

    def linked(a, b, step):
        if a["side"] == b["side"]:
            return False
        if step == 2:
            return a["ex"] == b["ex"] or (a["pay"] and a["pay"] == b["pay"]) or (a["rec"] and a["rec"] == b["rec"])
        if "M-C36" in MUT:
            return False
        return "M-C37" in MUT or sessions(a["ex"], b["ex"]) <= LINK_WINDOW

    for step in (2, 3):                                           # 2. shared dates; 3. the linking window
        rest = [i for i in range(len(st)) if i not in used]
        seen = set()
        for i in rest:
            if i in seen:
                continue
            group, todo = {i}, [i]
            while todo:
                k = todo.pop()
                for j in rest:
                    if j not in group and linked(st[k], st[j], step):
                        group.add(j)
                        todo.append(j)
            seen |= group
            if len(group) > 1:
                used |= group
                out.append(("DISAGREEMENT", [st[k] for k in sorted(group)]))
    for i in range(len(st)):                                      # 4. single-source statements
        if i not in used:
            out.append(("SINGLE_SOURCE", [st[i]]))
    return out


# ---- benchmarks: sources, proxies, Current mode (Rulings 5.2, 5.5, 5.7, 5.8 as of 1.2) -----------------
class Bench3:
    def __init__(self, entries, w):
        entries = sorted(entries, key=lambda e: e.get("source_priority", 1))
        self.b, self.w = entries[0], w
        self.ccy, self.basis = self.b["currency"], self.b["return_basis"]
        self.cal = w.cals[self.b["calendar"]]
        self.conflict_from = None
        self.breaks = []
        self.span_states = []
        if self.b.get("construction") == "ETF_PROXY":
            self.rows = self._proxy()
        else:
            use = entries[:1] if "M-C3" in MUT else entries
            per = [self._rows(e) for e in use]
            # risk Ruling 5.7 (1.9): each source's bound is 0 if it publishes at least the index's official decimals,
            # else half a unit of its own last declared decimal (market-data Ruling 4.2)
            D_off = self.b.get("official_decimals")

            def prec(e):
                if "M-C45" in MUT:                              # inferred: the most decimals any level text shows
                    texts = [s["level"] for s in e["steps"]] + ((e.get("cycle") or {}).get("levels") or []) + \
                            [o["level"] for o in e.get("level_overrides", [])]
                    return max(len(t.split(".")[1]) if "." in t else 0 for t in texts)
                return e.get("precision_decimals", D_off)
            bound = [F(0) if (D_off is None or prec(e) >= D_off) else F(1, 2 * 10 ** prec(e)) for e in use]
            self.rows = {}
            for d in sorted(set().union(*[set(r) for r in per])):
                have = [(r[d], bd) for r, bd in zip(per, bound) if d in r]
                agree = all(abs(a - b) <= da + db for (a, da) in have for (b, db) in have)
                if not agree and "M-C4" not in MUT:
                    self.rows[d] = CONFLICT
                else:
                    self.rows[d] = have[0][0]
        self.row_days = sorted(self.rows)

    def _rows(self, e):
        steps = P1.expand_steps(e["steps"], e.get("cycle"), "level")
        gaps = {D(x) for x in e["gaps"]}
        over = {D(o["date"]): F(o["level"]) for o in e.get("level_overrides", [])}
        first, last = D(e["first"]), D(e["last"])
        rows = {d: P1.step_at(steps, d) for d in self.cal.days if first <= d <= last and d not in gaps}
        rows.update({d: v for d, v in over.items() if d in rows})
        return rows

    def _proxy(self):
        """Ruling 5.5 (1.2, 1.6): TR(first usable print) = that close; on each later usable print t, with t- the previous
        usable print, TR_t = TR_t- * (P_t + sum of d with ex-date in (t-, t]) / P_t-.
        (1.6) A print whose two price sources DISAGREE is withheld: that day's level is SOURCE_CONFLICT, and the chain links
        around it (no price of the withheld day is needed). A corporate action in DISAGREEMENT BREAKS the chain at its
        ex-date: a ratio spanning it is unavailable (checked in item_result), ratios on either side are not."""
        prices = self.w.prices[self.b["listing_id"]]
        self.breaks = []
        self.span_states = []
        divs = {}
        for status, stmts in identify_dividends(self.w.ca, self.b["listing_id"], self.cal):
            exs = sorted({s["ex"] for s in stmts})
            if status == "DISAGREEMENT":
                if "M-C7" in MUT:
                    feed = [s for s in stmts if s["side"] == "FEED"][0]
                    divs[feed["ex"]] = divs.get(feed["ex"], F(0)) + feed["amount"]
                elif "M-C21" in MUT:
                    self.conflict_from = prices.row_days[0]
                elif "M-C32" in MUT:                            # the 1.2 reading: suppressed from the ex-date on
                    self.conflict_from = exs[0] if self.conflict_from is None else min(self.conflict_from, exs[0])
                else:
                    self.breaks.extend(exs)                     # every ex-date either statement names (Ruling 5.5 (1.7))
                continue
            if "M-C6" in MUT and status != "CORROBORATED":
                continue
            s = stmts[0]
            amount = self._in_price_ccy(s)
            if amount is None:
                continue
            divs[s["ex"]] = divs.get(s["ex"], F(0)) + amount
        second = self.w.price_json[self.b["listing_id"]].get("second_source")
        disputed = set()
        if second:
            disputed = {D(o["date"]) for o in second["price_overrides"] if F(o["close"]) != prices.rows.get(D(o["date"]))}
        rows, prev, poisoned = {}, None, False
        for d in prices.row_days:
            if d in disputed or poisoned:
                if "M-C34" in MUT:                              # a disputed print treated as a missing print
                    continue
                rows[d] = CONFLICT
                poisoned = poisoned or "M-C33" in MUT           # M-C33: every later print withheld too
                continue
            p = prices.rows[d]
            if prev is None:
                rows[d] = p
            else:
                dv = F(0) if "M-C5" in MUT else sum((v for x, v in divs.items() if prev < x <= d), F(0))
                rows[d] = rows[prev] * (p + dv) / prices.rows[prev]
            prev = d
        return rows

    def _in_price_ccy(self, s):
        """Ruling 5.5 (1.8): a dividend in the ETF's price currency is used as stated. Otherwise: the amount the issuer
        states as paid in the price currency, if any; else the declared amount converted at the ECB fixing u(ex-date)
        (cross via EUR), whose freshness (market-data Ruling 1.6) is the state of every ratio spanning the ex-date."""
        p = self.w.listing_ccy[self.b["listing_id"]]
        if s["ccy"] in (None, p) or "M-C38" in MUT:
            return s["amount"]
        if s["paid"] and s["paid"][0] == p and "M-C41" not in MUT:
            return s["paid"][1]
        if "M-C42" in MUT:                                     # the interim order: refuse from the ex-date
            self.conflict_from = s["ex"] if self.conflict_from is None else min(self.conflict_from, s["ex"])
            return None
        on = D(s["pay"]) if "M-C39" in MUT else s["ex"]
        x, st, _, _ = self.w.fx_fixing(s["ccy"], p, on)
        if "M-C40" in MUT:
            st = St()
        self.span_states.append((s["ex"], st))
        return None if x is None or st.level() == 2 else s["amount"] * x

    def _closed_by_t(self, d):
        return CTX["t"] is None or "M-C1" in MUT or self.w.instant(self.cal.id, d) <= CTX["t"]

    def at(self, g):
        prior = [x for x in self.row_days if x <= g and self._closed_by_t(x)]
        if not prior:
            return None, St([("INSUFFICIENT_DATA", "MISSING_BENCHMARK", "BENCHMARK_NOT_COVERING_WINDOW")]), None, None
        e = prior[-1]
        if self.rows[e] is CONFLICT or (self.conflict_from is not None and e >= self.conflict_from):
            return None, St([("INSUFFICIENT_DATA", "SOURCE_CONFLICT", "BENCHMARK_SOURCE_CONFLICT")]), e, 0
        m = sum(1 for d in self.cal.days if e < d <= g and self._closed_by_t(d))
        st = St() if m == 0 else St([({1: "AVAILABLE"}.get(m, "LIMITED" if m <= 4 else "INSUFFICIENT_DATA"),
                                      "STALE_DATA", "BENCHMARK_STALE")])
        return (None if st.level() == 2 else self.rows[e]), st, e, m


class World3(P2.World2):
    def __init__(self, fx):
        md = dict(fx["market_data"], benchmarks=[])
        super().__init__(dict(fx, market_data=md))
        self.ca = fx["market_data"].get("corporate_actions", [])
        self.price_json = {s["listing_id"]: s for s in fx["market_data"]["prices"]["series"]}
        groups = {}
        for b in fx["market_data"]["benchmarks"]:
            groups.setdefault(b["benchmark_id"], []).append(b)
        # risk Ruling 5.7 (1.9): a benchmark served by several sources needs the index's official decimals and every
        # source's declared precision; without them it cannot be reconciled and is not a usable series (not in w.bench)
        declared = lambda v: len(v) == 1 or ("M-C44" in MUT) or all(
            "precision_decimals" in e and "official_decimals" in e for e in v)
        self.bench = {k: Bench3(v, self) for k, v in groups.items() if declared(v)}
        self.splits = {}
        for ca in self.ca:
            if ca["type"] == "SPLIT" and {r["side"] for r in ca["records"]} == {"FEED", "FILING"}:
                self.splits.setdefault(ca["listing_id"], []).append(
                    (D(ca["ex_date"]), F(ca["ratio"]["new_units"]), F(ca["ratio"]["old_units"])))
        self.cal_sets = {k: set(c.days) for k, c in self.cals.items()}

    def published(self, f):
        c = self.cal_json[self.ecb_id]
        h, m = map(int, c["fixing"]["publication"].split(":"))
        return dt.datetime(f.year, f.month, f.day, h, m, tzinfo=ZoneInfo(c["timezone"])).astimezone(UTC)

    def fx_fixing(self, c, r, g):
        if c == r or CTX["t"] is None or "M-C1" in MUT:
            return super().fx_fixing(c, r, g)
        t = CTX["t"]
        days = [x for x in self.fx.cal.days if x <= g and x in self.fx.rows[c] and x in self.fx.rows[r]
                and self.published(x) <= t]
        if not days:
            return None, St([("INSUFFICIENT_DATA", "MISSING_FX_HISTORY", "NO_FIXING")]), None, None
        u = days[-1]
        m = sum(1 for x in self.fx.cal.days if u < x <= g and self.published(x) <= t)
        st = P1.fresh(m, "FX")
        return (None if st.level() == 2 else self.fx.rows[r][u] / self.fx.rows[c][u]), st, u, m


# ---- the portfolio, by scope (performance Rulings 4.1-4.5, 5.1-5.3; risk Rulings 0.1, 2.4) ---------------
class Portfolio3(P1.Portfolio):
    def __init__(self, p, w, account=None):
        self.w, self.R, self.account = w, p["reporting_currency"], account
        ev = [e["event"] for e in sorted(p["events"], key=lambda e: e["ledger_seq"])]
        self.events = [e for e in ev if account is None or e["account_id"] == account]
        snaps = [D(e["event_date"]) for e in self.events if e["event_type"] in ("OPENING_POSITION", "OPENING_CASH")]
        self.snapshot = max(snaps) if snaps else None
        self.I0 = self.snapshot if self.snapshot else min(D(e["event_date"]) for e in self.events) - ONE

    def _ordered(self):
        return sorted(self.events, key=lambda e: (D(e["event_date"]), 0 if e["event_type"] == "SPLIT" else 1))

    def holdings(self, d):
        cash, qty = {}, {}
        for e in self._ordered():
            if D(e["event_date"]) > d:
                break
            t = e["event_type"]
            if t in ("DEPOSIT", "OPENING_CASH") or (t == "TRANSFER_IN" and "amount" in e and "listing_id" not in e):
                cash[e["currency"]] = cash.get(e["currency"], F(0)) + F(e["amount"]["amount"])
            elif t == "WITHDRAWAL" or (t == "TRANSFER_OUT" and "listing_id" not in e):
                cash[e["currency"]] = cash.get(e["currency"], F(0)) - F(e["amount"]["amount"])
            elif t == "BUY":
                c = e["amount"]["currency"]
                cash[c] = cash.get(c, F(0)) - F(e["amount"]["amount"])
                qty[e["listing_id"]] = qty.get(e["listing_id"], F(0)) + F(e["quantity"])
            elif t in ("OPENING_POSITION", "TRANSFER_IN"):
                qty[e["listing_id"]] = qty.get(e["listing_id"], F(0)) + F(e["quantity"])
            elif t == "SPLIT" and "M-C23" in MUT:
                pass
            elif t == "SPLIT":
                r = e["split_ratio"]
                qty[e["listing_id"]] = qty.get(e["listing_id"], F(0)) * F(r["new_units"]) / F(r["old_units"])
            else:
                raise ValueError(f"event type not handled by this calculator: {t}")
        return cash, qty

    def _suppressed(self, l, d):
        """market-data Ruling 6.4 item 2: a corroborated split with no ledger SPLIT dated its ex-date."""
        if "M-C8" in MUT:
            return False
        for x, n, o in self.w.splits.get(l, []):
            if x > d:
                continue
            held = self.holdings(x - ONE)[1].get(l, F(0)) != 0
            recorded = any(e["event_type"] == "SPLIT" and e["listing_id"] == l and D(e["event_date"]) == x
                           and F(e["split_ratio"]["new_units"]) / F(e["split_ratio"]["old_units"]) == n / o
                           for e in self.events)
            if held and not recorded:
                return True
        return False

    def V(self, d):
        if self.snapshot is None and d <= self.I0:
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
            if self._suppressed(l, d):
                st.add(St([("INSUFFICIENT_DATA", "SOURCE_CONFLICT", "SPLIT_NOT_RECORDED")]))
                continue
            p, s, _, _ = self.w.prices[l].at(d)
            x, s2 = self.w.fx.X(self.w.listing_ccy[l], self.R, d)
            st.add(s).add(s2)
            if p is not None and x is not None:
                total += q * p * x
        return (None if st.level() == 2 else total), st

    def _is_flow(self, e):
        t, internal = e["event_type"], "counterparty_account_id" in e
        if t in ("DEPOSIT", "WITHDRAWAL"):
            return True
        if t in ("TRANSFER_IN", "TRANSFER_OUT"):
            if not internal:
                return True
            return self.account is not None and "M-C10" not in MUT
        return False

    def flows(self, d):
        ic, ik, o, st = F(0), F(0), F(0), St()
        for e in self.events:
            if D(e["event_date"]) != d or not self._is_flow(e):
                continue
            t = e["event_type"]
            if "listing_id" in e:
                p, s, _, _ = self.w.prices[e["listing_id"]].at(d)
                x, s2 = self.w.fx.X(self.w.listing_ccy[e["listing_id"]], self.R, d)
                st.add(s).add(s2)
                v = F(e["quantity"]) * p * x
                if t == "TRANSFER_IN":
                    ik += v
                else:
                    o += v
            else:
                x, s = self.w.fx.X(e["currency"], self.R, d)
                st.add(s)
                v = F(e["amount"]["amount"]) * x
                if t in ("DEPOSIT", "TRANSFER_IN"):
                    ic += v
                else:
                    o += v
        return ic, ik, o, st

    def twr(self, a, b):
        events_in = [e for e in self.events if a < D(e["event_date"]) <= b]
        if not events_in and "M-C9" not in MUT:
            va, _ = self.V(a)
            vb, _ = self.V(b)
            if va == 0 and vb == 0:                                  # Ruling 2.4: no capital at any time
                return None, St([("INSUFFICIENT_DATA", None, "ZERO_CAPITAL_PERIOD")])
        flow_days = sorted({D(e["event_date"]) for e in events_in if self._is_flow(e)})
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
            if den == 0 and num == 0:
                return F(1)                                          # ZERO_CAPITAL_RUN
            if den <= 0:                                             # performance Ruling 5.3
                st.add(St([("INSUFFICIENT_DATA", None, "NON_POSITIVE_BASE")]))
                return None
            return num / den

        factor, prev = F(1), a
        for fd in flow_days:
            if fd - ONE != prev:
                r = ratio(v(fd - ONE), v(prev))
                factor = None if (factor is None or r is None) else factor * r
            ic, ik, o, s = self.flows(fd)
            st.add(s)
            vb_, ve = v(fd - ONE), v(fd)
            r = ratio(None if ve is None else ve + o - ik, None if vb_ is None else vb_ + ic)
            factor = None if (factor is None or r is None) else factor * r
            prev = fd
        if prev != b:
            r = ratio(v(b), v(prev))
            factor = None if (factor is None or r is None) else factor * r
        return (None if st.level() == 2 else factor), st


# ---- windows with snapshots (performance Ruling 5.4) ------------------------------------------------------
_orig_window = P1.window


def window3(port, req, freq, E):
    out = _orig_window(port, req, freq, E)
    if "refusal" in out and "WINDOW_BEFORE_INCEPTION" in out["refusal"].details() and getattr(port, "snapshot", None):
        if "M-C11" in MUT:
            pts = [d for d in P1.daterange(out["requested_base"], E) if P1.on_grid(freq, d)]
            return {"requested_base": out["requested_base"], "points": pts}
        out["refusal"] = St([("INSUFFICIENT_DATA", "NOT_RECONSTRUCTABLE", "WINDOW_BEFORE_SNAPSHOT")])
    return out


P1.window = window3


# ---- Current mode: D_c(t) (performance Ruling 1.7 (1.12)) ---------------------------------------------------
def d_c(port, w, t):
    D_ = t.astimezone(UTC).date()
    if "M-C2" in MUT:
        return D_
    while True:
        ok = True
        cash, qty = port.holdings(D_)
        dated = [e for e in port.events if D(e["event_date"]) == D_]
        listings = {l for l, q in qty.items() if q != 0} | {e["listing_id"] for e in dated if "listing_id" in e}
        for l in listings:
            cid = w.listing_cal[l]
            if D_ in w.cal_sets[cid] and w.instant(cid, D_) > t:
                ok = False
        foreign = any(a != 0 and c != port.R for c, a in cash.items()) or \
            any(w.listing_ccy[l] != port.R for l in listings) or any(e["currency"] != port.R for e in dated)
        if foreign and D_ in w.cal_sets[w.ecb_id] and w.published(D_) > t:
            ok = False
        if ok:
            return D_
        D_ -= ONE


# ---- one item ------------------------------------------------------------------------------------------------
# ---- the selection log with reversals and corrections (risk Ruling 5.6 (1.4)) ------------------------------
def _rtype(r):
    return r.get("record_type") or ("SELECT" if r.get("benchmark_id") else "CLEAR")


def _position(r, by_id):
    """A replacement takes the order position of the record it corrects (followed to the root of the chain)."""
    if "M-C29" in MUT:
        return r["seq"]
    while r.get("corrects_selection_id"):
        r = by_id[r["corrects_selection_id"]]
    return r["seq"]


def resolve_selection(port_json, version):
    """(state, record or None): state in NONE, CLEARED, IN_FORCE, REFUSED (Ruling 5.6 (1.4))."""
    log = port_json.get("benchmark_selections", [])
    by_id = {r["selection_id"]: r for r in log}
    known = [r for r in log if r["seq"] <= version]
    if "M-C27" not in MUT:
        for rv in (r for r in known if _rtype(r) == "REVERSAL"):
            if any(x.get("corrects_selection_id") == rv["reverses_selection_id"] and x["seq"] > version for x in log):
                return "REFUSED", None                   # the version cuts a correction pair
    if not known:
        return "NONE", None
    if "M-C26" in MUT and _rtype(max(known, key=lambda r: r["seq"])) == "REVERSAL":
        return "NONE", None
    voided = set() if "M-C25" in MUT else {r["reverses_selection_id"] for r in known if _rtype(r) == "REVERSAL"}
    live = [r for r in known if _rtype(r) != "REVERSAL" and r["selection_id"] not in voided]
    if not live:
        return "NONE", None
    key = lambda r: (_position(r, by_id), r["seq"])
    rec = min(live, key=key) if "M-C28" in MUT else max(live, key=key)
    return ("IN_FORCE" if _rtype(rec) == "SELECT" else "CLEARED"), rec


def _selection_for_p2(port_json, version):
    state, rec = resolve_selection(port_json, version)
    return rec


P2.selection = _selection_for_p2


def selection_item(p, item, version):
    state, rec = resolve_selection(p, version)
    return {"kind": "selection_resolution", "details": [],
            "selection": {"state": state, "selection_id": None if rec is None else rec["selection_id"],
                          "seq": None if rec is None else rec["seq"],
                          "benchmark_id": None if rec is None else rec.get("benchmark_id")}}


def item_result(w, p, item, E, version):
    scope = item.get("scope")
    port = Portfolio3(p, w, account=None if scope is None else scope["account_id"])
    if item["kind"] == "selection_resolution":
        return selection_item(p, item, version)
    if item["kind"] == "default_view":
        return default_view(w, p, port, item, E, version)
    res = P2.metric2(w, port, p, item, E, version)
    if "M-C14" in MUT and item["kind"] in ("beta", "r_squared", "alpha_jensen") \
            and "ZERO_BENCHMARK_VARIANCE" in res.get("details", []):
        res.update(state="LIMITED", reason=None, value="0.000000000000", exact="0")
    ew = res.get("effective_window")
    if item["kind"] == "active_return" and ew and "M-C30" not in MUT:
        # risk Ruling 6.9 (1.5): a grid period of (g_0, g_n] with no capital at any time (Ruling 2.4) makes the active
        # return INSUFFICIENT_DATA, detail ZERO_CAPITAL_PERIOD (the TWR's factor 1 is not a measured return).
        pts = [d for d in P1.daterange(D(ew["base_date"]), D(ew["last_period_end"])) if P1.on_grid(item["frequency"], d)]
        if any("ZERO_CAPITAL_PERIOD" in port.twr(a, b)[1].details() for a, b in zip(pts, pts[1:])):
            if res["state"] != "INSUFFICIENT_DATA":
                res["reason"] = None
            res.update(state="INSUFFICIENT_DATA", value=None, exact=None, comparability=None,
                       details=res.get("details", []) + ["ZERO_CAPITAL_PERIOD"])
            res.pop("decomposition_view", None)
    if item["kind"] in P2.BENCHMARK_KINDS and ew:
        # risk Ruling 5.5 (1.6): a ratio of proxy levels that spans a disputed corporate action's ex-date is unavailable.
        b = P2.resolve_benchmark(w, p, version)[0]
        if b is not None and getattr(b, "breaks", None):
            pts = [d for d in P1.daterange(D(ew["base_date"]), D(ew["last_period_end"])) if P1.on_grid(item["frequency"], d)]
            used = pts if item["kind"] in P2.STATISTICS else [pts[0], pts[-1]]
            if any(a < x <= c for x in b.breaks for a, c in zip(used, used[1:])):
                prior = res["reason"] if res["state"] == "INSUFFICIENT_DATA" else None
                codes = [c for c in (prior, "SOURCE_CONFLICT") if c]
                res.update(state="INSUFFICIENT_DATA", value=None, exact=None, comparability=None,
                           reason=next(c for c in P1.PRIORITY if c in codes),
                           details=res.get("details", []) + ["BENCHMARK_SOURCE_CONFLICT"])
                for k in ("decomposition_view", "v_beta", "exact_square", "sign", "_boundary_distance_quanta"):
                    res.pop(k, None)
        if b is not None and getattr(b, "span_states", None):
            # risk Ruling 5.5 (1.8): a converted dividend's FX freshness is the state of every ratio spanning its ex-date
            pts = [d for d in P1.daterange(D(ew["base_date"]), D(ew["last_period_end"])) if P1.on_grid(item["frequency"], d)]
            used = pts if item["kind"] in P2.STATISTICS else [pts[0], pts[-1]]
            extra = [c for x, s in b.span_states if any(a < x <= c2 for a, c2 in zip(used, used[1:])) for c in s.causes]
            if extra:
                lv0 = P1.RANK[res["state"]]
                lv = max([lv0] + [P1.RANK[c[0]] for c in extra])
                codes = [c[1] for c in extra if P1.RANK[c[0]] == lv and c[1]] + ([res["reason"]] if lv == lv0 and res["reason"] else [])
                if lv == 0:
                    codes = [c for c in codes if c == "STALE_DATA"]
                state = {0: "AVAILABLE", 1: "LIMITED", 2: "INSUFFICIENT_DATA"}[lv]
                res.update(state=state, reason=next((c for c in P1.PRIORITY if c in codes), None))
                if lv == 2:
                    res.update(value=None, exact=None, comparability=None)
                    for k in ("decomposition_view", "v_beta", "exact_square", "sign", "_boundary_distance_quanta"):
                        res.pop(k, None)
    if "M-C31" in MUT and res.get("state") == "INSUFFICIENT_DATA":
        refusal = [x for x in res.get("details", []) if x in ("WINDOW_BEFORE_INCEPTION", "WINDOW_BEFORE_SNAPSHOT")]
        if refusal:
            res.update(reason="NOT_RECONSTRUCTABLE" if refusal[0] == "WINDOW_BEFORE_SNAPSHOT" else None, details=refusal)
    return res


SHOWN = ["request", "requested_base", "effective_window", "state", "reason", "value", "exact", "exact_square", "sign"]


def default_view(w, p, port, item, E, version):
    """Ruling 7.7 (1.2; PD-0040): the default request, and MAX_AVAILABLE when it is refused for history."""
    base = dict(kind=item["metric"], frequency=item["frequency"], request=item["default_request"])
    if item.get("scope"):
        base["scope"] = item["scope"]
    first = item_result(w, p, base, E, version)
    hist = first["state"] == "INSUFFICIENT_DATA" and bool(FALLBACK_DETAILS & set(first.get("details", [])))
    ew = first.get("effective_window")
    if first["state"] == "INSUFFICIENT_DATA" and item["metric"] == "active_return" and ew and "M-C35" not in MUT:
        # Ruling 7.7 (1.6): a portfolio leg TWR(g_0, g_n] that is INSUFFICIENT_DATA is a history refusal too.
        hist = hist or port.twr(D(ew["base_date"]), D(ew["last_period_end"]))[1].level() == 2
    fall = ("M-C12" in MUT) or (bool(hist) and "M-C13" not in MUT)
    shown = item_result(w, p, dict(base, request={"rule": "MAX_AVAILABLE"}), E, version) if fall else first
    pick = lambda r: dict({k: r.get(k) for k in SHOWN if k in r},
                          details_include=sorted(x for x in r.get("details", []) if x in RISK_DETAILS))
    return {"kind": "default_view", "metric": item["metric"], "frequency": item["frequency"],
            "default_request": item["default_request"], "fallback": fall,
            "refused": pick(first) if fall else None, "shown": pick(shown), "details": []}


def derive(fx):
    w = World3(fx)
    out = {}
    saved = (set(P2.MUT), P1.svar)
    P2.MUT = ({"M-B5"} if "M-C17" in MUT else set()) | ({"M-B14"} if "M-C18" in MUT else set()) | \
        ({"M-B1"} if "M-C20" in MUT else set()) | ({"M-B23"} if "M-C22" in MUT else set())
    if "M-C19" in MUT:
        P1.svar = lambda xs: (lambda m: sum(((x - m) ** 2 for x in xs), F(0)) / len(xs))(P1.mean(xs))
    _orig_reason = P1.St.reason
    if "M-C24" in MUT:
        def reason_any_level(self):
            codes = [c[1] for c in self.causes if c[1]]
            if self.level() == 0:
                codes = [c for c in codes if c == "STALE_DATA"]
            return next((p for p in P1.PRIORITY if p in codes), None)
        P1.St.reason = reason_any_level
    _orig_bench_R, _orig_inputs = P2.bench_R, P2.portfolio_inputs
    if "M-C16" in MUT:
        def bench_R(w_, b, R, g):
            v, s, e, u, lag = _orig_bench_R(w_, b, R, g)
            return v, s, e, u, (b.at(g)[3] or 0)
        P2.bench_R = bench_R
    if "M-C15" in MUT:
        def inputs(w_, port, g):
            cals, fxp, lag, days = _orig_inputs(w_, port, g)
            cash, qty = port.holdings(g)
            ccys = {c for c, a in cash.items() if a != 0 and c != port.R} | \
                   {w_.listing_ccy[l] for l, q in qty.items() if q != 0 and w_.listing_ccy[l] != port.R}
            return cals, fxp, max([w_.fx_fixing(c, port.R, g)[3] or 0 for c in ccys] + [0]), days
        P2.portfolio_inputs = inputs
    try:
        for p in fx["portfolios"]:
            for a in p["assertions"]:
                version = a.get("selection_log_version", 0)
                if a.get("valuation_mode") == "CURRENT":
                    t = dt.datetime.fromisoformat(a["instant"].replace("Z", "+00:00"))
                    CTX["t"] = t
                    E = d_c(Portfolio3(p, w), w, t)
                else:
                    CTX["t"] = None
                    E = D(a["as_of"])
                res = []
                for x in a["expect"]:
                    r = item_result(w, p, x, E, version)
                    if a.get("valuation_mode") == "CURRENT":
                        r["as_of_resolved"] = E.isoformat()
                    res.append(r)
                out[a["id"]] = res
    finally:
        CTX["t"] = None
        P2.MUT, P1.svar = saved
        P2.bench_R, P2.portfolio_inputs = _orig_bench_R, _orig_inputs
        P1.St.reason = _orig_reason
    return out


COMPARED = P2.COMPARED + ["as_of_resolved", "fallback", "refused", "shown", "returns", "selection"]


def diff(exp, got):
    out = [k for k in COMPARED if (k in exp or k in got) and exp.get(k) != got.get(k)]
    if got.get("kind") != "default_view":
        own = sorted(x for x in got.get("details", []) if x in RISK_DETAILS)
        if "details_include" in exp and own != sorted(exp["details_include"]):
            out.append("details_include")
    return out


def check(fx, out, quiet=False):
    bad = 0
    for p in fx["portfolios"]:
        for a in p["assertions"]:
            if len(a["expect"]) != len(out[a["id"]]):
                bad += 1
                print(f"MISMATCH {a['id']}: item count")
            for e, got in zip(a["expect"], out[a["id"]]):
                exp = P2.expected(a, e)
                for k in diff(exp, got):
                    bad += 1
                    if not quiet:
                        print(f"MISMATCH {a['id']} {e['kind']} {k}: fixture={exp.get(k)!r} calculator={got.get(k)!r}")
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
    """Cross-checks against part 2's closed forms (derivation section 12)."""
    r = [F(1, 25), F(-3, 104), F(-3, 101), F(1, 49)]
    b = [F(3, 100), F(-2, 103), F(-2, 101), F(1, 99)]
    mr, mb = sum(r) / 4, sum(b) / 4
    srb = sum((x - mr) * (y - mb) for x, y in zip(r, b))
    sbb = sum((y - mb) ** 2 for y in b)
    srr = sum((x - mr) ** 2 for x in r)
    beta = srb / sbb
    checks = []
    checks.append(("R8-K1 A1-scope beta = part-2 Q1 beta", F(out["R8-K1"][0]["exact"]), beta))
    checks.append(("R12-X1 recorded split: beta = part-2 Q1 beta", F(out["R12-X1"][0]["exact"]), beta))
    checks.append(("R1-F1 flat benchmark: TE^2 = 52 s2(r)", F(out["R1-F1"][3]["exact_square"]), 52 * 13 * srr / 51))
    ma = mr
    checks.append(("R1-F1 flat benchmark: IR^2 = 52 rbar^2 / s2(r)", F(out["R1-F1"][4]["exact_square"]), 52 * ma ** 2 / (13 * srr / 51)))
    bad = 0
    for label, got, want in checks:
        ok = got == want
        bad += not ok
        print(("ok  " if ok else "BAD ") + label + " = " + frac(want))
    print("CLOSED FORMS", "AGREE" if not bad else "DISAGREE")
    return bad


def retrieval_check(fx):
    """The declared vintages (fixture 1.1-part3, market_data.retrieval) against market-data Ruling 3.1's
    after-retrieval test and performance Ruling 1.7's M_t: (a) every row's file is retrieved at or after the row's
    availability instant (scheduled close, or publication); (b) at every Current-mode instant t of the fixture, a row
    is in M_t (file retrieved <= t) exactly when its availability instant is <= t. So M_t holds exactly the rows due
    at t, and the calculator's instant rule (Ruling 5.8) and the engine's M_t restriction select the same rows."""
    md = fx["market_data"]
    ret = md["retrieval"]
    cal = {c["calendar_id"]: c for c in md["calendars"]}
    ts = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

    def available(cid, d):
        c = cal[cid]
        if c["kind"] == "EXCHANGE_SESSIONS":
            t = c["close"]["default"]
        else:
            t = c["fixing"]["publication"] if c["kind"] == "ECB_FIXINGS" else c["publication"]["time"]
        h, m = map(int, t.split(":"))
        return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=ZoneInfo(c["timezone"])).astimezone(UTC)

    def retrieved(cid, d):
        for v in ret["vintages"]:
            lo, hi = D(v.get("rows_from", "0001-01-01")), D(v.get("rows_through", "9999-12-31"))
            if lo <= d <= hi:
                return ts(v["retrieval_time"]) if "retrieval_time" in v else ts(v["retrieval_time_by_calendar"][cid])
        raise ValueError(f"no vintage holds {cid} {d}")

    instants = [ts(a["instant"]) for p in fx["portfolios"] for a in p["assertions"]
                if a.get("valuation_mode") == "CURRENT"]
    bad, rows = 0, 0
    for cid, c in cal.items():
        days = [d for d in P1.daterange(D(c["coverage"]["from"]), D(c["coverage"]["to"])) if d.weekday() < 5]
        for d in days:
            rows += 1
            a, r = available(cid, d), retrieved(cid, d)
            if r < a:
                bad += 1
                print(f"BAD  {cid} {d}: retrieved {r} before it is available {a} (market-data Ruling 3.1)")
            for t in instants:
                if (a <= t) != (r <= t):
                    bad += 1
                    print(f"BAD  {cid} {d} at t = {t}: due {a <= t}, in M_t {r <= t}")
    ca_t = ts(ret["corporate_actions_retrieval_time"])
    for ca in md.get("corporate_actions", []):
        if any(ca_t > t for t in instants):   # a record may precede its ex-date (announced ahead); it must be in M_t
            bad += 1
            print(f"BAD  corporate action {ca['listing_id']} {ca['ex_date']}: retrieval {ca_t}")
    print(f"RETRIEVAL {'CONSISTENT' if not bad else 'INCONSISTENT'} - {rows} calendar rows, "
          f"{len(instants)} Current-mode instant(s), {bad} problem(s)")
    return bad


VINTAGE_STABLE = {"RAW", "AS_PUBLISHED"}


def release_outcome(fx, case, mut=frozenset()):
    """market-data Ruling 0.1 (1.12): the release-build outcome of one case's file set (one series key)."""
    rc = fx["release_cases"]
    w = World3(fx)
    series_rows = w.prices[rc["series_key"]["listing_id"]].rows
    files = case["files"]
    cov = {f["file"]: (D(f["coverage"][0]), D(f["coverage"][1])) for f in files if f["coverage"] is not None}

    def rows(f):
        if isinstance(f["rows"], dict):
            out = {D(k): F(v) for k, v in f["rows"].items()}
        else:                                  # 'series': the SYN42 rows inside the declared coverage, or the
            lo, hi = map(D, f.get("rows_range") or f["coverage"])     # stated rows_range when none is declared
            out = {d: v for d, v in series_rows.items() if lo <= d <= hi}
        out.update({D(k): F(v) for k, v in f.get("extra_rows", {}).items()})
        return out

    if len(files) > 1 and "M-R4" in mut:
        return {"outcome": "REFUSED_TWO_VINTAGES", "segments": None, "overlap": None}
    ident = lambda f: (f["adjustment_status"], f["anchor"], f["synthetic"])
    if len({ident(f) for f in files}) > 1:
        return {"outcome": "REFUSED_IDENTITY", "segments": None, "overlap": None}
    if len(files) > 1 and files[0]["adjustment_status"] not in VINTAGE_STABLE and "M-R2" not in mut:
        return {"outcome": "REFUSED_NOT_SEGMENTABLE", "segments": None, "overlap": None}
    if len(files) > 1:
        for f in files:                        # Ruling 0.1 (1.13) item 1(b): coverage must be statable
            if f["coverage"] is None:
                if "M-R7" not in mut:
                    return {"outcome": "REFUSED_COVERAGE_UNDETERMINED", "segments": None, "overlap": None}
                ds = sorted(rows(f))
                cov[f["file"]] = (ds[0], ds[-1])
        for f in files:                        # Ruling 0.1 (1.13) item 1(c): no row outside the declared coverage
            lo, hi = cov[f["file"]]
            outside = [d for d in rows(f) if not lo <= d <= hi]
            if outside and "M-R6" not in mut:
                if "M-R5" in mut:
                    cov[f["file"]] = (min([lo] + outside), max([hi] + outside))
                else:
                    return {"outcome": "REFUSED_ROW_OUTSIDE_COVERAGE", "segments": None, "overlap": None}
    overlap = []
    for i, a in enumerate(files):
        for b in files[i + 1:]:
            if "M-R1" in mut:
                common = sorted(set(rows(a)) & set(rows(b)))
            else:
                lo, hi = max(cov[a["file"]][0], cov[b["file"]][0]), min(cov[a["file"]][1], cov[b["file"]][1])
                common = [lo, hi] if lo <= hi else []
                if common and "M-R3" in mut:
                    ra, rb = rows(a), rows(b)
                    days = [d for d in w.cals[rc["series_key"]["calendar"]].days if lo <= d <= hi]
                    if all(ra.get(d) == rb.get(d) for d in days):
                        common = []
            if common:
                overlap.append((min(common), max(common)))
    if overlap:
        lo, hi = min(o[0] for o in overlap), max(o[1] for o in overlap)
        return {"outcome": "REFUSED_OVERLAP", "segments": None, "overlap": [lo.isoformat(), hi.isoformat()]}
    return {"outcome": "ADMITTED", "segments": len(files), "overlap": None}


def release_check(fx):
    rc = fx["release_cases"]
    bad = 0
    for case in rc["cases"]:
        got = release_outcome(fx, case)
        ok = got == case["expected"]
        bad += not ok
        print(("ok  " if ok else "BAD ") + f"{case['id']}: {got}" + ("" if ok else f"  fixture {case['expected']}"))
    for mid in rc["mutation_catalog"]:
        changed = {c["id"] for c in rc["cases"] if release_outcome(fx, c, {mid}) != release_outcome(fx, c)}
        named = {c["id"] for c in rc["cases"] if mid in c["bites"]}
        ok = changed == named
        bad += not ok
        print(("ok  " if ok else "BAD ") + f"{mid}: changes {sorted(changed)}; fixture names {sorted(named)}")
    print("RELEASE CASES", "AGREE" if not bad else "DISAGREE")
    return bad


if __name__ == "__main__":
    fixture = json.load(open(sys.argv[1]))
    if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
        fixture["portfolios"] = json.load(open(sys.argv[2]))
    results = derive(fixture)
    status = 0
    if "--closed" in sys.argv:
        status |= 1 if closed_forms(results) else 0
    if "--mutations" in sys.argv:
        status |= 1 if mutations(fixture) else 0
    if "--check" in sys.argv:
        status |= 1 if check(fixture, results) else 0
    if "--retrieval" in sys.argv:
        status |= 1 if retrieval_check(fixture) else 0
    if "--release" in sys.argv:
        status |= 1 if release_check(fixture) else 0
    if not any(x in sys.argv for x in ("--check", "--mutations", "--closed", "--retrieval", "--release")):
        print(json.dumps(results, indent=1, default=lambda x: frac(x) if isinstance(x, F) else str(x)))
    sys.exit(status)
