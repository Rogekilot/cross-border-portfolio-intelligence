# Additive independent P11 financial references for CP6

**Issued:** 2026-10-19 by the Quant/methodology specialist, independent of the CP6
implementation. This adds financial dependency examples required by PD-0041; it
does not modify the frozen `cp6_golden/1.0-part1` rule fixtures or any CP3–CP5
artifact. No CP6 implementation, generated demo output or engineer numeric result
was read to derive these expected values.

## Source and the separate classification premise

The only financial input is
`methodology/fixtures/cp4_golden/cp4_golden_part1.json`, issue
`cp4_golden/1.0-part1`, SHA-256
`e78385b3a6c9ae1ac1fe5ecd527ec6a2d253666a1ee28b92aad8bf6321f3cd3a`.
Its portfolio `d4000000-0000-4000-8000-000000000011` (P11) records:

1. P11-E1, 2022-12-30: deposit 20,000 USD.
2. P11-E2, same date: buy 100 SYN3 for 10,000 USD.
3. P11-E3, 2025-10-06: buy 100 SYN8 for 10,000 USD.

There are no additional P11 events, fees, dividends or receivables in this source.
Both listings trade in USD, matching the portfolio currency, so no FX estimate is
needed. SYN3 is listing `c4000000-0000-4000-8000-000000000003`, SYN8 ends `0008`.

**The financial source has no country or sector classifications.** On that source
alone, the positive security values belong to sector UNKNOWN; they cannot be
called technology, US exposure or a known synthetic sector by inference.

For the CP6 integration example, PM and engineer separately supplied only this
explicit synthetic metadata premise, without supplying output values: every
original fixture listing is assigned country EXPLICIT_SYNTHETIC_COUNTRY and
sector EXPLICIT_SYNTHETIC_SECTOR. The metadata identity is
`synthetic-classification/1`, source `independent synthetic fixture`, taxonomy
`synthetic-sector/1`, as-of 2022-01-01, synthetic true. Thus both P11 securities are
in the same declared synthetic sector. Cash remains the structural CASH sector.
The conditional known-sector expected values below rely on that premise, not on
a sector fact in the original price/ledger fixture. No real classification or
data-source admission is asserted.

## Exact valuation and weights

SYN3's original price cycle starts 2022-12-30, changes every 7 days and alternates
100, 104 USD. For 2025-09-26 the cycle index is 143; for 2026-01-02 it is 157.
Both indices are odd, so the relevant close is 104 USD. SYN8 is not held on the
first date; its price history before first purchase is unnecessary. The original
SYN8 step at 2026-01-02 is 108 USD. Both dates are Friday sessions under the
fixture's deliberately holiday-free synthetic NYSE calendar.

| As-of | SYN3 value | SYN8 value | USD cash | Full NAV | Nonzero capital buckets |
|---|---:|---:|---:|---:|---:|
| 2025-09-26 | 100 × 104 = 10,400 | 0 (not yet held) | 10,000 | 20,400 | 2 |
| 2026-01-02 | 100 × 104 = 10,400 | 100 × 108 = 10,800 | 0 | 21,200 | 2 |

The full-NAV capital convention includes all cash, excludes zero buckets, and
keeps listing identities separate. Therefore the exact bucket weights are:

- 2025-09-26: SYN3 `26/51`, CASH:USD `25/51`.
- 2026-01-02: SYN3 `26/53`, SYN8 `27/53`; no nonzero cash bucket.

## Independently authored expected values

| Quantity | 2025-09-26 exact | 2026-01-02 exact | Display at 12 decimals, HALF_UP |
|---|---|---|---|
| HHI concentration | `(26²+25²)/51² = 1301/2601` | `(26²+27²)/53² = 1405/2809` | `0.500192233756` → `0.500177999288` |
| Largest position/security weight | `26/51` | `27/53` | `0.509803921569` → `0.509433962264` |
| Top-five concentration | `1` | `1` | `1.000000000000` on both dates |
| Effective positions | `2601/1301` | `2809/1405` | `1.999231360492` → `1.999288256228` |
| Declared synthetic sector, conditional on metadata above | `26/51` | `1` | `0.509803921569` → `1.000000000000` |
| Structural CASH sector | `25/51` | `0` (category may be omitted) | `0.490196078431` → `0.000000000000` |
| Declared synthetic country, conditional on metadata above | `26/51` | `1` | `0.509803921569` → `1.000000000000` |
| Structural CASH country | `25/51` | `0` (category may be omitted) | `0.490196078431` → `0.000000000000` |
| USD denomination exposure | `1` | `1` | `1.000000000000` on both dates |
| Asset-class EQUITY | `26/51` | `1` | `0.509803921569` → `1.000000000000` |
| Asset-class CASH | `25/51` | `0` (category may be omitted) | `0.490196078431` → `0.000000000000` |

The country/sector and asset-class maps partition the same full NAV, each summing
exactly to one. Original source `listings` explicitly gives COMMON_STOCK for SYN3
and SYN8; mapping those to asset-class EQUITY follows the issued CP5 convention,
so EQUITY does not depend on invented sector metadata. Both securities and cash
are USD-denominated; hence their denomination weights sum to USD `1`, not separate
USD exposures added to more than one. There are no nonzero receivables, ETFs or
other currencies/classes/buckets at either date. Such zero categories may be
absent from a complete exposure map; their absence is not missing valuation.

The exact HHI difference is
`1405/2809 - 1301/2601 = -104/7306209 < 0`, so a compatible CP6 HHI history-change
rule must say DECREASED / INTERPRETATION / OBSERVATION. This is direction only;
it is not proof that overall economic diversification improved. Both dates have
two nonzero capital buckets, while the security count changed from one to two.

Conditional synthetic-sector exposure increases by `25/51`. Its current value is
exactly one: it breaches any explicitly valid MAXIMUM below one, equals a maximum
of one, and does not breach a maximum above one. No personal policy value is
invented here. Severity additionally depends on actual supported availability,
freshness and comparability; this arithmetic alone cannot certify WARNING.

Without the added classification premise, the source-only country and sector
results are UNKNOWN `26/51` plus CASH `25/51` initially, and UNKNOWN `1` finally, with
UNKNOWN_CLASSIFICATION / LIMITED. The exact same HHI values remain valid because
HHI requires bucket valuation, not sector labels. This distinction must survive
in any integrated evidence statement.

These are capital snapshots, so statistical frequency and observation counts are
not requirements for these numbers. They establish the financial arithmetic of
these named outputs, not source-timestamp freshness, runtime policy wiring,
reproduction enforcement or the remaining HG3 supporting evidence gaps generally.

## Independent read-only reproduction

The following stdlib-only code was run against the original JSON, without any
product module imports. It mechanically reads its three ledger events and price
rules, then checks the independently authored fractions above. It writes nothing.

```python
from datetime import date
from fractions import Fraction as F
from pathlib import Path
from hashlib import sha256
import json

path = Path("methodology/fixtures/cp4_golden/cp4_golden_part1.json")
raw = path.read_bytes()
assert sha256(raw).hexdigest() == "e78385b3a6c9ae1ac1fe5ecd527ec6a2d253666a1ee28b92aad8bf6321f3cd3a"
data = json.loads(raw)
p = next(x for x in data["portfolios"] if x["portfolio_id"].endswith("000000000011"))
prices = {s["listing_id"]: s for s in data["market_data"]["prices"]["series"]}
expected = {
    "2025-09-26": (F(20400), F(1301, 2601), F(26, 51)),
    "2026-01-02": (F(21200), F(1405, 2809), F(1)),
}
for day, (expected_nav, expected_hhi, expected_security_share) in expected.items():
    holdings, cash = {}, F(0)
    for row in p["events"]:
        e = row["event"]
        if e["event_date"] > day:
            continue
        assert e["currency"] == "USD"
        if e["event_type"] == "DEPOSIT":
            cash += F(e["amount"]["amount"])
        elif e["event_type"] == "BUY":
            k = e["listing_id"]
            holdings[k] = holdings.get(k, F(0)) + F(e["quantity"])
            cash -= F(e["amount"]["amount"])
        else:
            raise AssertionError("unexpected source event")
    values = []
    for listing, quantity in holdings.items():
        s = prices[listing]
        assert s["currency"] == "USD"
        if s["cycle"]:
            c = s["cycle"]
            j = (date.fromisoformat(day) - date.fromisoformat(c["from"])).days // c["every_days"]
            close = F(c["closes"][j % len(c["closes"])] )
        else:
            close = F(max((x for x in s["steps"] if x["from"] <= day), key=lambda x: x["from"])["close"])
        values.append(quantity * close)
    securities = sum(values, F(0))
    if cash:
        values.append(cash)
    nav = sum(values, F(0))
    hhi = sum((v / nav) ** 2 for v in values)
    assert (nav, hhi, securities / nav) == (expected_nav, expected_hhi, expected_security_share)
    print(day, "NAV", nav, "HHI", hhi, "conditional sector", securities / nav)
```

Run result: both dates matched all three independently authored exact quantities;
no product implementation or CP6 demo output was a dependency of this derivation.
