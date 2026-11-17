"""The real loader's one entry into the market-data projection (F1 R3; closes R4a review LOW-7; design 3.3 "The narrowing").

`market_data_store.write_release` runs its LISTING-level admission gate (a real reading bound to a listing whose market the source's profile
does not cover) only when the caller supplies `exchange_of`, the identity's `exchange_mic`; without it a real reading could be stored on an
unmapped or unadmitted market, and the tables are append-only, so it could never be removed. The read side still fails closed, so no number
was ever served, but a stored row of that kind is a row the loader should not be able to write.

The loader is a database role that holds INSERT on the thirteen tables and SELECT on `md_file` and `md_release` only, so the database cannot
know a listing's market (the identity registry is not in it). The check therefore stays where the identity is: here. `load_release`:

  * requires `exchange_of` (a callable mapping a listing id to its exchange MIC): None is refused BEFORE any statement is sent, so nothing
    is written and no connection is touched;
  * always passes it to `write_release`, and always passes `count_rows=False` (the loader cannot read the counts back).

It does not change `write_release`: its default stays as R4a pinned it (an in-memory or owner-side caller may omit `exchange_of`, and the
1.16 label describes that function as shipped). The REAL path's loader code calls THIS function, not `write_release`.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Sequence
import uuid

from persistence import market_data_store as mds

LOADER_NO_IDENTITY = "RW_LOADER_NO_IDENTITY"


class RealLoaderError(ValueError):
    """A refusal by the loader entry; `code` is a stable string."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def load_release(conn: Any, release: Any, manifests: Sequence[Any], contents: Any, calendars: Any, *,
                 exchange_of: Optional[Callable[[uuid.UUID], Optional[str]]]) -> Any:
    """Project one release as the real loader. `exchange_of` is required (keyword-only, no default): see the module docstring."""
    if exchange_of is None or not callable(exchange_of):
        raise RealLoaderError(LOADER_NO_IDENTITY, "the loader writes a release only with the identity's exchange_mic, so that the listing-level "
                              "admission gate runs before any write (nothing is written)")
    return mds.write_release(conn, release, manifests, contents, calendars, exchange_of=exchange_of, count_rows=False)
