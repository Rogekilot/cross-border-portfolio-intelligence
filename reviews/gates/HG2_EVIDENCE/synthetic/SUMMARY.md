# HG2 evidence pack: DEMO-A: US + HK + CN synthetic cross-border portfolio

**Subject kind:** `SYNTHETIC_DEMONSTRATION_A`. **Pack schema:** `finweb.hg2_evidence_pack/1`. **Engine:** `performance/cp3f-0.10`. **Conventions:** `ledger-replay/1.5`, `market-data/1.10`, `performance/1.10`.

> **SYNTHETIC: every result below was computed from a market-data version that holds synthetic files; none is a real market fact (market-data Ruling 4.8).**
> DEMONSTRATION LEDGER: these events are not a user's holdings (P8); they exist to exercise the engine.
> PD-0035 section 3: Mainland China and Hong Kong price behaviour is shown on SYNTHETIC data only. No admissible real CN or HK price source exists (PD-0031, PD-0032); the real slice is US prices (Alpha Vantage, the last 100 sessions) and ECB FX only. A synthetic result is never a real market fact (market-data Ruling 4.8).

This pack REPORTS what the engine computed. It derives no expected value and states no judgment; the golden fixtures and their tests are the correctness proof, and the owner decides (HG2).

## Subject

Golden P1 (US AAPL and MSFT, HK 0700; USD and HKD cash; a 4:1 split; an internal transfer; a conversion with its correction; fees and financing; a missing and an unresolved cost basis) extended with a Mainland China account (CNY cash, SYNA), a HK dividend accrued from its ex-date and a USD withdrawal. Prices, fixings and calendars are the golden SYNTHETIC release (parts 1 to 4); the engine is the production engine.

- Reporting currency: **USD**. As-of date: **2025-04-30**. Ledger version pinned: **30** (30 events).
- Windows: `SINCE_INCEPTION`, `CUSTOM_FROM_2025-03-31`, `TRAILING_1M`, `YTD`.
- Split detection: **F8B_DRY_RUN** (split detection ran read-only over the pinned ledger and the whole release).
- The as-of date 2025-04-30 is the last session of the synthetic CN series (SYNA); P1's later events (May and June) are in the ledger and not yet in force at that date.
- YTD starts before the portfolio's first event, so it is an explicit INSUFFICIENT_DATA (WINDOW_BEFORE_INCEPTION), not a number.
- SYNA has stale sessions 2025-03-17 to 03-19 (the golden P3 case): returns that need every day (attribution) are LIMITED + STALE_DATA there.

## Current value

| view | value | state | reason | details | why (first cause) | manifest |
|---|---|---|---|---|---|---|
| portfolio_value NATIVE CNY | 32000 CNY | AVAILABLE | - | - | - | `93d0cb616f9f` |
| portfolio_value NATIVE HKD | 29350 HKD | AVAILABLE | - | - | - | `93d0cb616f9f` |
| portfolio_value NATIVE USD | 13998 USD | AVAILABLE | - | - | - | `93d0cb616f9f` |
| portfolio_value REPORTING USD | 22168.59 USD | AVAILABLE | - | - | - | `93d0cb616f9f` |

## Returns and gains by window

| window | G | TWR | MWR | attribution (money) | attribution (%) |
|---|---|---|---|---|---|
| SINCE_INCEPTION | 1937.82 (AVAILABLE) | 0.112614862893 (AVAILABLE) | 0.120522994754 (AVAILABLE) | 1937.82 (LIMITED STALE_DATA) | 0.112614862893 (LIMITED STALE_DATA) |
| CUSTOM_FROM_2025-03-31 | 160.05 (AVAILABLE) | 0.007097640053 (AVAILABLE) | 0.007190176216 (AVAILABLE) | 160.05 (AVAILABLE) | 0.007097640053 (AVAILABLE) |
| TRAILING_1M | 160.05 (AVAILABLE) | 0.007097640053 (AVAILABLE) | 0.007190176216 (AVAILABLE) | 160.05 (AVAILABLE) | 0.007097640053 (AVAILABLE) |
| YTD | no value (INSUFFICIENT_DATA WINDOW_BEFORE_INCEPTION) | no value (INSUFFICIENT_DATA WINDOW_BEFORE_INCEPTION) | no value (INSUFFICIENT_DATA WINDOW_BEFORE_INCEPTION) | no value (INSUFFICIENT_DATA WINDOW_BEFORE_INCEPTION) | no value (INSUFFICIENT_DATA WINDOW_BEFORE_INCEPTION) |

## Evidence items (PRD 38.4)

- Reconstructed positions from ledger events: `01_positions.json`
- Current portfolio value: `02_current_value.json`
- Reporting and native currencies: `03_currencies.json`
- Price and FX timestamps: `04_price_fx_timestamps.json`
- Historical FX handling: `05_historical_fx.json`
- Deposits versus investment gains: `06_deposits_vs_gains.json`
- Internal transfers: `07_internal_transfers.json`
- Dividends: `08_dividends.json`
- Splits: `09_splits.json`
- Missing cost basis behaviour: `10_missing_cost_basis.json`
- TWR: `11_twr.json`
- MWR / IRR where supported: `12_mwr_irr.json`
- Realized and unrealized gain where supported: `13_realized_unrealized.json`
- FX attribution: `14_fx_attribution.json`
- Reconciliation proof: `15_reconciliation_proof.json`
- Known numerical tolerances: `16_tolerances.json`

## Reconciliation proof

| identity | status counts |
|---|---|
| I-1 | PASS x 5 |
| I-2 | PASS x 9 |
| I-3 | PASS x 9 |
| I-4 | PASS x 6 |
| I-5 | PASS x 89 |
| I-6 | NOT_APPLICABLE x 3 |
| I-7 | NOT_APPLICABLE x 4 |
| I-8 | NOT_COMPUTABLE x 4, PASS x 16 |
| I-9 | PASS x 6 |

Identities that FAILED: **0** (a failure is an engine fault and withholds the number).

## Reproduction (manifest id, expected result digest)

| computation | manifest id | expected digest | re-run |
|---|---|---|---|
| valuation@2025-04-30 | `93d0cb616f9f7923` | `b7a3a8cffa3464d5` | REPRODUCED |
| valuation@2025-04-23 | `4ee7019bacbddc3c` | `83d4fa7b2c7b7093` | REPRODUCED |
| window:SINCE_INCEPTION | `752261ae07538eb4` | `43d34d1bafdc379b` | REPRODUCED |
| gains:SINCE_INCEPTION | `ebf57afcc0af965c` | `77151e8a086947a8` | REPRODUCED |
| attribution:SINCE_INCEPTION | `679691f4f1747052` | `800120c232566519` | REPRODUCED |
| valuation@2025-01-01 | `12174ebc0e817bf4` | `718b5c8543ce76b0` | REPRODUCED |
| window:CUSTOM_FROM_2025-03-31 | `d1331a0c49db3e81` | `fc4aeb7228a9b934` | REPRODUCED |
| gains:CUSTOM_FROM_2025-03-31 | `8b4065464ba7c6a7` | `7cc87e18e7f643ce` | REPRODUCED |
| attribution:CUSTOM_FROM_2025-03-31 | `2c2bc30ffab09ba7` | `48b6e9f6a3b0eb3f` | REPRODUCED |
| valuation@2025-03-31 | `6612c14e5d6a0515` | `91113ba5bd7fc130` | REPRODUCED |
| window:TRAILING_1M | `9f7c6faa449e7e9f` | `9652b1107fa75553` | REPRODUCED |
| gains:TRAILING_1M | `5814e842257629e3` | `c2020ae891259424` | REPRODUCED |
| attribution:TRAILING_1M | `465ccf3f4220a51e` | `dfed5cfa200e31b1` | REPRODUCED |
| window:YTD | `a2f7dbf6ced8eebf` | `2a8590c097172d3b` | REPRODUCED |
| gains:YTD | `4875b0249fedcfa0` | `f9cf96d6dbaa00cb` | REPRODUCED |
| attribution:YTD | `d18a8fcd41d1a97b` | `cc4d3ffbbf0fb025` | REPRODUCED |
| valuation@2024-12-31 | `64ef6c0e84fd6354` | `ef3e6d745d278a95` | REPRODUCED |

Reproduced with a matching digest: **17 of 17**. `RESULT_NOT_COMPARED` (never counted as reproduced): 0.

## Known tolerances and open items

- tier-E identities I-1 to I-9: 0 (exact rationals)
- a presented money value against its exact value: <= 1/2 minor unit (Ruling 2.2)
- independently presented parts against their presented total: <= (k+1)/2 quanta (Ruling 2.4 item 2)
- an apportioned decomposition, displayed parts against displayed total: 0 (Ruling 2.4 item 3)
- a presented return against its exact value: <= 0.5 x 10^-12 (the quantum)
- Carino sum of components against the TWR, internal: <= 1E-40 (precision 50)
- presented components against the presented TWR: <= 4.5 x 10^-12 (Ruling 2.4 item 2, K = 8)
- IRR against the true root: <= 10^-30 relative + 0.5 x 10^-12 (Ruling 6.2)
- fixture against engine, exact outputs: 0 on the presented value (Ruling 11.2)
- fixture against engine, transcendental outputs: 10^-10 absolute (Ruling 11.2)

`is_conformant` = **False**. Open items the convention set still lists:
- HG2 evidence pack: built (performance_tools, CP3f); the gate decision is the owner's. Identity I-7 (method independence) runs in the test suite and the evidence pack only (Ruling 11.1 (1.2))
- minor-unit table minor-units/1: rows from memory, owner to confirm against ISO 4217: AUD,CAD,CHF,CNY,EUR,GBP,HKD,JPY,SGD,USD

## Limitations of this pack
- Synthetic data throughout: this proves the engine and the pack, not a market fact.
- Gains follow FIFO/1; a broker's lot method may differ.
- `is_conformant` is False while the convention set's open items are listed (section 16).

## Files

- `00_inputs.json` sha256 `bc1458354c6ed6e8`
- `00_manifests.json` sha256 `30429de4afe9d6ee`
- `00_open_items.json` sha256 `eaf8c72804b3c068`
- `01_positions.json` sha256 `3850fd5b9157de9d`
- `02_current_value.json` sha256 `3450abfada84002b`
- `03_currencies.json` sha256 `0cef5c8b2288efa8`
- `04_price_fx_timestamps.json` sha256 `d22485f140540de9`
- `05_historical_fx.json` sha256 `aef3ce9dd421550a`
- `06_deposits_vs_gains.json` sha256 `3b27e6a99614e53d`
- `07_internal_transfers.json` sha256 `67a6e6a9280b99af`
- `08_dividends.json` sha256 `678a88215e647a14`
- `09_splits.json` sha256 `72375812fff5d205`
- `10_missing_cost_basis.json` sha256 `46005d1b9d76c4dd`
- `11_twr.json` sha256 `694c941eeec3d637`
- `12_mwr_irr.json` sha256 `6d930315f1ac16ac`
- `13_realized_unrealized.json` sha256 `47c964c38ea28b2c`
- `14_fx_attribution.json` sha256 `adb8d9a4a6fd2ac9`
- `15_reconciliation_proof.json` sha256 `f5ded8e2d964156e`
- `16_tolerances.json` sha256 `b3c847faf6926552`

Reproduce: `PYTHONPATH=src python -m performance_tools.evidence_pack synthetic --out <dir>` re-runs every computation and compares every digest.
