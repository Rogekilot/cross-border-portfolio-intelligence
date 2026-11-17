# P3 independent financial-source reference for CP6

Author: `quant_cp6_p3`, 2026-10-19. Reference: `cp6-p3-source-reference/1.0`.
This additive source reference defines twelve financial expectations before any
comparison to saved CP6 results. It does not modify the original CP4/CP5/CP6 fixtures,
the CP6 calculator, the P11 derivation, or product code. No CP6 result, demo output,
or product implementation was read to derive it. Review and acceptance are separate.

## Authority, input identity and explicit premise

The sole raw financial source is
`methodology/fixtures/cp4_golden/cp4_golden_part1.json`, fixture
`cp4_golden/1.0-part1`, SHA-256
`e78385b3a6c9ae1ac1fe5ecd527ec6a2d253666a1ee28b92aad8bf6321f3cd3a`.
Use P3 portfolio `d4000000-0000-4000-8000-000000000003`, account
`a4030000-0000-4000-8000-000000000001`, ledger version **2**, as-of
**2026-01-02**, reporting currency **USD**, and listing
`c4000000-0000-4000-8000-000000000003` (`SYN3`). The independent volatility
anchor is original assertion **P3-A1**, `kind=volatility`, `frequency=WEEKLY`,
`TRAILING_MONTHS=36`; this is the pre-existing hand-authored expectation, not an
engine value.

Apply issued `diversification/1.0` §§2–6 without a new financial method.
The convention document's SHA-256 is
`76520201893cb0397967fc73c17b95f3dff0dbb58d5fd128bdcbf20b91a89c21`.
Its historical candidate wording is superseded for capital-policy authority by
PD-0041's explicit FULL_NAV/GLOBAL_PRODUCT owner decision. That decision does not
create personal risk preferences or source admission.

The task separately supplies this **conditional synthetic metadata premise**:
all original fixture listings have country `EXPLICIT_SYNTHETIC_COUNTRY`, sector
`EXPLICIT_SYNTHETIC_SECTOR`, taxonomy `synthetic-sector/1`, effective as-of
`2022-01-01`, `synthetic=true`. These are deliberate test labels, not real domiciles
or sectors, and were not inferred from the raw fixture. The adjacent JSON preserves
the premise apart from raw financial input. A comparison must check the actual
metadata configuration and provenance against it.

## Capital arithmetic and all five concentration values

P3-E1 deposits USD 10,000 on 2022-12-30; P3-E2 buys 100 SYN3 shares for USD 10,000
on the same date. These are P3's only events, so quantity is 100, cash is 0, and
there is no receivable-producing event. SYN3's explicit price cycle begins
2022-12-30, stepping every seven days between 100 and 104. At 2026-01-02,
`j=(2026-01-02 - 2022-12-30)/7=157`, so close is 104.

Thus security value = `100*104=10400`, complete NAV = `10400+0+0=10400` USD,
and the sole nonzero capital bucket is
`SECURITY:c4000000-0000-4000-8000-000000000003`, exact weight **1**.
Zero USD cash is excluded as `ZERO_VALUE`; no positive receivable bucket is invented.
This is listing-and-cash-bucket concentration, not an issuer aggregation.

| Named metric | Exact independent result | Presented result |
|---|---:|---:|
| `largest_position_weight` | max(1) = 1 | 1.000000000000 |
| `largest_security_weight` | max security weight = 1 | 1.000000000000 |
| `top5_concentration` | sum of min(5,1) buckets = 1 | 1.000000000000 |
| `hhi_concentration` | 1² = 1 | 1.000000000000 |
| `effective_positions` | 1/1 = 1 | 1.000000000000 |

All five are AVAILABLE under the complete synthetic valuation; effective positions
has unit COUNT, the other four FRACTION. None establishes a severity threshold.

## Exposure maps: raw UNKNOWN versus explicit synthetic metadata

The raw listing specifies USD quotation currency and `COMMON_STOCK`; §3 maps the
latter to EQUITY. It contains no country or sector classification. Therefore raw-only
country and sector maps are each `{UNKNOWN: 1}`, with classified share 0, unknown
share 1, state LIMITED, reason null and detail `UNKNOWN_CLASSIFICATION`.
Raw XNYS and USD do not justify a US-country or sector claim.

With the explicit metadata premise, the complete maps are instead:

| Dimension / metric | Sole positive category | Exact share | State |
|---|---|---:|---|
| Country / `country_exposure` | EXPLICIT_SYNTHETIC_COUNTRY | 1 | AVAILABLE, conditional on premise |
| Sector / `sector_exposure` | EXPLICIT_SYNTHETIC_SECTOR | 1 | AVAILABLE, conditional on premise |
| Currency / `currency_exposure` | USD | 1 | AVAILABLE |
| Asset class / `asset_class_exposure` | EQUITY | 1 | AVAILABLE |

Each dimension totals the same complete NAV exactly; each presented share is
`1.000000000000`, unit FRACTION. The dated premise precedes the snapshot, carries
its explicit taxonomy and is synthetic. No look-through or real classification is
created. A mismatch in actual metadata prevents matching the named conditional
country/sector dependencies, even if some other category also has numeric share 1.

## Single-security covariance and Euler witness

P3-A1's requested base is 2023-01-02. Its full weekly grid runs from 2023-01-06
through 2026-01-02, with 156 returns, start stub four days and end stub zero.
There are 78 returns of `1/25` and 78 of `-1/26`. No post-purchase P3 flow or
other positive capital leg exists, so the independently specified P3 return series
is also its sole security leg in this synthetic complete-history model.

The following exact arithmetic reproduces the original independent CP4 anchor:

```
n = 156; mean = (1/25 - 1/26)/2 = 1/1300
S = 78*(1/25 - mean)^2 + 78*(-1/26 - mean)^2 = 7803/32500
C = S/(n-1) = 7803/5037500
w = [1]; Q = w' C w = C
A = 52; A*Q = 7803/96875
modeled_volatility = +sqrt(7803/96875) -> 0.283808204205
b_security = w_security*(Cw)_security = Q
risk_contribution_share_security = b_security/Q = 1
risk_contribution_component_security = 1*sqrt(A*Q) -> 0.283808204205
```

Both radical outputs have positive sign and exact-square witness `7803/96875`;
the share is exactly 1. The radical rounding is certified directly with integer
squared bounds below, without using a rounded volatility as an input. Euler sums
are therefore exactly one share and the full modeled volatility. At n=156, the
issued weekly thresholds 51/155 make these three metrics AVAILABLE, reason null,
unit FRACTION. Historical fixed-current-weight modeled volatility is a different
metric from CP4 actual-portfolio volatility; their values coincide only because of
this fixture's single fixed holding and zero positive cash/receivable capital.

This mathematical reuse of the raw CP4 independent expectation does not certify
runtime total-return/action-coverage provenance. CP5 §4's total-return coverage,
alignment and state requirements still apply: a runtime coverage or lineage failure
requires refusal. In particular, absence of dividend rows is not real-world evidence
of complete corporate-action coverage. These synthetic results are neither forecasts
nor personalized risk judgments.

## Standalone source check

Run the Python block below from the repository root. It reads only the raw CP4
source, the issued CP5 convention and this new reference JSON. It uses only the
stdlib; it does not import product code, read any CP6 saved/demo result, touch a
database, fetch data or write files. The parent separately compares the frozen
reference with the actual twelve saved dependencies and checks their provenance.

```python
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from fractions import Fraction as F
from hashlib import sha256
from math import isqrt
from pathlib import Path
import json

root = Path.cwd()
ref = json.loads((root / "methodology/fixtures/cp6_golden/cp6_p3_source_reference.json").read_text())
source = ref["source"]
raw = (root / source["path"]).read_bytes()
assert sha256(raw).hexdigest() == source["sha256"]
assert sha256((root / ref["method"]["path"]).read_bytes()).hexdigest() == ref["method"]["sha256"]
d = json.loads(raw)
assert d["fixture_id"] == source["fixture_id"] and d["market_data"]["synthetic"] is True
p = next(p for p in d["portfolios"] if p["portfolio_id"] == source["portfolio_id"])
assert p["reporting_currency"] == source["reporting_currency"] == "USD"
assert p["accounts"][0]["account_id"] == source["account_id"]
events = [x["event"] for x in p["events"]]
assert len(events) == source["ledger_version"] == 2
assert [e["event_type"] for e in events] == ["DEPOSIT", "BUY"]
assert all(e["event_date"] == "2022-12-30" and e["currency"] == "USD" for e in events)
assert all(e["account_id"] == source["account_id"] for e in events)
assert events[1]["listing_id"] == source["listing_id"]
cash = F(events[0]["amount"]["amount"]) - F(events[1]["amount"]["amount"])
quantity = F(events[1]["quantity"])
listing = next(x for x in d["listings"] if x["listing_id"] == source["listing_id"])
assert listing["trading_currency"] == "USD" and listing["security_type"] == "COMMON_STOCK"
assert not any(k in listing for k in ("country", "sector"))
series = next(x for x in d["market_data"]["prices"]["series"] if x["listing_id"] == source["listing_id"])
assert series["steps"] == [] and series["gaps"] == [] and d["market_data"]["corporate_actions"] == []
cycle = series["cycle"]
asof = date.fromisoformat(source["as_of"])
origin = date.fromisoformat(cycle["from"])
assert series["currency"] == "USD" and series["calendar"] == "SYN4_NYSE"
calendar = next(x for x in d["market_data"]["calendars"] if x["calendar_id"] == series["calendar"])
assert calendar["closed_weekdays"] == [] and calendar["actual_through"] >= source["as_of"]
assert cycle["every_days"] == 7 and list(map(F, cycle["closes"])) == [F(100), F(104)]
assert date.fromisoformat(series["first"]) <= origin <= asof <= date.fromisoformat(series["last"])
j = (asof - origin).days // cycle["every_days"]
close = F(cycle["closes"][j % len(cycle["closes"])])
security_value = quantity * close
nav = security_value + cash
assert (j, quantity, close, cash, security_value, nav) == (157, F(100), F(104), F(0), F(10400), F(10400))
assert [F(ref["capital"][k]) for k in ("quantity", "close", "cash_usd", "security_value_usd", "nav_usd")] == [quantity, close, cash, security_value, nav]
assert ref["capital"]["price_cycle_index"] == j and F(ref["capital"]["receivable_usd"]) == 0
assert ref["capital"]["nonzero_buckets"] == [{"key": "SECURITY:" + source["listing_id"], "value_usd": "10400", "weight_exact": "1"}]
anchor = next(a for a in p["assertions"] if a["id"] == source["assertion_id"])
assert anchor["as_of"] == source["as_of"] and anchor["ledger_version"] == 2
vol = next(e for e in anchor["expect"] if e["kind"] == "volatility")
assert vol["frequency"] == "WEEKLY" and vol["request"] == {"rule": "TRAILING_MONTHS", "months": 36}
assert vol["requested_base"] == "2023-01-02"
window = vol["effective_window"]
assert window == {"base_date": "2023-01-06", "last_period_end": "2026-01-02", "observation_count": 156, "stub_start_days": 4, "stub_end_days": 0}
grid = [date.fromisoformat(window["base_date"]) + timedelta(days=7*k) for k in range(157)]
levels = [F(cycle["closes"][((day-origin).days // 7) % 2]) for day in grid]
returns = [levels[k+1]/levels[k] - 1 for k in range(156)]
assert Counter(returns) == Counter({F(1,25): 78, F(-1,26): 78})
mean = sum(returns, F(0)) / 156
S = sum(((r-mean)**2 for r in returns), F(0))
C = S / 155
w = security_value / nav
Q = w*w*C
b = w*(C*w)
annual_square = 52*Q
assert (mean, S, C, Q, b) == (F(1,1300), F(7803,32500), F(7803,5037500), F(7803,5037500), F(7803,5037500))
assert annual_square == F(vol["exact_square"]) == F(7803,96875)
assert vol["state"] == "AVAILABLE" and vol["reason"] is None
assert vol["thresholds"] == {"insufficient_below": 51, "available_from": 155}
# Positive sqrt, rounded half away from zero, certified by rational squared bounds.
scale = 10**12
k = isqrt((annual_square.numerator * scale**2) // annual_square.denominator)
if (2*k+1)**2 * annual_square.denominator <= 4*annual_square.numerator*scale**2:
    k += 1
assert F((2*k-1)**2, 4*scale**2) < annual_square < F((2*k+1)**2, 4*scale**2)
presented_vol = format(Decimal(k) / Decimal(scale), ".12f")
assert presented_vol == vol["value"] == "0.283808204205"
premise = ref["metadata_premise"]
assert {key: premise[key] for key in ("scope", "effective_as_of", "country", "sector", "taxonomy_id", "synthetic")} == {"scope": "All original fixture listings", "effective_as_of": "2022-01-01", "country": "EXPLICIT_SYNTHETIC_COUNTRY", "sector": "EXPLICIT_SYNTHETIC_SECTOR", "taxonomy_id": "synthetic-sector/1", "synthetic": True}
bucket = "SECURITY:" + source["listing_id"]
expected = {
    ("largest_position_weight", None): (w, "FRACTION"),
    ("largest_security_weight", None): (w, "FRACTION"),
    ("top5_concentration", None): (w, "FRACTION"),
    ("hhi_concentration", None): (w*w, "FRACTION"),
    ("effective_positions", None): (1/(w*w), "COUNT"),
    ("country_exposure", premise["country"]): (w, "FRACTION"),
    ("sector_exposure", premise["sector"]): (w, "FRACTION"),
    ("currency_exposure", "USD"): (w, "FRACTION"),
    ("asset_class_exposure", "EQUITY"): (w, "FRACTION"),
    ("risk_contribution_share", bucket): (b/Q, "FRACTION"),
    ("modeled_volatility", None): (None, "FRACTION"),
    ("risk_contribution_component", bucket): (None, "FRACTION"),
}
assert len(ref["dependencies"]) == len(expected) == 12
assert {(x["metric_id"], x["subject"]) for x in ref["dependencies"]} == set(expected)
for item in ref["dependencies"]:
    exact, unit = expected[item["metric_id"], item["subject"]]
    assert item["state"] == "AVAILABLE" and item["reason"] is None and item["unit"] == unit
    if exact is None:
        assert item["exact"] is None and F(item["exact_square"]) == annual_square and item["sign"] == 1
        assert item["value"] == presented_vol
    else:
        assert F(item["exact"]) == exact and Decimal(item["value"]) == Decimal(exact.numerator)/Decimal(exact.denominator)
for dimension in ("country", "sector"):
    raw_class = ref["raw_only_classification"][dimension]
    assert raw_class == {"complete_map_exact": {"UNKNOWN": "1"}, "state": "LIMITED", "reason": None, "details": ["UNKNOWN_CLASSIFICATION"], "classified_share_exact": "0", "unknown_share_exact": "1"}
print("P3 standalone source checks PASS; 12 independent named expectations; no product imports")
```

This reference closes only the authored expectation side of these twelve named
dependencies. Saved-output matching, metadata/provenance verification, independent
review and the PM's bounded completeness assessment remain separate work. It does
not close the entire historical 66-entry supporting-output inventory or authorize
CP7 implementation, source admission, downloads, purchases, publication or release.
