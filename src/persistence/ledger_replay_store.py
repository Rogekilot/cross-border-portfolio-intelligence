"""Read side of the ledger for CP1-C replay (ledger-replay/1.3 §0.1, §2.3).

`current_ledger_version` is the portfolio's max committed `ledger_seq` (0 for a
portfolio with no events). That integer is what a Computation Manifest cites as
`ledger_version` (Tech Plan §6.2). It is a stable pin: within one portfolio the
sequence value is drawn under a per-portfolio lock held to commit (migration
0003), so no event with `ledger_seq <= L` can become visible after L was read.

`load_events` returns exactly the events with `ledger_seq <= L`, ordered by
`ledger_seq`, as `SequencedEvent`. It reads nothing else and takes no wall
clock. Two statements, no shared snapshot needed: every row at or below a
committed maximum is already committed, and the `<= L` cap excludes anything that
commits later.

`replay` composes the two with `domain.replay.reconstruct`. A pin above the
current maximum is refused: it could not be reproduced, because events that later
commit would fall below it. A pin below it must be a committed transaction boundary
(`require_committed_boundary`, C1C-2): a seq inside an atomic append is refused, judged by
the rows' `append_xid` (migration 0008); `recorded_at` is used only for pre-0008 rows.
`load_events` is the low-level read and does not check the pin; go through `replay`.

`conn` is a psycopg 3 connection; this module does not import the driver.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Optional, Tuple

from domain.replay import ReplayedState, SequencedEvent, reconstruct
from persistence.ledger_store import EVENT_COLUMNS, row_to_event

_EVENT_SELECT = ", ".join(f"e.{c}" for c in EVENT_COLUMNS)

PORTFOLIO_EXISTS_SQL = "SELECT 1 FROM portfolio WHERE portfolio_id = %s"
LEDGER_VERSION_SQL = (
    "SELECT COALESCE(MAX(e.ledger_seq), 0) FROM ledger_event e "
    "JOIN account a ON a.account_id = e.account_id WHERE a.portfolio_id = %s"
)
LOAD_EVENTS_SQL = (
    f"SELECT e.ledger_seq, {_EVENT_SELECT} FROM ledger_event e "
    "JOIN account a ON a.account_id = e.account_id "
    "WHERE a.portfolio_id = %s AND e.ledger_seq <= %s ORDER BY e.ledger_seq"
)


# C1C-2 (pin guard, on `append_xid` since migration 0008).
#
# `ledger_event.append_xid` is the full xid8 of the TOP-LEVEL appending transaction, forced
# by the insert trigger: equal for every row of one append transaction (savepoints included),
# different for rows of different transactions, whatever the clock does. `portfolio_id` is
# forced from the account, and the index (portfolio_id, ledger_seq) INCLUDE (append_xid)
# serves the queries below. A pin L is a valid boundary UNLESS the portfolio rows on both
# sides of L share one append_xid: such an L cuts an atomic append (Ruling 2.3; Example
# 5A-B's 9,998 / -7,000), and no committed state ever had that content.
#
# Adjacent rows suffice (so two index probes, not a scan). Within one portfolio the rows of
# one transaction have contiguous ledger_seq: the trigger stamps the xid, takes the
# per-portfolio advisory lock (held to commit), THEN draws the sequence value, so no other
# transaction can insert a row of this portfolio between two rows of this one. Proof: if some
# row a <= L and some row b > L share an xid X, every portfolio row between a and b has xid X;
# the last row at or below L (`lo`) and the first row above L (`hi`) lie between a and b, so
# lo and hi share X. Conversely an equal adjacent pair is one transaction. Rows of different
# transactions never share an xid, so equal xids are never a false alarm.
#
# Pre-0008 rows have NULL append_xid and NULL portfolio_id. `recorded_at` (the transaction
# start time) is used ONLY for them, and only between two adjacent pre-0008 rows: all pre-0008
# rows of a portfolio come BEFORE its first post-0008 row (0008 runs once, before any later
# append). Scoping of the fallback:
#   - If some post-0008 row is at or below L, then `hi` is post-0008 too: compare xids only.
#   - Otherwise `lo` (if any) is pre-0008. If `hi` is pre-0008, compare their recorded_at
#     (the old rule, with its old limit: two different pre-0008 transactions with an equal
#     recorded_at make that pin refuse; fail closed). If `hi` is post-0008, a pre-0008 row and
#     a post-0008 row are different transactions by definition: a boundary.
#   - A pre-0008 row after a post-0008 row would break the ordering premise: refuse.
# So a portfolio that is partly pre-0008 is judged by xid wherever a post-0008 row is on the
# lower side, and by recorded_at only inside its pre-0008 prefix.
POST_BELOW_SQL = (
    "SELECT ledger_seq, append_xid::text FROM ledger_event "
    "WHERE portfolio_id = %s AND ledger_seq <= %s ORDER BY ledger_seq DESC LIMIT 1"
)
POST_ABOVE_SQL = (
    "SELECT ledger_seq, append_xid::text FROM ledger_event "
    "WHERE portfolio_id = %s AND ledger_seq > %s ORDER BY ledger_seq ASC LIMIT 1"
)
PRE_BELOW_SQL = (
    "SELECT e.ledger_seq, e.recorded_at FROM ledger_event e "
    "JOIN account a ON a.account_id = e.account_id "
    "WHERE e.portfolio_id IS NULL AND a.portfolio_id = %s AND e.ledger_seq <= %s "
    "ORDER BY e.ledger_seq DESC LIMIT 1"
)
PRE_ABOVE_SQL = (
    "SELECT e.ledger_seq, e.recorded_at FROM ledger_event e "
    "JOIN account a ON a.account_id = e.account_id "
    "WHERE e.portfolio_id IS NULL AND a.portfolio_id = %s AND e.ledger_seq > %s "
    "ORDER BY e.ledger_seq ASC LIMIT 1"
)


class PortfolioNotFoundError(LookupError):
    """No such portfolio. Refused rather than reported as an empty ledger."""


class LedgerVersionNotCommittedError(ValueError):
    """The requested pin is above the portfolio's max committed `ledger_seq`."""


class LedgerVersionNotABoundaryError(ValueError):
    """The requested pin falls inside an atomic append (for example between a reversal
    and its replacement): no committed state ever had that content (Ruling 2.3)."""


def require_committed_boundary(conn: Any, portfolio_id: uuid.UUID, ledger_version: int) -> None:
    """Refuse a pin that splits an atomic append (C1C-2). Pins 0 and the current maximum
    are boundaries by construction. Call after checking the pin is not above the maximum."""
    if ledger_version == 0:
        return
    args = (portfolio_id, ledger_version)
    post_below = conn.execute(POST_BELOW_SQL, args).fetchone()
    post_above = conn.execute(POST_ABOVE_SQL, args).fetchone()
    split = False
    if post_below is not None:
        # A post-0008 row is at or below L, so the next row above is post-0008 as well.
        split = (post_above is not None and post_below[1] is not None
                 and post_below[1] == post_above[1])
    else:
        pre_above = conn.execute(PRE_ABOVE_SQL, args).fetchone()
        if pre_above is not None:
            if post_above is not None and post_above[0] < pre_above[0]:
                split = True  # ordering premise broken: fail closed
            else:
                pre_below = conn.execute(PRE_BELOW_SQL, args).fetchone()
                # recorded_at is used only here, between two adjacent pre-0008 rows.
                split = pre_below is not None and pre_below[1] == pre_above[1]
        # else: the next row above is post-0008 (or none) and the row below is pre-0008 (or
        # none): different transactions by definition, a boundary.
    if split:
        raise LedgerVersionNotABoundaryError(
            f"ledger_version {ledger_version} lies inside an atomic append of portfolio "
            f"{portfolio_id}; pin the last ledger_seq of a committed append instead"
        )


def _require_portfolio(conn: Any, portfolio_id: uuid.UUID) -> None:
    if conn.execute(PORTFOLIO_EXISTS_SQL, (portfolio_id,)).fetchone() is None:
        raise PortfolioNotFoundError(f"portfolio {portfolio_id} does not exist")


def current_ledger_version(conn: Any, portfolio_id: uuid.UUID) -> int:
    """The portfolio's max committed `ledger_seq`, or 0 if it has no events."""
    _require_portfolio(conn, portfolio_id)
    return int(conn.execute(LEDGER_VERSION_SQL, (portfolio_id,)).fetchone()[0])


def load_events(
    conn: Any, portfolio_id: uuid.UUID, ledger_version: int
) -> Tuple[SequencedEvent, ...]:
    """All events of the portfolio with `ledger_seq <= ledger_version`, in
    `ledger_seq` order. Includes REVERSAL rows; replay applies them."""
    if isinstance(ledger_version, bool) or not isinstance(ledger_version, int) or ledger_version < 0:
        raise ValueError(f"ledger_version must be an int >= 0, got {ledger_version!r}")
    _require_portfolio(conn, portfolio_id)
    rows = conn.execute(LOAD_EVENTS_SQL, (portfolio_id, ledger_version)).fetchall()
    out = []
    for row in rows:
        seq, event = row_to_event(tuple(row))
        out.append(SequencedEvent(seq, event))
    return tuple(out)


def replay(
    conn: Any,
    portfolio_id: uuid.UUID,
    as_of: datetime.date,
    ledger_version: Optional[int] = None,
) -> ReplayedState:
    """`S(as_of, ledger_version)` for one portfolio. `ledger_version=None` pins the
    current max committed version; the pin used is `state.ledger_version`."""
    current = current_ledger_version(conn, portfolio_id)
    pin = current if ledger_version is None else ledger_version
    if isinstance(pin, bool) or not isinstance(pin, int) or pin < 0:
        raise ValueError(f"ledger_version must be an int >= 0, got {pin!r}")
    if pin > current:
        raise LedgerVersionNotCommittedError(
            f"ledger_version {pin} is above the portfolio's max committed {current}"
        )
    if pin != current:
        require_committed_boundary(conn, portfolio_id, pin)
    return reconstruct(load_events(conn, portfolio_id, pin), as_of, pin)
