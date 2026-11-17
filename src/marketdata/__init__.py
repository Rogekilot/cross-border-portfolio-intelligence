"""CP2: vendor-independent market-data normalization (Tech Plan §15).

Layers, innermost first: `contracts` (normalized types) and `canonical` (deterministic
encodings); `manifest` (file lineage, release, data-set reference); `conventions`
(protocols and clearly-named placeholders for rules the quant-analyst owns); `port`
(what analytics depends on); `adapters` (pure translators, one per source); `files`,
`ingest`, `store`, `resolver` (verified files -> resolved readings -> in-memory port);
`consumption` (the analytics-facing consumer).

Nothing here makes a network call, reads a clock or uses randomness. Nothing in `domain`
imports this package: CP1 replay produces native-currency facts and has no market data
(Tech Plan §13.E). Downloading files is a human step in `marketdata_tools`, which no
product module imports.
"""
