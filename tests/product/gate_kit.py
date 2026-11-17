"""Test support: the world a hand-built REAL store needs under market-data/1.16 Ruling 4.7 item 6.

The per-reading gate (`profiles.listing_market_refusal`) refuses a REAL reading whose listing's MIC maps to no V1 market, and a REAL
reading of a source that has no profile (SOURCE_NOT_ADMITTED). Many performance and corporate-action tests build a store by hand with
REAL-marked readings of invented sources ("test.feed", "test.filing", "synthetic.us") on an invented exchange ("XTST"), because what they
test is the service over real, admitted data, not the gate. Under 1.16 such a store cannot be built unless the world says the sources
are admitted and the exchange is a US venue. This module says so, for the duration of the construction only: `admitted_real_world`
adds, for the readings it is given, a profile for each real source that has none (upstream `alphavantage`, markets US) and a US market
for each MIC that has none, and removes them on exit. The gate itself is not bypassed or weakened: the readings pass it by the same
rule that refuses them elsewhere, and `test_marketdata_r4a_inputs.GateTests` shows the refusals with the world NOT installed.

Nothing here changes `src/`. The gate runs in the store's constructor, so a store built inside the context stays built after it.
"""

from __future__ import annotations

import contextlib
import dataclasses
import sys
from pathlib import Path
from typing import Iterable, Iterator, Optional
from unittest import mock

_SRC = str(Path(__file__).resolve().parents[2] / "src")
if _SRC not in sys.path:  # the module is imported before the kits that set the path, in a test module run on its own
    sys.path.insert(0, _SRC)

from marketdata import profiles  # noqa: E402


def synthetic_profile(source_id: str) -> profiles.SourceProfile:
    """A US profile of an admitted upstream (the A.5 order for US lists `alphavantage`), for a source that exists only in a test."""
    return profiles.SourceProfile(source_id, "alphavantage", profiles.OBSERVED, markets=("US",))


@contextlib.contextmanager
def delivered_dp(source_id: str, dp: int) -> Iterator[None]:
    """A HYPOTHETICAL profile of `source_id` whose price fields deliver `dp` decimals, for the duration of the context.

    market-data/1.16 item 26 (A.4 item 7 on every route) refuses a file whose price text shows more decimals than the profile's
    `delivered_dp`. The recorded Eastmoney profile (`akshare.cn`) declares 2, so a 3-decimal ETF close, a 1.234 B-share close or an
    adjusted value with eight decimals is now refused by the PROFILE check, before the class grid or the adjusted path sees it. The tests
    of those later steps need such a text to reach them, so they run against this profile. It changes no recorded value (the real
    profile is untouched outside the context) and it is a finding for the Quant, not a method: see the self-validation section."""
    base = profiles.SOURCES[source_id]
    fields = {name: (dataclasses.replace(f, delivered_dp=dp) if f.delivered_dp is not None else f) for name, f in base.fields.items()}
    with mock.patch.dict(profiles.SOURCES, {source_id: dataclasses.replace(base, fields=fields)}):
        yield


@contextlib.contextmanager
def admitted_real_world(readings: Iterable[object], *mics: Optional[str]) -> Iterator[None]:
    sources = {r.source_id for r in readings if not r.observation.lineage.is_synthetic}  # type: ignore[attr-defined]
    with admitted_sources(sources, *mics):
        yield


@contextlib.contextmanager
def admitted_sources(source_ids: Iterable[str], *mics: Optional[str]) -> Iterator[None]:
    """The same world for sources named up front (a test that builds, writes and reads a release has no readings yet when it enters)."""
    add_sources = {s: synthetic_profile(s) for s in sorted(set(source_ids)) if s not in profiles.SOURCES}
    add_mics = {m: "US" for m in mics if m is not None and m not in profiles.MIC_MARKET}
    with mock.patch.dict(profiles.SOURCES, add_sources), mock.patch.dict(profiles.MIC_MARKET, add_mics):
        yield
