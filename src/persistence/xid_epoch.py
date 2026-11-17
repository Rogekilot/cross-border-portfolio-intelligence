"""Python mirror of the SQL function `ledger_full_xid` (migration 0006, R2-1).

PostgreSQL's `xmin` system column is a 32-bit transaction id; the ledger's
same-transaction check needs the FULL 64-bit id (`xid8`, with its epoch) to ask
`pg_xact_status`. The full id is recovered from an anchor that is itself a full id (the
current transaction's own): the true id is the unique X with X == x (mod 2^32) and
|X - anchor| < 2^31. PostgreSQL's xid-wraparound protection guarantees every unfrozen xid a
visible tuple can carry is inside that window around a live xid, so the recovery is exact in
every epoch, including across a wraparound. This mirror exists so the boundary arithmetic is
unit-tested on a cluster that is still in epoch 0, and so the SQL and Python can be compared
over a grid of anchors and values.
"""

from __future__ import annotations

from typing import Optional

_TWO_32 = 1 << 32
_TWO_31 = 1 << 31
FIRST_NORMAL_XID = 3  # 0 invalid, 1 bootstrap, 2 frozen: never "in progress"


def full_xid(xmin32: int, anchor: int) -> Optional[int]:
    """The full transaction id for a 32-bit `xmin` seen from a transaction whose full id is
    `anchor`, or None for the special (frozen/bootstrap/invalid) ids."""
    if xmin32 < FIRST_NORMAL_XID:
        return None
    diff = xmin32 - (anchor % _TWO_32)
    if diff > _TWO_31 - 1:
        diff -= _TWO_32
    elif diff < -_TWO_31:
        diff += _TWO_32
    result = anchor + diff
    if result < FIRST_NORMAL_XID:
        return None
    return result
