"""CP4b-3: the benchmark selection store and migration 0015 (PD-0039 D5; tech plan 17.5, 17.14).

The PURE parts (row mapping, the store and the migration agreeing on the columns, the import boundary) always run. The DATABASE tests are opt-in (the integration variables plus `FINWEB_PG_APP_USER`) and run
as the least-privilege application role in one disposable schema created, migrated and dropped by the owner role, like the ledger's:

    FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app \\
        uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t . -p 'test_postgres_benchmark_selection.py' -v

Every test makes its own portfolio, so tests share nothing and can run in any order.
"""

import ast
import datetime
import re
import sys
import threading
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pg_market_kit as pk  # noqa: E402

from domain import benchmark_selection as bs  # noqa: E402
from domain.benchmark_selection import BenchmarkSelection, Origin, RecordType, SelectionState  # noqa: E402
from persistence import benchmark_selection_store as store  # noqa: E402
from persistence import connection, migrator  # noqa: E402
from persistence.ledger_replay_store import PortfolioNotFoundError  # noqa: E402

D = datetime.date
_SKIP = pk.skip_reason()
_USER = uuid.UUID("a1111111-1111-1111-1111-1111111111b5")
_COUNTER = [0]


def new_id():
    _COUNTER[0] += 1
    return uuid.UUID(int=(0xB5 << 120) + _COUNTER[0])


def select(portfolio, benchmark="SPX", on=D(2026, 1, 5), origin=Origin.USER_CHOSEN, **kw):
    return BenchmarkSelection(new_id(), portfolio, RecordType.SELECT, on, benchmark, None, origin, **kw)


def clear(portfolio, on=D(2026, 1, 5), **kw):
    return BenchmarkSelection(new_id(), portfolio, RecordType.CLEAR, on, **kw)


def reversal(portfolio, target, on=D(2026, 1, 5)):
    return BenchmarkSelection(new_id(), portfolio, RecordType.REVERSAL, on, reverses_selection_id=target)


class StoreUnitTests(unittest.TestCase):
    """No database: the store, the domain and the migration agree."""

    MIGRATION = (Path(migrator.MIGRATIONS_DIR) / "0015_benchmark_selection.sql").read_text(encoding="utf-8")

    def test_every_store_column_is_a_column_of_the_table_and_every_domain_field_is_stored(self):
        body = self.MIGRATION[self.MIGRATION.index("CREATE TABLE benchmark_selection"):self.MIGRATION.index("ALTER SEQUENCE")]
        table_columns = set(re.findall(r"^    (\w+) (?:bigint|uuid|text|date|timestamptz|xid8)\b", body, re.M))
        self.assertTrue(set(store.COLUMNS) <= table_columns, set(store.COLUMNS) - table_columns)
        self.assertEqual(set(store.COLUMNS), {"selection_id", "portfolio_id", "record_type", "selected_on", "benchmark_id", "catalog_version", "origin", "reverses_selection_id", "corrects_selection_id"})
        import dataclasses  # noqa: PLC0415

        self.assertEqual({f.name for f in dataclasses.fields(BenchmarkSelection)}, set(store.COLUMNS))
        # what the trigger sets and the caller cannot: the sequence, the clock stamp and the transaction id
        self.assertEqual(table_columns - set(store.COLUMNS), {"selection_seq", "recorded_at", "append_xid"})

    def test_row_round_trip(self):
        p = uuid.UUID(int=5)
        for s in (select(p), clear(p), reversal(p, new_id()), select(p, "NDX", origin=Origin.RECOMMENDATION_ACCEPTED, corrects_selection_id=new_id())):
            row = (7,) + store.to_row(s)
            back = store.from_row(row)
            self.assertEqual((back.selection_seq, back.selection), (7, s))
            from domain.benchmark_selection import NOT_STATED  # noqa: PLC0415

            self.assertIs(back.atomic_with_seq, NOT_STATED)  # a plain read states no boundary fact: never "appended alone" (CP4M-10 point 6)
            self.assertIsNone(store.from_row(row + (None,)).atomic_with_seq)  # the loader's query states it, here "alone"
            self.assertEqual(store.from_row(row + (9,)).atomic_with_seq, 9)

    def test_the_insert_is_idempotent_by_construction(self):
        self.assertIn("ON CONFLICT DO NOTHING RETURNING selection_seq", store.INSERT_SQL)
        self.assertEqual(store.INSERT_SQL.count("%s"), len(store.COLUMNS))

    def test_the_migration_states_the_rules_the_domain_states(self):
        for needle in ("benchmark_selection_fields_select", "benchmark_selection_fields_clear", "benchmark_selection_fields_reversal", "benchmark_selection_benchmark_id_format",
                       "benchmark_selection_correction_same_transaction", "benchmark_selection_reversal_of_reversal",
                       "benchmark_selection_reversed_once", "benchmark_selection_corrected_once", "benchmark_selection_search_path_pin_stale", "benchmark_selection_append_only",
                       "SET search_path = %I, pg_temp", "pg_advisory_xact_lock", "pg_current_xact_id()"):
            self.assertIn(needle, self.MIGRATION, needle)
        # the id pattern in SQL is the domain's pattern
        self.assertIn("'^" + bs.BENCHMARK_ID_PATTERN.pattern + "$'", self.MIGRATION)
        self.assertIn("'^" + bs.CATALOG_VERSION_PATTERN.pattern + "$'", self.MIGRATION)
        # the sequence is drawn AFTER the lock: the lock statement comes first in the trigger
        self.assertLess(self.MIGRATION.index("pg_advisory_xact_lock"), self.MIGRATION.index("nextval('benchmark_selection_seq_seq')"))
        self.assertNotIn("DEFAULT nextval", self.MIGRATION)  # no default: a value drawn before the lock would break commit order

    def test_the_store_and_the_domain_read_no_clock_and_the_store_imports_no_engine(self):
        src = Path(__file__).resolve().parents[2] / "src"
        for rel in ("persistence/benchmark_selection_store.py", "domain/benchmark_selection.py"):
            text = (src / rel).read_text(encoding="utf-8")
            self.assertNotIn(".now(", text, rel)
            self.assertNotIn(".today(", text, rel)
            roots = set()
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.ImportFrom):
                    roots.add((node.module or "").split(".")[0])
                elif isinstance(node, ast.Import):
                    roots |= {a.name.split(".")[0] for a in node.names}
            self.assertFalse(roots & {"performance", "risk", "marketdata", "time", "random", "secrets", "socket"}, (rel, roots))

    def test_no_application_code_writes_a_selection_but_the_store(self):
        src = Path(__file__).resolve().parents[2] / "src"
        for path in sorted(src.rglob("*.py")):
            if path.name == "benchmark_selection_store.py":
                continue
            self.assertNotIn("INTO benchmark_selection", path.read_text(encoding="utf-8"), str(path))
            self.assertFalse("append_selection" in path.read_text(encoding="utf-8") and path.parts[-2] in ("performance", "risk"), str(path))


@unittest.skipIf(bool(_SKIP), _SKIP)
class BenchmarkSelectionDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg  # noqa: PLC0415

        cls.pg = psycopg
        cls.db = pk.PgSchema(prefix="finweb_it_bs_")
        try:
            cls.db.open()
        except BaseException:  # a failed migration must not leave its disposable schema behind
            if cls.db.owner is not None:
                cls.db.close()
            raise
        cls.addClassCleanup(cls.db.close)
        cls.owner = cls.db.owner
        cls.owner.execute("INSERT INTO app_user VALUES (%s)", (_USER,))
        cls.app = cls.db.app_connection()
        cls.addClassCleanup(cls.app.close)

    # -- helpers ---------------------------------------------------------------------------------------------------------------------------

    def portfolio(self):
        p = new_id()
        self.owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (p, _USER))
        return p

    def append(self, s, conn=None):
        return store.append_selection(conn or self.app, s)

    def refused(self, constraint, action):
        with self.assertRaises(store.SelectionRuleRejectedError) as cm:
            action()
        self.assertEqual(cm.exception.constraint_name, constraint, str(cm.exception))

    def other_connection(self, autocommit=True):
        conn = self.db.app_connection(autocommit=autocommit)
        self.addCleanup(conn.close)
        return conn

    def raw_insert(self, row, conn=None, schema=None):
        cols = list(row)
        (conn or self.app).execute('INSERT INTO %sbenchmark_selection (%s) VALUES (%s)' % ('"%s".' % schema if schema else "", ", ".join(cols), ", ".join(["%s"] * len(cols))),
                                   [row[c] for c in cols])

    def raw(self, s, **extra):
        row = dict(zip(store.COLUMNS, store.to_row(s)))
        row.update(extra)
        return row

    # -- append, idempotency ---------------------------------------------------------------------------------------------------------------

    def test_append_a_selection_and_read_it_back_in_force(self):
        p = self.portfolio()
        s = select(p, "SPX")
        r = self.append(s)
        self.assertTrue(r.created)
        self.assertGreater(r.selection_seq, 0)
        self.assertEqual(store.get_selection(self.app, s.selection_id).selection, s)
        in_force = store.selection_in_force(self.app, p)
        self.assertEqual((in_force.state, in_force.version, in_force.row.selection), (SelectionState.IN_FORCE, r.selection_seq, s))

    def test_the_catalog_check_stores_the_catalog_version_and_refuses_a_non_entry_before_anything_is_written(self):
        from domain.catalogs import BenchmarkNotInCatalogError, parse_benchmark_catalog  # noqa: PLC0415
        import json  # noqa: PLC0415

        row = {"benchmark_id": "SPX", "name": "n", "provider": "p", "source_id": "s", "licensing": "l", "currency": "USD", "return_basis": "TOTAL_RETURN_GROSS", "dividend_treatment": "d",
               "calendar_id": "C", "series_form": "LEVELS", "proxy_of": None, "synthetic": False}
        cat = parse_benchmark_catalog(json.dumps({"catalog_id": "bench:7", "entries": [row]}).encode())
        p = self.portfolio()
        s = select(p, "SPX")
        stored = store.append_selection(self.app, s, catalog=cat)
        self.assertEqual(stored.selection.catalog_version, "bench:7")
        self.assertEqual(store.get_selection(self.app, s.selection_id).selection.catalog_version, "bench:7")
        self.assertEqual(store.selection_pin(self.app, p).catalog_version, "bench:7")  # the pin names the catalog the choice was admitted under
        again = store.append_selection(self.app, s, catalog=cat)  # a resubmission is still a no-op
        self.assertEqual((again.created, again.selection_seq), (False, stored.selection_seq))
        with self.assertRaises(BenchmarkNotInCatalogError):
            store.append_selection(self.app, select(p, "NOT_IN_CATALOG"), catalog=cat)
        self.assertEqual(len(store.load_selections(self.app, p, 10**12)), 1)  # nothing was written
        # a correction's replacement is checked too, and the pair is not half-written
        rev = reversal(p, s.selection_id)
        with self.assertRaises(BenchmarkNotInCatalogError):
            store.append_correction(self.app, rev, select(p, "NOT_IN_CATALOG", corrects_selection_id=s.selection_id), catalog=cat)
        self.assertEqual(len(store.load_selections(self.app, p, 10**12)), 1)
        ok = store.append_correction(self.app, reversal(p, s.selection_id), select(p, "SPX", corrects_selection_id=s.selection_id), catalog=cat)
        self.assertEqual(ok.replacement.selection.catalog_version, "bench:7")
        # a CLEAR needs no entry
        self.assertTrue(store.append_selection(self.app, clear(p), catalog=cat).created)

    def test_an_empty_portfolio_has_no_selection_and_version_zero(self):
        p = self.portfolio()
        self.assertEqual(store.current_selection_version(self.app, p), 0)
        self.assertEqual(store.selection_in_force(self.app, p).state, SelectionState.NONE)
        self.assertEqual(store.selection_pin(self.app, p).state, "NONE")

    def test_resubmission_with_the_same_content_is_a_no_op_returning_the_stored_row(self):
        p = self.portfolio()
        s = select(p)
        first = self.append(s)
        again = self.append(s)
        self.assertFalse(again.created)
        self.assertEqual((again.selection_seq, again.selection), (first.selection_seq, s))
        self.assertEqual(len(store.load_selections(self.app, p, 10**12)), 1)

    def test_the_same_id_with_different_content_is_refused(self):
        p = self.portfolio()
        s = select(p, "SPX")
        self.append(s)
        clash = BenchmarkSelection(s.selection_id, p, RecordType.SELECT, s.selected_on, "NDX", None, Origin.USER_CHOSEN)
        with self.assertRaises(store.DuplicateSelectionIdError):
            self.append(clash)

    def test_sequence_numbers_increase_and_a_resubmission_leaves_a_gap(self):
        p = self.portfolio()
        a = self.append(select(p, on=D(2026, 1, 5)))
        s = select(p, "NDX", on=D(2026, 1, 6))
        b = self.append(s)
        self.append(s)  # a no-op that consumes a sequence value
        c = self.append(select(p, "CSI", on=D(2026, 1, 7)))
        self.assertLess(a.selection_seq, b.selection_seq)
        self.assertGreater(c.selection_seq, b.selection_seq + 1)

    def test_resubmission_after_the_state_moved_on_is_still_a_no_op(self):
        # the CP1B-2 case: the old row is resubmitted after a newer one and after its own reversal; the rules for NEW rows (ordering, same transaction) must not apply to a row that will not be written
        p = self.portfolio()
        first = select(p, "SPX", on=D(2026, 1, 5))
        stored = self.append(first)
        self.append(select(p, "NDX", on=D(2026, 2, 1)))
        again = self.append(first)
        self.assertEqual((again.created, again.selection_seq), (False, stored.selection_seq))
        rev = reversal(p, first.selection_id, D(2026, 3, 1))
        self.append(rev)
        self.assertFalse(self.append(rev).created)
        self.assertFalse(self.append(first).created)
        self.assertEqual(len(store.load_selections(self.app, p, 10**12)), 3)

    def test_a_replacement_resubmitted_in_a_later_transaction_is_still_a_no_op(self):
        # the rule that a replacement's reversal must be THIS transaction's applies to a new row only: a resubmission of a stored replacement, long after its transaction, must be recognised first and
        # change nothing (without the early return the same-transaction rule would refuse it). Under risk/1.1 Ruling 5.6 (1.1) there is no ordering rule left that could show this for a plain record.
        p = self.portfolio()
        original = select(p, "SPX", on=D(2026, 1, 5))
        self.append(original)
        rev, replacement = reversal(p, original.selection_id, D(2026, 2, 1)), select(p, "NDX", on=D(2026, 2, 1), corrects_selection_id=original.selection_id)
        done = store.append_correction(self.app, rev, replacement)
        self.append(select(p, "CSI", on=D(2026, 3, 1)))  # the state moves on
        again = self.append(replacement)
        self.assertEqual((again.created, again.selection_seq), (False, done.replacement.selection_seq))
        self.assertFalse(store.append_correction(self.app, rev, replacement).replacement.created)  # and the whole pair
        self.assertEqual(len(store.load_selections(self.app, p, 10**12)), 4)

    def test_an_unknown_portfolio_is_refused_on_write_and_on_read(self):
        ghost = new_id()
        with self.assertRaises(store.SelectionRuleRejectedError) as cm:
            self.append(select(ghost))
        self.assertEqual(cm.exception.constraint_name, "benchmark_selection_portfolio_id_fkey")
        for read in (store.current_selection_version, store.selection_in_force, store.selection_pin):
            with self.assertRaises(PortfolioNotFoundError):
                read(self.app, ghost)

    # -- the database enforces what the domain states --------------------------------------------------------------------------------------

    def test_the_database_and_the_domain_agree_on_every_field_combination(self):
        """Differential: for every record type and every presence mask of the five optional fields, the domain constructor and the database accept exactly the same rows. A target row (and its reversal,
        for a correction) is built in the same transaction so that a combination the domain allows is satisfiable in the database."""
        values = {"benchmark_id": "SPX", "catalog_version": "v1", "origin": "USER_CHOSEN"}
        accepted_by_both = refused_by_both = 0
        for record_type in RecordType:
            for mask in __import__("itertools").product((False, True), repeat=len(bs.FIELDS)):
                present = {f for f, on in zip(bs.FIELDS, mask) if on}
                p = self.portfolio()
                target = select(p, "SPX", on=D(2026, 1, 1))
                kwargs = {f: values[f] if f in values else None for f in present}
                db_row = {"selection_id": new_id(), "portfolio_id": p, "record_type": record_type.value, "selected_on": D(2026, 1, 5)}
                db_row.update({f: values[f] for f in present if f in values})
                if "reverses_selection_id" in present:
                    db_row["reverses_selection_id"] = target.selection_id
                if "corrects_selection_id" in present:
                    db_row["corrects_selection_id"] = target.selection_id
                try:
                    BenchmarkSelection(db_row["selection_id"], p, record_type, D(2026, 1, 5),
                                       benchmark_id=db_row.get("benchmark_id"), catalog_version=db_row.get("catalog_version"),
                                       origin=None if "origin" not in db_row else Origin(db_row["origin"]),
                                       reverses_selection_id=db_row.get("reverses_selection_id"), corrects_selection_id=db_row.get("corrects_selection_id"))
                    domain_ok = True
                except bs.BenchmarkSelectionError:
                    domain_ok = False
                try:
                    with self.app.transaction():
                        self.raw_insert(self.raw(target))
                        if "corrects_selection_id" in present and "reverses_selection_id" not in present:
                            self.raw_insert(self.raw(reversal(p, target.selection_id, D(2026, 1, 2))))  # the correction's target must be reversed, in the same transaction
                        self.raw_insert(db_row)
                    db_ok = True
                except self.pg.Error:
                    db_ok = False
                self.assertEqual(db_ok, domain_ok, (record_type.value, sorted(present)))
                accepted_by_both += db_ok
                refused_by_both += not db_ok
        self.assertEqual(accepted_by_both + refused_by_both, 96)
        self.assertGreaterEqual(accepted_by_both, 6)

    def test_benchmark_id_and_catalog_version_formats_are_enforced_by_the_database(self):
        p = self.portfolio()
        for bad in ("", " SPX", "SPX\n", "A" * 65, ".SPX", "标普", "S P"):
            self.assertRaises(self.pg.errors.CheckViolation, self.raw_insert, self.raw(select(p), benchmark_id=bad))
        for ok in ("SPX", "A" * 64, "MSCI.ACWI", "csi-300", "x:y_z"):
            self.raw_insert(self.raw(select(p, on=D(2026, 1, 5)), benchmark_id=ok, selection_id=new_id()))
        for bad in ("", "v 1", "v1\n", "B" * 65):
            self.assertRaises(self.pg.errors.CheckViolation, self.raw_insert, self.raw(select(p), catalog_version=bad))
        self.raw_insert(self.raw(select(p), catalog_version="cat-1.0+x", selection_id=new_id()))

    def test_the_date_is_bounded_so_every_stored_row_can_be_read_back(self):
        p = self.portfolio()
        for bad in ("infinity", "-infinity", "10000-01-01"):
            self.assertRaises(self.pg.errors.CheckViolation, self.raw_insert, self.raw(select(p), selected_on=bad))
        self.raw_insert(self.raw(select(p), selected_on=D(1, 1, 1), selection_id=new_id()))
        self.raw_insert(self.raw(select(p), selected_on=D(9999, 12, 31), selection_id=new_id()))
        self.assertEqual(len(store.load_selections(self.app, p, 10**12)), 2)

    def test_the_caller_cannot_choose_the_sequence_the_clock_or_the_transaction_id(self):
        p = self.portfolio()
        s = select(p)
        self.raw_insert(self.raw(s, selection_seq=5, recorded_at="1999-01-01T00:00:00Z", append_xid="1"))
        row = self.owner.execute("SELECT selection_seq, recorded_at, append_xid::text, append_xid = pg_current_xact_id() FROM benchmark_selection WHERE selection_id = %s", (s.selection_id,)).fetchone()
        self.assertNotEqual(row[0], 5)
        self.assertGreater(row[1].year, 2000)
        self.assertNotEqual(row[2], "1")

    def test_non_read_committed_appends_are_refused(self):
        p = self.portfolio()
        conn = self.db.app_connection(autocommit=False)
        self.addCleanup(conn.close)
        conn.isolation_level = self.pg.IsolationLevel.REPEATABLE_READ
        self.refused("benchmark_selection_requires_read_committed", lambda: self.append(select(p), conn))

    # -- ordering, reversal, correction ----------------------------------------------------------------------------------------------------

    def test_the_log_is_ordered_by_sequence_alone_the_date_is_only_data(self):
        # risk/1.1 Ruling 5.6 (1.1): the LATEST record up to the version is in force. A record dated earlier than the previous one is stored as it was made and, being appended later, is the latest.
        p = self.portfolio()
        self.append(select(p, "SPX", on=D(2026, 2, 1)))
        self.append(select(p, "NDX", on=D(2026, 1, 31)))   # back-dated: accepted, and NOT placed behind the earlier row by its date
        self.assertEqual(store.selection_in_force(self.app, p).row.selection.benchmark_id, "NDX")
        self.append(clear(p, on=D(2026, 1, 1)))
        self.assertEqual(store.selection_in_force(self.app, p).state, SelectionState.CLEARED)
        self.append(select(p, "CSI", on=D(2026, 3, 1)))
        self.assertEqual(store.selection_in_force(self.app, p).row.selection.benchmark_id, "CSI")

    def test_withdrawing_the_latest_record_leaves_the_latest_of_the_rest_and_portfolios_are_independent(self):
        p, q = self.portfolio(), self.portfolio()
        first = self.append(select(p, "SPX", on=D(2026, 1, 5))).selection
        late = self.append(select(p, "NDX", on=D(2026, 6, 1))).selection
        self.append(select(q, "CSI", on=D(2026, 1, 1)))                                  # another portfolio: unaffected
        self.append(reversal(p, late.selection_id, D(2026, 6, 2)))                      # the latest record is withdrawn as an error
        self.assertEqual(store.selection_in_force(self.app, p).row.selection.selection_id, first.selection_id)
        self.assertEqual(store.selection_in_force(self.app, q).row.selection.benchmark_id, "CSI")

    def test_a_reversal_cannot_be_reversed_and_a_row_is_reversed_once(self):
        p = self.portfolio()
        s = self.append(select(p)).selection
        rev = self.append(reversal(p, s.selection_id)).selection
        self.refused("benchmark_selection_reversal_of_reversal", lambda: self.append(reversal(p, rev.selection_id)))
        self.refused("benchmark_selection_reversed_once", lambda: self.append(reversal(p, s.selection_id)))

    def test_a_reversal_must_name_a_row_of_the_same_portfolio(self):
        p, q = self.portfolio(), self.portfolio()
        s = self.append(select(p)).selection
        self.refused("benchmark_selection_reversal_target_fk", lambda: self.append(reversal(q, s.selection_id)))
        self.refused("benchmark_selection_reversal_target_fk", lambda: self.append(reversal(p, new_id())))

    def test_a_correction_is_a_reversal_and_a_replacement_in_one_transaction(self):
        p = self.portfolio()
        old = self.append(select(p, "SPX", on=D(2026, 1, 5))).selection
        rev = reversal(p, old.selection_id, D(2026, 1, 5))
        rep = select(p, "NDX", on=D(2026, 1, 5), corrects_selection_id=old.selection_id)
        out = store.append_correction(self.app, rev, rep)
        self.assertLess(out.reversal.selection_seq, out.replacement.selection_seq)
        self.assertEqual(store.selection_in_force(self.app, p).row.selection.benchmark_id, "NDX")

    def test_a_replacement_needs_a_reversed_target_and_the_same_transaction(self):
        p = self.portfolio()
        old = self.append(select(p, "SPX")).selection
        self.refused("benchmark_selection_corrects_reversed", lambda: self.append(select(p, "NDX", corrects_selection_id=old.selection_id)))
        self.append(reversal(p, old.selection_id))  # reversed by an EARLIER transaction
        self.refused("benchmark_selection_correction_same_transaction", lambda: self.append(select(p, "NDX", corrects_selection_id=old.selection_id)))

    def test_a_reversal_cannot_carry_a_correction_link_even_when_the_trigger_would_allow_it(self):
        # T is reversed by R1 in the transaction, so `corrects T` passes the trigger's checks; the row is a REVERSAL of T2, and only the field rule refuses it
        p = self.portfolio()
        t, t2 = self.append(select(p, "SPX", on=D(2026, 1, 1))).selection, self.append(select(p, "NDX", on=D(2026, 1, 2))).selection
        with self.assertRaises(self.pg.errors.CheckViolation) as cm:
            with self.app.transaction():
                self.raw_insert(self.raw(reversal(p, t.selection_id)))
                self.raw_insert(self.raw(reversal(p, t2.selection_id), corrects_selection_id=t.selection_id))
        self.assertEqual(cm.exception.diag.constraint_name, "benchmark_selection_fields_reversal")

    def test_a_row_is_corrected_at_most_once(self):
        p = self.portfolio()
        old = self.append(select(p, "SPX")).selection
        with self.app.transaction():  # one transaction, so the reversal is "its own": the second replacement can only be refused for being the second
            store.append_correction(self.app, reversal(p, old.selection_id), select(p, "NDX", corrects_selection_id=old.selection_id))
            self.refused("benchmark_selection_corrected_once", lambda: self.append(select(p, "CSI", corrects_selection_id=old.selection_id)))
        self.assertEqual(store.selection_in_force(self.app, p).row.selection.benchmark_id, "NDX")  # the first replacement committed, the second never existed

    def test_a_correction_that_fails_midway_leaves_neither_row(self):
        p = self.portfolio()
        old = self.append(select(p, "SPX")).selection
        taken = self.append(select(p, "SPX", on=D(2026, 1, 6))).selection
        rev = reversal(p, old.selection_id)
        clash = BenchmarkSelection(taken.selection_id, p, RecordType.SELECT, D(2026, 1, 5), "NDX", None, Origin.USER_CHOSEN, corrects_selection_id=old.selection_id)
        with self.assertRaises(store.DuplicateSelectionIdError):
            store.append_correction(self.app, rev, clash)
        self.assertIsNone(store.get_selection(self.app, rev.selection_id))  # the reversal rolled back with the failed replacement
        self.assertEqual(store.selection_in_force(self.app, p).row.selection.selection_id, taken.selection_id)

    def test_a_replacement_takes_the_position_of_the_record_it_corrects(self):
        # risk/1.4 Ruling 5.6 (1.4) (CP4M-4, R13-V8): correcting an OLD, superseded record does not override the user's later choice
        p = self.portfolio()
        old = self.append(select(p, "SPX", on=D(2026, 1, 5))).selection
        later_row = self.append(select(p, "NDX", on=D(2026, 2, 1)))
        later = later_row.selection
        out = store.append_correction(self.app, reversal(p, old.selection_id), select(p, "CSI", on=D(2026, 1, 5), corrects_selection_id=old.selection_id))
        in_force = store.selection_in_force(self.app, p)
        self.assertEqual((in_force.row.selection.selection_id, in_force.state), (later.selection_id, SelectionState.IN_FORCE))
        self.assertGreater(out.replacement.selection_seq, in_force.row.selection_seq)  # the replacement was appended last and is NOT in force
        # correcting the LATEST record puts the replacement in force (R13-V10), and the pin records its position
        out2 = store.append_correction(self.app, reversal(p, later.selection_id), select(p, "CSI2", on=D(2026, 2, 1), corrects_selection_id=later.selection_id))
        now = store.selection_in_force(self.app, p)
        self.assertEqual((now.row.selection.selection_id, now.position), (out2.replacement.selection.selection_id, later_row.selection_seq))
        pin = store.selection_pin(self.app, p)
        self.assertEqual((pin.selection_seq, pin.position), (out2.replacement.selection_seq, later_row.selection_seq))

    def test_the_quants_r13_log_resolves_at_every_version_through_the_database(self):
        # cp4_golden/1.2-part3, portfolio R13: 1 SELECT US, 2 SELECT CN, 3 REVERSAL of 2, 4 CLEAR, 5 REVERSAL of 4, 6 SELECT CN, 7+8 REVERSAL of 1 replaced by the ETF proxy, 9+10 REVERSAL of 6 replaced by the
        # two-source US index. The database numbers its own sequence, so the fixture's seq is mapped to the stored one.
        p = self.portfolio()
        stored = {}
        stored[1] = self.append(select(p, "US", on=D(2025, 1, 2)))
        stored[2] = self.append(select(p, "CN", on=D(2025, 2, 3)))
        stored[3] = self.append(reversal(p, stored[2].selection.selection_id, D(2025, 2, 4)))
        stored[4] = self.append(clear(p, on=D(2025, 3, 3)))
        stored[5] = self.append(reversal(p, stored[4].selection.selection_id, D(2025, 3, 4)))
        stored[6] = self.append(select(p, "CN", on=D(2025, 4, 1)))
        pair1 = store.append_correction(self.app, reversal(p, stored[1].selection.selection_id, D(2025, 5, 2)), select(p, "ETF", on=D(2025, 5, 2), corrects_selection_id=stored[1].selection.selection_id))
        stored[7], stored[8] = pair1.reversal, pair1.replacement
        pair2 = store.append_correction(self.app, reversal(p, stored[6].selection.selection_id, D(2025, 6, 2)), select(p, "US2", on=D(2025, 6, 2), corrects_selection_id=stored[6].selection.selection_id))
        stored[9], stored[10] = pair2.reversal, pair2.replacement
        want = {2: ("IN_FORCE", 2), 3: ("IN_FORCE", 1), 4: ("CLEARED", 4), 5: ("IN_FORCE", 1), 8: ("IN_FORCE", 6), 10: ("IN_FORCE", 10)}
        for fixture_version, (state, fixture_seq) in want.items():
            in_force = store.selection_in_force(self.app, p, stored[fixture_version].selection_seq)
            self.assertEqual((in_force.state.value, in_force.row.selection_seq), (state, stored[fixture_seq].selection_seq), fixture_version)
        # version 7 holds the reversal of a correction pair without its replacement: refused
        with self.assertRaises(store.SelectionVersionNotABoundaryError):
            store.selection_in_force(self.app, p, stored[7].selection_seq)
        with self.assertRaises(store.SelectionVersionNotABoundaryError):
            store.selection_in_force(self.app, p, stored[9].selection_seq)
        # CP4M-9: ONE error type and ONE check. `load_selections` states each row's same-transaction partner, so exactly what it returns for version 9 (nothing above it) is refused by the domain with the
        # same class `selection_in_force` raises, and a boundary resolves the same from the truncated rows as through the store
        from domain.benchmark_selection import SelectionVersionNotPinnableError, resolve_selection  # noqa: PLC0415

        self.assertIs(store.SelectionVersionNotABoundaryError, SelectionVersionNotPinnableError)
        for cut, partner in ((7, 8), (9, 10)):
            rows = store.load_selections(self.app, p, stored[cut].selection_seq)
            self.assertEqual((rows[-1].selection_seq, rows[-1].atomic_with_seq), (stored[cut].selection_seq, stored[partner].selection_seq))
            with self.assertRaises(SelectionVersionNotPinnableError):
                resolve_selection(p, rows, stored[cut].selection_seq)
        for ok in (8, 10, 6, 4):
            rows = store.load_selections(self.app, p, stored[ok].selection_seq)
            self.assertEqual(resolve_selection(p, rows, stored[ok].selection_seq).row.selection_seq, store.selection_in_force(self.app, p, stored[ok].selection_seq).row.selection_seq)
        self.assertIsNone(store.load_selections(self.app, p, stored[6].selection_seq)[-1].atomic_with_seq)  # a row appended alone has no partner
        # a reversal of the reversal is refused at append (a change of mind is a new SELECT)
        with self.assertRaises(store.SelectionRuleRejectedError):
            self.append(reversal(p, stored[3].selection.selection_id))

    # -- the version, the pin and UAT-03 ---------------------------------------------------------------------------------------------------

    def test_the_pin_changes_whenever_the_selection_changes_and_old_versions_stay_reproducible(self):
        p = self.portfolio()
        a = self.append(select(p, "SPX", on=D(2026, 1, 5)))
        pin_a = store.selection_pin(self.app, p)
        b = self.append(select(p, "NDX", on=D(2026, 2, 1)))
        pin_b = store.selection_pin(self.app, p)
        c = self.append(reversal(p, b.selection.selection_id, D(2026, 2, 2)))
        pin_c = store.selection_pin(self.app, p)
        d = self.append(clear(p, D(2026, 3, 1)))
        pin_d = store.selection_pin(self.app, p)
        digests = [x.digest for x in (pin_a, pin_b, pin_c, pin_d)]
        self.assertEqual(len(set(digests)), 4)
        self.assertEqual([x.benchmark_id for x in (pin_a, pin_b, pin_c, pin_d)], ["SPX", "NDX", "SPX", None])
        self.assertEqual([x.state for x in (pin_a, pin_b, pin_c, pin_d)], ["IN_FORCE", "IN_FORCE", "IN_FORCE", "CLEARED"])
        self.assertEqual([x.version for x in (pin_a, pin_b, pin_c, pin_d)], [a.selection_seq, b.selection_seq, c.selection_seq, d.selection_seq])
        # reversing back restores the SPX ROW, not the version
        self.assertEqual(pin_c.row_digest, pin_a.row_digest)
        # a pinned old version still reproduces its own pin after everything that followed
        for version, expected in ((a.selection_seq, pin_a), (b.selection_seq, pin_b), (c.selection_seq, pin_c), (d.selection_seq, pin_d)):
            self.assertEqual(store.selection_pin(self.app, p, version), expected)
        self.assertEqual(store.selection_pin(self.app, p, 0).state, "NONE")

    def test_two_portfolios_do_not_affect_each_other(self):
        p, q = self.portfolio(), self.portfolio()
        self.append(select(p, "SPX"))
        before = store.selection_pin(self.app, p)
        self.append(select(q, "NDX"))
        self.assertEqual(store.selection_pin(self.app, p), before)
        self.assertEqual(store.selection_in_force(self.app, q).row.selection.benchmark_id, "NDX")

    def test_a_version_above_the_current_is_refused_and_a_version_inside_a_correction_is_refused(self):
        p = self.portfolio()
        first = self.append(select(p, "SPX", on=D(2026, 1, 5)))
        out = store.append_correction(self.app, reversal(p, first.selection.selection_id), select(p, "NDX", on=D(2026, 1, 5), corrects_selection_id=first.selection.selection_id))
        with self.assertRaises(store.SelectionVersionNotCommittedError):
            store.selection_in_force(self.app, p, out.replacement.selection_seq + 1000)
        # between the reversal and its replacement: no committed state ever showed the withdrawal alone
        self.assertEqual(out.replacement.selection_seq - out.reversal.selection_seq, 1)
        with self.assertRaises(store.SelectionVersionNotABoundaryError):
            store.selection_in_force(self.app, p, out.reversal.selection_seq)
        self.assertEqual(store.selection_in_force(self.app, p, first.selection_seq).row.selection.benchmark_id, "SPX")  # the version before the whole append is a boundary
        self.assertEqual(store.selection_in_force(self.app, p, out.replacement.selection_seq).row.selection.benchmark_id, "NDX")
        for bad in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                store.selection_in_force(self.app, p, bad)

    # -- concurrency -----------------------------------------------------------------------------------------------------------------------

    def test_appends_to_one_portfolio_serialize_but_other_portfolios_do_not_block(self):
        p, q = self.portfolio(), self.portfolio()
        conn2 = self.other_connection()
        conn2.execute("SET lock_timeout = '300ms'")
        with self.app.transaction():
            held = self.append(select(p, "SPX"))  # holds p's lock until this block commits
            with self.assertRaises(self.pg.Error) as cm:
                self.append(select(p, "NDX", on=D(2026, 2, 1)), conn2)
            self.assertEqual(cm.exception.sqlstate, "55P03")  # lock_not_available: the server bounds the wait, nothing sleeps
            self.append(select(q, "NDX"), conn2)                # another portfolio is not blocked
        after = self.append(select(p, "NDX", on=D(2026, 2, 1)), conn2)  # released at commit
        self.assertGreater(after.selection_seq, held.selection_seq)

    def test_the_lock_is_in_the_schema_namespace(self):
        p = self.portfolio()
        with self.app.transaction():
            self.append(select(p))
            keys = self.owner.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND granted AND pid = %s", (self.app.info.backend_pid,)).fetchone()[0]
            self.assertGreaterEqual(keys, 1)
            # the key is 'finweb.benchmark_selection.portfolio:<schema>:<portfolio>': another session cannot take that key, and can take the same text without the schema
            same = self.owner.execute("SELECT pg_try_advisory_xact_lock(hashtextextended('finweb.benchmark_selection.portfolio:' || %s || ':' || %s, 0))", (self.db.schema, str(p))).fetchone()[0]
            other = self.owner.execute("SELECT pg_try_advisory_xact_lock(hashtextextended('finweb.benchmark_selection.portfolio:' || %s || ':' || %s, 0))", ("some_other_schema", str(p))).fetchone()[0]
            self.assertFalse(same)
            self.assertTrue(other)

    def test_sequence_order_is_commit_order_within_a_portfolio(self):
        p = self.portfolio()
        conn2 = self.other_connection(autocommit=False)
        results = {}

        def append_second():
            results["b"] = store.append_selection(conn2, select(p, "NDX", on=D(2026, 2, 1)))

        with self.app.transaction():
            first = self.append(select(p, "SPX", on=D(2026, 1, 5)))
            t = threading.Thread(target=append_second)
            t.start()
            t.join(timeout=0.5)
            self.assertTrue(t.is_alive(), "the second append must wait for the first transaction's lock")
        t.join(timeout=10)
        self.assertFalse(t.is_alive())
        self.assertGreater(results["b"].selection_seq, first.selection_seq)

    # -- append-only, grants, pins ---------------------------------------------------------------------------------------------------------

    def test_update_delete_truncate_are_refused_for_the_app_role_and_for_the_owner(self):
        p = self.portfolio()
        self.append(select(p))
        for sql in ("UPDATE benchmark_selection SET benchmark_id = benchmark_id", "DELETE FROM benchmark_selection", "TRUNCATE benchmark_selection"):
            with self.assertRaises(self.pg.Error, msg=sql) as cm:
                self.app.execute(sql)
            self.assertEqual(cm.exception.sqlstate, "42501", sql)  # the role holds no such privilege
            with self.assertRaises(self.pg.Error, msg=sql) as cm:
                self.owner.execute(sql)
            self.assertEqual(cm.exception.diag.constraint_name, "benchmark_selection_append_only", sql)  # the trigger refuses the owner too

    def test_the_role_cannot_defeat_the_triggers_or_alter_the_table(self):
        for sql in ("ALTER TABLE benchmark_selection DISABLE TRIGGER ALL", "DROP TRIGGER benchmark_selection_before_insert ON benchmark_selection",
                    "ALTER TABLE benchmark_selection DROP CONSTRAINT benchmark_selection_benchmark_id_format", "DROP TABLE benchmark_selection",
                    "ALTER TABLE benchmark_selection ADD COLUMN extra integer",
                    "CREATE OR REPLACE FUNCTION benchmark_selection_before_insert() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END $$"):
            with self.assertRaises(self.pg.Error, msg=sql) as cm:
                self.app.execute(sql)
            self.assertEqual(cm.exception.sqlstate, "42501", sql)

    def test_the_grants_are_exactly_select_and_insert_and_each_is_load_bearing(self):
        import test_postgres_least_privilege as lp  # noqa: PLC0415

        held = {pr for (t, pr) in lp.table_privileges(self.owner, self.db.schema, self.db.app_role) if t == "benchmark_selection"}
        self.assertEqual(held, {"SELECT", "INSERT"})
        self.assertTrue(self.owner.execute("SELECT has_sequence_privilege(%s, %s, 'USAGE')", (self.db.app_role, '"%s".benchmark_selection_seq_seq' % self.db.schema)).fetchone()[0])
        p = self.portfolio()
        seq = '"%s".benchmark_selection_seq_seq' % self.db.schema
        role = '"%s"' % self.db.app_role
        self.owner.execute("REVOKE USAGE ON SEQUENCE %s FROM %s" % (seq, role))
        try:
            with self.assertRaises(self.pg.Error) as cm:
                self.append(select(p))
            self.assertEqual(cm.exception.sqlstate, "42501")
        finally:
            self.owner.execute("GRANT USAGE ON SEQUENCE %s TO %s" % (seq, role))
        self.assertTrue(self.append(select(p)).created)

    def test_every_function_of_the_migration_is_pinned_to_the_schema(self):
        rows = self.owner.execute("SELECT p.proname, p.proconfig FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = %s AND p.proname LIKE 'benchmark\\_selection\\_%%'",
                                  (self.db.schema,)).fetchall()
        self.assertEqual({r[0] for r in rows}, {"benchmark_selection_reject_mutation", "benchmark_selection_before_insert"})
        for name, config in rows:
            self.assertEqual([c.replace('"', "") for c in (config or [])], ["search_path=%s, pg_temp" % self.db.schema], name)

    # -- TEMP-shadow attacks (the CP1B-1 probes) against the new table ---------------------------------------------------------------------

    def attacker(self, schema=None):
        schema = schema or self.db.schema
        conn = self.db.app_connection()  # as the least-privilege role; it holds TEMPORARY through the PUBLIC default
        self.addCleanup(conn.close)
        conn.execute('SET search_path TO "%s"' % schema)
        conn.execute('CREATE TEMP TABLE benchmark_selection (LIKE "%s".benchmark_selection)' % schema)
        conn.execute("CREATE TEMP SEQUENCE benchmark_selection_seq_seq START 1000000000")
        self.assertEqual(conn.execute("SELECT count(*) FROM benchmark_selection").fetchone()[0], 0)  # the shadow is real: the unqualified name is the empty TEMP table
        return conn

    def test_a_temp_shadow_cannot_reverse_a_row_twice_by_hiding_the_first_reversal(self):
        p = self.portfolio()
        s = self.append(select(p)).selection
        self.append(reversal(p, s.selection_id))
        conn = self.attacker()
        with self.assertRaises(self.pg.errors.UniqueViolation):  # the partial unique index sees the real table whatever the search_path says
            self.raw_insert(self.raw(reversal(p, s.selection_id)), conn, self.db.schema)

    def test_a_temp_shadow_cannot_reverse_a_reversal_or_replace_without_its_reversal(self):
        p = self.portfolio()
        s = self.append(select(p)).selection
        rev = self.append(reversal(p, s.selection_id)).selection
        conn = self.attacker()
        with self.assertRaises(self.pg.errors.CheckViolation) as cm:
            self.raw_insert(self.raw(reversal(p, rev.selection_id)), conn, self.db.schema)
        self.assertEqual(cm.exception.diag.constraint_name, "benchmark_selection_reversal_of_reversal")
        q = self.portfolio()
        t = self.append(select(q)).selection
        with self.assertRaises(self.pg.errors.CheckViolation) as cm:
            self.raw_insert(self.raw(select(q, "NDX", corrects_selection_id=t.selection_id)), conn, self.db.schema)
        self.assertEqual(cm.exception.diag.constraint_name, "benchmark_selection_corrects_reversed")

    def test_a_shadow_sequence_is_ignored_and_the_portfolio_lock_is_still_taken(self):
        p = self.portfolio()
        conn = self.attacker()
        s = select(p)
        with conn.transaction():
            self.raw_insert(self.raw(s, selection_seq=7), conn, self.db.schema)
            held = self.owner.execute("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND granted AND pid = %s", (conn.info.backend_pid,)).fetchone()[0]
            self.assertGreaterEqual(held, 1, "no per-portfolio advisory lock was taken")
        seq = self.owner.execute("SELECT selection_seq FROM benchmark_selection WHERE selection_id = %s", (s.selection_id,)).fetchone()[0]
        self.assertLess(seq, 1_000_000_000)
        self.assertNotEqual(seq, 7)

    def test_control_the_same_attack_succeeds_when_the_functions_are_not_pinned(self):
        """The attack is real and the tests above would fail without the pin: in a scratch schema whose trigger function has lost its pin, the shadow hides the first reversal and a REVERSAL of that reversal is ACCEPTED."""
        scratch = pk.PgSchema(prefix="finweb_it_bsc_").open()
        try:
            scratch.owner.execute("INSERT INTO app_user VALUES (%s)", (_USER,))
            p = self.portfolio_in(scratch)
            for fn in ("benchmark_selection_before_insert()", "benchmark_selection_reject_mutation()"):
                scratch.owner.execute("ALTER FUNCTION %s RESET search_path" % fn)
            app = scratch.app_connection()
            self.addCleanup(app.close)
            first = store.append_selection(app, select(p, "SPX")).selection
            rev = store.append_selection(app, reversal(p, first.selection_id)).selection
            conn = self.attacker(schema=scratch.schema)
            self.raw_insert(self.raw(reversal(p, rev.selection_id)), conn, scratch.schema)
            self.assertEqual(scratch.owner.execute("SELECT count(*) FROM benchmark_selection WHERE portfolio_id = %s AND record_type = 'REVERSAL'", (p,)).fetchone()[0], 2)
        finally:
            scratch.close()

    def portfolio_in(self, scratch):
        p = new_id()
        scratch.owner.execute("INSERT INTO portfolio VALUES (%s, %s, 'USD')", (p, _USER))
        return p

    def test_a_schema_rename_fails_closed_instead_of_reopening_the_bypass(self):
        scratch = pk.PgSchema(prefix="finweb_it_bsr_").open()
        try:
            scratch.owner.execute("INSERT INTO app_user VALUES (%s)", (_USER,))
            p = self.portfolio_in(scratch)
            honest = scratch.app_connection()
            self.addCleanup(honest.close)
            store.append_selection(honest, select(p, "SPX"))  # a row, so the UPDATE below fires the row trigger
            old = scratch.schema
            new = old + "_r"
            scratch.owner.execute('ALTER SCHEMA "%s" RENAME TO "%s"' % (old, new))
            scratch.schema = new
            scratch.owner.execute('SET search_path TO "%s"' % new)
            app = scratch.app_connection()
            self.addCleanup(app.close)
            with self.assertRaises(store.SelectionRuleRejectedError) as cm:
                store.append_selection(app, select(p))
            self.assertEqual(cm.exception.constraint_name, "benchmark_selection_search_path_pin_stale")
            with self.assertRaises(self.pg.Error) as cm2:
                scratch.owner.execute("UPDATE benchmark_selection SET benchmark_id = benchmark_id")
            self.assertEqual(cm2.exception.diag.constraint_name, "benchmark_selection_search_path_pin_stale")
        finally:
            scratch.close()


if __name__ == "__main__":
    unittest.main()
