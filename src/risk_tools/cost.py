"""Cost measurement for the periodic return series (tech plan 17.3.4; the CP4b-1 gate). A human/CI tool: it reads a clock, which is its purpose; nothing it prints is an input to a computation.

    python -m risk_tools.cost [--listings 30] [--events 2000] [--flow-days 40] [--frequencies weekly,daily] [--no-identities] [--end 2025-06-30]

WHAT IS BUILT (all SYNTHETIC; deterministic from `--seed`): a world of `--listings` listings (half US in USD on XNAS, half HK in HKD on XHKG), a weekday session calendar and a daily ECB-style fixing for USD and
HKD, one close per listing per weekday over the window and 60 days before it, and a ledger of `--events` events: three accounts (USD, HKD and EUR cash), an opening deposit each, BUY and SELL events spread over the
period (a SELL never exceeds the held quantity) and `--flow-days` days with an external deposit or withdrawal in one of the three currencies. Reporting currency USD, so the HKD holdings and the EUR cash need FX
(HKD through the EUR cross). The window is the PRD default shape: TRAILING_MONTHS 36 ending `--end`.

WHAT IS MEASURED. For each frequency: the time of `compute_return_series` (a fresh run, so every valuation is built once), the number of valuations it needed, and the number of periods; with identities on, the extra time
of I-10; and then the exact sums a statistic will need over the period returns (the sum and the sum of squares, the raw-sum variance numerator) done naively (`Fraction` addition in a loop) and by pairwise (tree)
summation, with their times, the bit lengths of the exact results, and a check that the two give the identical exact value (a mitigation must be output-neutral). It also times `reconstruct` for every valuation date on
its own, because that is the other cost the plan named.

The tool loads the market-data and performance test kits from `tests/product` at run time (like `performance_tools.synthetic`); it is never imported by product code.
"""

from __future__ import annotations

import argparse
import datetime
import sys
import time
from fractions import Fraction
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[2]
D = datetime.date


class KitNotFoundError(RuntimeError):
    pass


def _kits() -> Any:
    kit_dir = REPO / "tests" / "product"
    if not (kit_dir / "performance_kit.py").is_file():
        raise KitNotFoundError(f"the performance kit is not at {kit_dir}: the cost world is built from it")
    if str(kit_dir) not in sys.path:
        sys.path.insert(0, str(kit_dir))
    import performance_kit as pk  # noqa: PLC0415

    return pk


class Lcg:
    """A fixed linear congruential generator: the world is the same on every run."""

    def __init__(self, seed: int):
        self.state = seed % (2**61 - 1) or 1

    def below(self, n: int) -> int:
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) % (2**64)
        return (self.state >> 33) % n


def weekdays(start: datetime.date, end: datetime.date) -> List[datetime.date]:
    out, d = [], start
    while d <= end:
        if d.weekday() < 5:
            out.append(d)
        d += datetime.timedelta(days=1)
    return out


def cents(c: int) -> str:
    return f"{c // 100}.{c % 100:02d}"


class Case:
    """One generated world and ledger."""

    def __init__(self, listings: int, events: int, flow_days: int, end: datetime.date, seed: int):
        pk = _kits()
        from domain.currency import CurrencyCode  # noqa: PLC0415
        from domain.instrument import SecurityType  # noqa: PLC0415
        from domain.ledger import EventType  # noqa: PLC0415
        from marketdata.calendars import CalendarSet  # noqa: PLC0415
        from marketdata.manifest import MarketDataRelease  # noqa: PLC0415
        from marketdata.market11 import market11_conventions  # noqa: PLC0415
        from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: PLC0415
        from marketdata.store import InMemoryMarketData  # noqa: PLC0415

        self.pk, self.end = pk, end
        usd, hkd, eur = CurrencyCode("USD"), CurrencyCode("HKD"), CurrencyCode("EUR")
        rng = Lcg(seed)
        history_start = D(end.year - 3, end.month, 1) - datetime.timedelta(days=75)
        days = weekdays(history_start, end)
        self.days = days
        ident = InMemoryIdentityRegistry(pk.k.kit.SequentialIds())
        specs: List[Tuple[str, str, Any, str]] = []
        for i in range(listings):
            us = i % 2 == 0
            specs.append((f"U{i:03d}" if us else f"{i:04d}", "XNAS" if us else "XHKG", usd if us else hkd, "US" if us else "HK"))
        ident.register_instruments([InstrumentEntry(f"Synthetic {t}", SecurityType.COMMON_STOCK, mic, "SYN", t, ccy) for t, mic, ccy, _m in specs])
        lids = [pk.x.lid(ident, t, mic) for t, mic, _c, _m in specs]
        readings: List[Any] = []
        prices: Dict[Tuple[int, datetime.date], int] = {}
        for i, (_t, _mic, ccy, market) in enumerate(specs):
            c = 2000 + rng.below(20000)
            for d in days:
                c = max(100, c + rng.below(41) - 20)
                prices[(i, d)] = c
                readings.append(pk.quote(lids[i], d, cents(c), ccy, market))
        usd_rate = 10800
        for d in days:
            usd_rate += rng.below(9) - 4
            hkd_rate = usd_rate * 78 // 10 + rng.below(41) - 20  # HKD per USD within 7.80 +- 0.002: inside the peg band the market-data plausibility check applies
            readings.append(pk.fixing(d, "USD", f"{usd_rate // 10000}.{usd_rate % 10000:04d}"))
            readings.append(pk.fixing(d, "HKD", f"{hkd_rate // 10000}.{hkd_rate % 10000:04d}"))
        calendars = CalendarSet([
            pk.k.exchange_calendar("HKEX_SESSIONS", ("XHKG",), days, tz="Asia/Hong_Kong", default_close=datetime.time(16, 10)),
            pk.k.exchange_calendar("NYSE_SESSIONS", ("XNYS", "XNAS"), days, tz="America/New_York"),
            pk.k.ecb_calendar(days),
        ])
        release = MarketDataRelease(name="cost-world", files=(), source_precedence=())
        self.store = InMemoryMarketData(release, readings, exchange_of=ident.exchange_mic, source_records=pk.k.records_for(readings))
        self.ident, self.market, self.usd = ident, market11_conventions(calendars), usd
        a1, a2, a3 = pk.A1, pk.A2, __import__("uuid").UUID(int=3)
        led = pk.Ledger()
        first = days[0]
        led.add(a1, EventType.DEPOSIT, first, usd, amount=led.money("500000000", usd))
        led.add(a2, EventType.DEPOSIT, first, hkd, amount=led.money("3000000000", hkd))
        led.add(a3, EventType.DEPOSIT, first, eur, amount=led.money("1000000", eur))
        flow_idx = {rng.below(len(days) - 1) + 1 for _ in range(flow_days)}
        trade_budget = max(0, events - 3 - len(flow_idx))
        trade_idx = sorted(rng.below(len(days) - 1) + 1 for _ in range(trade_budget))
        held: Dict[Tuple[int, int], int] = {}
        plan = sorted([(i, "flow") for i in flow_idx] + [(i, "trade") for i in trade_idx])
        for idx, kind in plan:
            d = days[idx]
            if kind == "flow":
                which = rng.below(3)
                acct, ccy = ((a1, usd), (a2, hkd), (a3, eur))[which]
                et = EventType.DEPOSIT if rng.below(2) == 0 else EventType.WITHDRAWAL
                led.add(acct, et, d, ccy, amount=led.money(str(1000 * (1 + rng.below(50))), ccy))
                continue
            i = rng.below(listings)
            acct = a1 if specs[i][2] is usd else a2
            ccy = specs[i][2]
            qty = 10 * (1 + rng.below(50))
            have = held.get((i, 0), 0)
            if have >= qty and rng.below(4) == 0:
                et, held[(i, 0)] = EventType.SELL, have - qty
            else:
                et, held[(i, 0)] = EventType.BUY, have + qty
            from decimal import Decimal  # noqa: PLC0415

            amount = Decimal(prices[(i, d)]) * qty / 100
            led.add(acct, et, d, ccy, listing_id=lids[i], quantity=Decimal(qty), amount=led.money(str(amount), ccy))
        self.ledger = led
        self.flow_days = len(flow_idx)


def grid_for(label: str, base: datetime.date, end: datetime.date) -> Tuple[datetime.date, ...]:
    """The grid points of `risk/1.0` Ruling 2.2 in `[base, end]` (what the engine's rule gives for the window)."""
    from performance.grid import Frequency, grid_dates  # noqa: PLC0415

    return grid_dates(Frequency(label.upper()), base, end)


def naive_sums(values: Sequence[Fraction]) -> Tuple[Fraction, Fraction]:
    s, ss = Fraction(0), Fraction(0)
    for v in values:
        s += v
        ss += v * v
    return s, ss


def pairwise_sum(values: Sequence[Fraction]) -> Fraction:
    if not values:
        return Fraction(0)
    level = list(values)
    while len(level) > 1:
        nxt = [level[i] + level[i + 1] for i in range(0, len(level) - 1, 2)]
        if len(level) % 2:
            nxt.append(level[-1])
        level = nxt
    return level[0]


def bits(f: Fraction) -> int:
    return max(f.numerator.bit_length(), f.denominator.bit_length())


def measure(case: Case, label: str, identities: bool) -> Dict[str, Any]:
    from performance import engine, series as S  # noqa: PLC0415
    from performance.periods import WindowRule, WindowSpec  # noqa: PLC0415

    conventions = engine.performance_conventions()
    spec = WindowSpec(WindowRule.TRAILING_MONTHS, 36)
    rule = S.WeekdayFridayMonthEndGrid()
    out: Dict[str, Any] = {"frequency": label}
    t0 = time.perf_counter()
    res = engine.compute_return_series(case.ledger.rows, case.ledger.version, spec, case.end, S.Frequency(label.upper()), rule, case.usd, case.store,
                                       case.ident, case.market, conventions, suppressions=(), verify_identities=False)
    out["series_seconds"] = time.perf_counter() - t0
    assert res.series is not None, res.refusal
    s = res.series
    out["periods"] = len(s.periods)
    out["valuation_dates_read"] = len(s.valuation_dates_read)
    out["flow_days_in_window"] = sum(p.flow_days for p in s.periods)
    out["states"] = s.assessment.to_obj() | {"freshness": s.assessment.freshness.summary}
    if identities:
        t0 = time.perf_counter()
        engine.compute_return_series(case.ledger.rows, case.ledger.version, spec, case.end, S.Frequency(label.upper()), rule, case.usd, case.store,
                                     case.ident, case.market, conventions, suppressions=(), verify_identities=True)
        out["series_with_identities_seconds"] = time.perf_counter() - t0
    values = [p.exact for p in s.periods if p.exact is not None]
    out["exact_periods"] = len(values)
    if values:
        t0 = time.perf_counter()
        s1, ss1 = naive_sums(values)
        var_naive = (len(values) * ss1 - s1 * s1)
        out["naive_sums_seconds"] = time.perf_counter() - t0
        t0 = time.perf_counter()
        s2 = pairwise_sum(values)
        ss2 = pairwise_sum([v * v for v in values])
        var_pair = (len(values) * ss2 - s2 * s2)
        out["pairwise_sums_seconds"] = time.perf_counter() - t0
        out["pairwise_equals_naive"] = (s1, ss1, var_naive) == (s2, ss2, var_pair)
        out["bits"] = {"period_return_max": max(bits(v) for v in values), "sum": bits(s1), "sum_of_squares": bits(ss1), "variance_numerator": bits(var_naive)}
    return out


def reconstruct_seconds(case: Case, dates: Sequence[datetime.date]) -> float:
    from domain.replay import reconstruct  # noqa: PLC0415

    t0 = time.perf_counter()
    for d in dates:
        reconstruct(case.ledger.rows, d, case.ledger.version)
    return time.perf_counter() - t0


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="risk_tools.cost", description=__doc__.split("\n")[0])
    p.add_argument("--listings", type=int, default=30)
    p.add_argument("--events", type=int, default=2000)
    p.add_argument("--flow-days", type=int, default=40)
    p.add_argument("--frequencies", default="weekly,daily")
    p.add_argument("--no-identities", action="store_true")
    p.add_argument("--end", default="2025-06-30")
    p.add_argument("--seed", type=int, default=20261002)
    a = p.parse_args(argv)
    if str(REPO / "src") not in sys.path:
        sys.path.insert(0, str(REPO / "src"))
    from performance.periods import sub_months  # noqa: PLC0415

    end = D.fromisoformat(a.end)
    base = sub_months(end, 36)
    t0 = time.perf_counter()
    case = Case(a.listings, a.events, a.flow_days, end, a.seed)
    print(f"python {sys.version.split()[0]}; world: {a.listings} listings, {len(case.ledger.rows)} ledger events, {case.flow_days} external-flow days, {len(case.days)} weekdays; "
          f"window (36 months) {base.isoformat()} .. {end.isoformat()}; built in {time.perf_counter() - t0:.1f}s")
    for label in [f.strip() for f in a.frequencies.split(",") if f.strip()]:
        bounds = grid_for(label, base, end)
        r = measure(case, label, not a.no_identities)
        r["reconstruct_all_valuation_dates_seconds"] = reconstruct_seconds(case, [d for d in bounds if d <= end])
        for k in sorted(r):
            v = r[k]
            print(f"  {label}: {k} = {v:.3f}" if isinstance(v, float) else f"  {label}: {k} = {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
