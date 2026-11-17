"""Human-run tools of the real-data path (F1 R4b onward). NEVER imported by product code.

`qualification` is the qualification run of design 6.4: it reads a market-data store, builds the release through the engine's own ingest, and
writes a PROPOSAL (`persistence.real_proposal`) for the owner to review before a publish. It sits outside `persistence` because it needs the
adapters and the ingest build, which the persistence layer must not import (`tests/product/test_marketdata_boundaries.py`).
"""
