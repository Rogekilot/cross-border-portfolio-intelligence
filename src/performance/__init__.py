"""CP3: the deterministic performance engine (Tech Plan section 16).

CP3a: valuation (native and reporting views), state propagation, the Computation Manifest and `reproduce`, the convention
set with placeholders for every rule the Quant owns, exact numerics, and the flow-classification structure.

Pure: no persistence, no adapters, no vendors, no clock, no randomness, no float. Public surface: `engine`, `results`,
`manifest`, `conventions`. The AI layer reads `ComputedMetric.to_canonical_dict()`; it never computes a number.
"""
