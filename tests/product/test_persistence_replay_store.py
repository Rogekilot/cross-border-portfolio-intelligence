"""CP1-C store read (`persistence.ledger_replay_store`), driven by a fake
connection: no database, no driver. The real-server behaviour is in
`test_postgres_replay_integration.py` (opt-in)."""

import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent  # noqa: E402
from persistence import ledger_replay_store as store  # noqa: E402
from persistence import ledger_store  # noqa: E402

USD = CurrencyCode("USD")
P = uuid.UUID(int=1)
A = uuid.UUID(int=2)


def event(n, kind=EventType.DEPOSIT, day="2025-01-02", amt="100"):
    return LedgerEvent(uuid.UUID(int=100 + n), A, kind, datetime.date.fromisoformat(day), USD,
                       amount=Money(Decimal(amt), USD))


class _Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class FakeConn:
    def __init__(self, portfolio_exists=True, rows=(), meta=()):
        self.portfolio_exists = portfolio_exists
        self.rows = list(rows)
        # (ledger_seq, append_xid or None for a pre-0008 row, recorded_at) of the portfolio
        self.meta = sorted(meta)
        self.calls = []

    def _boundary_query(self, sql, params):
        post = sql in (store.POST_BELOW_SQL, store.POST_ABOVE_SQL)
        below = sql in (store.POST_BELOW_SQL, store.PRE_BELOW_SQL)
        pin = params[1]
        chosen = [m for m in self.meta
                  if (m[1] is not None) == post and ((m[0] <= pin) if below else (m[0] > pin))]
        if not chosen:
            return _Result([])
        m = chosen[-1] if below else chosen[0]
        return _Result([(m[0], m[1] if post else m[2])])

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))
        if sql in (store.POST_BELOW_SQL, store.POST_ABOVE_SQL, store.PRE_BELOW_SQL, store.PRE_ABOVE_SQL):
            return self._boundary_query(sql, params)
        if sql == store.PORTFOLIO_EXISTS_SQL:
            return _Result([(1,)] if self.portfolio_exists else [])
        if sql == store.LEDGER_VERSION_SQL:
            return _Result([(max([r[0] for r in self.rows], default=0),)])
        if sql == store.LOAD_EVENTS_SQL:
            cap = params[1]
            return _Result([r for r in self.rows if r[0] <= cap])
        raise AssertionError(sql)


def row(seq, ev):
    return (seq,) + ledger_store.event_to_row(ev)


class ReplayStoreTests(unittest.TestCase):
    def conn(self):
        return FakeConn(rows=[row(3, event(1)), row(7, event(2, amt="50")), row(9, event(3, amt="25"))])

    def test_current_version_is_the_max_seq_and_zero_when_empty(self):
        self.assertEqual(store.current_ledger_version(self.conn(), P), 9)
        self.assertEqual(store.current_ledger_version(FakeConn(), P), 0)

    def test_unknown_portfolio_is_an_error_not_an_empty_ledger(self):
        with self.assertRaises(store.PortfolioNotFoundError):
            store.current_ledger_version(FakeConn(portfolio_exists=False), P)
        with self.assertRaises(store.PortfolioNotFoundError):
            store.load_events(FakeConn(portfolio_exists=False), P, 5)

    def test_load_events_caps_at_the_pin_and_keeps_order(self):
        loaded = store.load_events(self.conn(), P, 7)
        self.assertEqual([e.ledger_seq for e in loaded], [3, 7])
        self.assertEqual(loaded[1].event.amount.amount, Decimal(50))

    def test_sql_is_scoped_to_the_portfolio_and_ordered(self):
        self.assertIn("a.portfolio_id = %s", store.LOAD_EVENTS_SQL)
        self.assertIn("e.ledger_seq <= %s", store.LOAD_EVENTS_SQL)
        self.assertTrue(store.LOAD_EVENTS_SQL.endswith("ORDER BY e.ledger_seq"))
        for column in ledger_store.EVENT_COLUMNS:
            self.assertIn(f"e.{column}", store.LOAD_EVENTS_SQL)

    def test_replay_defaults_to_the_current_version_and_reports_the_pin(self):
        state = store.replay(self.conn(), P, datetime.date(2025, 1, 2))
        self.assertEqual(state.ledger_version, 9)
        self.assertEqual(state.cash_balance(A, USD).value, Decimal(175))

    def test_replay_at_an_earlier_pin_is_unchanged_by_later_events(self):
        state = store.replay(self.conn(), P, datetime.date(2025, 1, 2), 7)
        self.assertEqual(state.ledger_version, 7)
        self.assertEqual(state.cash_balance(A, USD).value, Decimal(150))

    def test_a_pin_above_the_committed_maximum_is_refused(self):
        with self.assertRaises(store.LedgerVersionNotCommittedError):
            store.replay(self.conn(), P, datetime.date(2025, 1, 2), 10)

    ROWS = [3, 7, 9]

    def conn_with(self, meta):
        return FakeConn(rows=[row(s, event(i)) for i, s in enumerate(self.ROWS, start=1)], meta=meta)

    def pin(self, conn, version):
        return store.replay(conn, P, datetime.date(2025, 1, 2), version).ledger_version

    def test_c1c2_a_pin_between_rows_of_one_append_xid_is_refused(self):
        conn = self.conn_with([(3, "X1", "t1"), (7, "X2", "t2"), (9, "X2", "t2")])
        with self.assertRaises(store.LedgerVersionNotABoundaryError):
            self.pin(conn, 7)  # rows 7 and 9 are one append
        self.assertEqual(self.pin(conn, 3), 3)  # 3 | 7: different xids
        self.assertEqual(self.pin(conn, 5), 5)  # a gap pin between two appends is a boundary too
        self.assertEqual(self.pin(conn, 9), 9)  # the current maximum
        self.assertEqual(self.pin(conn, 0), 0)

    def test_c1c2_an_identical_recorded_at_no_longer_matters_for_post_0008_rows(self):
        # Three different transactions with the very same recorded_at (clock step back,
        # same microsecond): distinct append_xid, so no pin is refused.
        conn = self.conn_with([(3, "X1", "T"), (7, "X2", "T"), (9, "X3", "T")])
        self.assertEqual([self.pin(conn, v) for v in (3, 7)], [3, 7])

    def test_c1c2_mixed_pre_and_post_0008_portfolio(self):
        # pre-0008 rows 1,2 (one transaction, recorded_at T1), 4 (T2), then post-0008 rows
        # 5,6 (xid X1, recorded_at deliberately equal to T2) and 8 (xid X2).
        meta = [(1, None, "T1"), (2, None, "T1"), (4, None, "T2"),
                (5, "X1", "T2"), (6, "X1", "T2"), (8, "X2", "T3")]
        conn = FakeConn(rows=[row(s, event(s)) for s in (1, 2, 4, 5, 6, 8)], meta=meta)
        with self.assertRaises(store.LedgerVersionNotABoundaryError):
            self.pin(conn, 1)  # inside the pre-0008 prefix: recorded_at of rows 1 and 2 is equal
        self.assertEqual(self.pin(conn, 2), 2)  # 2 | 4: different recorded_at
        self.assertEqual(self.pin(conn, 3), 3)  # a gap
        # 4 | 5: a pre-0008 row and a post-0008 row are different transactions by definition,
        # although their recorded_at happens to be equal: recorded_at is not consulted.
        self.assertEqual(self.pin(conn, 4), 4)
        with self.assertRaises(store.LedgerVersionNotABoundaryError):
            self.pin(conn, 5)  # inside the post-0008 append X1 (rows 5, 6): judged by xid
        self.assertEqual(self.pin(conn, 6), 6)
        self.assertEqual(self.pin(conn, 8), 8)

    def test_c1c2_pre_0008_rows_only_use_the_recorded_at_fallback(self):
        conn = FakeConn(rows=[row(s, event(s)) for s in (1, 2, 3)],
                        meta=[(1, None, "T1"), (2, None, "T2"), (3, None, "T2")])
        self.assertEqual(self.pin(conn, 1), 1)
        with self.assertRaises(store.LedgerVersionNotABoundaryError):
            self.pin(conn, 2)

    def test_c1c2_a_pre_0008_row_above_a_post_0008_row_fails_closed(self):
        # rows: pre 1, post 2, pre 3. Pin 1: no post row at or below it, and a pre row (3) sits
        # above the next post row (2), which breaks the "pre-0008 rows come first" premise.
        conn = FakeConn(rows=[row(s, event(s)) for s in (1, 2, 3)],
                        meta=[(1, None, "a"), (2, "X1", "b"), (3, None, "c")])
        with self.assertRaises(store.LedgerVersionNotABoundaryError):
            self.pin(conn, 1)

    def test_c1c2_the_queries_use_the_index_columns_and_are_scoped_to_the_portfolio(self):
        for sql in (store.POST_BELOW_SQL, store.POST_ABOVE_SQL):
            self.assertIn("portfolio_id = %s", sql)
            self.assertIn("LIMIT 1", sql)
            self.assertIn("append_xid", sql)
            self.assertNotIn("recorded_at", sql)
        for sql in (store.PRE_BELOW_SQL, store.PRE_ABOVE_SQL):
            self.assertIn("e.portfolio_id IS NULL", sql)  # pre-0008 rows only
            self.assertIn("a.portfolio_id = %s", sql)

    def test_bad_pin_types(self):
        for bad in (True, -1, "3"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                store.replay(self.conn(), P, datetime.date(2025, 1, 2), bad)
            with self.subTest(load=bad), self.assertRaises(ValueError):
                store.load_events(self.conn(), P, bad)


if __name__ == "__main__":
    unittest.main()
