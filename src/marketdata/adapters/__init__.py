"""Source adapters: one pure translator per source (Tech Plan §15.1, §15.2).

An adapter turns the bytes of one saved file into unresolved normalized observations.
It does no I/O, reads no clock, imports no vendor library and rounds nothing. Analytics
code never imports this package (an import-boundary test enforces it).
"""
