"""Human-run market-data tools (Tech Plan §15.4, PD-0027, PD-0029).

NOTHING IN THE PRODUCT IMPORTS THIS PACKAGE (an import-boundary test enforces it), and
agents never run it: it makes network calls and may use API keys, both of which are human
steps under PD-0027. It exists to save raw source responses as immutable, hashed files with
lineage manifests, which the platform then reads.
"""
