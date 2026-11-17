"""The I/O edge of the performance engine (tech plan 16.1): loads the ledger, hands the engine its inputs, and produces the
valuation suppressions in DETECT-ONLY mode. A performance computation NEVER writes the ledger (CP3a PM ruling 3): applying
confirmed splits is a separate, explicit step (`corporate_actions_service.confirm_splits`, normal mode) run before computing.
"""
