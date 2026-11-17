"""CP1-C replay against a real PostgreSQL server (SKIPPED by default).

Appends through `persistence.ledger_store`, reads with `persistence.
ledger_replay_store`, replays with `domain.replay`. Expected values are copied
from the worked examples in `methodology/CP1_LEDGER_REPLAY_CONVENTIONS.md`.

Opt in with ALL of:

  FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 \\
  FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev
      uv run --no-cache --no-sync --frozen --offline python -m unittest \\
      discover -s tests/product -t . -p 'test_postgres_replay_integration.py' -v

Concurrency: safe to run several copies at once against one database. Every schema name
and every portfolio, account, user and listing id is random, so no advisory-lock key (derived
from the portfolio id, database-wide) is shared between runs.

Isolation: one disposable schema `finweb_it_<random>` is created, migrated, and
dropped at the end; every test uses its own portfolio inside it. Randomness is
used only for the schema name and is not part of any asserted value.
"""

import datetime
import importlib.util
import os
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent, SplitRatio  # noqa: E402
from domain.replay import AccountStatus, ReplayDetail  # noqa: E402
from persistence import connection, ledger_replay_store, ledger_store, migrator  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

_MISSING = connection.missing_env_vars(os.environ)
_HAS_DRIVER = importlib.util.find_spec("psycopg") is not None
if _MISSING:
    _SKIP = "replay DB integration tests are opt-in; set: " + "; ".join(_MISSING)
elif not _HAS_DRIVER:
    _SKIP = "psycopg is not installed (owner runs `uv lock` / `uv sync --python 3.12`)"
else:
    _SKIP = ""

USD, HKD = CurrencyCode("USD"), CurrencyCode("HKD")
# Random per process (R3-4): no fixed id is shared between concurrent runs.
_USER = uuid.uuid4()
_ISSUER = uuid.uuid4()
_INSTR = uuid.uuid4()
LU = uuid.uuid4()  # U, USD listing
LH = uuid.uuid4()  # H, HKD listing


def d(text):
    return datetime.date.fromisoformat(text)


@unittest.skipIf(bool(_SKIP), _SKIP)
class ReplayDatabaseTests(unittest.TestCase):
    counter = 0

    @classmethod
    def setUpClass(cls):
        cls.conn = connection.connect(connection.conninfo_from_env(os.environ), autocommit=True)
        cls.schema = "finweb_it_" + uuid.uuid4().hex[:12]
        cls.addClassCleanup(cls._cleanup)
        cls.conn.execute('CREATE SCHEMA "%s"' % cls.schema)
        cls.conn.execute('SET search_path TO "%s"' % cls.schema)
        migrator.apply_migrations(cls.conn)
        cls.conn.execute("INSERT INTO app_user VALUES (%s)", (_USER,))
        cls.conn.execute("INSERT INTO issuer VALUES (%s, 'Issuer', NULL)", (_ISSUER,))
        cls.conn.execute("INSERT INTO instrument VALUES (%s, %s, 'COMMON_STOCK')", (_INSTR, _ISSUER))
        for listing, ccy in ((LU, "USD"), (LH, "HKD")):
            cls.conn.execute(
                "INSERT INTO listing VALUES (%s, %s, 'XNYS', 'NYSE', 'T', %s, NULL, true)",
                (listing, _INSTR, ccy),
            )

    @classmethod
    def _cleanup(cls):
        try:
            cls.conn.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % cls.schema)
        finally:
            cls.conn.close()

    # -- helpers -------------------------------------------------------------

    def next_id(self):
        type(self).counter += 1
        return type(self).counter

    def portfolio(self, accounts=2):
        n = self.next_id()
        # Random ids (R3-4): the ledger's advisory lock key is derived from the portfolio id and
        # advisory locks are database-wide, so fixed ids would make two concurrent runs (in
        # different disposable schemas) contend on the same locks. Nothing asserted depends
        # on the values.
        pid = uuid.uuid4()
        self.conn.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (pid, _USER))
        ids = [uuid.uuid4() for _ in range(accounts)]
        for acct in ids:
            self.conn.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (acct, pid))
        return pid, ids

    def ev(self, kind, acct, day, ccy=USD, listing=None, q=None, amt=None, basis=None,
           bought=None, ratio=None, cp=None, reverses=None, corrects=None, settle=None):
        return LedgerEvent(
            event_id=uuid.UUID(int=(0xD3 << 120) + self.next_id()), account_id=acct,
            event_type=kind, event_date=d(day), currency=ccy, listing_id=listing,
            quantity=None if q is None else Decimal(q),
            amount=None if amt is None else Money(Decimal(amt), ccy),
            cost_basis=None if basis is None else Money(Decimal(basis), ccy),
            bought_amount=None if bought is None else Money(Decimal(bought[0]), bought[1]),
            split_ratio=None if ratio is None else SplitRatio(Decimal(ratio[0]), Decimal(ratio[1])),
            counterparty_account_id=cp,
            settlement_date=None if settle is None else d(settle),
            reverses_event_id=None if reverses is None else reverses,
            corrects_event_id=None if corrects is None else corrects,
        )

    def add(self, event):
        return ledger_store.append_event(self.conn, event)

    def replay(self, pid, day, version=None):
        return ledger_replay_store.replay(self.conn, pid, d(day), version)

    def cash(self, state, acct, ccy):
        return state.cash_balance(acct, ccy).value

    # -- ledger version --------------------------------------------------------

    def test_ledger_version_is_the_portfolios_max_committed_seq(self):
        pid, (a1, a2) = self.portfolio()
        other, (b1, _) = self.portfolio()
        self.assertEqual(ledger_replay_store.current_ledger_version(self.conn, pid), 0)
        first = self.add(self.ev(EventType.DEPOSIT, a1, "2025-01-02", amt="100"))
        self.assertEqual(ledger_replay_store.current_ledger_version(self.conn, pid), first.ledger_seq)
        self.add(self.ev(EventType.DEPOSIT, b1, "2025-01-02", amt="7"))  # another portfolio
        self.assertEqual(ledger_replay_store.current_ledger_version(self.conn, pid), first.ledger_seq)
        second = self.add(self.ev(EventType.DEPOSIT, a2, "2025-01-03", amt="1"))
        self.assertGreater(second.ledger_seq, first.ledger_seq)
        self.assertEqual(ledger_replay_store.current_ledger_version(self.conn, pid), second.ledger_seq)
        loaded = ledger_replay_store.load_events(self.conn, pid, second.ledger_seq)
        self.assertEqual([e.ledger_seq for e in loaded], [first.ledger_seq, second.ledger_seq])
        self.assertEqual({e.event.account_id for e in loaded}, {a1, a2})  # nothing from the other portfolio

    def test_unknown_portfolio_and_future_pin_are_refused(self):
        with self.assertRaises(ledger_replay_store.PortfolioNotFoundError):
            ledger_replay_store.current_ledger_version(self.conn, uuid.uuid4())
        pid, (a1, _) = self.portfolio()
        current = self.add(self.ev(EventType.DEPOSIT, a1, "2025-01-02", amt="1")).ledger_seq
        with self.assertRaises(ledger_replay_store.LedgerVersionNotCommittedError):
            self.replay(pid, "2025-01-02", current + 1)

    def test_empty_ledger_replays_to_no_accounts(self):
        pid, _ = self.portfolio()
        state = self.replay(pid, "2025-01-02")
        self.assertEqual((state.ledger_version, state.accounts), (0, ()))

    # -- examples through the store -------------------------------------------

    def test_example_2a_correction_and_pinned_versions(self):
        pid, (a1, _) = self.portfolio()
        r1 = self.add(self.ev(EventType.DEPOSIT, a1, "2025-01-02", amt="10000"))
        r2 = self.add(self.ev(EventType.BUY, a1, "2025-01-06", listing=LU, q="50", amt="7500"))
        reversal = self.ev(EventType.REVERSAL, a1, "2025-01-20", reverses=r2.event.event_id)
        replacement = self.ev(EventType.BUY, a1, "2025-01-07", listing=LU, q="40", amt="6000",
                              corrects=r2.event.event_id)
        fix = ledger_store.append_correction(self.conn, reversal, replacement)
        v_old, v_new = r2.ledger_seq, fix.replacement.ledger_seq
        for day, version, u, usd_cash in (
            ("2025-01-10", v_old, "50", "2500"),
            ("2025-01-10", v_new, "40", "4000"),
            ("2025-01-06", v_new, "0", "10000"),
            ("2025-01-25", v_new, "40", "4000"),
        ):
            with self.subTest(day=day, version=version):
                state = self.replay(pid, day, version)
                self.assertEqual(state.position_quantity(a1, LU).value, Decimal(u))
                self.assertEqual(self.cash(state, a1, USD), Decimal(usd_cash))
        # reproducibility: the old pin still gives the old answer after later appends
        before = self.replay(pid, "2025-01-10", v_old).canonical_json()
        self.add(self.ev(EventType.DEPOSIT, a1, "2025-02-01", amt="1"))
        self.assertEqual(self.replay(pid, "2025-01-10", v_old).canonical_json(), before)
        self.assertEqual(r1.ledger_seq < v_old < v_new, True)

    def test_example_5a_conversion_and_correction_round_trip_through_numeric(self):
        pid, (a1, _) = self.portfolio()
        self.add(self.ev(EventType.DEPOSIT, a1, "2025-04-01", amt="10000"))
        conv = self.add(self.ev(EventType.CURRENCY_CONVERSION, a1, "2025-04-02", amt="1000",
                                bought=("7780", HKD), settle="2025-04-04"))
        self.add(self.ev(EventType.FEE, a1, "2025-04-02", amt="2"))
        buy = self.add(self.ev(EventType.BUY, a1, "2025-04-02", HKD, listing=LH, q="200", amt="7000"))
        state = self.replay(pid, "2025-04-04")
        self.assertEqual(self.cash(state, a1, USD), Decimal(8998))
        self.assertEqual(self.cash(state, a1, HKD), Decimal(780))
        self.assertEqual(state.position_quantity(a1, LH).value, Decimal(200))
        v4 = buy.ledger_seq
        fix = ledger_store.append_correction(
            self.conn,
            self.ev(EventType.REVERSAL, a1, "2025-04-10", reverses=conv.event.event_id),
            self.ev(EventType.CURRENCY_CONVERSION, a1, "2025-04-02", amt="1000",
                    bought=("7750", HKD), corrects=conv.event.event_id),
        )
        self.assertEqual(self.cash(self.replay(pid, "2025-04-02", v4), a1, HKD), Decimal(780))
        after = self.replay(pid, "2025-04-02", fix.replacement.ledger_seq)
        self.assertEqual((self.cash(after, a1, USD), self.cash(after, a1, HKD)),
                         (Decimal(8998), Decimal(750)))

    def test_c1c2_example_5a_b_the_half_correction_pin_is_refused(self):
        """Example 5A-B: seqs buy 4, reversal 5, replacement 6. L=5 is the state the atomic
        append forbids (9,998 USD / -7,000 HKD); replay must refuse it, not return it."""
        pid, (a1, _) = self.portfolio()
        self.add(self.ev(EventType.DEPOSIT, a1, "2025-04-01", amt="10000"))
        conv = self.add(self.ev(EventType.CURRENCY_CONVERSION, a1, "2025-04-02", amt="1000",
                                bought=("7780", HKD)))
        self.add(self.ev(EventType.FEE, a1, "2025-04-02", amt="2"))
        buy = self.add(self.ev(EventType.BUY, a1, "2025-04-02", HKD, listing=LH, q="200", amt="7000"))
        fix = ledger_store.append_correction(
            self.conn,
            self.ev(EventType.REVERSAL, a1, "2025-04-10", reverses=conv.event.event_id),
            self.ev(EventType.CURRENCY_CONVERSION, a1, "2025-04-02", amt="1000",
                    bought=("7750", HKD), corrects=conv.event.event_id),
        )
        l4, l5, l6 = buy.ledger_seq, fix.reversal.ledger_seq, fix.replacement.ledger_seq
        self.assertLess(l4, l5)
        self.assertLess(l5, l6)
        with self.assertRaises(ledger_replay_store.LedgerVersionNotABoundaryError):
            self.replay(pid, "2025-04-02", l5)
        ok4, ok6 = self.replay(pid, "2025-04-02", l4), self.replay(pid, "2025-04-02", l6)
        self.assertEqual((self.cash(ok4, a1, USD), self.cash(ok4, a1, HKD)), (Decimal(8998), Decimal(780)))
        self.assertEqual((self.cash(ok6, a1, USD), self.cash(ok6, a1, HKD)), (Decimal(8998), Decimal(750)))
        self.assertEqual(self.replay(pid, "2025-04-02").ledger_version, l6)  # the default pin

    def test_c1c2_pins_inside_a_batch_and_between_transfer_legs_are_refused(self):
        pid, (a1, a3) = self.portfolio()
        first = self.add(self.ev(EventType.DEPOSIT, a1, "2025-02-01", amt="2500"))
        out_r, in_r = ledger_store.append_internal_transfer(
            self.conn,
            self.ev(EventType.TRANSFER_OUT, a1, "2025-02-10", amt="1000", cp=a3),
            self.ev(EventType.TRANSFER_IN, a3, "2025-02-10", amt="1000", cp=a1),
        )
        later = self.add(self.ev(EventType.DEPOSIT, a1, "2025-02-11", amt="1"))
        with self.assertRaises(ledger_replay_store.LedgerVersionNotABoundaryError):
            self.replay(pid, "2025-02-10", out_r.ledger_seq)  # out-leg only: half a transfer
        self.assertEqual(self.replay(pid, "2025-02-10", first.ledger_seq).ledger_version, first.ledger_seq)
        self.assertEqual(self.replay(pid, "2025-02-10", in_r.ledger_seq).ledger_version, in_r.ledger_seq)
        self.assertEqual(self.replay(pid, "2025-02-11", later.ledger_seq).ledger_version, later.ledger_seq)
        batch = ledger_store.append_batch(self.conn, [
            self.ev(EventType.DEPOSIT, a1, "2025-03-01", amt="1"),
            self.ev(EventType.DEPOSIT, a1, "2025-03-01", amt="2"),
            self.ev(EventType.DEPOSIT, a1, "2025-03-01", amt="3"),
        ])
        self.add(self.ev(EventType.DEPOSIT, a1, "2025-03-02", amt="4"))
        for inside in (batch[0], batch[1]):
            with self.assertRaises(ledger_replay_store.LedgerVersionNotABoundaryError):
                self.replay(pid, "2025-03-01", inside.ledger_seq)
        self.assertEqual(self.replay(pid, "2025-03-01", batch[2].ledger_seq).ledger_version,
                         batch[2].ledger_seq)

    def xids(self, pid):
        return [r[0] for r in self.conn.execute(
            "SELECT append_xid::text FROM ledger_event WHERE portfolio_id = %s ORDER BY ledger_seq",
            (pid,)).fetchall()]

    def test_c1c2_guard_uses_append_xid_and_savepoints_do_not_hide_an_append(self):
        pid, (a1, _) = self.portfolio()
        # Separate transactions: distinct append_xid, so no pin between them is ever refused,
        # whatever their recorded_at.
        s1 = self.add(self.ev(EventType.DEPOSIT, a1, "2025-01-02", amt="1")).ledger_seq
        s2 = self.add(self.ev(EventType.DEPOSIT, a1, "2025-01-03", amt="2")).ledger_seq
        x = self.xids(pid)
        self.assertEqual(len(set(x)), 2)
        self.assertNotIn(None, x)
        self.assertEqual(self.replay(pid, "2025-01-03", s1).ledger_version, s1)
        # One caller transaction holding several savepoint-wrapped appends is ONE append.
        with self.conn.transaction():
            inner = [self.add(self.ev(EventType.DEPOSIT, a1, "2025-02-01", amt=str(n))).ledger_seq
                     for n in (1, 2, 3)]
        self.assertEqual(len(set(self.xids(pid)[2:])), 1)
        for inside in inner[:2]:
            with self.assertRaises(ledger_replay_store.LedgerVersionNotABoundaryError):
                self.replay(pid, "2025-02-01", inside)
        self.assertEqual(self.replay(pid, "2025-02-01", inner[2]).ledger_version, inner[2])
        self.assertEqual(self.replay(pid, "2025-02-01", s2).ledger_version, s2)  # before the block

    def test_c1c2_mixed_pre_and_post_0008_portfolio_on_a_real_server(self):
        """Pre-0008 rows (NULL append_xid/portfolio_id) are emulated in this disposable schema
        by disabling the insert trigger and the NOT VALID identity CHECK, then re-enabling."""
        pid, (a1, _) = self.portfolio()
        tbl = "ledger_event"
        self.conn.execute(f"ALTER TABLE {tbl} DISABLE TRIGGER ledger_event_before_insert")
        self.conn.execute(f"ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS ledger_event_append_identity_present")
        try:
            def pre(day, amt, recorded_at):
                event = self.ev(EventType.DEPOSIT, a1, day, amt=amt)
                seq = self.conn.execute("SELECT nextval('ledger_event_ledger_seq_seq')").fetchone()[0]
                cols = ["ledger_seq", *ledger_store.EVENT_COLUMNS, "recorded_at"]
                self.conn.execute(
                    "INSERT INTO ledger_event (%s) VALUES (%s)" % (", ".join(cols), ", ".join(["%s"] * len(cols))),
                    [seq, *ledger_store.event_to_row(event), recorded_at])
                return seq
            t1, t2 = "2020-01-01T00:00:00+00", "2020-01-02T00:00:00+00"
            p1, p2 = pre("2025-01-02", "1", t1), pre("2025-01-02", "2", t1)  # one pre-0008 append
            p3 = pre("2025-01-03", "4", t2)
        finally:
            self.conn.execute(f"ALTER TABLE {tbl} ENABLE TRIGGER ledger_event_before_insert")
        first = ledger_store.append_batch(self.conn, [
            self.ev(EventType.DEPOSIT, a1, "2025-02-01", amt="8"),
            self.ev(EventType.DEPOSIT, a1, "2025-02-01", amt="16")])
        last = self.add(self.ev(EventType.DEPOSIT, a1, "2025-02-02", amt="32"))
        with self.assertRaises(ledger_replay_store.LedgerVersionNotABoundaryError):
            self.replay(pid, "2025-01-02", p1)  # equal recorded_at inside the pre-0008 prefix
        self.assertEqual(self.replay(pid, "2025-01-02", p2).ledger_version, p2)  # 2 | 3: differ
        self.assertEqual(self.replay(pid, "2025-01-03", p3).ledger_version, p3)  # pre | post
        with self.assertRaises(ledger_replay_store.LedgerVersionNotABoundaryError):
            self.replay(pid, "2025-02-01", first[0].ledger_seq)  # inside a post-0008 append
        self.assertEqual(self.replay(pid, "2025-02-01", first[1].ledger_seq).ledger_version,
                         first[1].ledger_seq)
        state = self.replay(pid, "2025-02-02")  # default pin: all rows load, pre and post
        self.assertEqual(self.cash(state, a1, USD), Decimal(1 + 2 + 4 + 8 + 16 + 32))
        self.assertEqual(state.ledger_version, last.ledger_seq)

    def test_example_6a_internal_transfer_pair_is_neutral(self):
        pid, (a1, a3) = self.portfolio()
        self.add(self.ev(EventType.DEPOSIT, a1, "2025-02-01", amt="2500"))
        ledger_store.append_internal_transfer(
            self.conn,
            self.ev(EventType.TRANSFER_OUT, a1, "2025-02-10", amt="1000", cp=a3),
            self.ev(EventType.TRANSFER_IN, a3, "2025-02-10", amt="1000", cp=a1),
        )
        before, after = self.replay(pid, "2025-02-09"), self.replay(pid, "2025-02-10")
        self.assertEqual((self.cash(after, a1, USD), self.cash(after, a3, USD)),
                         (Decimal(1500), Decimal(1000)))
        self.assertEqual(before.portfolio_cash(USD).value, after.portfolio_cash(USD).value)
        self.assertEqual(after.portfolio_cash(USD).value, Decimal(2500))

    def test_example_3a_split_first_and_single_lot_basis(self):
        pid, (a1, _) = self.portfolio()
        self.add(self.ev(EventType.DEPOSIT, a1, "2025-01-02", amt="10000"))
        self.add(self.ev(EventType.BUY, a1, "2025-01-06", listing=LU, q="50", amt="7500"))
        self.add(self.ev(EventType.SELL, a1, "2025-02-03", listing=LU, q="100", amt="4500"))
        self.add(self.ev(EventType.SPLIT, a1, "2025-02-03", listing=LU, ratio=("4", "1")))
        state = self.replay(pid, "2025-02-03")
        self.assertEqual(state.position_quantity(a1, LU).value, Decimal(100))
        self.assertEqual(self.cash(state, a1, USD), Decimal(7000))
        (basis,) = state.position_basis(a1, LU)  # Example 3-A / Ruling 0.4.3 case 3: 3,750
        self.assertEqual((basis.currency, basis.result.value), (USD, Decimal(3750)))
        self.assertEqual(basis.result.sufficiency_state, SufficiencyState.AVAILABLE)
        self.assertEqual(state.account(a1).positions[0].basis_detail, ())
        self.assertEqual(state.convention_set, "ledger-replay/1.3")

    def test_example_7a_fractional_split_is_unresolved(self):
        pid, (a1, _) = self.portfolio()
        self.add(self.ev(EventType.BUY, a1, "2025-01-06", listing=LU, q="101", amt="7500"))
        self.add(self.ev(EventType.SPLIT, a1, "2025-02-03", listing=LU, ratio=("3", "2")))
        quantity = self.replay(pid, "2025-02-03").position_quantity(a1, LU)
        self.assertIsNone(quantity.value)
        self.assertEqual(quantity.reason_code, ReasonCode.UNRESOLVED_CONVENTION)
        self.assertEqual(self.replay(pid, "2025-02-02").position_quantity(a1, LU).value, Decimal(101))

    def test_example_8a_snapshot_horizon(self):
        pid, (a2, _) = self.portfolio()
        ledger_store.append_batch(self.conn, [
            self.ev(EventType.OPENING_POSITION, a2, "2025-06-30", HKD, listing=LH, q="500"),
            self.ev(EventType.OPENING_CASH, a2, "2025-06-30", HKD, amt="3000"),
        ])
        early = self.replay(pid, "2025-06-29")
        self.assertEqual(early.account(a2).status, AccountStatus.NOT_RECONSTRUCTABLE)
        self.assertEqual(early.position_quantity(a2, LH).sufficiency_state, SufficiencyState.INSUFFICIENT_DATA)
        state = self.replay(pid, "2025-06-30")
        self.assertEqual(state.position_quantity(a2, LH).value, Decimal(500))
        self.assertEqual(self.cash(state, a2, HKD), Decimal(3000))
        (basis,) = state.position_basis(a2, LH)
        self.assertIsNone(basis.result.value)
        self.assertEqual(basis.result.reason_code, ReasonCode.MISSING_COST_BASIS)

    def test_example_9a_negative_quantity(self):
        pid, (a1, _) = self.portfolio()
        self.add(self.ev(EventType.BUY, a1, "2025-03-01", listing=LU, q="10", amt="1500"))
        self.add(self.ev(EventType.SELL, a1, "2025-04-01", listing=LU, q="15", amt="2100"))
        state = self.replay(pid, "2025-04-01")
        self.assertIsNone(state.position_quantity(a1, LU).value)
        self.assertTrue(state.account(a1).has_inconsistency)
        self.assertEqual(self.cash(state, a1, USD), Decimal(600))

    # -- exactness and determinism --------------------------------------------

    def test_decimal_values_survive_numeric_and_replay_exactly(self):
        pid, (a1, _) = self.portfolio()
        # At the ledger's bounds (migration 0008): 29 integer digits, 24 decimals.
        big = "12345678901234567890123456789.123456789012345678901234"
        self.add(self.ev(EventType.DEPOSIT, a1, "2025-01-02", amt=big))
        self.add(self.ev(EventType.BUY, a1, "2025-01-03", listing=LU, q="10.5", amt="1.10"))
        state = self.replay(pid, "2025-01-03")
        # ...789.1234... minus 1.10, by hand: integer part 789 - 1 = 788, fraction .1234... - .10 = .0234...
        self.assertEqual(
            self.cash(state, a1, USD),
            Decimal("12345678901234567890123456788.023456789012345678901234"),
        )
        self.assertEqual(state.position_quantity(a1, LU).value, Decimal("10.5"))

    def test_two_runs_are_byte_identical(self):
        pid, (a1, a2) = self.portfolio()
        self.add(self.ev(EventType.DEPOSIT, a1, "2025-01-02", amt="2500.00"))
        self.add(self.ev(EventType.DEPOSIT, a2, "2025-01-02", HKD, amt="10.10"))
        self.add(self.ev(EventType.TRANSFER_IN, a1, "2025-03-10", listing=LU, q="10"))
        first = self.replay(pid, "2025-03-11").canonical_json()
        second = self.replay(pid, "2025-03-11").canonical_json()
        self.assertEqual(first.encode("utf-8"), second.encode("utf-8"))
        self.assertIn('"amount":"2500"', first)
        self.assertIn('"amount":"10.1"', first)


if __name__ == "__main__":
    unittest.main()
