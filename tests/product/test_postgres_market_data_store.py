"""The PostgreSQL market-data projection (migrations 0009-0011, `persistence.market_data_store`), proved on a real
server. Opt-in, like every database test here:

    FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev \\
    FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app \\
        uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t . \\
        -p 'test_postgres_market_data_store.py' -v

The OWNER role creates disposable `finweb_it_md_*` schemas, migrates them, writes the identity rows and projects
releases; the APP role (`finweb_app`) reads under exactly the production grants. Every schema is dropped at the end and
the cleanup fails loudly if one is left. All data is synthetic.

Expected values are written by hand from the inputs (row counts are counted from the files the worlds write), or are
properties the database must hold (an UPDATE is refused). No expected value is read from the code under test.
"""

import dataclasses
import datetime
import sys
import unittest
import uuid
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402
import pg_market_kit as pk  # noqa: E402

k = x.k
c = x.c

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import SplitRatio  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from marketdata.manifest import DataKind, FileManifest, MarketDataRelease  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.store import BenchmarkEntry, FXFileWindow, RiskFreeEntry, SeriesExclusion, StoreContents  # noqa: E402
from persistence import market_data_store as mds  # noqa: E402

D = datetime.date
_SKIP = pk.skip_reason()


def to_plain(obj):
    """A dataclass-aware plain form for byte comparison (the canonical encoder handles the leaves)."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {"__type__": type(obj).__name__, **{f.name: to_plain(getattr(obj, f.name)) for f in dataclasses.fields(obj)}}
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, (list, tuple)):
        return [to_plain(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(to_plain(v) for v in obj)
    if isinstance(obj, dict):
        return {str(kk): to_plain(v) for kk, v in obj.items()}
    return obj


def dump(obj) -> str:
    return canonical_json(to_plain(obj))


def rich_release(ident):
    """A small release holding ONE of every observation kind, built directly from objects (no file parsing): a quote,
    a rate, a SPLIT, a dividend with an issuer-paid currency, a symbol change, an unsupported action, a benchmark with
    two points, a verification-only adjusted row with per-field bounds, a calendar, an FX window and an exclusion."""
    aapl = x.lid(ident, "AAPL", "XNAS")
    sha = {n: n * 32 for n in ("a1", "b2", "c3", "d4", "e5", "f6", "a7")}  # 64 hex characters each
    shas = tuple(sorted(sha.values()))

    def manifest(name, kind, source):
        return FileManifest(
            file_sha256=sha[name], size_bytes=1, payload_filename=f"{name}.dat", payload_format="rich/1", source_id=source,
            data_kind=kind, retrieval_time=k.NOW, retrieved_by="synthetic", declared_adjustment=c.AdjustmentStatus.RAW,
            usage_scope=c.UsageScope.SYNTHETIC_TEST, market="US")

    manifests = [manifest("a1", DataKind.QUOTE, "rich.q"), manifest("b2", DataKind.FX, "rich.fx"),
                 manifest("c3", DataKind.CORPORATE_ACTION, "rich.feed"), manifest("d4", DataKind.CORPORATE_ACTION, "rich.filing"),
                 manifest("e5", DataKind.BENCHMARK, "rich.bm"), manifest("f6", DataKind.CALENDAR, "calendar.manual"), manifest("a7", DataKind.RISK_FREE, "rich.rf")]
    timing = c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY)
    quote = k.quote_reading(D(2025, 1, 2), "150.2500", volume="1000", source="rich.q", group="rich.q", sha=sha["a1"], listing=aapl)
    fx = k.fx_reading(D(2025, 1, 2), "USD", "1.0800", source="rich.fx", group="rich.fx", sha=sha["b2"])

    def action(name, source, **kw):
        return c.SourceReading(source, source, sha[name], c.CorporateActionObservation(
            aapl, kw.pop("kind"), kw.pop("day"), timing, k.lineage(source, sha[name]), **kw))

    split_feed = action("c3", "rich.feed", kind=c.CorporateActionType.SPLIT, day=D(2025, 2, 3),
                        split_ratio=SplitRatio(Decimal(4), Decimal(1)))
    split_filing = action("d4", "rich.filing", kind=c.CorporateActionType.SPLIT, day=D(2025, 2, 3),
                          split_ratio=SplitRatio(Decimal("4.0"), Decimal("1.0")))
    dividend = action("c3", "rich.feed", kind=c.CorporateActionType.CASH_DIVIDEND, day=D(2025, 3, 3),
                      amount_per_unit=Money(Decimal("0.2500"), k.USD), pay_date=D(2025, 3, 10), record_date=D(2025, 3, 4),
                      paid_currency=k.HKD, issuer_fx_rate=Decimal("0.1280"))
    change = action("c3", "rich.feed", kind=c.CorporateActionType.SYMBOL_CHANGE, day=D(2025, 4, 1),
                    old_ticker="OLD", new_ticker="NEW")
    other = action("c3", "rich.feed", kind=c.CorporateActionType.UNSUPPORTED, day=D(2025, 5, 1),
                   unsupported_label="RIGHTS_ISSUE")
    series = c.BenchmarkSeries(
        "BM1", "synthetic index provider", (c.BenchmarkPoint(D(2025, 1, 2), Decimal("100.0")),
                                            c.BenchmarkPoint(D(2025, 1, 3), Decimal("101.5"))),
        c.BenchmarkValueKind.LEVEL, k.USD, timing, k.lineage("rich.bm", sha["e5"]),
        c.LicensingMetadata(c.LicenseStatus.SYNTHETIC_TEST, False, "synthetic: not licensed"))
    adjusted = c.AdjustedQuote(
        aapl, D(2025, 1, 2), Decimal("142.75"), Decimal("143.75"), Decimal("141.75"), Decimal("142.75"), k.USD,
        c.AdjustmentLabel(c.AdjustmentStatus.DIVIDEND_ADJUSTED, c.AdjustmentMethod.SUBTRACTIVE, c.AnchorKind.LATEST, k.NOW),
        timing, k.lineage("rich.q", sha["a1"], adjustment=c.AdjustmentStatus.DIVIDEND_ADJUSTED), Decimal("0.005"),
        (Decimal("0.00005"), Decimal("0.00005"), Decimal("0.00005")))
    risk_free = c.RiskFreeSeries(
        "RF-USD-13W", "synthetic 13-week bill", "synthetic provider", k.USD, "13-WEEK SYNTHETIC BILL", 13, c.RiskFreeQuoteType.BANK_DISCOUNT, 360, c.RateUnit.PERCENT, 3,
        "the value date is the date the quote is FOR", "RF_PUBLICATIONS", c.RevisionPolicy.NOT_REVISED,
        (c.RiskFreePoint(D(2025, 1, 2), Decimal("4.250"), 91), c.RiskFreePoint(D(2025, 1, 3), Decimal("4.2600"), 91)),
        timing, k.lineage("rich.rf", sha["a7"]), c.LicensingMetadata(c.LicenseStatus.SYNTHETIC_TEST, False, "synthetic: not licensed"))
    contents = StoreContents(
        (quote, fx, split_feed, split_filing, dividend, change, other),
        (BenchmarkEntry("rich.bm", "rich.bm", sha["e5"], series),), (adjusted,),
        ((sha["b2"], FXFileWindow(D(2025, 1, 1), D(2025, 1, 8))),),
        (SeriesExclusion(aapl, sha["a1"], "V0", "2 date(s) are not sessions of NY_TEST"),), True,
        (RiskFreeEntry("rich.rf", "rich.rf", sha["a7"], risk_free),))
    calendar = k.exchange_calendar("NY_TEST", ("XNYS",), [D(2025, 1, 2), D(2025, 1, 3)], covers=(D(2025, 1, 1), D(2025, 1, 31)),
                                   sha=sha["f6"])
    release = MarketDataRelease(name="rich", files=shas, source_precedence=("rich.q", "rich.fx"), created_for="test")
    return release, manifests, contents, CalendarSet([calendar])


# one UPDATE per table that changes nothing observable: the row trigger fires per row, whatever is set
UPDATES = {
    "md_file": "UPDATE md_file SET market = market", "md_release": "UPDATE md_release SET name = name",
    "md_release_file": "UPDATE md_release_file SET ordinal = ordinal", "md_quote": "UPDATE md_quote SET price = price",
    "md_fx_rate": "UPDATE md_fx_rate SET rate = rate", "md_corporate_action": "UPDATE md_corporate_action SET detail = detail",
    "md_benchmark": "UPDATE md_benchmark SET provider = provider", "md_benchmark_point": "UPDATE md_benchmark_point SET value = value",
    "md_adjusted_quote": "UPDATE md_adjusted_quote SET open = open", "md_calendar": "UPDATE md_calendar SET timezone = timezone",
    "md_series_exclusion": "UPDATE md_series_exclusion SET reason = reason",
    "md_risk_free": "UPDATE md_risk_free SET provider = provider", "md_risk_free_point": "UPDATE md_risk_free_point SET rate = rate",
}


@unittest.skipIf(bool(_SKIP), _SKIP)
class MarketDataProjectionDbTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg  # noqa: PLC0415

        cls.pg = psycopg
        cls.db = pk.PgSchema().open(grant=False)  # NO grants yet: the negative control below needs a role with none
        cls.addClassCleanup(cls.db.close)
        cls.owner = cls.db.owner
        cls.ident = x.identity()
        pk.insert_identity(cls.owner, cls.ident)
        cls.app = cls.db.app_connection()
        cls.addClassCleanup(cls.app.close)
        # NEGATIVE CONTROL: with the schema USAGE the role has no table grant yet, so a read is "permission denied"
        usage = pk.grant_statements(cls.db.schema, cls.db.app_role)[0]
        assert usage.startswith("GRANT USAGE ON SCHEMA"), usage
        cls.owner.execute(usage)
        with _Expect(cls.pg.Error) as before:
            cls.app.execute("SELECT count(*) FROM md_release")
        cls.denied_before_grant = before.error.sqlstate
        cls.db.grant()
        cls.worlds = {fl: x.build_world(fl) for fl in x.FLAVOURS}
        for w in cls.worlds.values():
            cls.addClassCleanup(w.close)
        cls.results = {}
        for fl, w in cls.worlds.items():
            cls.results[fl] = mds.write_release(cls.owner, w.release, w.built.manifests, w.store.export(), w.built.calendars)
        cls.rich = rich_release(cls.ident)
        cls.rich_result = mds.write_release(cls.owner, cls.rich[0], cls.rich[1], cls.rich[2], cls.rich[3])

    # -- the grants ---------------------------------------------------------------------------------------------

    def test_negative_control_the_app_role_reads_nothing_until_the_md_grant_and_reads_after_it(self):
        self.assertEqual(self.denied_before_grant, "42501")  # before the grant: permission denied
        self.assertGreaterEqual(self.app.execute("SELECT count(*) FROM md_release").fetchone()[0], 5)  # after it

    def test_the_final_grant_spec_gives_the_app_role_exactly_select_on_the_md_tables_and_nothing_more(self):
        import test_postgres_least_privilege as lp  # noqa: PLC0415

        held = lp.table_privileges(self.owner, self.db.schema, self.db.app_role)
        self.assertEqual(held, lp.EXPECTED_TABLE_PRIVILEGES)
        self.assertEqual({t for t, p in held if t.startswith("md_")}, set(mds.MD_TABLES))
        self.assertEqual({p for t, p in held if t.startswith("md_")}, {"SELECT"})  # never INSERT, UPDATE, DELETE

    def test_the_app_role_cannot_write_to_any_md_table(self):
        for table in mds.MD_TABLES:
            for sql in (f"INSERT INTO {table} SELECT * FROM {table} LIMIT 0", UPDATES[table], f"DELETE FROM {table}",
                        f"TRUNCATE {table}"):
                with self.assertRaises(self.pg.Error, msg=sql) as cm:
                    self.app.execute(sql)
                self.assertEqual(cm.exception.sqlstate, "42501", sql)

    # -- what was projected ---------------------------------------------------------------------------------------

    def test_row_counts_follow_the_files_each_world_wrote(self):
        # every world: 4 calendar files, 3 quote series (AAPL, 0700, 600519) x 2 dates = 6 quotes, EUR -> USD/HKD/CNY x 2
        # fixing dates = 6 rates, 4 calendars, no action, no benchmark, no adjusted row, no exclusion. Files: 4 calendars
        # + 3 quote files + 1 FX file = 8 (the mock world writes one quote file per listing too).
        for fl, result in self.results.items():
            counts = dict(result.row_counts)
            self.assertEqual((counts["md_release"], counts["md_release_file"], counts["md_quote"], counts["md_fx_rate"],
                              counts["md_calendar"]), (1, 8, 6, 6, 4), fl)
            for empty in ("md_corporate_action", "md_benchmark", "md_benchmark_point", "md_adjusted_quote",
                          "md_series_exclusion", "md_risk_free", "md_risk_free_point"):
                self.assertEqual(counts[empty], 0, (fl, empty))
            self.assertTrue(result.created)

    def test_a_rich_release_projects_one_of_every_kind(self):
        counts = dict(self.rich_result.row_counts)
        self.assertEqual([(t, counts[t]) for t in sorted(counts)], [
            ("md_adjusted_quote", 1), ("md_benchmark", 1), ("md_benchmark_point", 2), ("md_calendar", 1),
            ("md_corporate_action", 5), ("md_fx_rate", 1), ("md_quote", 1), ("md_release", 1), ("md_release_file", 7),
            ("md_risk_free", 1), ("md_risk_free_point", 2), ("md_series_exclusion", 1)])

    def test_every_file_is_registered_by_its_hash_with_its_manifest(self):
        w = self.worlds["formats"]
        for m in w.manifests:
            row = self.app.execute("SELECT source_id, data_kind, usage_scope, manifest ->> 'file_sha256' FROM md_file "
                                   "WHERE file_sha256 = %s", (m.file_sha256,)).fetchone()
            self.assertEqual(row, (m.source_id, m.data_kind.value, "SYNTHETIC_TEST", m.file_sha256))
        row = self.app.execute("SELECT convention_set_id, contains_synthetic FROM md_release WHERE release_id = %s",
                               (w.release.release_id,)).fetchone()
        self.assertEqual(row, ("market-data/1.16", True))  # the convention-set id is stored with the release

    def test_listing_id_is_the_key_and_no_observation_table_has_a_ticker_or_figi_column(self):
        cols = self.owner.execute(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = %s AND table_name LIKE 'md\\_%%'",
            (self.db.schema,)).fetchall()
        for table, column in cols:
            for banned in ("ticker", "figi", "vendor"):
                self.assertNotIn(banned, column.lower(), (table, column))
        keyed = {t for t, col in cols if col == "listing_id"}
        self.assertEqual(keyed, {"md_quote", "md_corporate_action", "md_adjusted_quote", "md_series_exclusion"})
        types = dict(self.owner.execute(
            "SELECT table_name, data_type FROM information_schema.columns WHERE table_schema = %s "
            "AND column_name = 'listing_id'", (self.db.schema,)).fetchall())
        self.assertEqual(set(types.values()), {"uuid"})
        # the listing key is a real foreign key to the identity table
        fks = self.owner.execute(
            "SELECT conrelid::regclass::text FROM pg_constraint WHERE contype = 'f' AND confrelid = %s::regclass",
            ('"%s".listing' % self.db.schema,)).fetchall()
        self.assertTrue(keyed <= {r[0].split(".")[-1].strip('"') for r in fks}, fks)

    # -- reading back: the same port, the same answers ---------------------------------------------------------------

    def read(self, release_id, world=None):
        from marketdata.manifest import SourceRecord, SourceRegistry  # noqa: PLC0415

        registry = SourceRegistry([])  # a release the database does not hold fails before the registry is used
        owner = [w for w in self.worlds.values() if w.release.release_id == release_id]
        if owner:
            registry = x.k.registry_for(owner[0].store)
        elif release_id == self.rich[0].release_id:  # the hand-made rich release: the records its readings imply, plus its benchmark and calendar sources
            rich_contents = self.rich[2]
            extra = [SourceRecord(source_id=s, name=s, upstream_provider=s, independence_group=s, synthetic=True) for s in ("rich.bm", "rich.rf", "calendar.manual")]
            registry = SourceRegistry(x.k.records_for(rich_contents.readings) + extra)
        return mds.read_release(self.app, release_id, exchange_of=self.ident.exchange_mic, registry=registry)

    def test_every_world_reads_back_with_its_digest_and_its_exact_contents(self):
        for fl, w in self.worlds.items():
            pg = self.read(w.release.release_id)
            self.assertEqual(pg.projection_digest(), self.results[fl].projection_digest, fl)
            self.assertEqual(pg.release_id(), w.release.release_id)
            self.assertEqual(pg.release, w.release)
            memory = w.store.export()
            back = pg.export()
            order = mds._in_projection_order
            self.assertEqual([canonical_json(mds.observation_obj(r.observation)) for r in order(back.readings)],
                             [canonical_json(mds.observation_obj(r.observation)) for r in order(memory.readings)], fl)
            self.assertEqual(dump(pg.calendars().calendars()), dump(w.built.calendars.calendars()), fl)
            self.assertEqual(pg.contains_synthetic, True)

    def test_the_rich_release_round_trips_exactly(self):
        release, _, contents, calendars = self.rich
        pg = self.read(release.release_id)
        self.assertEqual(pg.projection_digest(), mds.projection_digest(release, contents, calendars))
        back = pg.export()
        self.assertEqual(dump(back.benchmarks), dump(contents.benchmarks))
        self.assertEqual(dump(back.adjusted), dump(contents.adjusted))
        self.assertEqual(dump(back.exclusions), dump(contents.exclusions))
        self.assertEqual(dump(back.fx_windows), dump(contents.fx_windows))
        by_type = {r.observation.action_type: r.observation for r in back.readings
                   if isinstance(r.observation, c.CorporateActionObservation)}
        self.assertEqual(by_type[c.CorporateActionType.CASH_DIVIDEND].paid_currency, k.HKD)
        self.assertEqual(by_type[c.CorporateActionType.CASH_DIVIDEND].issuer_fx_rate, Decimal("0.128"))
        self.assertEqual((by_type[c.CorporateActionType.SYMBOL_CHANGE].old_ticker, by_type[c.CorporateActionType.SYMBOL_CHANGE].new_ticker),
                         ("OLD", "NEW"))
        self.assertEqual(by_type[c.CorporateActionType.UNSUPPORTED].unsupported_label, "RIGHTS_ISSUE")
        # a Decimal keeps the scale it was stored with: 150.2500 stays 150.2500, not 150.25
        quote = next(r.observation for r in back.readings if isinstance(r.observation, c.QuoteObservation))
        self.assertEqual(str(quote.price), "150.2500")

    def test_both_stores_give_byte_identical_output_for_the_same_release_through_the_whole_port(self):
        """The same release in memory and in PostgreSQL, the same calls, the same bytes."""
        d1, d2, d6 = D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6)
        for fl, w in self.worlds.items():
            memory, pg = w.store, self.read(w.release.release_id)
            conv = market11_conventions(w.built.calendars)
            pg_conv = market11_conventions(pg.calendars())
            self.assertEqual(dump(conv.ids()), dump(pg_conv.ids()))
            for ticker, mic in x.FACTS_QUOTES:
                lid = x.lid(w.ident, ticker, mic)
                for day in (D(2025, 1, 1), d1, d2, d6, D(2025, 1, 31)):
                    self.assertEqual(dump(memory.quote_on(lid, day, conv)), dump(pg.quote_on(lid, day, pg_conv)), (fl, ticker, day))
                self.assertEqual(dump(memory.quotes(lid, d1, d6)), dump(pg.quotes(lid, d1, d6)))
                self.assertEqual(dump(memory.corporate_actions(lid, d1, d6)), dump(pg.corporate_actions(lid, d1, d6)))
            for base, quote in ((k.HKD, k.USD), (k.CNY, k.USD), (k.USD, k.HKD), (k.EUR, k.USD), (k.HKD, k.CNY), (k.CNH, k.USD),
                                (k.USD, k.USD)):
                for day in (d1, d2, d6):
                    self.assertEqual(dump(memory.fx_on(base, quote, day, conv)), dump(pg.fx_on(base, quote, day, pg_conv)),
                                     (fl, base, quote, day))
            self.assertEqual(dump(memory.fx_series(k.EUR, k.USD, d1, d6)), dump(pg.fx_series(k.EUR, k.USD, d1, d6)))
            self.assertEqual(dump(memory.benchmark("none", d1, d6)), dump(pg.benchmark("none", d1, d6)))

    def test_the_rich_release_gives_identical_actions_and_benchmarks_in_both_stores(self):
        release, _, contents, calendars = self.rich
        from marketdata.store import InMemoryMarketData  # noqa: PLC0415

        memory = InMemoryMarketData(release, contents.readings, contents.benchmarks, contents.adjusted,
                                    exchange_of=self.ident.exchange_mic, contains_synthetic=True,
                                    fx_windows=dict(contents.fx_windows), exclusions=contents.exclusions)
        pg = self.read(release.release_id)
        aapl = x.lid(self.ident, "AAPL", "XNAS")
        self.assertEqual(dump(memory.corporate_actions(aapl, D(2025, 1, 1), D(2025, 12, 31))),
                         dump(pg.corporate_actions(aapl, D(2025, 1, 1), D(2025, 12, 31))))
        self.assertEqual(dump(memory.benchmark("BM1", D(2025, 1, 1), D(2025, 1, 31))),
                         dump(pg.benchmark("BM1", D(2025, 1, 1), D(2025, 1, 31))))
        self.assertEqual(dump(memory.adjusted_series(aapl)), dump(pg.adjusted_series(aapl)))
        conv = market11_conventions(calendars)
        self.assertEqual(dump(memory.quote_on(aapl, D(2025, 1, 2), conv)), dump(pg.quote_on(aapl, D(2025, 1, 2), conv)))
        # the V0 exclusion survives the round trip, with its cause
        self.assertEqual(dump(memory.quote_on(aapl, D(2025, 1, 31), conv)), dump(pg.quote_on(aapl, D(2025, 1, 31), conv)))

    def test_an_unknown_release_is_a_typed_error_not_an_empty_store(self):
        with self.assertRaises(mds.ReleaseNotFoundError):
            self.read("0" * 64)

    # -- append-only, sealed, bounded, idempotent ---------------------------------------------------------------------

    def test_every_md_table_refuses_update_delete_and_truncate_even_to_the_owner(self):
        # TRUNCATE of a table another md_ table references is refused by PostgreSQL's own foreign-key rule before any
        # trigger runs, so each table is also truncated TOGETHER WITH ALL the others (the foreign keys are satisfied
        # then and the BEFORE TRUNCATE trigger is what refuses it)
        everything = ", ".join(mds.MD_TABLES)
        for table in mds.MD_TABLES:
            for sql in (UPDATES[table], f"DELETE FROM {table}", f"TRUNCATE {table}, {everything}"):
                with self.assertRaises(self.pg.Error, msg=sql) as cm:
                    self.owner.execute(sql)
                self.assertEqual((cm.exception.sqlstate, cm.exception.diag.constraint_name), ("23001", "md_append_only"), sql)
                typed = mds.translate_error(cm.exception)
                self.assertIsInstance(typed, mds.MarketDataImmutableError)
        for table in ("md_quote", "md_fx_rate", "md_corporate_action", "md_benchmark_point", "md_adjusted_quote",
                      "md_calendar", "md_series_exclusion", "md_risk_free_point"):  # nothing references these: a plain TRUNCATE reaches the trigger
            with self.assertRaises(self.pg.Error) as cm:
                self.owner.execute(f"TRUNCATE {table}")
            self.assertEqual(cm.exception.diag.constraint_name, "md_append_only", table)

    def test_every_md_table_holds_a_row_so_the_row_triggers_were_really_exercised(self):
        for table in mds.MD_TABLES:
            self.assertGreater(self.owner.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0, table)

    def test_a_committed_release_is_sealed_nothing_can_be_added_to_it(self):
        w = self.worlds["mock"]
        rid = w.release.release_id
        sha = w.release.files[0]
        for sql, params in (
            ("INSERT INTO md_release_file (release_id, file_sha256, ordinal, has_fx_window) VALUES (%s, %s, 99, false)",
             (rid, sha)),
            ("INSERT INTO md_series_exclusion (release_id, exclusion_ordinal, listing_id, file_sha256, test, reason) "
             "VALUES (%s, 99, %s, %s, 'V0', 'x')", (rid, x.lid(self.ident, "AAPL", "XNAS"), sha)),
        ):
            with self.assertRaises(self.pg.Error) as cm:
                self.owner.execute(sql, params)
            self.assertEqual((cm.exception.sqlstate, cm.exception.diag.constraint_name), ("23514", "md_release_sealed"))
            self.assertIsInstance(mds.translate_error(cm.exception), mds.ReleaseSealedError)
        # and a row for a release that does not exist is the same refusal
        with self.assertRaises(self.pg.Error) as cm:
            self.owner.execute("INSERT INTO md_release_file (release_id, file_sha256, ordinal, has_fx_window) "
                               "VALUES (%s, %s, 0, false)", ("9" * 64, sha))
        self.assertEqual(cm.exception.diag.constraint_name, "md_release_sealed")

    def test_projecting_the_same_release_again_is_a_no_op_and_a_different_projection_is_a_conflict(self):
        w = self.worlds["mock"]
        again = mds.write_release(self.owner, w.release, w.built.manifests, w.store.export(), w.built.calendars)
        self.assertEqual((again.created, again.projection_digest), (False, self.results["mock"].projection_digest))
        before = self.owner.execute("SELECT count(*) FROM md_quote").fetchone()[0]
        contents = w.store.export()
        changed = dataclasses.replace(contents, contains_synthetic=False)
        with self.assertRaises(mds.ReleaseConflictError):
            mds.write_release(self.owner, w.release, w.built.manifests, changed, w.built.calendars)
        self.assertEqual(self.owner.execute("SELECT count(*) FROM md_quote").fetchone()[0], before)

    def test_a_manifest_that_differs_from_the_registered_one_for_the_same_hash_is_refused(self):
        w = self.worlds["formats"]
        sneaky = dataclasses.replace(w.built.manifests[0], market="XX")  # same bytes (same hash), another manifest
        scratch = pk.PgSchema().open()
        try:
            pk.insert_identity(scratch.owner, self.ident)
            mds.write_release(scratch.owner, w.release, w.built.manifests, w.store.export(), w.built.calendars)
            other = dataclasses.replace(w.release, name="another-name")
            with self.assertRaises(mds.FileRegistrationConflictError):
                mds.write_release(scratch.owner, other, [sneaky] + list(w.built.manifests[1:]), w.store.export(), w.built.calendars)
            self.assertEqual(scratch.owner.execute("SELECT count(*) FROM md_release").fetchone()[0], 1)
        finally:
            scratch.close()

    def test_numbers_beyond_the_bounds_are_refused_with_a_typed_error_and_nothing_is_left(self):
        w = self.worlds["mock"]
        contents = w.store.export()
        first = next(r for r in contents.readings if isinstance(r.observation, c.QuoteObservation))
        cases = {
            "price at 1E30": Decimal("1E+30"),
            "price with 25 decimals": Decimal("1." + "0" * 24 + "1"),
        }
        for label, price in cases.items():
            bad = c.SourceReading(first.source_id, first.independence_group, first.file_sha256,
                                  dataclasses.replace(first.observation, price=price))
            tweaked = dataclasses.replace(contents, readings=(bad,) + tuple(r for r in contents.readings if r is not first))
            release = dataclasses.replace(w.release, name="bounded-" + label.replace(" ", "-"))
            with self.assertRaises(mds.MarketDataValueOutOfRangeError, msg=label):
                mds.write_release(self.owner, release, w.built.manifests, tweaked, w.built.calendars)
            self.assertEqual(self.owner.execute("SELECT count(*) FROM md_release WHERE release_id = %s",
                                                (release.release_id,)).fetchone()[0], 0, label)  # rolled back whole

    def test_a_precision_bound_may_have_the_scale_of_a_half_ulp_but_not_an_unbounded_one(self):
        # 2^-53 has 53 decimal places: a derived exact binary fraction, allowed up to scale 100 (migration 0010)
        w = self.worlds["mock"]
        contents = w.store.export()
        first = next(r for r in contents.readings if isinstance(r.observation, c.QuoteObservation))
        # 2^-53 = 5^53 / 10^53, built from its digits: any Decimal operation would round to 28 digits
        half_ulp = Decimal((0, tuple(int(d) for d in str(5 ** 53)), -53))
        fine = c.SourceReading(first.source_id, first.independence_group, first.file_sha256, dataclasses.replace(
            first.observation, recovered=False, precision_bound=half_ulp))
        scratch = pk.PgSchema().open()
        try:
            pk.insert_identity(scratch.owner, self.ident)
            tweaked = dataclasses.replace(contents, readings=(fine,) + tuple(r for r in contents.readings if r is not first))
            result = mds.write_release(scratch.owner, w.release, w.built.manifests, tweaked, w.built.calendars)
            self.assertTrue(result.created)
            self.assertEqual(Fraction(scratch.owner.execute("SELECT precision_bound FROM md_quote WHERE NOT recovered").fetchone()[0]),
                             Fraction(1, 2 ** 53))
            # market-data/1.4 section 9C item 6 (this test used to expect a typed refusal at scale 101): a bound with more than
            # 100 decimals is stored ROUNDED TOWARD +INFINITY, never lower and never refused. 1E-101 -> 1E-100 (the
            # smallest 100-decimal value >= it). 2^-120 has 120 decimals: stored as ceil(2^-120 x 10^100) / 10^100, by hand.
            import math  # noqa: PLC0415

            for name, bound, expected in (
                    ("one-e-minus-101", Decimal("1E-101"), Fraction(1, 10 ** 100)),
                    ("two-pow-minus-120", Decimal((0, tuple(int(d) for d in str(5 ** 120)), -120)),
                     Fraction(math.ceil(Fraction(1, 2 ** 120) * 10 ** 100), 10 ** 100))):
                rounded = c.SourceReading(first.source_id, first.independence_group, first.file_sha256, dataclasses.replace(
                    first.observation, recovered=False, precision_bound=bound))
                tweaked2 = dataclasses.replace(contents, readings=(rounded,) + tuple(r for r in contents.readings if r is not first))
                release = dataclasses.replace(w.release, name="rounded-" + name)
                result2 = mds.write_release(scratch.owner, release, w.built.manifests, tweaked2, w.built.calendars)
                self.assertTrue(result2.created, name)
                stored = Fraction(scratch.owner.execute(
                    "SELECT precision_bound FROM md_quote WHERE release_id = %s AND NOT recovered", (release.release_id,)).fetchone()[0])
                self.assertEqual(stored, expected, name)
                self.assertGreaterEqual(stored, Fraction(bound), name)  # never rounded down
                # the digest, the rows and a read-back describe the SAME (rounded) values: it reads back and verifies
                back = mds.read_release(scratch.owner, release.release_id, exchange_of=w.ident.exchange_mic, registry=x.k.registry_for(w.store))
                (read_q,) = [r for r in back.export().readings if isinstance(r.observation, c.QuoteObservation)
                             and not r.observation.recovered]
                self.assertEqual(Fraction(read_q.observation.precision_bound), expected, name)
                self.assertEqual(back.projection_digest(), result2.projection_digest, name)
            # a bound with exactly 100 decimals (1E-100 is one) is stored EXACTLY: nothing is rounded at the limit
            exact = Decimal("1E-100")
            same = c.SourceReading(first.source_id, first.independence_group, first.file_sha256, dataclasses.replace(
                first.observation, recovered=False, precision_bound=exact))
            self.assertEqual(mds.stored_contents(dataclasses.replace(contents, readings=(same,))).readings[0].observation.precision_bound,
                             exact)
        finally:
            scratch.close()

    # -- the security patterns of CP1-B -------------------------------------------------------------------------------

    def test_every_md_function_is_pinned_and_a_rename_guard_makes_a_stale_pin_fail_closed(self):
        rows = self.owner.execute(
            "SELECT p.proname, p.proconfig FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = %s AND p.proname LIKE 'md\\_%%'", (self.db.schema,)).fetchall()
        self.assertEqual({r[0] for r in rows}, {"md_reject_mutation", "md_release_stamp", "md_require_open_release"})
        for name, config in rows:
            settings = [s.replace('"', "") for s in (config or [])]
            self.assertEqual(settings, ["search_path=%s, pg_temp" % self.db.schema], name)

    def test_a_renamed_schema_leaves_a_stale_pin_and_every_function_fails_closed(self):
        scratch = pk.PgSchema().open()
        try:
            pk.insert_identity(scratch.owner, self.ident)
            w = self.worlds["mock"]
            mds.write_release(scratch.owner, w.release, w.built.manifests, w.store.export(), w.built.calendars)
            renamed = scratch.schema + "_r"
            scratch.owner.execute('ALTER SCHEMA "%s" RENAME TO "%s"' % (scratch.schema, renamed))
            scratch.schema = renamed
            scratch.owner.execute('SET search_path TO "%s"' % renamed)
            for sql in ("UPDATE md_file SET market = market", "DELETE FROM md_release", "TRUNCATE md_quote",
                        "INSERT INTO md_release (release_id, name, convention_set_id, release_content, contains_synthetic, "
                        "projection_digest) VALUES ('%s', 'n', 'c', '{}'::jsonb, false, '%s')" % ("1" * 64, "2" * 64)):
                with self.assertRaises(self.pg.Error, msg=sql) as cm:
                    scratch.owner.execute(sql)
                self.assertEqual(cm.exception.diag.constraint_name, "md_search_path_pin_stale", sql)
        finally:
            scratch.close()

    def test_temp_table_shadowing_cannot_open_a_sealed_release_and_the_control_shows_it_could_without_the_pin(self):
        """The CP1B-1 attack on the md_ functions, run as the APP role (which holds the default TEMPORARY privilege).
        The role is given INSERT on md_quote for this test only; it shadows md_release with a TEMP table that claims
        the sealed release is open to this very transaction. CONTROL: with the function's pin removed the insert goes
        through (so the attack is real and the test can fail). PINNED (as shipped): refused, md_release_sealed."""
        scratch = pk.PgSchema().open()
        try:
            pk.insert_identity(scratch.owner, self.ident)
            w = self.worlds["mock"]
            mds.write_release(scratch.owner, w.release, w.built.manifests, w.store.export(), w.built.calendars)
            role = '"%s"' % scratch.app_role
            scratch.owner.execute('GRANT INSERT ON "%s".md_quote TO %s' % (scratch.schema, role))
            app = scratch.app_connection(autocommit=False)
            aapl = x.lid(self.ident, "AAPL", "XNAS")
            sha = next(m.file_sha256 for m in w.built.manifests if m.data_kind is DataKind.QUOTE)

            def attack():
                try:
                    app.execute("CREATE TEMP TABLE md_release (release_id text, append_xid xid8) ON COMMIT DROP")
                    app.execute("INSERT INTO md_release VALUES (%s, pg_current_xact_id())", (w.release.release_id,))
                    app.execute(
                        "INSERT INTO md_quote (release_id, row_ordinal, file_sha256, source_id, independence_group, listing_id, "
                        "value_date, price, currency, volume, price_kind, recovered, precision_bound, delay_status, lineage) "
                        "VALUES (%s, 999, %s, 's', 'g', %s, '2025-02-01', 1, 'USD', 1, 'SOURCE_CLOSE', true, 0, 'UNKNOWN', '{}'::jsonb)",
                        (w.release.release_id, sha, aapl))
                    return None
                except self.pg.Error as exc:
                    return exc
                finally:
                    app.rollback()

            fn = '"%s".md_require_open_release()' % scratch.schema
            scratch.owner.execute("ALTER FUNCTION %s RESET search_path" % fn)  # CONTROL: unpinned
            try:
                self.assertIsNone(attack(), "the control must show the attack succeeds on an unpinned function")
            finally:
                scratch.owner.execute('ALTER FUNCTION %s SET search_path = "%s", pg_temp' % (fn, scratch.schema))
            refused = attack()  # AS SHIPPED
            self.assertIsNotNone(refused)
            self.assertEqual(refused.diag.constraint_name, "md_release_sealed")
            app.close()
        finally:
            scratch.close()

    def test_a_tampered_projection_is_refused_on_read_fail_closed(self):
        scratch = pk.PgSchema().open()
        try:
            pk.insert_identity(scratch.owner, self.ident)
            w = self.worlds["mock"]
            mds.write_release(scratch.owner, w.release, w.built.manifests, w.store.export(), w.built.calendars)
            app = scratch.app_connection()
            self.assertEqual(mds.read_release(app, w.release.release_id, registry=x.k.registry_for(w.store)).release_id(), w.release.release_id)
            scratch.owner.execute("ALTER TABLE md_quote DISABLE TRIGGER USER")  # what only an owner could do
            scratch.owner.execute("UPDATE md_quote SET price = price + 1 WHERE row_ordinal = 0")
            scratch.owner.execute("ALTER TABLE md_quote ENABLE TRIGGER USER")
            with self.assertRaises(mds.ProjectionDigestMismatchError):
                mds.read_release(app, w.release.release_id, registry=x.k.registry_for(w.store))
            app.close()
        finally:
            scratch.close()

    def test_a_rebuilt_projection_in_a_fresh_schema_has_the_same_digest(self):
        """Rebuildable: the files are the record. Build the same release again from the same files in a fresh schema."""
        w = self.worlds["formats"]
        rebuilt = x.build_world("formats", root=w.root)  # the very files on disk, parsed again
        scratch = pk.PgSchema().open()
        try:
            pk.insert_identity(scratch.owner, rebuilt.ident)
            result = mds.write_release(scratch.owner, rebuilt.release, rebuilt.built.manifests, rebuilt.store.export(),
                                       rebuilt.built.calendars)
            self.assertEqual(result.projection_digest, self.results["formats"].projection_digest)
            self.assertEqual(rebuilt.release.release_id, w.release.release_id)
        finally:
            scratch.close()


class _Expect:
    """A tiny context manager to capture the error the app role gets before it holds any grant."""

    def __init__(self, error_type):
        self.error_type, self.error = error_type, None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is None:
            raise AssertionError("expected a database error")
        self.error = exc
        return isinstance(exc, self.error_type)


if __name__ == "__main__":
    unittest.main()
