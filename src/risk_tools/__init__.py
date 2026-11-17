"""Human/CI tools for the CP4 risk and benchmark engine (tech plan 17). NEVER imported by product code (`tests/product/test_performance_series.py::ToolBoundaryTests` enforces it, like
`performance_tools` and `marketdata_tools`).

`cost` measures the cost of the periodic return series and of the exact sums a statistic will need over a worst-case 3-year window (tech plan 17.3.4, the CP4b gate). It reads a clock, which is its
purpose; it is therefore a TOOL, not a product module, and its numbers are measurements, never inputs to a computation.
"""
