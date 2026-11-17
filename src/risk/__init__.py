"""The CP4 risk and benchmark statistics (tech plan 17; `risk/1.2`, `methodology/CP4_RISK_CONVENTIONS.md`).

Pure and deterministic, like `performance`: no clock, no randomness, no I/O, no float, no persistence, no adapter. It imports `performance` (the return series spine, results, numerics, states) and the analytics-facing
`marketdata` modules, and `performance` never imports it. Modules: `registry` (the methodology registry as data), `sqrt` (the exact integer square root), `risk_free` (the risk-free leg), `benchmark` (the benchmark leg),
`stats` (the exact statistics and the one drawdown function), `states` (the only module that names a reason code), `results`, `single` (the single-series metrics and the one metric builder), `manifest` (the Risk
Manifest and `reproduce_risk`) and `engine` (`compute_risk`, the one module that reaches the portfolio leg). The benchmark-relative statistics follow after the independent review of this midpoint.
"""
