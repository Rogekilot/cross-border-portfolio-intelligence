"""CP1-B step 2 — ledger database integration tests (SKIPPED by default).

Nothing here has been run against a server as of this file's writing: the
database and role CP1-B may use have not been decided. They are written to run
once they are.

Opt in by setting ALL of:

  FINWEB_PG_INTEGRATION=1
  FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432          (or FINWEB_PG_HOST and FINWEB_PG_PORT)
  FINWEB_PG_DATABASE=<a database the role may create a schema in>
  FINWEB_PG_USER=<role>
  (password, if any: libpq's PGPASSWORD or ~/.pgpass; never a repo variable)

and have the `psycopg` package installed (uv sync --python 3.12).

    FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 \\
    FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb \\
        uv run --no-cache --no-sync --frozen --offline python -m unittest \\
        discover -s tests/product -t . -p 'test_postgres_ledger_integration.py' -v

Isolation and cleanup: the ledger is append-only, so rows cannot be deleted.
The tests instead create one uniquely named schema (finweb_it_<random>) in the
given database, run every migration into it, and `DROP SCHEMA ... CASCADE`
that schema at the end. Nothing else in the database is touched. The role
needs CREATE on the database. This is the only place tests use randomness (the
disposable schema name); it does not affect any asserted value.
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
from domain.ledger import FIELD_RULES, FORBIDDEN, REQUIRED, EventType, LedgerEvent, SplitRatio  # noqa: E402
from persistence import connection, ledger_store, migrator  # noqa: E402

_MISSING = connection.missing_env_vars(os.environ)
_HAS_DRIVER = importlib.util.find_spec("psycopg") is not None
if _MISSING:
    _SKIP = "ledger DB integration tests are opt-in; set: " + "; ".join(_MISSING)
elif not _HAS_DRIVER:
    _SKIP = "psycopg is not installed (owner runs `uv lock` / `uv sync --python 3.12`)"
else:
    _SKIP = ""

USD = CurrencyCode("USD")
HKD = CurrencyCode("HKD")
D = datetime.date(2024, 3, 15)

_USER = uuid.UUID("a1111111-1111-1111-1111-111111111111")
# Random per process (R3-4): concurrent runs against one database must never share a
# portfolio. (The ledger's advisory lock key also includes the schema name since 0008.)
_P1 = uuid.uuid4()
_P2 = uuid.uuid4()
_A1 = uuid.UUID("a3333333-3333-3333-3333-333333333331")
_A2 = uuid.UUID("a3333333-3333-3333-3333-333333333332")
_B1 = uuid.UUID("a3333333-3333-3333-3333-333333333339")  # other portfolio
_ISSUER = uuid.UUID("b1111111-1111-1111-1111-111111111111")
_INSTR = uuid.UUID("b2222222-2222-2222-2222-222222222222")
_L1 = uuid.UUID("b3333333-3333-3333-3333-333333333331")
_L2 = uuid.UUID("b3333333-3333-3333-3333-333333333332")


class _ExpectSqlstate:
    def __init__(self, test, code):
        self.test, self.code = test, code

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.test.fail("expected SQLSTATE %s, no error raised" % self.code)
        if issubclass(exc_type, self.test.pg.Error):
            self.test.assertEqual(exc.sqlstate, self.code, str(exc))
            return True
        return False


def usd(x):
    return Money(Decimal(x), USD)


@unittest.skipIf(bool(_SKIP), _SKIP)
class LedgerDatabaseTests(unittest.TestCase):
    counter = 0

    @classmethod
    def setUpClass(cls):
        import psycopg  # noqa: PLC0415

        cls.pg = psycopg
        cls.conn = connection.connect(
            connection.conninfo_from_env(os.environ), autocommit=True
        )
        cls.schema = "finweb_it_" + uuid.uuid4().hex[:12]
        cls.addClassCleanup(cls._cleanup)
        cls.conn.execute('CREATE SCHEMA "%s"' % cls.schema)
        cls.conn.execute('SET search_path TO "%s"' % cls.schema)
        cls.applied = migrator.apply_migrations(cls.conn)
        c = cls.conn
        c.execute("INSERT INTO app_user VALUES (%s)", (_USER,))
        c.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (_P1, _USER))
        c.execute("INSERT INTO portfolio VALUES (%s, %s, 'HKD')", (_P2, _USER))
        for acc, p in ((_A1, _P1), (_A2, _P1), (_B1, _P2)):
            c.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (acc, p))
        c.execute("INSERT INTO issuer VALUES (%s, 'Issuer', NULL)", (_ISSUER,))
        c.execute("INSERT INTO instrument VALUES (%s, %s, 'COMMON_STOCK')", (_INSTR, _ISSUER))
        for lst, ccy in ((_L1, "USD"), (_L2, "HKD")):
            c.execute(
                "INSERT INTO listing VALUES (%s, %s, 'XNYS', 'NYSE', 'T', %s, NULL, true)",
                (lst, _INSTR, ccy),
            )

    @classmethod
    def _cleanup(cls):
        try:
            cls.conn.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % cls.schema)
        finally:
            cls.conn.close()

    # -- helpers -------------------------------------------------------------

    def eid(self):
        type(self).counter += 1
        return uuid.UUID(int=(0xE1 << 120) + type(self).counter)

    def expect(self, code):
        return _ExpectSqlstate(self, code)

    def buy(self, **kw):
        base = dict(event_id=self.eid(), account_id=_A1, event_type=EventType.BUY,
                    event_date=D, currency=USD, listing_id=_L1,
                    quantity=Decimal("10"), amount=usd("1500"))
        base.update(kw)
        return LedgerEvent(**base)

    def reversal(self, target, **kw):
        base = dict(event_id=self.eid(), account_id=_A1, event_type=EventType.REVERSAL,
                    event_date=D, currency=USD, reverses_event_id=target)
        base.update(kw)
        return LedgerEvent(**base)

    def append(self, event):
        return ledger_store.append_event(self.conn, event)

    def raw_insert(self, row):
        cols = list(row)
        self.conn.execute(
            "INSERT INTO ledger_event (%s) VALUES (%s)"
            % (", ".join(cols), ", ".join(["%s"] * len(cols))),
            [row[c] for c in cols],
        )

    def row_of(self, event):
        return dict(zip(ledger_store.EVENT_COLUMNS, ledger_store.event_to_row(event)))

    # -- migrations ----------------------------------------------------------

    def test_migrations_applied_and_rerun_is_a_no_op(self):
        self.assertEqual(len(self.applied), 19)  # 0019: CSV reports; 0018: web revisions; 0017: accounts; 0016: RISK_FREE; 0015: selection; 0014: acquired_on; 0009-0013: market-data projection
        self.assertEqual(migrator.apply_migrations(self.conn), [])
        rows = self.conn.execute(
            "SELECT version, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        self.assertEqual(
            [(r[0], r[1]) for r in rows],
            [(m.version, m.checksum) for m in migrator.load_migrations()],
        )

    def test_tampered_checksum_is_refused_and_nothing_changes(self):
        original = self.conn.execute(
            "SELECT checksum FROM schema_migrations WHERE version = 1"
        ).fetchone()[0]
        self.conn.execute(
            "UPDATE schema_migrations SET checksum = repeat('0', 64) WHERE version = 1"
        )
        try:
            with self.assertRaises(migrator.MigrationChecksumError):
                migrator.apply_migrations(self.conn)
        finally:
            self.conn.execute(
                "UPDATE schema_migrations SET checksum = %s WHERE version = 1", (original,)
            )

    # -- Decimal <-> NUMERIC (exact) ------------------------------------------

    def test_decimal_numeric_round_trip_is_exact(self):
        for text in ("1.10", "0.000000000000000000000001",  # 24 decimals: the finest allowed
                     "123456789012345678901234567890.123456789012345678901234",  # 30 + 24
                     "7", "0.5000"):
            q = Decimal(text)
            got = self.append(self.buy(quantity=q, amount=usd(text)))
            back = ledger_store.get_event(self.conn, got.event.event_id).event
            self.assertEqual(back.quantity, q, text)
            self.assertEqual(str(back.quantity), str(q), text)  # scale preserved
            self.assertEqual(back.amount.amount, q, text)

    def test_exponent_form_decimal_round_trips_numerically(self):
        q = Decimal("1E+3")
        back = self.append(self.buy(quantity=q)).event
        self.assertEqual(ledger_store.get_event(self.conn, back.event_id).event.quantity, q)

    # -- FIELD_RULES vs the database ------------------------------------------

    def new_account(self, portfolio=_P1):
        """A fresh account, so snapshot-date rules never couple unrelated tests."""
        type(self).counter += 1
        account = uuid.UUID(int=(0xACC << 100) + type(self).counter)
        self.conn.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (account, portfolio))
        return account

    def _valid(self, t):
        account = self.new_account()
        kw = dict(event_id=self.eid(), account_id=account, event_type=t, event_date=D,
                  currency=USD)
        extra = {
            EventType.BUY: dict(listing_id=_L1, quantity=Decimal("1"), amount=usd("1")),
            EventType.SELL: dict(listing_id=_L1, quantity=Decimal("1"), amount=usd("1")),
            EventType.DIVIDEND: dict(listing_id=_L1, amount=usd("1")),
            EventType.INTEREST: dict(amount=usd("1")),
            EventType.FEE: dict(amount=usd("1")),
            EventType.TAX: dict(amount=usd("1")),
            EventType.DEPOSIT: dict(amount=usd("1")),
            EventType.WITHDRAWAL: dict(amount=usd("1")),
            EventType.TRANSFER_IN: dict(amount=usd("1")),
            EventType.TRANSFER_OUT: dict(amount=usd("1")),
            EventType.SPLIT: dict(listing_id=_L1,
                                  split_ratio=SplitRatio(Decimal("2"), Decimal("1"))),
            EventType.OPENING_POSITION: dict(listing_id=_L1, quantity=Decimal("1")),
            EventType.OPENING_CASH: dict(amount=usd("1")),
            EventType.INTEREST_CHARGED: dict(amount=usd("1")),
            EventType.CURRENCY_CONVERSION: dict(
                amount=usd("1"), bought_amount=Money(Decimal("7.78"), HKD)),
        }.get(t)
        if t is EventType.REVERSAL:
            # Built only for REVERSAL: the target BUY (dated D) must not land in the
            # fresh account of any other type, or it would trip the snapshot rule for
            # OPENING_* rows dated D.
            extra = dict(reverses_event_id=self.append(
                self.buy(account_id=account)).event.event_id)
        kw.update(extra)
        return self.row_of(LedgerEvent(**kw))

    _FORBIDDEN_VALUE = {
        "listing_id": _L1, "quantity": Decimal("1"), "amount": Decimal("1"),
        "cost_basis": Decimal("1"), "counterparty_account_id": _A2,
        "settlement_date": datetime.date(2024, 3, 20), "ex_date": datetime.date(2024, 3, 1),
        "reverses_event_id": uuid.UUID(int=12345), "corrects_event_id": uuid.UUID(int=12346),
        "acquired_on": datetime.date(2024, 3, 1),  # PD-0036: FORBIDDEN except on OPENING_POSITION and TRANSFER_IN
    }

    def test_acquired_on_rules_in_the_database(self):
        """PD-0036 §1, migration 0014: allowed only on OPENING_POSITION and an EXTERNAL SECURITY TRANSFER_IN, never after the event date."""
        opening = self._valid(EventType.OPENING_POSITION)
        opening["acquired_on"] = opening["event_date"] - datetime.timedelta(days=30)
        self.raw_insert(opening)  # allowed, and before the event date
        same_day = self._valid(EventType.OPENING_POSITION)
        same_day["acquired_on"] = same_day["event_date"]
        self.raw_insert(same_day)  # equal to the event date is allowed
        late = self._valid(EventType.OPENING_POSITION)
        late["acquired_on"] = late["event_date"] + datetime.timedelta(days=1)
        with self.expect("23514"):  # never after the event date
            self.raw_insert(late)
        external = self.row_of(self.transfer(listing_id=_L1, quantity=Decimal("2")))
        external["acquired_on"] = external["event_date"] - datetime.timedelta(days=5)
        self.raw_insert(external)  # an external security in-leg: allowed
        internal = self.row_of(self.transfer(listing_id=_L1, quantity=Decimal("2"), counterparty_account_id=_A2))
        internal["acquired_on"] = internal["event_date"]
        with self.expect("23514"):  # an internal in-leg carries its source lot's date
            self.raw_insert(internal)
        cash = self.row_of(self.transfer(amount=usd("5")))
        cash["acquired_on"] = cash["event_date"]
        with self.expect("23514"):  # a cash transfer has no lot
            self.raw_insert(cash)

    def test_database_enforces_field_rules_for_every_type(self):
        for t in EventType:
            self.raw_insert(self._valid(t))  # a valid row is accepted
            for field, rule in FIELD_RULES[t].items():
                if rule == REQUIRED:
                    cols = {"split_ratio": ("split_new", "split_old"),
                            "bought_amount": ("bought_amount", "bought_currency"),
                            }.get(field, (field,))
                    row = self._valid(t)
                    for c in cols:
                        row[c] = None
                    with self.expect("23514"):
                        self.raw_insert(row)
                elif rule == FORBIDDEN:
                    row = self._valid(t)
                    if field == "split_ratio":
                        row["split_new"] = row["split_old"] = Decimal("1")
                    elif field == "bought_amount":
                        row["bought_amount"], row["bought_currency"] = Decimal("1"), "HKD"
                    else:
                        row[field] = self._FORBIDDEN_VALUE[field]
                    with self.expect("23514"):
                        self.raw_insert(row)

    def test_transfer_shape(self):
        sec = dict(listing_id=_L1, quantity=Decimal("2"))
        self.raw_insert(self.row_of(self.transfer(**sec)))
        self.raw_insert(self.row_of(self.transfer(amount=usd("5"))))
        bad = self.row_of(self.transfer(amount=usd("5")))
        bad["listing_id"] = _L1  # listing without quantity
        with self.expect("23514"):
            self.raw_insert(bad)
        bad = self.row_of(self.transfer(amount=usd("5")))
        bad["cost_basis"] = Decimal("1")  # cash form with cost basis
        with self.expect("23514"):
            self.raw_insert(bad)

    def transfer(self, **kw):
        base = dict(event_id=self.eid(), account_id=_A1, event_type=EventType.TRANSFER_IN,
                    event_date=D, currency=USD)
        base.update(kw)
        return LedgerEvent(**base)

    def test_value_checks(self):
        for col, bad in (("quantity", Decimal("0")), ("quantity", Decimal("NaN")),
                         ("quantity", Decimal("Infinity")), ("quantity", Decimal("-1")),
                         ("amount", Decimal("0")), ("amount", Decimal("NaN"))):
            row = self.row_of(self.buy())
            row[col] = bad
            with self.expect("23514"):
                self.raw_insert(row)
        row = self.row_of(self.buy())
        row["settlement_date"] = datetime.date(2024, 3, 1)
        with self.expect("23514"):
            self.raw_insert(row)
        row = self.row_of(self.buy())
        row["currency"] = "usd"
        with self.expect("23514"):
            self.raw_insert(row)
        row = self.row_of(self.buy())
        row["source_reference"] = "  "
        with self.expect("23514"):
            self.raw_insert(row)

    # -- append-only ---------------------------------------------------------

    def test_update_delete_truncate_are_rejected(self):
        self.append(self.buy())
        with self.expect("23001"):
            self.conn.execute("UPDATE ledger_event SET event_date = event_date")
        with self.expect("23001"):
            self.conn.execute("DELETE FROM ledger_event")
        # 0019's source-key FK requires both tables in the statement. PostgreSQL
        # fires BEFORE TRUNCATE in table order; ledger first proves its own guard.
        with self.assertRaises(self.pg.Error) as refused:
            self.conn.execute("TRUNCATE ledger_event, web_csv_source_key")
        self.assertEqual(refused.exception.sqlstate, "23001")
        self.assertEqual(refused.exception.diag.constraint_name, "ledger_event_append_only")
        self.assertEqual(refused.exception.diag.message_primary,
                         "ledger_event is append-only: TRUNCATE is not permitted")

    # -- idempotency ---------------------------------------------------------

    def test_same_key_same_content_is_a_no_op_returning_the_original(self):
        first = self.append(self.buy(source_reference="K-1"))
        self.assertTrue(first.created)
        again = self.append(self.buy(source_reference="K-1"))  # new event_id
        self.assertFalse(again.created)
        self.assertEqual(again.event.event_id, first.event.event_id)
        self.assertEqual(again.ledger_seq, first.ledger_seq)

    def test_scale_difference_is_same_content_and_stored_scale_wins(self):
        first = self.append(self.buy(source_reference="K-2", quantity=Decimal("10.0")))
        again = self.append(self.buy(source_reference="K-2", quantity=Decimal("10.00")))
        self.assertFalse(again.created)
        self.assertEqual(str(again.event.quantity), "10.0")
        self.assertEqual(again.event.event_id, first.event.event_id)

    def test_same_key_different_content_conflicts(self):
        first = self.append(self.buy(source_reference="K-3"))
        with self.assertRaises(ledger_store.IdempotencyConflictError) as cm:
            self.append(self.buy(source_reference="K-3", quantity=Decimal("11")))
        self.assertEqual(cm.exception.existing_event_id, first.event.event_id)

    def test_same_reference_in_another_account_is_a_new_event(self):
        self.append(self.buy(source_reference="K-4"))
        self.assertTrue(self.append(self.buy(source_reference="K-4", account_id=_A2)).created)

    def test_no_reference_means_no_dedupe(self):
        self.assertTrue(self.append(self.buy()).created)
        self.assertTrue(self.append(self.buy()).created)

    def test_event_id_reuse(self):
        e = self.buy()
        self.append(e)
        self.assertFalse(self.append(e).created)
        with self.assertRaises(ledger_store.DuplicateEventIdError):
            self.append(self.buy(event_id=e.event_id, quantity=Decimal("99")))

    # -- reversal / correction -------------------------------------------------

    def test_reversal_once_only(self):
        target = self.append(self.buy()).event
        self.assertTrue(self.append(self.reversal(target.event_id)).created)
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            self.append(self.reversal(target.event_id))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_reversed_once")

    def test_reversal_needs_existing_target_same_account_same_currency(self):
        target = self.append(self.buy()).event
        for bad in (self.reversal(uuid.UUID(int=777)),
                    self.reversal(target.event_id, account_id=_A2),
                    self.reversal(target.event_id, currency=HKD)):
            with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
                self.append(bad)
            self.assertEqual(cm.exception.constraint_name, "ledger_event_reversal_target_fk")

    def test_a_reversal_cannot_be_reversed(self):
        target = self.append(self.buy()).event
        rev = self.append(self.reversal(target.event_id)).event
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            self.append(self.reversal(rev.event_id))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_reversal_of_reversal")

    def test_correction_requires_a_reversed_target(self):
        target = self.append(self.buy()).event
        replacement = dict(corrects_event_id=target.event_id, quantity=Decimal("12"))
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            self.append(self.buy(**replacement))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_corrects_reversed_event")
        # CP1B-5: once the reversal has COMMITTED, a later replacement is refused too
        self.append(self.reversal(target.event_id))
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            self.append(self.buy(**replacement))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_correction_same_transaction")
        # ...while reversal + replacement in ONE transaction is accepted
        other = self.append(self.buy()).event
        fixed = ledger_store.append_correction(
            self.conn, self.reversal(other.event_id),
            self.buy(corrects_event_id=other.event_id, quantity=Decimal("12")))
        self.assertTrue(fixed.replacement.created)

    # -- references --------------------------------------------------------------

    def test_unknown_account_and_listing_rejected(self):
        for bad in (self.buy(account_id=uuid.UUID(int=1)), self.buy(listing_id=uuid.UUID(int=2))):
            with self.assertRaises(ledger_store.LedgerRuleRejectedError):
                self.append(bad)

    def test_transfer_counterparty_must_share_the_portfolio(self):
        bad = self.transfer(amount=usd("5"), counterparty_account_id=_B1)
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            self.append(bad)
        self.assertEqual(cm.exception.constraint_name,
                         "ledger_event_counterparty_same_portfolio")

    # -- F1: internal transfer pairing ---------------------------------------------

    def leg(self, kind, account, other, amount="5", date=D, **kw):
        base = dict(event_id=self.eid(), account_id=account, event_type=kind,
                    event_date=date, currency=USD, counterparty_account_id=other,
                    amount=None if amount is None else usd(amount))
        base.update(kw)
        return LedgerEvent(**base)

    def pair(self, a, b, **kw):
        return (self.leg(EventType.TRANSFER_OUT, a, b, **kw),
                self.leg(EventType.TRANSFER_IN, b, a, **kw))

    def test_internal_transfer_pair_appends_atomically(self):
        a, b = self.new_account(), self.new_account()
        out, inn = self.pair(a, b)
        r_out, r_in = ledger_store.append_internal_transfer(self.conn, out, inn)
        self.assertTrue(r_out.created and r_in.created)
        self.assertLess(r_out.ledger_seq, r_in.ledger_seq)

    def test_security_pair_and_duplicate_identical_pairs(self):
        a, b = self.new_account(), self.new_account()
        kw = dict(amount=None, listing_id=_L1, quantity=Decimal("50"))
        out, inn = self.pair(a, b, **kw)
        ledger_store.append_internal_transfer(self.conn, out, inn)
        out2, inn2 = self.pair(a, b, **kw)  # identical twin: counts still balance
        ledger_store.append_internal_transfer(self.conn, out2, inn2)

    def test_single_leg_alone_fails_at_commit(self):
        a, b = self.new_account(), self.new_account()
        out, _ = self.pair(a, b)
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            self.append(out)
        self.assertEqual(cm.exception.constraint_name, "ledger_event_transfer_pairing")
        self.assertIsNone(ledger_store.get_event(self.conn, out.event_id))  # rolled back

    def test_legs_appended_separately_in_one_transaction_pass(self):
        a, b = self.new_account(), self.new_account()
        out, inn = self.pair(a, b)
        with self.conn.transaction():
            self.append(out)
            self.append(inn)
        self.assertIsNotNone(ledger_store.get_event(self.conn, inn.event_id))

    def test_mismatched_legs_fail_at_commit(self):
        a, b = self.new_account(), self.new_account()
        out = self.leg(EventType.TRANSFER_OUT, a, b, amount="5")
        bad_amount = self.leg(EventType.TRANSFER_IN, b, a, amount="6")
        bad_date = self.leg(EventType.TRANSFER_IN, b, a, amount="5",
                            date=datetime.date(2024, 3, 16))
        for bad in (bad_amount, bad_date):
            with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
                ledger_store.append_batch(self.conn, [out, bad])  # bypasses the Python pair check
            self.assertEqual(cm.exception.constraint_name, "ledger_event_transfer_pairing")

    def test_reversing_one_leg_needs_the_partner_reversed_too(self):
        a, b = self.new_account(), self.new_account()
        out, inn = self.pair(a, b)
        ledger_store.append_internal_transfer(self.conn, out, inn)
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            self.append(self.reversal(out.event_id, account_id=a))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_transfer_pairing")
        ledger_store.append_batch(self.conn, [
            self.reversal(out.event_id, account_id=a),
            self.reversal(inn.event_id, account_id=b),
        ])

    def test_internal_transfer_in_with_cost_basis_rejected_by_check(self):
        a, b = self.new_account(), self.new_account()
        row = self.row_of(self.transfer(account_id=b, event_type=EventType.TRANSFER_IN,
                                        listing_id=_L1, quantity=Decimal("1")))
        row["counterparty_account_id"] = a
        row["cost_basis"] = Decimal("10")
        with self.expect("23514"):
            self.raw_insert(row)

    # -- PD-0024: INTEREST_CHARGED and CURRENCY_CONVERSION ------------------------------
    # Inputs are the Quant's hand-derived Examples 5-A and 5A-A/B/C. Replay does not exist
    # yet, so these assert only what append and storage can show, never a balance.

    def hkd_event(self, account, kind, date, **kw):
        return LedgerEvent(self.eid(), account, kind, date, HKD, **kw)

    def conv(self, account, sold="1000", bought="7780", **kw):
        base = dict(event_id=self.eid(), account_id=account,
                    event_type=EventType.CURRENCY_CONVERSION,
                    event_date=datetime.date(2025, 4, 2), currency=USD,
                    amount=usd(sold), bought_amount=Money(Decimal(bought), HKD))
        base.update(kw)
        return LedgerEvent(**base)

    def test_example_5_a_interest_charged_is_stored_as_given(self):
        a = self.new_account()
        self.append(self.hkd_event(a, EventType.DEPOSIT, datetime.date(2025, 5, 2),
                                   amount=Money(Decimal("5000"), HKD)))
        got = self.append(self.hkd_event(a, EventType.INTEREST_CHARGED,
                                         datetime.date(2025, 5, 31),
                                         amount=Money(Decimal("3.50"), HKD)))
        back = ledger_store.get_event(self.conn, got.event.event_id).event
        self.assertEqual(back.event_type, EventType.INTEREST_CHARGED)
        self.assertEqual(str(back.amount.amount), "3.50")
        self.assertIsNone(back.listing_id)

    def test_interest_charged_with_a_listing_is_refused_by_the_database(self):
        row = self.row_of(self.hkd_event(self.new_account(), EventType.INTEREST_CHARGED, D,
                                         amount=Money(Decimal("3.50"), HKD)))
        row["listing_id"] = _L1
        with self.expect("23514"):
            self.raw_insert(row)

    def test_example_5a_a_conversion_stores_both_sides_and_no_rate(self):
        a = self.new_account()
        got = self.append(self.conv(a, settlement_date=datetime.date(2025, 4, 4)))
        back = ledger_store.get_event(self.conn, got.event.event_id).event
        self.assertEqual((back.currency, back.amount), (USD, usd("1000")))
        self.assertEqual(back.bought_amount, Money(Decimal("7780"), HKD))
        cols = [r[0] for r in self.conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = 'ledger_event'", (self.schema,))]
        self.assertIn("bought_currency", cols)
        self.assertEqual([c for c in cols if "rate" in c], [])

    def test_conversion_database_checks(self):
        a = self.new_account()
        good = self.row_of(self.conv(a))
        for col, value in (("bought_currency", "USD"),       # same as the sold currency
                           ("bought_amount", Decimal("0")),
                           ("bought_amount", Decimal("-1")),
                           ("bought_amount", Decimal("NaN")),
                           ("bought_amount", Decimal("Infinity")),
                           ("bought_currency", "hk"),
                           ("bought_amount", None),           # one side missing
                           ("bought_currency", None)):
            row = dict(good, event_id=self.eid())
            row[col] = value
            with self.expect("23514"):
                self.raw_insert(row)

    def test_example_5a_b_correcting_a_conversion(self):
        a = self.new_account()
        original = self.append(self.conv(a)).event                       # seq 2 of the example
        reversal = self.reversal(original.event_id, account_id=a,
                                 event_date=datetime.date(2025, 4, 10))  # sold currency: USD
        replacement = self.conv(a, bought="7750", corrects_event_id=original.event_id)
        result = ledger_store.append_correction(self.conn, reversal, replacement)
        self.assertLess(result.reversal.ledger_seq, result.replacement.ledger_seq)
        self.assertEqual(result.replacement.event.bought_amount,
                         Money(Decimal("7750"), HKD))

    def test_a_conversion_reversal_must_carry_the_sold_currency(self):
        a = self.new_account()
        original = self.append(self.conv(a)).event
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            self.append(self.reversal(original.event_id, account_id=a, currency=HKD))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_reversal_target_fk")

    def test_example_5a_c_both_valid_recordings_append_storage_does_not_judge_double_count(self):
        # 5A-C: "amount 1,002, no FEE" and "amount 1,000 + FEE 2" are the valid recordings;
        # "1,002 + FEE 2" double-counts, which only replay/ingest can notice (no rule here).
        for sold, fee in (("1002", None), ("1000", "2")):
            a = self.new_account()
            self.append(self.conv(a, sold=sold))
            if fee:
                self.append(LedgerEvent(self.eid(), a, EventType.FEE,
                                        datetime.date(2025, 4, 2), USD, amount=usd(fee)))

    def test_conversion_is_not_a_transfer_and_needs_no_pairing(self):
        # No counterparty, no pairing group: a lone conversion commits.
        self.assertTrue(self.append(self.conv(self.new_account())).created)

    def test_conversion_after_a_snapshot_follows_the_snapshot_rule(self):
        s = self.new_account()
        self.append(self.opening(s))
        with self.assertRaises(ledger_store.LedgerRuleRejectedError):
            self.append(self.conv(s, event_date=D))
        self.append(self.conv(s, event_date=datetime.date(2024, 3, 16)))

    # -- F5: ex_date -------------------------------------------------------------------

    def test_dividend_ex_date_round_trips_and_is_bounded(self):
        e = LedgerEvent(self.eid(), self.new_account(), EventType.DIVIDEND, D, USD,
                        listing_id=_L1, amount=usd("2"), ex_date=datetime.date(2024, 3, 1))
        got = self.append(e)
        self.assertEqual(ledger_store.get_event(self.conn, e.event_id).event.ex_date,
                         datetime.date(2024, 3, 1))
        row = self.row_of(e)
        row["event_id"] = self.eid()
        row["ex_date"] = datetime.date(2024, 3, 16)
        with self.expect("23514"):
            self.raw_insert(row)
        self.assertTrue(got.created)

    # -- F6: snapshot accounts -------------------------------------------------------------

    def opening(self, account, kind=EventType.OPENING_CASH, date=D):
        if kind is EventType.OPENING_CASH:
            return self.opening_kw(account, kind, date, amount=usd("100"))
        return self.opening_kw(account, kind, date, listing_id=_L1, quantity=Decimal("5"))

    def opening_kw(self, account, kind, date, **kw):
        return LedgerEvent(self.eid(), account, kind, date, USD, **kw)

    def dated(self, account, kind, date, **kw):
        return LedgerEvent(self.eid(), account, kind, date, USD, **kw)

    def test_opening_events_share_one_date_and_activity_follows_it(self):
        s = self.new_account()
        self.append(self.opening(s))
        self.append(self.opening(s, EventType.OPENING_POSITION))  # same date ok
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            self.append(self.opening(s, date=datetime.date(2024, 3, 16)))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_snapshot_single_date")
        buy = dict(listing_id=_L1, quantity=Decimal("1"), amount=usd("1"))
        for bad_date in (D, datetime.date(2024, 3, 14)):  # on or before the snapshot date
            with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
                self.append(self.dated(s, EventType.BUY, bad_date, **buy))
            self.assertEqual(cm.exception.constraint_name, "ledger_event_after_snapshot_date")
        self.append(self.dated(s, EventType.BUY, datetime.date(2024, 3, 16), **buy))
        self.append(self.dated(s, EventType.DEPOSIT, datetime.date(2024, 3, 16), amount=usd("1")))

    def test_split_on_the_snapshot_date_is_the_only_exception(self):
        s = self.new_account()
        self.append(self.opening(s, EventType.OPENING_POSITION))
        ratio = SplitRatio(Decimal("2"), Decimal("1"))
        self.append(self.dated(s, EventType.SPLIT, D, listing_id=_L1, split_ratio=ratio))
        with self.assertRaises(ledger_store.LedgerRuleRejectedError):
            self.append(self.dated(s, EventType.SPLIT, datetime.date(2024, 3, 14),
                                   listing_id=_L1, split_ratio=ratio))

    def test_opening_after_existing_activity_is_refused_unless_earlier(self):
        s = self.new_account()
        self.append(self.dated(s, EventType.DEPOSIT, D, amount=usd("1")))
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            self.append(self.opening(s, date=D))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_snapshot_precedes_activity")
        self.append(self.opening(s, date=datetime.date(2024, 3, 14)))

    def test_a_reversed_opening_no_longer_constrains_the_account(self):
        s = self.new_account()
        first = self.append(self.opening(s)).event
        self.append(self.reversal(first.event_id, account_id=s))
        self.append(self.opening(s, date=datetime.date(2024, 3, 20)))

    # -- F7: commit-stable ledger_seq per portfolio ---------------------------------------

    def _second_connection(self):
        conn = connection.connect(connection.conninfo_from_env(os.environ), autocommit=True)
        self.addCleanup(conn.close)
        conn.execute('SET search_path TO "%s"' % self.schema)
        return conn

    def test_ledger_seq_increases_with_append_order(self):
        seqs = [self.append(self.buy()).ledger_seq for _ in range(3)]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(len(set(seqs)), 3)

    def test_appends_to_one_portfolio_serialize_but_other_portfolios_do_not_block(self):
        import threading

        conn2 = self._second_connection()
        results = {}

        def append_on(name, event):
            results[name] = ledger_store.append_event(conn2, event)

        first = self.buy()
        with self.conn.transaction():
            r1 = self.append(first)  # holds the P1 lock until this block commits
            same = threading.Thread(target=append_on, args=("same", self.buy(account_id=_A2)))
            other = threading.Thread(target=append_on, args=("other", self.buy(account_id=_B1)))
            other.start()
            other.join(timeout=10)
            self.assertFalse(other.is_alive(), "another portfolio must not be blocked")
            same.start()
            same.join(timeout=1.0)
            self.assertTrue(same.is_alive(), "same portfolio must wait for the lock")
        same.join(timeout=10)
        self.assertFalse(same.is_alive())
        self.assertGreater(results["same"].ledger_seq, r1.ledger_seq)

    def test_non_read_committed_appends_are_refused(self):
        conn3 = connection.connect(connection.conninfo_from_env(os.environ))
        self.addCleanup(conn3.close)
        # psycopg refuses to change the isolation level once a transaction is open, and
        # the first statement opens one on a non-autocommit connection: set it first.
        conn3.isolation_level = self.pg.IsolationLevel.REPEATABLE_READ
        conn3.execute('SET search_path TO "%s"' % self.schema)
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_event(conn3, self.buy())
        self.assertEqual(cm.exception.constraint_name, "ledger_event_requires_read_committed")

    # -- F10 / item 10b: corrections ------------------------------------------------------------

    def test_correction_is_atomic_and_reversal_comes_first(self):
        target = self.append(self.buy()).event
        rev = self.reversal(target.event_id)
        rep = self.buy(corrects_event_id=target.event_id, quantity=Decimal("12"))
        result = ledger_store.append_correction(self.conn, rev, rep)
        self.assertLess(result.reversal.ledger_seq, result.replacement.ledger_seq)

    def test_failed_replacement_rolls_back_the_reversal(self):
        target = self.append(self.buy()).event
        rev = self.reversal(target.event_id)
        rep = self.buy(corrects_event_id=target.event_id, listing_id=uuid.UUID(int=4))  # no such listing
        with self.assertRaises(ledger_store.LedgerRuleRejectedError):
            ledger_store.append_correction(self.conn, rev, rep)
        self.assertIsNone(ledger_store.get_event(self.conn, rev.event_id))

    def test_a_reversed_event_is_corrected_at_most_once(self):
        target = self.append(self.buy()).event
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_batch(self.conn, [
                self.reversal(target.event_id),
                self.buy(corrects_event_id=target.event_id, quantity=Decimal("12")),
                self.buy(corrects_event_id=target.event_id, quantity=Decimal("13")),
            ])
        self.assertEqual(cm.exception.constraint_name, "ledger_event_corrected_once")

    def test_replacement_must_be_in_the_account_of_the_corrected_event(self):
        target = self.append(self.buy()).event
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_batch(self.conn, [
                self.reversal(target.event_id),
                self.buy(account_id=_A2, corrects_event_id=target.event_id),
            ])
        self.assertEqual(cm.exception.constraint_name, "ledger_event_correction_target_fk")

    def test_event_currency_may_differ_from_listing_currency(self):
        self.assertTrue(self.append(self.buy(listing_id=_L2)).created)  # USD event, HKD listing

    # -- CP1B-2: idempotency is decided before the state-dependent rules ---------------------

    def test_resubmission_after_the_state_moved_on_is_still_a_no_op(self):
        a = self.new_account()
        june15 = datetime.date(2025, 6, 15)
        first = self.append(self.buy(account_id=a, event_date=june15, source_reference="CSV-17"))
        self.append(self.reversal(first.event.event_id, account_id=a))
        self.append(self.opening(a, date=datetime.date(2025, 6, 30)))  # BUY is now pre-snapshot
        resubmitted = self.buy(account_id=a, event_date=june15, source_reference="CSV-17")
        fresh = self.dated(a, EventType.DEPOSIT, datetime.date(2025, 7, 1), amount=usd("5"))
        results = ledger_store.append_batch(self.conn, [resubmitted, fresh])
        self.assertFalse(results[0].created)
        self.assertEqual(results[0].event.event_id, first.event.event_id)
        self.assertTrue(results[1].created, "the no-op must not roll back the rest of the batch")
        # different content under the same key is still a typed conflict, not a rule error
        with self.assertRaises(ledger_store.IdempotencyConflictError):
            self.append(self.buy(account_id=a, event_date=june15, source_reference="CSV-17",
                                 quantity=Decimal("11")))

    def test_resubmitted_snapshot_survives_a_snapshot_correction(self):
        s = self.new_account()
        original = self.append(LedgerEvent(
            self.eid(), s, EventType.OPENING_CASH, D, USD, amount=usd("100"),
            source_reference="SNAP-2025Q1")).event
        moved = LedgerEvent(self.eid(), s, EventType.OPENING_CASH, datetime.date(2024, 3, 12),
                            USD, amount=usd("100"), corrects_event_id=original.event_id,
                            source_reference="SNAP-2025Q1-fix")
        ledger_store.append_correction(
            self.conn, self.reversal(original.event_id, account_id=s), moved)  # CP1B-6 too
        again = self.append(LedgerEvent(
            self.eid(), s, EventType.OPENING_CASH, D, USD, amount=usd("100"),
            source_reference="SNAP-2025Q1"))
        self.assertFalse(again.created)
        self.assertEqual(again.event.event_id, original.event_id)

    # -- CP1B-3: account identity is immutable ------------------------------------------------

    def test_account_id_and_portfolio_are_immutable_but_the_name_can_change(self):
        a = self.new_account()
        with self.expect("23001"):
            self.conn.execute("UPDATE account SET portfolio_id = %s WHERE account_id = %s",
                              (_P2, a))
        with self.expect("23001"):
            self.conn.execute("UPDATE account SET account_id = %s WHERE account_id = %s",
                              (uuid.UUID(int=99), a))
        self.conn.execute("UPDATE account SET name = 'renamed' WHERE account_id = %s", (a,))
        self.assertEqual(self.conn.execute(
            "SELECT name, portfolio_id FROM account WHERE account_id = %s", (a,)
        ).fetchone(), ("renamed", _P1))

    # -- CP1B-6: a corrected opening keeps its audit link -------------------------------------

    def test_opening_events_can_carry_the_correction_link(self):
        for kind in (EventType.OPENING_CASH, EventType.OPENING_POSITION):
            s = self.new_account()
            first = self.append(self.opening(s, kind)).event
            replacement = LedgerEvent(
                self.eid(), s, kind, D, USD, corrects_event_id=first.event_id,
                **(dict(amount=usd("250")) if kind is EventType.OPENING_CASH
                   else dict(listing_id=_L1, quantity=Decimal("400"))))
            result = ledger_store.append_correction(
                self.conn, self.reversal(first.event_id, account_id=s), replacement)
            stored = ledger_store.get_event(self.conn, replacement.event_id).event
            self.assertEqual(stored.corrects_event_id, first.event_id)
            self.assertLess(result.reversal.ledger_seq, result.replacement.ledger_seq)

    # -- CP1B-7: SQL and Python agree on "blank" -------------------------------------------------

    def test_the_sql_blank_class_is_exactly_pythons_isspace(self):
        from persistence import ledger_sql

        rows = self.conn.execute(
            "SELECT g FROM generate_series(1, 1114111) g "
            "WHERE (g < 55296 OR g > 57343) AND chr(g) ~ %s ORDER BY g",
            (ledger_sql.render_blank_pattern(),)).fetchall()
        self.assertEqual({r[0] for r in rows},
                         {c for c in range(1, 0x110000) if chr(c).isspace()})

    def test_tab_nbsp_and_newline_are_refused_by_sql_and_python_alike(self):
        for blank in ("\t", "\xa0", "\n", "  \t　 ", "\x85"):
            with self.assertRaises(ValueError):  # LedgerEventRuleError is a ValueError
                self.buy(source_reference=blank)
            row = self.row_of(self.buy())
            row["source_reference"] = blank
            with self.expect("23514"):
                self.raw_insert(row)
        for fine in ("a\tb", "​", "x"):  # zero-width space is not whitespace
            event = self.buy(source_reference=fine + str(self.eid()))
            self.assertTrue(self.append(event).created)
            self.assertTrue(ledger_store.get_event(self.conn, event.event_id).event
                            .has_same_content(event))

    # -- CP1B-8: recorded_at cannot be forged ----------------------------------------------------

    def test_recorded_at_is_set_by_the_database(self):
        for forged in (datetime.datetime(2001, 1, 1, tzinfo=datetime.timezone.utc),
                       datetime.datetime(2999, 1, 1, tzinfo=datetime.timezone.utc)):
            row = self.row_of(self.buy())
            row["recorded_at"] = forged
            self.raw_insert(row)
            ok = self.conn.execute(
                "SELECT recorded_at > '2020-01-01'::timestamptz AND recorded_at <= now() "
                "FROM ledger_event WHERE event_id = %s", (row["event_id"],)).fetchone()[0]
            self.assertTrue(ok, forged)

    def test_the_ledger_seq_a_caller_supplies_is_ignored(self):
        row = self.row_of(self.buy())
        row["ledger_seq"] = 777_000_000
        self.raw_insert(row)
        seq = self.conn.execute("SELECT ledger_seq FROM ledger_event WHERE event_id = %s",
                                (row["event_id"],)).fetchone()[0]
        self.assertNotEqual(seq, 777_000_000)

    # -- observations: typed errors ---------------------------------------------------------------

    def test_numeric_overflow_is_a_typed_error(self):
        huge = Decimal("1E+200000")  # beyond NUMERIC's 131072 integer digits
        with self.assertRaises(ledger_store.LedgerValueOutOfRangeError):
            self.append(self.buy(quantity=huge))

    def test_cross_portfolio_batches_are_allowed_and_deadlocks_are_typed(self):
        results = ledger_store.append_batch(self.conn, [
            self.buy(account_id=_A1),
            self.dated(_B1, EventType.DEPOSIT, D, amount=usd("5")),
        ])
        self.assertTrue(all(r.created for r in results))

    # -- F12 / Ruling 3.4: one live SPLIT per (account, listing, event_date) -------------------

    def split(self, account, ratio=("3", "2"), listing=None, date=datetime.date(2025, 5, 16),
              **kw):
        return self.dated(account, EventType.SPLIT, date, listing_id=listing or _L1,
                          split_ratio=SplitRatio(Decimal(ratio[0]), Decimal(ratio[1])), **kw)

    def test_a_second_live_split_on_the_same_position_and_day_is_refused(self):
        a = self.new_account()
        self.append(self.split(a, ("13", "10")))
        with self.assertRaises(ledger_store.SameDaySplitError) as cm:
            self.append(self.split(a, ("12", "10")))
        self.assertEqual(cm.exception.constraint_name, "ledger_event_split_once_per_day")
        self.assertIsInstance(cm.exception, ledger_store.LedgerRuleRejectedError)
        self.assertEqual(self.conn.execute(
            "SELECT count(*) FROM ledger_event WHERE account_id = %s AND event_type = 'SPLIT'",
            (a,)).fetchone()[0], 1)

    def test_the_combined_split_replaces_the_first_through_append_correction(self):
        """'10送3转增2' recorded as (13,10) then fixed to the combined (15,10)."""
        a = self.new_account()
        first = self.append(self.split(a, ("13", "10"))).event
        combined = self.split(a, ("15", "10"), corrects_event_id=first.event_id)
        result = ledger_store.append_correction(
            self.conn, self.reversal(first.event_id, account_id=a), combined)
        self.assertLess(result.reversal.ledger_seq, result.replacement.ledger_seq)
        # ...and the corrected day again refuses a further live split
        with self.assertRaises(ledger_store.SameDaySplitError):
            self.append(self.split(a, ("2", "1")))

    def test_a_reversed_split_no_longer_blocks_a_new_one(self):
        a = self.new_account()
        first = self.append(self.split(a)).event
        self.append(self.reversal(first.event_id, account_id=a))
        self.assertTrue(self.append(self.split(a, ("15", "10"))).created)

    def test_splits_on_another_listing_date_or_account_are_allowed(self):
        a = self.new_account()
        self.append(self.split(a))
        self.assertTrue(self.append(self.split(a, listing=_L2)).created)  # other listing
        self.assertTrue(self.append(self.split(
            a, date=datetime.date(2025, 5, 17))).created)  # other date
        self.assertTrue(self.append(self.split(self.new_account())).created)  # other account

    def test_an_unchanged_split_resubmission_is_still_a_no_op(self):
        a = self.new_account()
        first = self.append(self.split(a, source_reference="SPLIT-2025-05-16"))
        again = self.append(self.split(a, source_reference="SPLIT-2025-05-16"))
        self.assertFalse(again.created)
        self.assertEqual(again.event.event_id, first.event.event_id)
        same_id = self.append(first.event)  # the identical event (same event_id)
        self.assertFalse(same_id.created)
        # a different split under the same key is the typed idempotency conflict, not a rule error
        with self.assertRaises(ledger_store.IdempotencyConflictError):
            self.append(self.split(a, ("2", "1"), source_reference="SPLIT-2025-05-16"))

    def test_the_split_rule_holds_inside_one_batch_and_across_the_lock(self):
        a = self.new_account()
        with self.assertRaises(ledger_store.SameDaySplitError):
            ledger_store.append_batch(self.conn, [self.split(a), self.split(a, ("2", "1"))])
        self.assertEqual(self.conn.execute(
            "SELECT count(*) FROM ledger_event WHERE account_id = %s", (a,)).fetchone()[0], 0)

    # -- R2-1: the epoch-safe same-transaction rule -------------------------------------------

    def test_sql_full_xid_matches_the_python_mirror_across_epochs(self):
        from persistence import xid_epoch

        anchors = []
        for epoch in range(4):
            base = epoch * 2 ** 32
            anchors += [base + 3, base + 10, base + 2 ** 31, base + 2 ** 32 - 5,
                        base + 2 ** 32 - 1]
        offsets = [-(2 ** 31 - 1), -70000, -1, 0, 1, 64, 70000, 2 ** 31 - 1]
        compared = 0
        for anchor in anchors:
            for offset in offsets:
                true_id = anchor + offset
                if true_id < 0:
                    continue
                x = true_id % 2 ** 32
                got = self.conn.execute("SELECT ledger_full_xid(%s, %s)",
                                        (str(x), Decimal(anchor))).fetchone()[0]
                expected = xid_epoch.full_xid(x, anchor)
                self.assertEqual(None if got is None else int(got), expected, (anchor, x))
                compared += 1
        self.assertGreater(compared, 100)
        for special in ("0", "1", "2"):
            self.assertIsNone(self.conn.execute(
                "SELECT ledger_full_xid(%s, %s)", (special, Decimal(7 * 2 ** 32 + 100))
            ).fetchone()[0])

    def _correction_pair(self):
        target = self.append(self.buy()).event
        return (target, self.reversal(target.event_id),
                self.buy(corrects_event_id=target.event_id, quantity=Decimal("12")))

    def test_correction_across_a_released_savepoint_is_accepted(self):
        _, reversal, replacement = self._correction_pair()
        with self.conn.transaction():
            with self.conn.transaction():  # released when the block ends
                self.append(reversal)
            self.assertTrue(self.append(replacement).created)

    def test_correction_after_a_rolled_back_savepoint_is_refused(self):
        _, reversal, replacement = self._correction_pair()
        with self.conn.transaction():
            with self.conn.transaction():
                self.append(reversal)
                raise self.pg.Rollback()  # rolls this savepoint back, swallowed by the block
            with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
                self.append(replacement)
            self.assertEqual(cm.exception.constraint_name,
                             "ledger_event_corrects_reversed_event")

    def test_correction_across_nested_and_sibling_subtransactions_is_accepted(self):
        _, reversal, replacement = self._correction_pair()
        with self.conn.transaction():
            with self.conn.transaction():
                with self.conn.transaction():
                    self.append(reversal)  # in a sub-subtransaction
            with self.conn.transaction():  # a sibling subtransaction
                self.assertTrue(self.append(replacement).created)

    def test_a_reversal_open_in_another_session_blocks_then_the_replacement_is_refused(self):
        import threading

        target, reversal, replacement = self._correction_pair()
        other = self._second_connection()
        outcome = {}

        def run():
            try:
                outcome["result"] = ledger_store.append_event(self.conn, replacement)
            except Exception as exc:  # noqa: BLE001
                outcome["error"] = exc

        with other.transaction():
            ledger_store.append_event(other, reversal)  # uncommitted, holds the portfolio lock
            worker = threading.Thread(target=run)
            worker.start()
            worker.join(timeout=1.0)
            self.assertTrue(worker.is_alive(), "the replacement must wait for the lock")
        worker.join(timeout=10)
        self.assertFalse(worker.is_alive())
        self.assertNotIn("result", outcome)
        self.assertEqual(outcome["error"].constraint_name,
                         "ledger_event_correction_same_transaction")

    # -- R2-2: every function in the ledger schema carries the pinned search_path -----------

    def test_every_function_in_the_schema_has_the_pinned_search_path(self):
        rows = self.conn.execute(
            "SELECT p.proname, p.proconfig FROM pg_proc p JOIN pg_namespace n "
            "ON n.oid = p.pronamespace WHERE n.nspname = %s ORDER BY p.proname",
            (self.schema,)).fetchall()
        names = {r[0] for r in rows}
        self.assertTrue({"ledger_event_before_insert", "ledger_event_check_transfer_pairing",
                         "ledger_event_reject_mutation", "account_guard_identity",
                         "ledger_full_xid"} <= names, names)
        for name, config in rows:
            settings = [c.replace('"', "") for c in (config or [])]
            self.assertEqual(settings, ["search_path=%s, pg_temp" % self.schema],
                             "%s lost its search_path pin: %r" % (name, config))
        # and every function a trigger on the ledger tables calls is among them
        triggered = {r[0] for r in self.conn.execute(
            "SELECT DISTINCT p.proname FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
            "JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND NOT t.tgisinternal", (self.schema,))}
        self.assertTrue(triggered <= names)
        self.assertGreaterEqual(len(triggered), 4)

    # -- R2-4: a deadlock inside a caller-owned transaction ----------------------------------------

    def test_a_deadlock_in_a_caller_owned_transaction_is_not_claimed_retry_safe(self):
        import threading
        import time

        conn_a = connection.connect(connection.conninfo_from_env(os.environ))
        conn_b = connection.connect(connection.conninfo_from_env(os.environ))
        for c in (conn_a, conn_b):
            self.addCleanup(c.close)
            c.execute('SET search_path TO "%s"' % self.schema)
            c.commit()
            c.execute("SELECT 1")  # opens the caller's transaction: appends become savepoints
        p1_a = self.buy(account_id=_A1)
        p2_b = self.dated(_B1, EventType.DEPOSIT, D, amount=usd("2"))
        ledger_store.append_event(conn_a, p1_a)  # conn_a holds P1
        ledger_store.append_event(conn_b, p2_b)  # conn_b holds P2
        results = {}

        def a_wants_p2():
            try:
                ledger_store.append_event(conn_a, self.dated(_B1, EventType.DEPOSIT, D,
                                                             amount=usd("3")))
                results["a"] = "ok"
            except ledger_store.LedgerConcurrencyError as exc:
                results["a"] = exc
                conn_a.rollback()  # the documented recovery: the WHOLE transaction

        worker = threading.Thread(target=a_wants_p2)
        worker.start()
        time.sleep(0.5)
        self.assertTrue(worker.is_alive(), "conn_a must be waiting for P2's lock")
        try:
            ledger_store.append_event(conn_b, self.buy(account_id=_A1))  # conn_b wants P1
            results["b"] = "ok"
        except ledger_store.LedgerConcurrencyError as exc:
            results["b"] = exc
            conn_b.rollback()
        worker.join(timeout=20)
        self.assertFalse(worker.is_alive())
        victims = [v for v in results.values() if isinstance(v, ledger_store.LedgerConcurrencyError)]
        self.assertEqual(len(victims), 1, results)
        error = victims[0]
        self.assertEqual(error.sqlstate, "40P01")
        self.assertFalse(error.transaction_owned)
        self.assertFalse(error.retry_safe)
        self.assertIn("roll back the WHOLE transaction", str(error))
        # the victim's rollback discarded its EARLIER append too: nothing of it is visible
        victim_event = p1_a if results["a"] is error else p2_b
        conn_b.rollback()
        conn_a.rollback()
        self.assertIsNone(ledger_store.get_event(self.conn, victim_event.event_id))

    # -- R3-1: bounded numeric values (value < 1E30, scale <= 24) -------------------------------

    _BOUND_COLUMNS = ("quantity", "amount", "cost_basis", "bought_amount",
                      "split_new", "split_old")

    def test_the_reviewers_extreme_inputs_are_refused_at_append_with_a_typed_error(self):
        for text in ("1E+5000", "1E+150", "1E-60", "1E+131071"):
            for kwargs in (dict(quantity=Decimal(text)), dict(amount=usd(text))):
                with self.assertRaises(ledger_store.LedgerValueOutOfRangeError, msg=text):
                    self.append(self.buy(**kwargs))
        with self.assertRaises(ledger_store.LedgerValueOutOfRangeError):
            self.append(self.dated(self.new_account(), EventType.DEPOSIT, D,
                                   amount=usd("1E+5000")))

    def test_every_realistic_value_fits(self):
        realistic = [
            Decimal("0.000000000000000001"),          # 18-decimal crypto quantity (wei)
            Decimal("1E-24"),                          # a very small unit price
            Decimal("9999999999999999.99"),            # ~1e16 JPY
            Decimal("123456789012345.6789"),           # a large CNY/HKD portfolio
            Decimal("1E+15"),                          # a token supply
            Decimal("999999999999999999999999999999"),  # 30 nines: the largest allowed
            Decimal("0.500000000000000000000000"),     # trailing zeros up to scale 24
        ]
        for value in realistic:
            event = self.append(self.buy(quantity=value, amount=usd("1"))).event
            self.assertEqual(ledger_store.get_event(self.conn, event.event_id).event.quantity,
                             value)

    def test_the_boundaries_on_each_column(self):
        refused = (Decimal("1E+30"), Decimal("1E+31"), Decimal("0.0000000000000000000000001"),
                   Decimal("1.0000000000000000000000000"))  # 25 decimals, even if trailing zeros
        for column in self._BOUND_COLUMNS:
            for bad in refused:
                row = self._valid(EventType.BUY)
                if column in ("split_new", "split_old"):
                    row = self._valid(EventType.SPLIT)
                elif column == "cost_basis":
                    row = self._valid(EventType.OPENING_POSITION)
                    row["cost_basis"] = Decimal("1")
                elif column == "bought_amount":
                    row = self._valid(EventType.CURRENCY_CONVERSION)
                row[column] = bad
                with self.expect("23514"):
                    self.raw_insert(row)

    def test_the_database_bound_equals_the_python_statement_of_it(self):
        from domain.ledger import numeric_bounds_violation

        for text in ("1E+29", "9.9E+29", "1E+30", "5E+30", "1E-24", "1E-25", "0.1",
                     "123.456", "1.000000000000000000000000", "1.0000000000000000000000000",
                     "999999999999999999999999999999", "1000000000000000000000000000000"):
            value = Decimal(text)
            in_db = self.conn.execute(
                "SELECT %s::numeric < 1E30 AND scale(%s::numeric) <= 24", (text, text)
            ).fetchone()[0]
            self.assertEqual(in_db, numeric_bounds_violation(value) is None, text)

    def test_a_ledger_holding_an_out_of_bound_row_still_upgrades_and_replays(self):
        """R4-1: the six bound CHECKs are NOT VALID, so 0008 is applied to a ledger that
        already holds a row legal before it (a 28-decimal deposit); the old row stays stored
        and replay still returns a state for it; a NEW out-of-bound append is refused."""
        from persistence import ledger_replay_store

        old = "finweb_it_r41_" + uuid.uuid4().hex[:8]
        owner = connection.connect(connection.conninfo_from_env(os.environ), autocommit=True)
        self.addCleanup(owner.close)
        self.addCleanup(lambda: owner.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % old))
        owner.execute('CREATE SCHEMA "%s"' % old)
        owner.execute('SET search_path TO "%s"' % old)
        migrations = migrator.load_migrations()
        migrator.apply_migrations(owner, migrations[:7])
        user, portfolio, account = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        owner.execute("INSERT INTO app_user VALUES (%s)", (user,))
        owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (portfolio, user))
        owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (account, portfolio))
        fine = Decimal("1.0000000000000000000000000001")  # 28 decimals, legal before 0008
        old_deposit = LedgerEvent(self.eid(), account, EventType.DEPOSIT, D, USD,
                                  amount=Money(fine, USD))
        ledger_store.append_event(owner, old_deposit)

        applied = migrator.apply_migrations(owner)  # would fail if the CHECKs were VALID
        # 0008 and every later migration (0009-0011, CP2c-2) are pending after 0007
        self.assertEqual(applied, [m.filename for m in migrations[7:]])
        stored = ledger_store.get_event(owner, old_deposit.event_id).event
        self.assertEqual(stored.amount.amount, fine)
        validated = dict(owner.execute(
            "SELECT conname, convalidated FROM pg_constraint WHERE conrelid = "
            "'ledger_event'::regclass AND conname LIKE 'ledger_event_%%_bounds'").fetchall())
        self.assertEqual(len(validated), 6)
        self.assertFalse(any(validated.values()), validated)  # NOT VALID: new rows only

        state = ledger_replay_store.replay(owner, portfolio, D)  # replay stays robust
        balance = state.cash_balance(account, USD)
        self.assertEqual(balance.value, fine)  # the correct, exact value (AVAILABLE)

        with self.assertRaises(ledger_store.LedgerValueOutOfRangeError):  # new rows are bounded
            ledger_store.append_event(owner, LedgerEvent(
                self.eid(), account, EventType.DEPOSIT, D, USD,
                amount=Money(Decimal("1.0000000000000000000000001"), USD)))  # 25 decimals
        with self.assertRaises(ledger_store.LedgerValueOutOfRangeError):
            ledger_store.append_event(owner, LedgerEvent(
                self.eid(), account, EventType.DEPOSIT, D, USD, amount=usd("1E+30")))

    def test_resubmitting_a_stored_out_of_bound_value_is_a_typed_refusal_not_a_no_op(self):
        """Known limitation, pinned so it is not silently changed: the CHECKs run before
        ON CONFLICT, so an unchanged resubmission written at scale 25 is refused."""
        a = self.new_account()
        event = self.dated(a, EventType.DEPOSIT, D, amount=usd("1.0000000000000000000000001"),
                           source_reference="SCALE-25")
        with self.assertRaises(ledger_store.LedgerValueOutOfRangeError):
            self.append(event)

    # -- R3-2: the append-transaction identity ----------------------------------------------------

    def test_append_xid_and_portfolio_are_set_by_the_database_and_cannot_be_forged(self):
        a = self.new_account()
        event = self.buy(account_id=a)
        row = self.row_of(event)
        cols = list(row) + ["append_xid", "portfolio_id"]
        with self.conn.transaction():
            self.conn.execute(
                "INSERT INTO ledger_event (%s) VALUES (%s, '12345'::xid8, %%s)"
                % (", ".join(cols), ", ".join(["%s"] * len(row))),
                [row[c] for c in row] + [_P2])  # forged xid and a forged (wrong) portfolio
            mine, stored_xid, stored_portfolio = self.conn.execute(
                "SELECT pg_current_xact_id()::text, append_xid::text, portfolio_id "
                "FROM ledger_event WHERE event_id = %s", (event.event_id,)).fetchone()
        self.assertEqual(stored_xid, mine)
        self.assertNotEqual(stored_xid, "12345")
        self.assertEqual(stored_portfolio, _P1)

    def test_rows_of_one_append_transaction_share_an_xid_and_others_do_not(self):
        a = self.new_account()
        first = self.buy(account_id=a)
        second = self.buy(account_id=a)
        third = self.buy(account_id=a)
        ledger_store.append_batch(self.conn, [first, second])
        self.append(third)
        xids = dict(self.conn.execute(
            "SELECT event_id, append_xid::text FROM ledger_event WHERE account_id = %s", (a,)))
        self.assertEqual(xids[first.event_id], xids[second.event_id])
        self.assertNotEqual(xids[first.event_id], xids[third.event_id])
        # savepoints inside one caller transaction still share the top-level id
        fourth, fifth = self.buy(account_id=a), self.buy(account_id=a)
        with self.conn.transaction():
            with self.conn.transaction():
                self.append(fourth)
            self.append(fifth)
        xids = dict(self.conn.execute(
            "SELECT event_id, append_xid::text FROM ledger_event WHERE account_id = %s", (a,)))
        self.assertEqual(xids[fourth.event_id], xids[fifth.event_id])

    def test_the_identity_columns_are_required_for_new_rows_and_indexed(self):
        state = self.conn.execute(
            "SELECT convalidated FROM pg_constraint WHERE conname = "
            "'ledger_event_append_identity_present' AND connamespace = %s::regnamespace",
            ('"%s"' % self.schema,)).fetchone()
        self.assertEqual(state, (False,))  # NOT VALID: enforced for new rows only
        index = self.conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname = %s AND indexname = "
            "'ledger_event_portfolio_seq'", (self.schema,)).fetchone()[0]
        self.assertIn("(portfolio_id, ledger_seq)", index)
        self.assertIn("INCLUDE (append_xid)", index)

    def test_recorded_at_is_documented_as_never_a_computation_input(self):
        comment = self.conn.execute(
            "SELECT col_description(%s::regclass, attnum) FROM pg_attribute "
            "WHERE attrelid = %s::regclass AND attname = 'recorded_at'",
            ('"%s".ledger_event' % self.schema, '"%s".ledger_event' % self.schema)
        ).fetchone()[0]
        self.assertIn("never an input to any computation", comment)

    def test_rows_appended_before_0008_have_null_identity_and_old_reversals_are_refused(self):
        """Upgrade path: rows from a schema migrated only through 0007 keep NULL append_xid
        and portfolio_id after 0008 is applied, and a replacement correcting such an old
        reversal gets the NAMED same-transaction refusal (R3-3), never an untyped error."""
        old = "finweb_it_pre8_" + uuid.uuid4().hex[:8]
        owner = connection.connect(connection.conninfo_from_env(os.environ), autocommit=True)
        self.addCleanup(owner.close)
        self.addCleanup(lambda: owner.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % old))
        owner.execute('CREATE SCHEMA "%s"' % old)
        owner.execute('SET search_path TO "%s"' % old)
        migrations = migrator.load_migrations()
        self.assertEqual(len(migrator.apply_migrations(owner, migrations[:7])), 7)
        user, portfolio, account = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        owner.execute("INSERT INTO app_user VALUES (%s)", (user,))
        owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (portfolio, user))
        owner.execute("INSERT INTO account VALUES (%s, %s, 'acct')", (account, portfolio))
        target = LedgerEvent(self.eid(), account, EventType.DEPOSIT, D, USD, amount=usd("5"))
        reversal = LedgerEvent(self.eid(), account, EventType.REVERSAL, D, USD,
                               reverses_event_id=target.event_id)
        ledger_store.append_batch(owner, [target])
        ledger_store.append_batch(owner, [reversal])
        self.assertEqual(migrator.apply_migrations(owner), [m.filename for m in migrations[7:]])
        old_rows = owner.execute(
            "SELECT append_xid, portfolio_id FROM ledger_event ORDER BY ledger_seq").fetchall()
        self.assertEqual(old_rows, [(None, None), (None, None)])
        replacement = LedgerEvent(self.eid(), account, EventType.DEPOSIT, D, USD,
                                  amount=usd("6"), corrects_event_id=target.event_id)
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_event(owner, replacement)
        self.assertEqual(cm.exception.constraint_name,
                         "ledger_event_correction_same_transaction")
        # new rows after the upgrade carry the identity
        fresh = LedgerEvent(self.eid(), account, EventType.DEPOSIT, D, USD, amount=usd("7"))
        ledger_store.append_event(owner, fresh)
        self.assertEqual(owner.execute(
            "SELECT append_xid IS NOT NULL, portfolio_id FROM ledger_event WHERE event_id = %s",
            (fresh.event_id,)).fetchone(), (True, portfolio))

    # -- round trip of every shape ---------------------------------------------------

    def test_every_event_type_round_trips(self):
        for t in EventType:
            row = self._valid(t)
            self.raw_insert(row)
            got = ledger_store.get_event(self.conn, row["event_id"])
            self.assertIsNotNone(got, t)
            self.assertEqual(ledger_store.event_to_row(got.event), tuple(row.values()))


if __name__ == "__main__":
    unittest.main()
