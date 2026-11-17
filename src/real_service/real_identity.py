"""F1 R8: the REAL world's fixed inputs, in ONE product-side place (G8). Both the human-run tools (the tools' input module: the qualification run and the loader's
window tool) and the real-mode launcher (`web_api.real_launcher`: the create's `WorldInputs`) import this module, so the identity digest in a proposal is
the one the create rebuilds (`worlds.verify_world` recomputes it and refuses the create on any difference, `RW_WORLD_DIFFERS`). Nothing here reads a file,
a clock, the environment or a database.

Each is the ENGINEER'S choice that no approved document names (listed to the PM):
  * the identity: one instrument, AAPL on XNAS in USD (the HG4 context), with surrogate keys `uuid5(IDENTITY_NAMESPACE, "real-identity-N")` in registration order;
  * the F8B policy: option B of PD-0072 (no corporate-action source is admitted, so the policy names two sources that do not exist);
  * the market conventions: `market11_conventions(calendars)`, as a FUNCTION of the release's calendars (`worlds.market_conventions_for`), and the performance
    conventions: `performance_conventions()`.
"""
from __future__ import annotations

import uuid

from corporate_actions_service import split_confirmation as f8b
from domain.currency import CurrencyCode
from domain.instrument import SecurityType
from marketdata.market11 import market11_conventions
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry
from performance.engine import performance_conventions
from real_service import worlds

#: A fixed namespace for the real identity's surrogate keys. An idempotence key, not a secret.
IDENTITY_NAMESPACE = uuid.UUID("7d1b6a3e-52f0-5b8c-8a1d-3c9e0f4a6b21")
REAL_INSTRUMENTS = (
    InstrumentEntry("Apple Inc.", SecurityType.COMMON_STOCK, "XNAS", "NASDAQ", "AAPL", CurrencyCode("USD"), vendor_ids=(("alphavantage.us", "AAPL"),)),
)
#: Option B of PD-0072: no corporate-action source is admitted, so the policy names two sources that do not exist.
REAL_POLICY = f8b.ConfirmationPolicy(frozenset({"none.admitted.feed"}), frozenset({"none.admitted.filing"}))


def real_resolver():
    """The real identity registry, built the same way every time (ids are a function of the registration order)."""
    counter = [0]

    def new_id():
        counter[0] += 1
        return uuid.uuid5(IDENTITY_NAMESPACE, "real-identity-%d" % counter[0])
    resolver = InMemoryIdentityRegistry(new_id)
    resolver.register_instruments(REAL_INSTRUMENTS)
    return resolver


def real_world_inputs():
    """`WorldInputs` of the REAL branch's create: the real identity, the market conventions as a function of the release's calendars, the performance
    conventions and the option-B policy."""
    return worlds.WorldInputs(real_resolver(), market11_conventions, performance_conventions(), REAL_POLICY)
