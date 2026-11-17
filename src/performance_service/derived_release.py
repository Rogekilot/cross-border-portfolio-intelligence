"""`M_t`: the release derived from `M` for an instant `t` (performance/1.2 Ruling 1.7; tech plan 16.16).

"Current value" at `t` is computed over the files of `M` retrieved at or before `t` (a calendar file counts by its registration time, which is its manifest's
`retrieval_time`), with EVERY CP2 step re-run over exactly those files: the build path (`build_in_memory_market_data`) does ingest, V0 and V0-FX admission,
provenance confirmation, reconciliation inputs and the one-vintage rule on the derived release, so a file retrieved after `t` can neither supply a value nor change
a verdict, and it is not merely hidden at read time. The derived release is a deterministic function of `(M, t)`. Its id is `M_t`'s; the view records `M`'s id and the
hashes of the files left out, for the Computation Manifest.
"""

from __future__ import annotations

import datetime
from typing import Callable, Dict, List, Mapping, Optional, Tuple

from marketdata.conventions import ConventionSet
from marketdata.files import FileStore
from marketdata.ingest import build_in_memory_market_data
from marketdata.adapters.base import AdapterRegistry
from marketdata.manifest import FileManifest, MarketDataRelease, SourceRegistry
from marketdata.market11 import market11_conventions
from marketdata.port import InstrumentResolverPort
from performance.inputs import MarketView


class DerivedReleaseView:
    """A `MarketAtInstant` over a stored release `M` and its file store."""

    def __init__(self, release: MarketDataRelease, files: FileStore, registry: SourceRegistry, adapters: AdapterRegistry,
                 resolver: InstrumentResolverPort,
                 *, catalog_calendars: Mapping[str, str], conventions_for: Callable[..., ConventionSet] = market11_conventions):
        """`catalog_calendars` (benchmark id -> the calendar its catalog entry names) is REQUIRED and passed to the build: a SEGMENTED benchmark file's declared calendar must be the entry's (market-data Ruling 0.1
        (1.13)); a forgotten argument must not mean "no check" (CP4F-8). An explicit empty mapping is for a release read with no benchmark catalog."""
        self._release, self._files, self._registry, self._adapters = release, files, registry, adapters
        self._resolver, self._conventions_for = resolver, conventions_for
        self._catalog_calendars = catalog_calendars

    def view(self, instant: datetime.datetime) -> MarketView:
        if instant.tzinfo is None:
            raise ValueError("the instant t must be timezone-aware")
        index = self._files.index()
        keep: List[str] = []
        left_out: List[str] = []
        for sha in self._release.files:
            path = index.get(sha)
            if path is None:  # the build path raises ReleaseFileMissingError for a file the store lacks; do not hide it here
                keep.append(sha)
                continue
            manifest = FileManifest.from_json(path.read_text(encoding="utf-8"))
            (keep if manifest.retrieval_time <= instant else left_out).append(sha)
        derived = MarketDataRelease(
            name=f"{self._release.name}@{instant.astimezone(datetime.timezone.utc).isoformat()}", files=tuple(sorted(keep)),
            source_precedence=self._release.source_precedence, conventions=self._release.conventions, created_for=self._release.created_for,
            convention_set_id=self._release.convention_set_id)
        built = build_in_memory_market_data(derived, self._files, self._registry, self._adapters, self._resolver, catalog_calendars=self._catalog_calendars)
        return MarketView(built.store, built.calendars, self._conventions_for(built.calendars), self._release.release_id,
                          tuple(sorted(left_out)), instant)
