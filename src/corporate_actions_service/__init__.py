"""Application services that act on corporate actions. They sit OUTSIDE the market-data layer (which never
imports persistence and never appends to the ledger) and outside the analytics core: they read the market-data port
and write to the user's ledger through the ledger's own append path. Advisory and execution capability stay
separable from the analytics core (PRD section 31); nothing here trades, advises or prices.
"""
