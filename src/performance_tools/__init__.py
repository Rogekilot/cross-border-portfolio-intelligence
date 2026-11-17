"""Human/CI tools for the performance engine (tech plan 16.10). NEVER imported by product code (`tests/product/test_performance_boundaries.py` enforces it, like `marketdata_tools`).

`pack` builds the HG2 evidence pack (a directory of JSON plus one Markdown summary) for a named portfolio and windows; `synthetic` and `real_slice` supply the two subjects (Demonstration A,
fully synthetic; Demonstration B, the real US/ECB slice); `evidence_pack` is the command line.
"""
