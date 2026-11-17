"""The identity registry as an INPUT of a computation (CP3-6; tech plan 16.2).

The resolver's answers (a listing's trading currency, its exchange MIC, its security type) are inputs to valuation: the native currency of an unpriced
listing, the currency of an in-kind flow, the freshness key, the choice of calendar in `D_c(t)`. A manifest that did not cite them would hide an input (P9,
P12). `RecordingResolver` forwards every call to the real resolver and records `(method, listing) -> answer`; its `digest()` goes into the manifest, so
`reproduce` can say "the identity registry facts used differ" instead of only "the result differs".
"""

from __future__ import annotations

import datetime
import uuid
from typing import Dict, Optional, Tuple

from domain.currency import CurrencyCode
from marketdata.canonical import canonical_json, sha256_hex
from marketdata.contracts import ExternalIdentifiers, InstrumentResolution
from marketdata.port import InstrumentResolverPort


class RecordingResolver:
    """An `InstrumentResolverPort` that records the facts it is asked for. Wrapping a `RecordingResolver` returns it unchanged (one record per computation)."""

    def __init__(self, inner: InstrumentResolverPort):
        self._inner = inner
        self.seen: Dict[Tuple[str, str], str] = {}

    @staticmethod
    def wrap(resolver: InstrumentResolverPort) -> "RecordingResolver":
        return resolver if isinstance(resolver, RecordingResolver) else RecordingResolver(resolver)

    def resolve(self, identifiers: ExternalIdentifiers, as_of: Optional[datetime.date]) -> InstrumentResolution:
        return self._inner.resolve(identifiers, as_of)

    def trading_currency(self, listing_id: uuid.UUID) -> Optional[CurrencyCode]:
        value = self._inner.trading_currency(listing_id)
        self.seen[("trading_currency", str(listing_id))] = "-" if value is None else value.code
        return value

    def exchange_mic(self, listing_id: uuid.UUID) -> Optional[str]:
        value = self._inner.exchange_mic(listing_id)
        self.seen[("exchange_mic", str(listing_id))] = "-" if value is None else value
        return value

    def security_type(self, listing_id: uuid.UUID) -> Optional[str]:
        value = self._inner.security_type(listing_id)
        self.seen[("security_type", str(listing_id))] = "-" if value is None else str(value)
        return value

    def digest(self) -> str:
        """sha256 of the canonical JSON of every identity fact the computation asked for, in a fixed order."""
        facts = [[method, listing, value] for (method, listing), value in sorted(self.seen.items())]
        return sha256_hex(canonical_json(facts).encode("utf-8"))
