"""CP1-B step 2 — database-free tests for `persistence` (migration runner,
FIELD_RULES <-> SQL consistency, row mapping, connection strings). No driver,
no server. The database integration tests are in
`test_postgres_ledger_integration.py` (skipped by default).
"""

import dataclasses
import datetime
import hashlib
import re
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent, SplitRatio  # noqa: E402
from persistence import connection, ledger_sql, ledger_store, migrator, xid_epoch  # noqa: E402

_MIG = migrator.MIGRATIONS_DIR


def _sql(name):
    return (_MIG / name).read_text(encoding="utf-8")


class MigrationFilesTests(unittest.TestCase):
    def test_real_migrations_load_contiguous(self):
        migs = migrator.load_migrations()
        self.assertEqual([m.version for m in migs], [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19])  # 0019: immutable CSV reports/source keys; prior migrations frozen
        for m in migs:
            self.assertEqual(
                m.checksum, hashlib.sha256((_MIG / m.filename).read_bytes()).hexdigest()
            )

    def test_only_expected_tables_no_positions_or_balances(self):
        text = "\n".join(m.sql for m in migrator.load_migrations())
        tables = set(re.findall(r"CREATE TABLE (\w+)", text))
        # 0009-0011 (CP2c-2) add the market-data projection: every table is md_*; there is still no
        # position, balance or holding table anywhere
        self.assertEqual(
            tables,
            {"app_user", "portfolio", "account", "issuer", "instrument", "listing",
             "ledger_event", "md_file", "md_release", "md_release_file", "md_quote", "md_fx_rate",
             "md_corporate_action", "md_benchmark", "md_benchmark_point", "md_adjusted_quote",
             "md_calendar", "md_series_exclusion", "benchmark_selection",  # 0015 (PD-0039 D5): the user's benchmark selection
             "md_risk_free", "md_risk_free_point",  # 0016: risk-free rate kind
             "web_identity", "web_session", "web_auth_rate", "web_saved_sandbox", "web_portfolio_revision", "web_csv_report", "web_csv_source_key"},  # 0017-0019
        )

    def test_ledger_event_has_no_external_ids_or_derived_columns(self):
        text = _sql("0002_ledger_event.sql")
        body = text[text.index("CREATE TABLE ledger_event"):]
        cols = body[: body.index("CONSTRAINT")]
        for banned in ("ticker", "figi", "mic", "exchange", "reporting", "fx_", "price",
                       "lot", "position", "balance", "shares"):
            self.assertNotIn(banned, cols.lower(), banned)

    def test_numeric_columns_have_no_scale(self):
        cols = _sql("0002_ledger_event.sql")
        for name in ("quantity", "amount", "cost_basis", "split_new", "split_old"):
            self.assertRegex(cols, r"\n    %s numeric NULL," % name)

    def test_every_event_field_has_a_column(self):
        text = _sql("0002_ledger_event.sql")
        for f in dataclasses.fields(LedgerEvent):
            names = ledger_sql.COLUMNS_FOR_FIELD.get(f.name, (f.name,))
            if f.name in ("amount", "cost_basis"):
                names = (f.name,)
            for n in names:
                if n == "acquired_on":  # PD-0036: added by migration 0014 (0002 is frozen)
                    self.assertIn("ADD COLUMN acquired_on date NULL", _sql("0014_acquired_on.sql"))
                    continue
                self.assertIn("\n    %s " % n, text, n)
        self.assertEqual(
            set(ledger_store.EVENT_COLUMNS) - {"split_new", "split_old", "bought_currency"},
            {f.name for f in dataclasses.fields(LedgerEvent)} - {"split_ratio"},
        )

    def test_no_rate_column_or_field_anywhere(self):
        """ledger-replay/1.1 §5A.7: no FX rate is stored, on the event or in the schema."""
        text = _sql("0002_ledger_event.sql")
        body = text[text.index("CREATE TABLE ledger_event"):text.index("CONSTRAINT")]
        for name in [f.name for f in dataclasses.fields(LedgerEvent)] + list(
                ledger_store.EVENT_COLUMNS):
            self.assertNotIn("rate", name)
        for line in body.splitlines():
            self.assertNotRegex(line.strip().split(" ")[0], r"rate")
        for member in EventType:
            self.assertNotIn("FX_RATE", member.value)

    def test_guard_names_used_by_store_exist_in_sql(self):
        text = _sql("0002_ledger_event.sql") + _sql("0003_ledger_event_guards.sql")
        for name in ("ledger_event_reversed_once", "ledger_event_append_only",
                     "ledger_event_reversal_of_reversal",
                     "ledger_event_corrects_reversed_event",
                     "ledger_event_counterparty_same_portfolio",
                     "ledger_event_idempotency_key"):
            self.assertIn(name, text)
        self.assertIn("BEFORE UPDATE OR DELETE", text)
        self.assertIn("BEFORE TRUNCATE", text)


class FieldRulesSqlConsistencyTests(unittest.TestCase):
    def test_latest_generated_region_matches_field_rules(self):
        """CP1B-4: FIELD_RULES is compared with the region of the LATEST migration that
        has one, so a rule change passes by adding a new migration (with a
        GENERATED-REPLACE region, see ledger_sql), never by editing a frozen one."""
        texts = [m.sql for m in migrator.load_migrations()]
        kind, region = ledger_sql.latest_generated_region(texts)
        self.assertEqual(kind, "replace")
        self.assertEqual(
            region, ledger_sql.render_replace_region(),
            "FIELD_RULES changed without a new migration. Do NOT edit an existing "
            "migration: add 000N_*.sql containing a GENERATED-REPLACE region equal to "
            "persistence.ledger_sql.render_replace_region(), and pin it in CHECKSUMS.",
        )

    def test_the_original_0002_region_is_frozen_history_not_the_current_rules(self):
        """0002 still holds the original region; it differs from today's rules (the
        opening types gained corrects_event_id in 0005) and must stay that way."""
        original = ledger_sql.extract_generated_region(_sql("0002_ledger_event.sql"))
        self.assertNotEqual(original, ledger_sql.render_generated_region())
        self.assertIn("ledger_event_fields_opening_cash", original)

    def test_latest_region_picks_the_newest_migration_only(self):
        old = "\n".join([ledger_sql.BEGIN_MARKER, "old", ledger_sql.END_MARKER])
        new = "\n".join([ledger_sql.REPLACE_BEGIN_MARKER, "new", ledger_sql.REPLACE_END_MARKER])
        self.assertEqual(ledger_sql.latest_generated_region([old, "x", new]), ("replace", "new"))
        self.assertEqual(ledger_sql.latest_generated_region([old, "x"]), ("create", "old"))
        with self.assertRaises(ValueError):
            ledger_sql.latest_generated_region(["x"])

    def test_opening_types_allow_the_correction_link_in_the_current_region(self):
        region = ledger_sql.render_replace_region()
        for line in region.split("\n"):
            if "ledger_event_fields_opening" in line and line.lstrip().startswith("ADD"):
                self.assertNotIn("corrects_event_id IS NULL", line)

    def test_blank_pattern_matches_python_strip_semantics(self):
        import re

        pattern = ledger_sql.render_blank_pattern()
        self.assertIn(pattern, _sql("0004_ledger_hardening.sql"))
        # every whitespace code point is inside the class, none outside it (BMP check)
        klass = pattern[2:-3]
        covered = set()
        for lo, hi in re.findall(r"\\x([0-9a-f]+)(?:-\\x([0-9a-f]+))?", klass):
            covered.update(range(int(lo, 16), int(hi or lo, 16) + 1))
        self.assertEqual(covered, {c for c in range(0x110000) if chr(c).isspace()})
        for probe in ("\t", "\xa0", "\n", " ", "　", "\x85", "\x1f"):
            self.assertEqual(probe.strip(), "")
            self.assertIn(ord(probe), covered)

    def test_one_presence_constraint_per_event_type(self):
        text = ledger_sql.render_generated_region()
        for t in EventType:
            self.assertIn("ledger_event_fields_%s " % t.value.lower(), text)

    def test_missing_markers_raise(self):
        with self.assertRaises(ValueError):
            ledger_sql.extract_generated_region("nothing here")


def _mig(version, name, sql="SELECT 1"):
    data = sql.encode("utf-8")
    return migrator.Migration(version, name, "%04d_%s.sql" % (version, name), sql,
                              migrator.checksum_of(data))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.m = [_mig(1, "a"), _mig(2, "b"), _mig(3, "c")]

    def test_fresh_applies_all_in_order(self):
        self.assertEqual([x.version for x in migrator.plan_migrations(self.m, {})], [1, 2, 3])

    def test_partial_applies_rest(self):
        applied = {1: ("a", self.m[0].checksum)}
        self.assertEqual([x.version for x in migrator.plan_migrations(self.m, applied)], [2, 3])

    def test_all_applied_is_empty(self):
        applied = {x.version: (x.name, x.checksum) for x in self.m}
        self.assertEqual(migrator.plan_migrations(self.m, applied), [])

    def test_changed_checksum_refused(self):
        applied = {1: ("a", "0" * 64)}
        with self.assertRaises(migrator.MigrationChecksumError):
            migrator.plan_migrations(self.m, applied)

    def test_renamed_refused(self):
        with self.assertRaises(migrator.MigrationChecksumError):
            migrator.plan_migrations(self.m, {1: ("z", self.m[0].checksum)})

    def test_applied_without_file_refused(self):
        with self.assertRaises(migrator.MigrationHistoryError):
            migrator.plan_migrations(self.m[:1], {2: ("b", "0" * 64)})

    def test_out_of_order_refused(self):
        applied = {1: ("a", self.m[0].checksum), 3: ("c", self.m[2].checksum)}
        with self.assertRaises(migrator.MigrationHistoryError):
            migrator.plan_migrations(self.m, applied)


class LoadTests(unittest.TestCase):
    def _dir(self, names):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        for n in names:
            (Path(tmp.name) / n).write_text("SELECT 1;\n", encoding="utf-8")
        return Path(tmp.name)

    def test_gap_refused(self):
        with self.assertRaises(migrator.MigrationFilesError):
            migrator.load_migrations(self._dir(["0001_a.sql", "0003_c.sql"]))

    def test_bad_name_refused(self):
        with self.assertRaises(migrator.MigrationFilesError):
            migrator.load_migrations(self._dir(["0001_a.sql", "second.sql"]))

    def test_non_sql_ignored_and_sorted(self):
        migs = migrator.load_migrations(self._dir(["0002_b.sql", "0001_a.sql", "notes.txt"]))
        self.assertEqual([m.version for m in migs], [1, 2])

    def test_checksum_is_stable_and_content_sensitive(self):
        self.assertEqual(migrator.checksum_of(b"x"), migrator.checksum_of(b"x"))
        self.assertNotEqual(migrator.checksum_of(b"x"), migrator.checksum_of(b"x\n"))


class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Tx:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.log.append("BEGIN")

    def __exit__(self, exc_type, exc, tb):
        self.conn.log.append("ROLLBACK" if exc_type else "COMMIT")
        return False


class FakeConn:
    """Records statements; `history` plays the schema_migrations table."""

    def __init__(self, history=()):
        self.history = list(history)
        self.log = []

    def transaction(self):
        return _Tx(self)

    def execute(self, sql, params=None):
        self.log.append(sql)
        if sql.startswith("SELECT version"):
            return _Cursor(sorted(self.history))
        if sql.startswith("INSERT INTO schema_migrations"):
            self.history.append(tuple(params))
        return _Cursor([])


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.m = [_mig(1, "a", "CREATE TABLE a ()"), _mig(2, "b", "CREATE TABLE b ()")]

    def test_applies_pending_in_one_transaction_and_records_checksums(self):
        conn = FakeConn()
        self.assertEqual(migrator.apply_migrations(conn, self.m),
                         ["0001_a.sql", "0002_b.sql"])
        self.assertEqual(conn.log[0], "BEGIN")
        self.assertEqual(conn.log[-1], "COMMIT")
        self.assertEqual(conn.log.count("BEGIN"), 1)
        self.assertLess(conn.log.index("CREATE TABLE a ()"),
                        conn.log.index("CREATE TABLE b ()"))
        self.assertEqual(conn.history, [(1, "a", self.m[0].checksum),
                                        (2, "b", self.m[1].checksum)])

    def test_second_run_is_a_no_op(self):
        conn = FakeConn()
        migrator.apply_migrations(conn, self.m)
        conn.log.clear()
        self.assertEqual(migrator.apply_migrations(conn, self.m), [])
        self.assertNotIn("CREATE TABLE a ()", conn.log)
        self.assertEqual(len(conn.history), 2)

    def test_changed_file_refuses_before_running_any_migration_sql(self):
        conn = FakeConn(history=[(1, "a", "f" * 64)])
        with self.assertRaises(migrator.MigrationChecksumError):
            migrator.apply_migrations(conn, self.m)
        self.assertNotIn("CREATE TABLE b ()", conn.log)
        self.assertEqual(conn.log[-1], "ROLLBACK")


class ConnectionTests(unittest.TestCase):
    def test_socket_path_becomes_dir_and_port(self):
        self.assertEqual(
            connection.build_conninfo(dbname="d", user="u", socket="/tmp/.s.PGSQL.5432"),
            "host='/tmp' port='5432' dbname='d' user='u'",
        )

    def test_tcp_and_quoting(self):
        self.assertEqual(
            connection.build_conninfo(dbname="a b", user="o'k", host="127.0.0.1", port="5433"),
            "host='127.0.0.1' port='5433' dbname='a b' user='o\\'k'",
        )

    def test_bad_socket_and_missing_transport(self):
        with self.assertRaises(ValueError):
            connection.build_conninfo(dbname="d", user="u", socket="/tmp/pg.sock")
        with self.assertRaises(ValueError):
            connection.build_conninfo(dbname="d", user="u")

    def test_missing_env_names_exactly_what_to_set(self):
        self.assertEqual(
            connection.missing_env_vars({}),
            ["FINWEB_PG_INTEGRATION=1",
             "FINWEB_PG_SOCKET (or FINWEB_PG_HOST and FINWEB_PG_PORT)",
             "FINWEB_PG_DATABASE", "FINWEB_PG_USER"],
        )
        full = {"FINWEB_PG_INTEGRATION": "1", "FINWEB_PG_HOST": "h", "FINWEB_PG_PORT": "1",
                "FINWEB_PG_DATABASE": "d", "FINWEB_PG_USER": "u"}
        self.assertEqual(connection.missing_env_vars(full), [])

    def test_driver_import_is_lazy_and_only_in_connect(self):
        for module in (connection, migrator, ledger_store, ledger_sql):
            source = Path(module.__file__).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"^(import|from) psycopg", source, re.M))
        source = Path(connection.__file__).read_text(encoding="utf-8")
        self.assertEqual(source.count("import psycopg"), 1)
        self.assertGreater(source.index("import psycopg"), source.index("def connect"))


_E = uuid.UUID("e1000000-0000-0000-0000-000000000001")
_ACC = uuid.UUID("a3333333-3333-3333-3333-333333333333")
_LST = uuid.UUID("b3333333-3333-3333-3333-333333333333")
_USD = CurrencyCode("USD")


class RowMappingTests(unittest.TestCase):
    def _roundtrip(self, event):
        row = (7,) + ledger_store.event_to_row(event)
        self.assertEqual(len(row), 1 + len(ledger_store.EVENT_COLUMNS))
        seq, back = ledger_store.row_to_event(row)
        self.assertEqual(seq, 7)
        self.assertTrue(back.has_same_content(event))
        self.assertEqual(back.event_id, event.event_id)
        return back

    def test_buy_roundtrip_keeps_decimal_scale(self):
        e = LedgerEvent(_E, _ACC, EventType.BUY, datetime.date(2024, 3, 15), _USD,
                        listing_id=_LST, quantity=Decimal("10.50"),
                        amount=Money(Decimal("1500.10"), _USD),
                        settlement_date=datetime.date(2024, 3, 17), source_reference="S1")
        back = self._roundtrip(e)
        self.assertEqual(str(back.quantity), "10.50")

    def test_split_and_snapshot_roundtrip(self):
        self._roundtrip(LedgerEvent(
            _E, _ACC, EventType.SPLIT, datetime.date(2024, 1, 2), _USD, listing_id=_LST,
            split_ratio=SplitRatio(Decimal("1"), Decimal("10"))))
        self._roundtrip(LedgerEvent(
            _E, _ACC, EventType.OPENING_POSITION, datetime.date(2024, 1, 2), _USD,
            listing_id=_LST, quantity=Decimal("5"), cost_basis=Money(Decimal("0"), _USD)))

    def test_row_values_are_native_types_only(self):
        e = LedgerEvent(_E, _ACC, EventType.DEPOSIT, datetime.date(2024, 1, 2), _USD,
                        amount=Money(Decimal("1"), _USD))
        row = ledger_store.event_to_row(e)
        self.assertEqual(row[ledger_store.EVENT_COLUMNS.index("currency")], "USD")
        self.assertEqual(row[ledger_store.EVENT_COLUMNS.index("event_type")], "DEPOSIT")
        self.assertIsInstance(row[ledger_store.EVENT_COLUMNS.index("amount")], Decimal)
        self.assertNotIn("Money", [type(v).__name__ for v in row])


class _AppendConn:
    """Scripted fake for append_event decision logic."""

    def __init__(self, insert_row, by_key=None, by_id=None, reversed_by=None):
        self.insert_row, self.by_key, self.by_id = insert_row, by_key, by_id
        self.reversed_by = reversed_by

    def transaction(self):
        return _Tx(type("L", (), {"log": []})())

    def execute(self, sql, params=None):
        if sql.startswith("INSERT INTO ledger_event"):
            return _Cursor([self.insert_row] if self.insert_row else [])
        if sql == ledger_store.SELECT_BY_KEY_SQL:
            return _Cursor([self.by_key] if self.by_key else [])
        if sql == ledger_store.SELECT_BY_EVENT_ID_SQL:
            return _Cursor([self.by_id] if self.by_id else [])
        if "reverses_event_id = %s" in sql:
            return _Cursor([self.reversed_by] if self.reversed_by else [])
        raise AssertionError(sql)


class AppendDecisionTests(unittest.TestCase):
    def _ev(self, event_id=_E, qty="10", ref="S1"):
        return LedgerEvent(event_id, _ACC, EventType.BUY, datetime.date(2024, 3, 15), _USD,
                           listing_id=_LST, quantity=Decimal(qty),
                           amount=Money(Decimal("100"), _USD), source_reference=ref)

    def _row(self, event, seq=3):
        return (seq,) + ledger_store.event_to_row(event)

    def test_new_event(self):
        r = ledger_store.append_event(_AppendConn((5,)), self._ev())
        self.assertTrue(r.created)
        self.assertEqual(r.ledger_seq, 5)

    def test_same_key_same_content_returns_existing_event(self):
        other = uuid.UUID("e1000000-0000-0000-0000-000000000009")
        stored = self._ev(event_id=other, qty="10.0")
        r = ledger_store.append_event(
            _AppendConn(None, by_key=self._row(stored)), self._ev(qty="10.00"))
        self.assertFalse(r.created)
        self.assertEqual(r.event.event_id, other)
        self.assertEqual(str(r.event.quantity), "10.0")  # stored scale kept

    def test_same_key_different_content_conflicts(self):
        stored = self._ev(event_id=uuid.UUID("e1000000-0000-0000-0000-000000000009"))
        with self.assertRaises(ledger_store.IdempotencyConflictError) as cm:
            ledger_store.append_event(
                _AppendConn(None, by_key=self._row(stored)), self._ev(qty="11"))
        self.assertEqual(cm.exception.existing_event_id, stored.event_id)

    def test_same_event_id_different_content_is_duplicate_id(self):
        stored = self._ev(ref=None)
        with self.assertRaises(ledger_store.DuplicateEventIdError):
            ledger_store.append_event(
                _AppendConn(None, by_id=self._row(stored)), self._ev(qty="11", ref=None))

    def test_same_event_id_same_content_is_no_op(self):
        stored = self._ev(ref=None)
        r = ledger_store.append_event(_AppendConn(None, by_id=self._row(stored)),
                                      self._ev(ref=None))
        self.assertFalse(r.created)

    def test_already_reversed_reports_the_rule(self):
        rev = LedgerEvent(uuid.UUID(int=99), _ACC, EventType.REVERSAL,
                          datetime.date(2024, 3, 16), _USD, reverses_event_id=_E)
        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_event(
                _AppendConn(None, reversed_by=(uuid.UUID(int=5),)), rev)
        self.assertEqual(cm.exception.constraint_name, "ledger_event_reversed_once")

    def test_database_rejection_is_translated(self):
        class Diag:
            constraint_name = "ledger_event_fields_buy"

        class DbError(Exception):
            sqlstate = "23514"
            diag = Diag()

        class Boom(_AppendConn):
            def execute(self, sql, params=None):
                raise DbError("check failed")

        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_event(Boom(None), self._ev())
        self.assertEqual(cm.exception.constraint_name, "ledger_event_fields_buy")

    def test_non_integrity_errors_propagate(self):
        class Boom(_AppendConn):
            def execute(self, sql, params=None):
                raise RuntimeError("connection lost")

        with self.assertRaises(RuntimeError):
            ledger_store.append_event(Boom(None), self._ev())


class _SeqConn:
    """Fake that accepts every INSERT, hands out increasing ledger_seq values
    and records the inserted event types in order."""

    def __init__(self, fail_on_type=None):
        self.next_seq = 10
        self.inserted = []
        self.log = []
        self.fail_on_type = fail_on_type

    def transaction(self):
        return _Tx(self)

    def execute(self, sql, params=None):
        if sql.startswith("INSERT INTO ledger_event"):
            event_type = params[ledger_store.EVENT_COLUMNS.index("event_type")]
            if event_type == self.fail_on_type:
                raise RuntimeError("boom")
            self.inserted.append(event_type)
            self.next_seq += 1
            return _Cursor([(self.next_seq,)])
        raise AssertionError(sql)


_ACC2 = uuid.UUID("a4444444-4444-4444-4444-444444444444")


class BatchPathTests(unittest.TestCase):
    def _buy(self, event_id, **kw):
        base = dict(listing_id=_LST, quantity=Decimal("10"), amount=Money(Decimal("100"), _USD))
        base.update(kw)
        return LedgerEvent(event_id, _ACC, EventType.BUY, datetime.date(2024, 3, 15), _USD, **base)

    def test_correction_appends_reversal_first_in_one_transaction(self):
        target = uuid.UUID(int=1)
        reversal = LedgerEvent(uuid.UUID(int=2), _ACC, EventType.REVERSAL,
                               datetime.date(2024, 3, 20), _USD, reverses_event_id=target)
        replacement = self._buy(uuid.UUID(int=3), corrects_event_id=target)
        conn = _SeqConn()
        result = ledger_store.append_correction(conn, reversal, replacement)
        self.assertEqual(conn.inserted, ["REVERSAL", "BUY"])
        self.assertLess(result.reversal.ledger_seq, result.replacement.ledger_seq)

    def test_correction_pair_is_validated_before_any_write(self):
        reversal = LedgerEvent(uuid.UUID(int=2), _ACC, EventType.REVERSAL,
                               datetime.date(2024, 3, 20), _USD,
                               reverses_event_id=uuid.UUID(int=1))
        conn = _SeqConn()
        with self.assertRaises(ValueError):
            ledger_store.append_correction(
                conn, reversal, self._buy(uuid.UUID(int=3), corrects_event_id=uuid.UUID(int=9)))
        self.assertEqual(conn.inserted, [])

    def test_failure_of_second_event_propagates_out_of_the_transaction(self):
        conn = _SeqConn(fail_on_type="BUY")
        reversal = LedgerEvent(uuid.UUID(int=2), _ACC, EventType.REVERSAL,
                               datetime.date(2024, 3, 20), _USD,
                               reverses_event_id=uuid.UUID(int=1))
        with self.assertRaises(RuntimeError):
            ledger_store.append_correction(
                conn, reversal, self._buy(uuid.UUID(int=3), corrects_event_id=uuid.UUID(int=1)))
        self.assertEqual(conn.log[-1], "ROLLBACK")

    def test_internal_transfer_appends_out_then_in_and_validates_first(self):
        d = datetime.date(2024, 3, 15)
        out = LedgerEvent(uuid.UUID(int=1), _ACC, EventType.TRANSFER_OUT, d, _USD,
                          amount=Money(Decimal("5"), _USD), counterparty_account_id=_ACC2)
        inn = LedgerEvent(uuid.UUID(int=2), _ACC2, EventType.TRANSFER_IN, d, _USD,
                          amount=Money(Decimal("5"), _USD), counterparty_account_id=_ACC)
        conn = _SeqConn()
        ledger_store.append_internal_transfer(conn, out, inn)
        self.assertEqual(conn.inserted, ["TRANSFER_OUT", "TRANSFER_IN"])
        bad = LedgerEvent(uuid.UUID(int=3), _ACC2, EventType.TRANSFER_IN, d, _USD,
                          amount=Money(Decimal("6"), _USD), counterparty_account_id=_ACC)
        conn2 = _SeqConn()
        with self.assertRaises(ValueError):
            ledger_store.append_internal_transfer(conn2, out, bad)
        self.assertEqual(conn2.inserted, [])

    def test_conversion_correction_appends_reversal_then_replacement(self):
        """Example 5A-B inputs: 1,000 USD -> 7,750 HKD replaces 1,000 USD -> 7,780 HKD."""
        hkd = CurrencyCode("HKD")
        target = uuid.UUID(int=1)
        d = datetime.date(2025, 4, 2)
        reversal = LedgerEvent(uuid.UUID(int=2), _ACC, EventType.REVERSAL,
                               datetime.date(2025, 4, 10), _USD, reverses_event_id=target)
        replacement = LedgerEvent(
            uuid.UUID(int=3), _ACC, EventType.CURRENCY_CONVERSION, d, _USD,
            amount=Money(Decimal("1000"), _USD),
            bought_amount=Money(Decimal("7750"), hkd), corrects_event_id=target)
        conn = _SeqConn()
        result = ledger_store.append_correction(conn, reversal, replacement)
        self.assertEqual(conn.inserted, ["REVERSAL", "CURRENCY_CONVERSION"])
        self.assertLess(result.reversal.ledger_seq, result.replacement.ledger_seq)

    def test_conversion_round_trips_both_sides_with_scale_and_no_rate(self):
        hkd = CurrencyCode("HKD")
        e = LedgerEvent(_E, _ACC, EventType.CURRENCY_CONVERSION, datetime.date(2025, 4, 2), _USD,
                        amount=Money(Decimal("1002.00"), _USD),
                        bought_amount=Money(Decimal("7780.00"), hkd),
                        settlement_date=datetime.date(2025, 4, 4))
        row = ledger_store.event_to_row(e)
        cols = ledger_store.EVENT_COLUMNS
        self.assertEqual(row[cols.index("currency")], "USD")
        self.assertEqual(row[cols.index("bought_currency")], "HKD")
        self.assertEqual(row[cols.index("bought_amount")], Decimal("7780.00"))
        _, back = ledger_store.row_to_event((1,) + row)
        self.assertEqual(back.bought_amount, Money(Decimal("7780.00"), hkd))
        self.assertEqual(str(back.bought_amount.amount), "7780.00")
        self.assertTrue(back.has_same_content(e))
        # no value in the row is a computed ratio of the two amounts
        self.assertNotIn(Decimal("7780.00") / Decimal("1002.00"), row)

    def test_already_corrected_reports_the_rule(self):
        replacement = self._buy(uuid.UUID(int=3), corrects_event_id=uuid.UUID(int=1))

        class Conn(_AppendConn):
            def execute(self, sql, params=None):
                if "corrects_event_id = %s" in sql:
                    return _Cursor([(uuid.UUID(int=8),)])
                return super().execute(sql, params)

        with self.assertRaises(ledger_store.LedgerRuleRejectedError) as cm:
            ledger_store.append_event(Conn(None), replacement)
        self.assertEqual(cm.exception.constraint_name, "ledger_event_corrected_once")

    def test_ex_date_round_trips_through_rows(self):
        e = LedgerEvent(_E, _ACC, EventType.DIVIDEND, datetime.date(2024, 3, 15), _USD,
                        listing_id=_LST, amount=Money(Decimal("3"), _USD),
                        ex_date=datetime.date(2024, 3, 1))
        seq, back = ledger_store.row_to_event((1,) + ledger_store.event_to_row(e))
        self.assertEqual(back.ex_date, datetime.date(2024, 3, 1))
        self.assertTrue(back.has_same_content(e))


class ManifestTests(unittest.TestCase):
    """CP1B-4: frozen migrations are pinned in the repository."""

    def test_every_migration_is_pinned_and_matches(self):
        manifest = migrator.read_manifest(_MIG)
        migrator.verify_manifest(migrator.load_migrations(), manifest)
        for name, digest in manifest.items():
            self.assertEqual(digest, hashlib.sha256((_MIG / name).read_bytes()).hexdigest())

    def test_the_frozen_migrations_are_pinned_to_their_applied_content(self):
        """0001-0003 were applied to a real database; these values are the checksums
        that database recorded. Changing them is a frozen-file violation."""
        manifest = migrator.read_manifest(_MIG)
        self.assertEqual(manifest["0001_domain_entities.sql"],
                         "76b7d0546204def14d8572cb6a3959fd27fd3ef202e7720a8411257988ed6749")
        self.assertEqual(manifest["0002_ledger_event.sql"],
                         "817d8f99e42f5618c5ed0788353107a6e4ee7c2152aabd1adc135fb2ec89f22f")
        self.assertEqual(manifest["0003_ledger_event_guards.sql"],
                         "9c701cc22de40f48d0020f107820f5f83d4fe6821fad52d482cc925ded34eac8")

    def test_an_edited_migration_is_refused_before_any_database_is_touched(self):
        migs = migrator.load_migrations()
        manifest = migrator.read_manifest(_MIG)
        edited = [
            migrator.Migration(m.version, m.name, m.filename, m.sql + "\n-- edit",
                               migrator.checksum_of((m.sql + "\n-- edit").encode()))
            if m.version == 3 else m
            for m in migs
        ]
        with self.assertRaises(migrator.MigrationManifestError):
            migrator.verify_manifest(edited, manifest)

    def test_unpinned_and_dangling_entries_are_refused(self):
        migs = migrator.load_migrations()
        manifest = dict(migrator.read_manifest(_MIG))
        without = dict(manifest)
        del without["0005_opening_correction_link.sql"]
        with self.assertRaises(migrator.MigrationManifestError):
            migrator.verify_manifest(migs, without)
        with self.assertRaises(migrator.MigrationManifestError):
            migrator.verify_manifest(migs, dict(manifest, **{"0006_x.sql": "0" * 64}))

    def test_runner_default_path_verifies_the_manifest(self):
        conn = FakeConn()
        self.assertEqual(len(migrator.apply_migrations(conn)), 19)  # 0019: immutable CSV reports/source keys; prior migrations frozen

    def test_manifest_parsing_errors(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "CHECKSUMS"
        for bad in ("abc  0001_a.sql\n", "%s  0001_a.sql\n%s  0001_a.sql\n" % ("0" * 64, "0" * 64)):
            path.write_text(bad, encoding="utf-8")
            with self.assertRaises(migrator.MigrationManifestError):
                migrator.read_manifest(Path(tmp.name))


class HardeningMigrationStructureTests(unittest.TestCase):
    """Text-level checks of 0004 (the real proofs are the integration tests)."""

    def setUp(self):
        self.sql = _sql("0004_ledger_hardening.sql")

    def test_every_trigger_function_is_pinned_with_pg_temp_last(self):
        self.assertIn("SET search_path = %I, pg_temp", self.sql)
        for fn in ("ledger_event_reject_mutation()", "ledger_event_before_insert()",
                   "ledger_event_check_transfer_pairing()", "account_guard_identity()"):
            self.assertIn("'%s'" % fn, self.sql)
        # the pin runs after every CREATE [OR REPLACE] FUNCTION in this file
        self.assertGreater(self.sql.index("ALTER FUNCTION"),
                           self.sql.rindex("CREATE OR REPLACE FUNCTION"))
        self.assertGreater(self.sql.index("ALTER FUNCTION"),
                           self.sql.rindex("CREATE FUNCTION"))

    def test_the_latest_definition_of_every_function_is_followed_by_a_pin(self):
        """R2-2 (DB-free half): CREATE OR REPLACE resets a function's SET list, so for each
        function the LAST migration that creates it must also contain, AFTER that create, a
        `SET search_path = %I, pg_temp` pin block naming it, or a LATER migration must pin
        it. (The integration test reads pg_proc.proconfig for the real proof.)"""
        import re

        migs = migrator.load_migrations()
        create = re.compile(r"CREATE (?:OR REPLACE )?FUNCTION (\w+)\(")
        latest = {}  # fn -> (migration index, offset of last create in that file)
        for index, m in enumerate(migs):
            for match in create.finditer(m.sql):
                latest[match.group(1)] = (index, match.start())
        self.assertGreaterEqual(len(latest), 5)
        for fn, (index, offset) in latest.items():
            pinned = False
            for later_index in range(index, len(migs)):
                text = migs[later_index].sql
                start = offset if later_index == index else 0
                block = text[start:]
                if ("SET search_path = %I, pg_temp" in block
                        and re.search(r"'%s\(" % re.escape(fn), block)):
                    pinned = True
            self.assertTrue(pinned, "%s is not re-pinned after its latest definition" % fn)

    def test_the_0006_pin_names_every_function_it_defines_and_the_earlier_ones(self):
        sql = _sql("0006_epoch_safe_correction_and_pin_guard.sql")
        for fn in ("ledger_event_reject_mutation()", "ledger_event_before_insert()",
                   "ledger_event_check_transfer_pairing()", "account_guard_identity()",
                   "ledger_full_xid(text,numeric)"):
            self.assertIn("'%s'" % fn, sql)
        self.assertEqual(sql.count("ledger_event_search_path_pin_stale"), 2)  # both trigger fns
        self.assertGreater(sql.index("ALTER FUNCTION"), sql.rindex("CREATE OR REPLACE FUNCTION"))

    def test_no_epoch_dropping_cast_remains_in_the_active_trigger(self):
        active = _sql("0006_epoch_safe_correction_and_pin_guard.sql")
        body = active[active.index("CREATE OR REPLACE FUNCTION ledger_event_before_insert"):]
        self.assertNotIn("reversal_xmin::xid8", body)
        self.assertIn("ledger_full_xid(", body)
        self.assertIn("pg_current_xact_id()", body)

    def test_the_fix_does_not_depend_on_revoking_temporary(self):
        self.assertNotIn("REVOKE", self.sql.upper().replace("-- ", "").split("DO $$")[0]
                         .replace("DOES NOT RELY ON REVOKING", ""))

    def test_idempotency_is_decided_before_the_rules_and_recorded_at_is_forced(self):
        body = self.sql[self.sql.index("CREATE OR REPLACE FUNCTION ledger_event_before_insert"):]
        order = [body.index(s) for s in (
            "NEW.recorded_at := now()", "pg_advisory_xact_lock", "NEW.ledger_seq := nextval",
            "RETURN NEW;", "a REVERSAL cannot be reversed",
            "ledger_event_correction_same_transaction", "ledger_event_after_snapshot_date")]
        self.assertEqual(order, sorted(order))

    def test_account_identity_trigger_exists(self):
        self.assertIn("CREATE TRIGGER account_identity_immutable", self.sql)
        self.assertIn("BEFORE UPDATE ON account", self.sql)


class StoreErrorMappingTests(unittest.TestCase):
    def _fail(self, sqlstate):
        class DbError(Exception):
            pass

        err = DbError("db said no")
        err.sqlstate = sqlstate

        class Boom(_AppendConn):
            def execute(self, sql, params=None):
                raise err

        ev = LedgerEvent(_E, _ACC, EventType.DEPOSIT, datetime.date(2024, 3, 15), _USD,
                         amount=Money(Decimal("1"), _USD))
        return lambda: ledger_store.append_event(Boom(None), ev)

    def test_deadlock_and_serialization_failures_are_typed_and_retryable(self):
        for state in ("40P01", "40001"):
            with self.assertRaises(ledger_store.LedgerConcurrencyError) as cm:
                self._fail(state)()
            self.assertEqual(cm.exception.sqlstate, state)

    def test_numeric_overflow_is_typed(self):
        with self.assertRaises(ledger_store.LedgerValueOutOfRangeError):
            self._fail("22003")()

    def test_other_errors_still_propagate_raw(self):
        with self.assertRaises(Exception) as cm:
            self._fail("08006")()
        self.assertNotIsInstance(cm.exception, ledger_store.LedgerStoreError)


class XidEpochTests(unittest.TestCase):
    """R2-1: the 32-bit xmin -> full 64-bit id recovery (Python mirror of ledger_full_xid)."""

    def test_epoch_zero_is_identity(self):
        self.assertEqual(xid_epoch.full_xid(11335, 11340), 11335)
        self.assertEqual(xid_epoch.full_xid(11340, 11340), 11340)
        self.assertEqual(xid_epoch.full_xid(11400, 11340), 11400)  # a later subtransaction id

    def test_rows_in_the_current_epoch_keep_the_epoch(self):
        anchor = 5 * 2 ** 32 + 10
        self.assertEqual(xid_epoch.full_xid(20, anchor), 5 * 2 ** 32 + 20)
        self.assertEqual(xid_epoch.full_xid(10, anchor), anchor)
        self.assertEqual(xid_epoch.full_xid(7, anchor), 5 * 2 ** 32 + 7)

    def test_a_row_from_before_the_epoch_boundary_maps_to_the_previous_epoch(self):
        anchor = 2 ** 32 + 3
        self.assertEqual(xid_epoch.full_xid(2 ** 32 - 6, anchor), 2 ** 32 - 6)
        self.assertEqual(xid_epoch.full_xid(2 ** 32 - 1, anchor), 2 ** 32 - 1)

    def test_a_subtransaction_id_just_past_the_boundary_maps_forward(self):
        anchor = 2 ** 32 - 2  # top-level xid just below the wrap, a subtransaction just above
        self.assertEqual(xid_epoch.full_xid(5, anchor), 2 ** 32 + 5)
        self.assertEqual(xid_epoch.full_xid(2 ** 32 - 1, anchor), 2 ** 32 - 1)

    def test_special_ids_are_never_in_progress(self):
        for special in (0, 1, 2):
            self.assertIsNone(xid_epoch.full_xid(special, 7 * 2 ** 32 + 100))
        self.assertIsNone(xid_epoch.full_xid(4000000000, 3))  # would be negative

    def test_exact_recovery_over_a_grid_of_anchors_and_offsets(self):
        """For every anchor (epochs 0..3, including boundary neighbourhoods) and every true
        id within +-(2^31 - 1) of it, reducing to 32 bits and recovering gives the id back."""
        anchors = []
        for epoch in range(4):
            base = epoch * 2 ** 32
            anchors += [base + 3, base + 10, base + 2 ** 31, base + 2 ** 32 - 5, base + 2 ** 32 - 1]
        offsets = [-(2 ** 31 - 1), -(2 ** 31) + 12345, -70000, -1, 0, 1, 64, 70000,
                   2 ** 31 - 12345, 2 ** 31 - 1]
        checked = 0
        for anchor in anchors:
            for offset in offsets:
                true_id = anchor + offset
                if true_id < xid_epoch.FIRST_NORMAL_XID or true_id % 2 ** 32 < 3:
                    continue
                self.assertEqual(xid_epoch.full_xid(true_id % 2 ** 32, anchor), true_id,
                                 (anchor, offset))
                checked += 1
        self.assertGreater(checked, 100)


class SameDaySplitContractTests(unittest.TestCase):
    """Migration 0007 (F12) and its typed error."""

    def setUp(self):
        self.sql = _sql("0007_one_live_split_per_position_per_day.sql")

    def test_the_check_runs_under_the_lock_after_the_idempotency_return(self):
        order = [self.sql.index(s) for s in (
            "pg_advisory_xact_lock", "NEW.ledger_seq := nextval", "RETURN NEW;",
            "ledger_event_split_once_per_day")]
        self.assertEqual(order, sorted(order))

    def test_liveness_excludes_reversed_splits_and_keys_on_account_listing_date(self):
        block = self.sql[self.sql.index("IF NEW.event_type = 'SPLIT'"):]
        block = block[:block.index("IF NEW.event_type IN ('OPENING")]
        for needle in ("s.account_id = NEW.account_id", "s.listing_id = NEW.listing_id",
                       "s.event_date = NEW.event_date", "r.reverses_event_id = s.event_id"):
            self.assertIn(needle, block)

    def test_the_replaced_function_keeps_the_rename_guard_and_is_repinned(self):
        self.assertIn("ledger_event_search_path_pin_stale", self.sql)
        self.assertIn("SET search_path = %I, pg_temp", self.sql)
        self.assertIn("'ledger_event_before_insert()'", self.sql)
        self.assertGreater(self.sql.index("ALTER FUNCTION"),
                           self.sql.rindex("CREATE OR REPLACE FUNCTION"))

    def test_the_constraint_name_maps_to_a_typed_error(self):
        class Diag:
            constraint_name = "ledger_event_split_once_per_day"

        class DbError(Exception):
            sqlstate = "23514"
            diag = Diag()

        class Boom(_AppendConn):
            def execute(self, sql, params=None):
                raise DbError("second split")

        event = LedgerEvent(_E, _ACC, EventType.SPLIT, datetime.date(2025, 5, 16), _USD,
                            listing_id=_LST,
                            split_ratio=SplitRatio(Decimal("3"), Decimal("2")))
        with self.assertRaises(ledger_store.SameDaySplitError) as cm:
            ledger_store.append_event(Boom(None), event)
        self.assertIsInstance(cm.exception, ledger_store.LedgerRuleRejectedError)
        self.assertEqual(cm.exception.constraint_name, ledger_store.SAME_DAY_SPLIT_CONSTRAINT)


class Migration0008Tests(unittest.TestCase):
    """R3-1 to R3-4 (DB-free half; the integration tests prove them on the server)."""

    def setUp(self):
        self.sql = _sql("0008_bounds_append_xid_and_lock_scope.sql")

    def test_bounds_python_statement(self):
        from domain.ledger import numeric_bounds_violation as bad

        for ok in ("0.000000000000000001", "1E-24", "9999999999999999.99",
                   "999999999999999999999999999999", "0.500000000000000000000000", "1E+3"):
            self.assertIsNone(bad(Decimal(ok)), ok)
        for over in ("1E+30", "1E+150", "1E+5000", "1E-25", "1E-60",
                     "1.0000000000000000000000000"):
            self.assertIsNotNone(bad(Decimal(over)), over)
        self.assertIsNone(bad(Decimal("NaN")))  # non-finite: the callers' own check

    def test_every_numeric_column_has_a_bounds_check_and_the_store_knows_the_names(self):
        for column in ("quantity", "amount", "cost_basis", "bought_amount", "split_new",
                       "split_old"):
            name = "ledger_event_%s_bounds" % column
            self.assertIn(name, self.sql)
            self.assertIn(name, ledger_store.NUMERIC_BOUND_CONSTRAINTS)
            self.assertIn("%s < 1E30 AND scale(%s) <= 24) NOT VALID" % (column, column),
                          self.sql)  # R4-1: new rows only; a ledger with old rows still upgrades

    def test_a_bounds_violation_is_a_typed_error(self):
        class Diag:
            constraint_name = "ledger_event_quantity_bounds"

        class DbError(Exception):
            sqlstate = "23514"
            diag = Diag()

        class Boom(_AppendConn):
            def execute(self, sql, params=None):
                raise DbError("bounds")

        event = LedgerEvent(_E, _ACC, EventType.DEPOSIT, datetime.date(2024, 3, 15), _USD,
                            amount=Money(Decimal("1E+5000"), _USD))
        with self.assertRaises(ledger_store.LedgerValueOutOfRangeError):
            ledger_store.append_event(Boom(None), event)

    def test_append_identity_is_trigger_set_before_the_idempotency_return(self):
        body = self.sql[self.sql.index("CREATE OR REPLACE FUNCTION ledger_event_before_insert"):]
        order = [body.index(s) for s in (
            "NEW.append_xid := pg_current_xact_id()", "NEW.portfolio_id := own_portfolio",
            "pg_advisory_xact_lock", "NEW.ledger_seq := nextval", "RETURN NEW;")]
        self.assertEqual(order, sorted(order))
        self.assertIn("NOT VALID", self.sql)
        self.assertIn("ON ledger_event (portfolio_id, ledger_seq) INCLUDE (append_xid)", self.sql)
        self.assertIn("never an input to any computation", self.sql)

    def test_the_correction_check_no_longer_uses_xmin_or_pg_xact_status(self):
        body = self.sql[self.sql.index("CREATE OR REPLACE FUNCTION ledger_event_before_insert"):]
        self.assertNotIn("xmin", body)
        self.assertNotIn("pg_xact_status", body)
        self.assertIn("reversal_xid IS DISTINCT FROM pg_current_xact_id()", body)

    def test_lock_keys_are_schema_scoped(self):
        self.assertIn("'finweb.ledger.portfolio:' || TG_TABLE_SCHEMA || ':'", self.sql)
        source = Path(migrator.__file__).read_text(encoding="utf-8")
        self.assertNotIn("_ADVISORY_LOCK_KEY", source)
        self.assertIn("current_schema()", source)

    def test_the_replaced_function_keeps_the_guard_and_is_repinned(self):
        self.assertIn("ledger_event_search_path_pin_stale", self.sql)
        self.assertIn("SET search_path = %I, pg_temp", self.sql)
        self.assertGreater(self.sql.index("ALTER FUNCTION"),
                           self.sql.rindex("CREATE OR REPLACE FUNCTION"))


class ConcurrencyErrorContractTests(unittest.TestCase):
    """R2-4: what LedgerConcurrencyError promises depends on who owns the transaction."""

    class _Info:
        def __init__(self, status):
            self.transaction_status = status

    def _conn_with_status(self, status):
        class Boom(_AppendConn):
            info = self._Info(status)

            def execute(self, sql, params=None):
                err = Exception("deadlock detected")
                err.sqlstate = "40P01"
                raise err

        return Boom(None)

    def _event(self):
        return LedgerEvent(_E, _ACC, EventType.DEPOSIT, datetime.date(2024, 3, 15), _USD,
                           amount=Money(Decimal("1"), _USD))

    def test_store_owned_transaction_is_retry_safe(self):
        with self.assertRaises(ledger_store.LedgerConcurrencyError) as cm:
            ledger_store.append_event(self._conn_with_status(0), self._event())  # IDLE
        self.assertTrue(cm.exception.transaction_owned)
        self.assertTrue(cm.exception.retry_safe)
        self.assertIn("retrying the same call is safe", str(cm.exception))

    def test_caller_owned_transaction_is_not_claimed_retry_safe(self):
        for status in (2, 3):  # INTRANS, INERROR
            with self.assertRaises(ledger_store.LedgerConcurrencyError) as cm:
                ledger_store.append_event(self._conn_with_status(status), self._event())
            error = cm.exception
            self.assertFalse(error.transaction_owned)
            self.assertFalse(error.retry_safe)
            self.assertIn("roll back the WHOLE transaction", str(error))
            self.assertNotIn("retrying the same call is safe", str(error))

    def test_a_double_without_connection_info_is_treated_as_store_owned(self):
        self.assertTrue(ledger_store._store_owns_transaction(_AppendConn(None)))


class GuardMigrationStructureTests(unittest.TestCase):
    """Text-level checks of properties that only a server can fully prove."""

    def setUp(self):
        self.guards = _sql("0003_ledger_event_guards.sql")
        self.table = _sql("0002_ledger_event.sql")

    def test_ledger_seq_is_drawn_after_the_portfolio_lock_and_has_no_default(self):
        self.assertLess(self.guards.index("pg_advisory_xact_lock"),
                        self.guards.index("NEW.ledger_seq := nextval"))
        self.assertLess(self.guards.index("transaction_isolation"),
                        self.guards.index("pg_advisory_xact_lock"))
        self.assertIn("ledger_seq bigint PRIMARY KEY,", self.table)
        self.assertNotIn("IDENTITY", self.table.upper().split("CREATE TABLE LEDGER_EVENT")[1])

    def test_only_one_before_insert_trigger_so_ordering_is_not_name_dependent(self):
        self.assertEqual(self.guards.count("BEFORE INSERT ON ledger_event"), 1)

    def test_pairing_check_is_a_deferred_constraint_trigger(self):
        self.assertIn("CREATE CONSTRAINT TRIGGER ledger_event_transfer_pairing", self.guards)
        self.assertIn("DEFERRABLE INITIALLY DEFERRED", self.guards)

    def test_correction_and_snapshot_rules_present(self):
        for name in ("ledger_event_corrected_once", "ledger_event_correction_target_fk",
                     "ledger_event_correction_target_key"):
            self.assertIn(name, self.table)
        for name in ("ledger_event_snapshot_single_date",
                     "ledger_event_snapshot_precedes_activity",
                     "ledger_event_after_snapshot_date"):
            self.assertIn(name, self.guards)
        self.assertIn("ex_date <= event_date", self.table)

    def test_edit_in_place_policy_is_stated_in_the_migrations(self):
        for text in (self.table, self.guards):
            self.assertIn("NEW numbered file", text.replace("new numbered file", "NEW numbered file"))


if __name__ == "__main__":
    unittest.main()
