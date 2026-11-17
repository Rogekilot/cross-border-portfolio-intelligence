"""The I/O edge of the risk engine (PM ruling Q9, tech plan 17.7.1): reads the committed catalogs, and in a later increment the selection log, the ledger and the release, then calls the pure `risk` package.
Nothing here computes a statistic. `risk` never imports this package."""
