"""F1 R6: the owner-run identity seed (`real_tools.identity_seed`).

Pure part: the seed file, the digest check that runs before any connection, the command line against a fake connection. PostgreSQL part: the
seed's writes and its idempotence on a TEST install (the owner of a disposable database; E11). The real database is never reached: `main` names
the real install's database and role as constants, and the only connection a test gives it is a fake or refuses.
"""
from __future__ import annotations

import datetime as dt
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import uuid

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from domain.currency import CurrencyCode  # noqa: E402
from domain.instrument import Instrument, Issuer, Listing, SecurityType  # noqa: E402
from marketdata.resolver import IdentifierRow  # noqa: E402
from persistence import real_preflight as pf  # noqa: E402
from persistence.real_digests import identity_digest  # noqa: E402
from real_gateway_kit import GatewayCase, KIT, setUpModule, tearDownModule  # noqa: E402,F401
from real_tools import identity_seed as seed  # noqa: E402


BASE = [0]      # the PostgreSQL tests share one cached install, whose identity tables keep their rows: each test takes its own block of ids


def uid(n):
    return uuid.UUID(int=BASE[0] * 1000 + n)


def resolver(extra_name="Alpha Holdings"):
    issuers = [Issuer(uid(1), extra_name, "US"), Issuer(uid(2), "Beta Group", None)]
    instruments = [Instrument(uid(11), uid(1), SecurityType.COMMON_STOCK, "BBG000AAAAA1"), Instrument(uid(12), uid(2), SecurityType.ETF)]
    listings = [Listing(uid(21), uid(11), "XNYS", "New York", "ALP", CurrencyCode("USD"), "BBG000AAAAA2", True, "BBG000AAAAA3"),
                Listing(uid(22), uid(12), "XHKG", "Hong Kong", "0002", CurrencyCode("HKD"), None, False)]
    rows = [IdentifierRow(uid(21), "TICKER", "ALP", "XNYS", dt.date(2020, 1, 1), None, "invented"), IdentifierRow(uid(22), "TICKER", "0002", "XHKG")]
    return seed.RowsResolver(issuers, instruments, listings, rows)


class SeedFileTests(unittest.TestCase):
    def test_the_seed_file_round_trips_to_the_same_identity_digest(self):
        original = resolver()
        data = seed.seed_bytes(original)
        again = seed.read_seed(data)
        self.assertEqual(identity_digest(again), identity_digest(original))
        self.assertEqual(seed.seed_bytes(again), data)

    def test_the_seed_bytes_do_not_depend_on_the_order_of_the_rows(self):
        a = resolver()
        i, n, l = a.snapshot()
        b = seed.RowsResolver(reversed(i), reversed(n), reversed(l), reversed(a.identifier_rows()))
        self.assertEqual(seed.seed_bytes(a), seed.seed_bytes(b))

    def test_a_changed_row_changes_the_digest_and_the_check_refuses(self):
        expected = identity_digest(resolver())
        self.assertEqual(seed.check_digest(resolver(), expected), expected)
        with self.assertRaises(seed.SeedError) as context:
            seed.check_digest(resolver("Alpha Holdings Ltd"), expected)
        self.assertEqual(context.exception.code, "RW_SEED_DIGEST_DIFFERS")

    def test_malformed_seed_files_are_a_shape_refusal(self):
        good = seed.seed_bytes(resolver()).decode()
        for bad in (b"", b"not json", b"[]", b'{"schema":"other"}', good.replace("real_identity_seed/1", "real_identity_seed/2").encode(),
                    good.replace('"identifiers"', '"extra"').encode(), b"\xff\xfe", good.replace(str(uid(1)), "not-a-uuid").encode()):
            with self.assertRaises(seed.SeedError) as context:
                seed.read_seed(bad)
            self.assertEqual(context.exception.code, "RW_SEED_SHAPE", bad[:40])


class FakeResult:
    def __init__(self, row, rows=()):
        self.row, self.rows = row, rows

    def fetchone(self):
        return self.row

    def fetchall(self):
        return list(self.rows)


class FakeSeedConnection:
    """Answers the seed's statements as empty tables would (every insert is new), reads back what was inserted, and records every statement.
    `corrupt` (table name) makes the read-back return that table's rows with another value in the last column."""

    def __init__(self, corrupt=None):
        self.statements, self.closed, self.corrupt, self.tables = [], False, corrupt, {}

    def execute(self, statement, params=()):
        self.statements.append(statement)
        if "RETURNING 1" in statement:
            table = statement.split(".", 1)[1].split(" ", 1)[0]
            self.tables.setdefault(table, []).append(tuple(params))
            return FakeResult((1,))
        if "= ANY(" in statement:
            table = statement.split(" FROM ", 1)[1].split(".", 1)[1].split(" ", 1)[0]
            rows = self.tables.get(table, [])
            if table == self.corrupt:
                rows = [row[:-1] + ("tampered",) for row in rows]
            return FakeResult(None, rows)
        if "count(*)" in statement:
            return FakeResult((len(self.tables.get(statement.split(".", 1)[1].rstrip('"'), [])),))
        return FakeResult(None)

    def transaction(self):
        return mock.MagicMock()

    def close(self):
        self.closed = True


class ReadBackTests(unittest.TestCase):
    """The rows are READ BACK after the writes, inside the same transaction, and compared with the seed on the stored columns."""

    def test_the_inserted_rows_are_read_back_for_each_table(self):
        connection = FakeSeedConnection()
        res = resolver()
        result = seed.apply_seed(connection, "finweb", res, identity_digest(res))
        self.assertEqual(result.inserted, {"issuer": 2, "instrument": 2, "listing": 2})
        reads = [s for s in connection.statements if "= ANY(" in s]
        self.assertEqual(len(reads), 3)
        self.assertTrue(all(s.startswith("SELECT") for s in reads))
        last_insert = max(i for i, s in enumerate(connection.statements) if "INSERT INTO" in s)
        self.assertGreater(connection.statements.index(reads[0]), connection.statements.index(next(s for s in connection.statements if "INSERT INTO" in s)))
        self.assertLess(connection.statements.index(reads[-1]), len(connection.statements))
        self.assertGreater(last_insert, 0)

    def test_a_row_that_reads_back_with_another_value_refuses_the_whole_seed(self):
        for table in ("issuer", "instrument", "listing"):
            res = resolver()
            with self.assertRaises(seed.SeedError, msg=table) as context:
                seed.apply_seed(FakeSeedConnection(corrupt=table), "finweb", res, identity_digest(res))
            self.assertEqual(context.exception.code, "RW_SEED_CONFLICT")
            self.assertIn("read back", str(context.exception))


class CommandLineTests(unittest.TestCase):
    def files(self, tmp, data=None):
        seed_file, proposal = Path(tmp, "seed.json"), Path(tmp, "proposal.json")
        seed_file.write_bytes(seed.seed_bytes(resolver()) if data is None else data)
        proposal.write_bytes(b"proposal bytes stand in; the digest read is patched")
        return ["--socket", "/nonexistent/.s.PGSQL.1", "--user", "superuser", "--seed-file", str(seed_file), "--proposal", str(proposal)]

    def run_main(self, argv, *, digest, connect):
        out = io.StringIO()
        with mock.patch.object(seed, "snapshot_identity_digest", return_value=digest):
            status = seed.main(argv, prompt=lambda role: self.fail("a password was asked for"), out=out, connect=connect)
        return status, out.getvalue()

    def test_a_matching_digest_connects_to_the_real_database_as_the_owner_role_and_writes_once(self):
        connection, opened = FakeSeedConnection(), []

        def connect(socket, database, user):
            opened.append((database, user))
            return connection
        with tempfile.TemporaryDirectory() as tmp:
            status, text = self.run_main(self.files(tmp), digest=identity_digest(resolver()), connect=connect)
        self.assertEqual(status, seed.EXIT_OK, text)
        self.assertEqual(opened, [(pf.REAL_DATABASE, "superuser")])
        self.assertEqual(connection.statements[0], 'SET ROLE "%s"' % pf.REAL_ROLES["owner"])
        self.assertEqual(sum("INSERT INTO" in s for s in connection.statements), 6)
        self.assertTrue(connection.closed)
        self.assertIn("issuer: 2 written", text)

    def test_a_digest_that_differs_refuses_before_any_connection(self):
        def connect(*args):
            raise AssertionError("a connection was opened")
        with tempfile.TemporaryDirectory() as tmp:
            status, text = self.run_main(self.files(tmp), digest="0" * 64, connect=connect)
        self.assertEqual(status, seed.EXIT_REFUSED)
        self.assertIn("RW_SEED_DIGEST_DIFFERS", text)
        self.assertIn("Nothing was written", text)

    def test_a_missing_or_malformed_file_refuses_before_any_connection(self):
        def connect(*args):
            raise AssertionError("a connection was opened")
        with tempfile.TemporaryDirectory() as tmp:
            argv = self.files(tmp, data=b"{}")
            status, text = self.run_main(argv, digest="0" * 64, connect=connect)
            self.assertEqual((status, "RW_SEED_SHAPE" in text), (seed.EXIT_REFUSED, True), text)
            argv[argv.index("--seed-file") + 1] = str(Path(tmp, "absent.json"))
            status, text = self.run_main(argv, digest="0" * 64, connect=connect)
            self.assertEqual(status, seed.EXIT_REFUSED)

    def test_the_command_line_takes_no_credential_option_and_no_database_option(self):
        parser = seed._build_parser()
        options = {o for action in parser._actions for o in action.option_strings}
        self.assertEqual(options, {"-h", "--help", "--socket", "--user", "--seed-file", "--proposal"})


class SeedOnTestInstall(GatewayCase):
    """The owner of a disposable TEST install runs the seed (the real database is never reached)."""
    INSTALL = "seed"
    _blocks = iter(range(1, 10000))

    def setUp(self):
        super().setUp()
        BASE[0] = next(SeedOnTestInstall._blocks)
        self.addCleanup(BASE.__setitem__, 0, 0)

    def apply(self, res=None, digest=None):
        res = res or resolver()
        return seed.apply_seed(self.owner, self.s, res, digest or identity_digest(res))

    def rows(self, table):
        return self.owner.execute("SELECT count(*) FROM %s.%s" % (self.s, table)).fetchone()[0]

    def test_the_seed_writes_the_rows_and_a_second_run_writes_nothing(self):
        base = (self.rows("issuer"), self.rows("instrument"), self.rows("listing"))
        first = self.apply()
        self.assertEqual(first.inserted, {"issuer": 2, "instrument": 2, "listing": 2})
        grown = tuple(b + 2 for b in base)
        self.assertEqual((self.rows("issuer"), self.rows("instrument"), self.rows("listing")), grown)
        second = self.apply()
        self.assertEqual(second.inserted, {"issuer": 0, "instrument": 0, "listing": 0})
        self.assertEqual(second.present, {"issuer": 2, "instrument": 2, "listing": 2})
        self.assertEqual(second.others, {"issuer": base[0], "instrument": base[1], "listing": base[2]})
        self.assertEqual((self.rows("issuer"), self.rows("instrument"), self.rows("listing")), grown)
        stored = self.owner.execute("SELECT trading_currency,figi,is_active FROM %s.listing WHERE listing_id=%%s" % self.s, (uid(21),)).fetchone()
        self.assertEqual(stored, ("USD", "BBG000AAAAA2", True))

    def test_a_different_existing_row_refuses_the_whole_seed_and_writes_nothing_new(self):
        self.apply()
        changed = resolver("Alpha Holdings Ltd")
        with self.assertRaises(seed.SeedError) as context:
            self.apply(changed)
        self.assertEqual(context.exception.code, "RW_SEED_CONFLICT")
        self.assertEqual(self.owner.execute("SELECT name FROM %s.issuer WHERE issuer_id=%%s" % self.s, (uid(1),)).fetchone()[0], "Alpha Holdings")

    def test_a_conflict_rolls_back_the_rows_of_the_same_run(self):
        self.apply()
        res = resolver("Alpha Holdings Ltd")
        i, n, l = res.snapshot()
        extra = seed.RowsResolver(list(i) + [Issuer(uid(3), "Gamma", None)], n, l, res.identifier_rows())
        before = self.rows("issuer")
        with self.assertRaises(seed.SeedError):
            self.apply(extra)
        self.assertEqual(self.rows("issuer"), before)

    def test_a_wrong_digest_writes_nothing(self):
        before = (self.rows("issuer"), self.rows("instrument"), self.rows("listing"))
        with self.assertRaises(seed.SeedError) as context:
            self.apply(digest="0" * 64)
        self.assertEqual(context.exception.code, "RW_SEED_DIGEST_DIFFERS")
        self.assertEqual((self.rows("issuer"), self.rows("instrument"), self.rows("listing")), before)

    def test_the_executor_has_no_grant_on_the_identity_tables_and_the_loader_and_publisher_have_none_either(self):
        for who in ("executor", "loader", "publisher"):
            for table in ("issuer", "instrument", "listing"):
                for privilege in ("INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                    granted = self.admin.execute("SELECT has_table_privilege(%s, %s, %s)", (self.inst.roles[who], "%s.%s" % (self.s, table), privilege)).fetchone()[0]
                    self.assertFalse(granted, (who, table, privilege))

    def test_a_proposal_of_another_identity_digest_refuses_through_the_real_snapshot_read(self):
        snapshot = self.snapshot()
        expected = seed.snapshot_identity_digest(self.proposal(snapshot))
        self.assertEqual(expected, snapshot.content["identity_digest"])
        with self.assertRaises(seed.SeedError) as context:
            seed.check_digest(resolver(), expected)
        self.assertEqual(context.exception.code, "RW_SEED_DIGEST_DIFFERS")


if __name__ == "__main__":
    unittest.main()
