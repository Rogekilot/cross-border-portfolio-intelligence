"""CP4d increment 2: two sources for one benchmark (Ruling 5.7 (1.2)), the ETF proxy (Ruling 5.5 (1.2)), Current mode on the benchmark leg (Ruling 5.8), the default view (Ruling 7.7) and the registry's
`source_priority` (tech plan 17.21). The golden fixture proves the VALUES (R4, R5, R7, R6/R9/R10 in `test_cp4_golden`); this module proves the rules the fixture does not state by itself.
"""

from __future__ import annotations

import datetime
import json
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import cp4_golden_kit as g  # noqa: E402
import marketdata_cp2c1_kit as k  # noqa: E402
from domain.catalogs import BenchmarkEntry, CatalogError, parse_benchmark_catalog  # noqa: E402
from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import SplitRatio  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.manifest import ManifestError, MarketDataRelease, SourceRecord, SourceRegistry, source_registry_digest  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.store import InMemoryMarketData  # noqa: E402
from product_contract.vocabulary import SufficiencyState as SS  # noqa: E402
from risk import benchmark as B  # noqa: E402
from risk import levels as L  # noqa: E402
from risk import states as S  # noqa: E402
from risk_service import default_view as dv  # noqa: E402

D = datetime.date
USD = CurrencyCode("USD")


def series(source, group, points, sha):
    lineage = c.Lineage("t", c.AdjustmentStatus.RAW, source_id=source, file_sha256=sha, adapter_id="t.benchmark", adapter_version="1", source_record_ref="r", retrieved_at=g.DEFAULT_RETRIEVED,
                        usage_scope=c.UsageScope.SYNTHETIC_TEST, independence_group=group)
    return c.BenchmarkSeries("B", "p", tuple(c.BenchmarkPoint(d, Decimal(v)) for d, v in points), c.BenchmarkValueKind.LEVEL, USD, c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY), lineage,
                             c.LicensingMetadata(c.LicenseStatus.SYNTHETIC_TEST, False))


DAYS = [D(2025, 1, 6), D(2025, 1, 7), D(2025, 1, 8), D(2025, 1, 9), D(2025, 1, 10)]
DECLARED = {"sa": 2, "sb": 2}  # the declared decimals of the two test sources (the index publishes 2)


class TwoSourceTests(unittest.TestCase):
    """Ruling 5.7 (1.2), per calculation day."""

    def book(self, a, b, pa=1, pb=2, official=2, da=2, db=2):
        by = {"sa": series("sa", "ga", a, "aa" * 32), "sb": series("sb", "gb", b, "bb" * 32)}
        return L.reconcile_sources(by, {"sa": pa, "sb": pb}, official, {"sa": da, "sb": db})

    def test_agreement_carries_the_primary_and_is_corroborated_when_the_upstreams_are_independent(self):
        book = self.book([(DAYS[0], "100.00")], [(DAYS[0], "100.0")])  # equal as numbers: the bound of a published decimal is 0
        (day,) = book.days
        self.assertEqual((day.value, day.status), (Fraction(100), L.CORROBORATED))
        self.assertTrue(day.note.startswith("sa=100.00"))  # the highest-priority source first in the lineage

    # -- CP4F-4: the bound, and independence by a DECLARED upstream ---------------------------------------------------------------------------------------------

    def test_levels_agree_within_the_sum_of_the_sources_declared_bounds_not_exactly(self):
        near = self.book([(DAYS[0], "4321.1234")], [(DAYS[0], "4321.12")], official=4, da=4, db=2)  # the index publishes 4 decimals, b writes 2 (declared): bound 0.005, a's 0 -> 0.0034 agrees
        self.assertEqual((near.days[0].value, near.days[0].status), (Fraction("4321.1234"), L.CORROBORATED))  # the primary's level, as published
        far = self.book([(DAYS[0], "4321.1234")], [(DAYS[0], "4321.13")], official=4, da=4, db=2)  # 0.0066 > 0.005
        self.assertEqual((far.days[0].value, far.days[0].status), (None, L.DISAGREEMENT))
        # CP4F-13 (market-data Ruling 4.2 example (b)): a source publishing at least the official decimals has bound 0, so one tick apart is NOT corroborated
        for a, b, d in (("100.12", "100.13", 2), ("187.44", "187.43", 2), ("8000", "8001", 0), ("8000.0", "8000.4", 1)):
            book = self.book([(DAYS[0], a)], [(DAYS[0], b)], official=d, da=d, db=d)
            self.assertEqual((book.days[0].value, book.days[0].status), (None, L.DISAGREEMENT), (a, b))
        self.assertEqual(self.book([(DAYS[0], "100.12")], [(DAYS[0], "100.12")]).days[0].status, L.CORROBORATED)
        # a declared-coarser source (integers, d = 0 against D = 1) has bound 0.5 and only corroborates
        coarse = self.book([(DAYS[0], "8000.0"), (DAYS[1], "8001.4")], [(DAYS[0], "8000"), (DAYS[1], "8001")], official=1, da=1, db=0)
        self.assertEqual([d.status for d in coarse.days], [L.CORROBORATED, L.CORROBORATED])

    def test_precision_is_declared_never_inferred_from_the_texts_of_the_levels(self):
        """Ruling 5.7 (1.9), fixture R4-S4 (mutation M-C45): the coarser source rounds to ONE declared decimal but its texts show none ('990'); inference would read 0 decimals and a bound of 0.5, agreeing with 990.30."""
        a, b = [(DAYS[0], "990.30")], [(DAYS[0], "990")]
        declared = self.book(a, b, official=2, da=2, db=1)  # b's declared bound is 0.05: |990.30 - 990| = 0.30 disagrees
        self.assertEqual((declared.days[0].value, declared.days[0].status), (None, L.DISAGREEMENT))
        self.assertEqual(self.book(a, b, official=2, da=2, db=0).days[0].status, L.CORROBORATED)  # a declaration of integers would agree: the DECLARATION decides, not the text
        by = {"sa": series("sa", "ga", [(DAYS[0], "100.00")], "aa" * 32), "sb": series("sb", "gb", [(DAYS[0], "100.00")], "bb" * 32)}
        for official, decimals in ((None, {"sa": 2, "sb": 2}), (2, {"sa": 2}), (2, {}), (None, {})):  # undeclared is not usable (M-C44)
            with self.assertRaises(L.PrecisionUndeclared):
                L.reconcile_sources(by, {"sa": 1, "sb": 2}, official, decimals)
        with self.assertRaises(L.PrecisionUndeclared):  # the content check (item 3): a level showing more decimals than its source declares contradicts the declaration
            L.reconcile_sources({"sa": series("sa", "ga", [(DAYS[0], "100.25")], "aa" * 32), "sb": series("sb", "gb", [(DAYS[0], "100.25")], "bb" * 32)}, {"sa": 1, "sb": 2}, 2, {"sa": 2, "sb": 1})  # sb declares ONE decimal and shows two

    def test_a_source_that_declares_no_upstream_is_never_independent_so_agreement_is_single_source(self):
        for ga, gb in ((None, "gb"), ("ga", None), (None, None)):
            by = {"sa": series("sa", ga, [(DAYS[0], "100.00")], "aa" * 32), "sb": series("sb", gb, [(DAYS[0], "100.00")], "bb" * 32)}
            self.assertEqual(L.reconcile_sources(by, {"sa": 1, "sb": 2}, 2, DECLARED).days[0].status, L.SINGLE_SOURCE, (ga, gb))
        by = {"sa": series("sa", "ga", [(DAYS[0], "100.00")], "aa" * 32), "sb": series("sb", "gb", [(DAYS[0], "100.00")], "bb" * 32)}
        self.assertEqual(L.reconcile_sources(by, {"sa": 1, "sb": 2}, 2, DECLARED).days[0].status, L.CORROBORATED)

    def test_the_priority_is_data_not_the_order_of_the_ids(self):
        book = self.book([(DAYS[0], "100.00")], [(DAYS[0], "100.00")], pa=2, pb=1)
        self.assertTrue(book.days[0].note.startswith("sb="))  # `sb` is the primary now

    def test_the_same_upstream_agreeing_is_single_source_not_corroborated(self):
        by = {"sa": series("sa", "same", [(DAYS[0], "100.00")], "aa" * 32), "sb": series("sb", "same", [(DAYS[0], "100.00")], "bb" * 32)}
        self.assertEqual(L.reconcile_sources(by, {"sa": 1, "sb": 2}, 2, DECLARED).days[0].status, L.SINGLE_SOURCE)

    def test_one_source_only_is_used_and_does_not_degrade(self):
        book = self.book([(DAYS[0], "100.00")], [(DAYS[0], "100.00"), (DAYS[1], "101.00")])
        self.assertEqual([(d.day, d.value, d.status) for d in book.days], [(DAYS[0], Fraction(100), L.CORROBORATED), (DAYS[1], Fraction(101), L.SINGLE_SOURCE)])

    def test_a_disagreement_withholds_the_day_whoever_is_primary_and_never_averages(self):
        for pa, pb in ((1, 2), (2, 1)):  # M-C4: the primary does not win a disagreement
            book = self.book([(DAYS[0], "100.00"), (DAYS[1], "101.00")], [(DAYS[0], "100.00"), (DAYS[1], "101.02")], pa, pb)
            self.assertEqual([(d.value, d.status) for d in book.days], [(Fraction(100), L.CORROBORATED), (None, L.DISAGREEMENT)])
            self.assertIn("BENCHMARK_SOURCE_CONFLICT", book.days[1].note)
            self.assertIn("sa=101.00", book.days[1].note)  # both sources' levels stay in the lineage

    def test_a_source_without_a_priority_or_two_with_the_same_one_is_refused_never_ordered_by_file(self):
        by = {"sa": series("sa", "ga", [(DAYS[0], "1")], "aa" * 32), "sb": series("sb", "gb", [(DAYS[0], "1")], "bb" * 32)}
        for priority in ({"sa": 1, "sb": None}, {"sa": 1}, {"sa": 1, "sb": 1}):
            with self.assertRaises(L.SourcePriorityError):
                L.reconcile_sources(by, priority, 2, DECLARED)

    def test_the_book_refuses_two_entries_for_one_day_and_finds_the_latest_day(self):
        with self.assertRaises(ValueError):
            L.LevelBook([L.DayLevel(DAYS[0], Fraction(1), "x"), L.DayLevel(DAYS[0], Fraction(2), "x")])
        book = L.LevelBook([L.DayLevel(d, Fraction(i + 1), "x") for i, d in enumerate(DAYS)])
        self.assertEqual(book.latest(D(2025, 1, 9)).day, DAYS[3])
        self.assertEqual(book.latest(D(2025, 1, 12)).day, DAYS[4])
        self.assertIsNone(book.latest(D(2025, 1, 5)))
        self.assertEqual(book.latest(D(2025, 1, 9), lambda day: day < DAYS[3]).day, DAYS[2])  # a day that does not exist is skipped (Current mode)


class LegOverSourcesTests(unittest.TestCase):
    """The leg through `open_benchmark`: the registry's `source_priority` reaches it through the port, and a multi-source benchmark without one is refused as a whole."""

    def entry(self, **kw):
        row = {"benchmark_id": "B", "name": "n", "provider": "p", "source_id": "sa", "licensing": "l", "currency": "USD", "return_basis": "TOTAL_RETURN_GROSS", "dividend_treatment": "d",
               "calendar_id": "C", "series_form": "LEVELS", "proxy_of": None, "synthetic": True, "additional_sources": [{"source_id": "sb", "return_basis": "TOTAL_RETURN_GROSS", "precision_decimals": 2}],
               "official_decimals": 2, "precision_decimals": 2}
        row.update(kw)
        return parse_benchmark_catalog(json.dumps({"catalog_id": "d", "entries": [row]}).encode(), allow_synthetic=True).get("B")

    def port(self, priorities):
        from marketdata.store import BenchmarkEntry as StoreEntry  # noqa: PLC0415

        entries = [StoreEntry("sa", "ga", "aa" * 32, series("sa", "ga", [(DAYS[0], "100.00")], "aa" * 32)), StoreEntry("sb", "gb", "bb" * 32, series("sb", "gb", [(DAYS[0], "100.00")], "bb" * 32))]
        records = [SourceRecord("sa", "a", "up_a", "ga", synthetic=True, source_priority=priorities[0]), SourceRecord("sb", "b", "up_b", "gb", synthetic=True, source_priority=priorities[1])]
        store = InMemoryMarketData(MarketDataRelease(name="d", files=(), source_precedence=()), benchmarks=entries, source_records=records)
        return store, market11_conventions(CalendarSet([]))

    def test_the_registry_priority_reaches_the_leg_and_the_primary_is_the_one_named(self):
        store, conventions = self.port((2, 1))
        leg = B.open_benchmark(self.entry(), "B", store, USD, conventions, D(2025, 1, 10))
        self.assertIsInstance(leg, B.BenchmarkLeg)
        self.assertEqual(leg.source_id, "sb")  # priority 1 carries the level and is the source the result names

    def test_a_second_source_the_catalog_does_not_declare_with_the_entrys_basis_is_refused_and_never_fills_a_day(self):
        """CP4F-4: the series contract carries no return basis, so the catalog binds it. A price-index copy (about half the total-return level) under the same id must not supply a day the primary lacks."""
        from marketdata.store import BenchmarkEntry as StoreEntry  # noqa: PLC0415

        primary = series("sa", "ga", [(DAYS[0], "8000.00"), (DAYS[2], "8100.00")], "aa" * 32)
        copy = series("sb", "gb", [(DAYS[0], "4000.00"), (DAYS[1], "4000.00"), (DAYS[2], "4050.00")], "bb" * 32)  # a different basis: it has DAYS[1], which the primary lacks
        records = [SourceRecord("sa", "a", "up_a", "ga", synthetic=True, source_priority=1), SourceRecord("sb", "b", "up_b", "gb", synthetic=True, source_priority=2)]
        store = InMemoryMarketData(MarketDataRelease(name="d", files=(), source_precedence=()), benchmarks=[StoreEntry("sa", "ga", "aa" * 32, primary), StoreEntry("sb", "gb", "bb" * 32, copy)], source_records=records)
        conventions = market11_conventions(CalendarSet([]))
        for declared in ([], [{"source_id": "sb", "return_basis": "PRICE_RETURN"}], [{"source_id": "sc", "return_basis": "TOTAL_RETURN_GROSS"}]):
            refused = B.open_benchmark(self.entry(additional_sources=declared), "B", store, USD, conventions, D(2025, 1, 10))
            self.assertIsInstance(refused, B.BenchmarkRefusal, declared)
            self.assertEqual((refused.reason, refused.detail), ("MISSING_BENCHMARK", "BENCHMARK_SERIES_UNAVAILABLE"))
            self.assertIn("sb", refused.note)
        leg = B.open_benchmark(self.entry(), "B", store, USD, conventions, D(2025, 1, 10))  # declared with the entry's basis: admitted, and now the sources disagree on 2025-01-06, as they should
        self.assertIsInstance(leg, B.BenchmarkLeg)

    def test_a_missing_or_repeated_priority_refuses_the_benchmark_as_unavailable(self):
        for priorities in ((None, None), (1, None), (1, 1)):
            store, conventions = self.port(priorities)
            refused = B.open_benchmark(self.entry(), "B", store, USD, conventions, D(2025, 1, 10))
            self.assertIsInstance(refused, B.BenchmarkRefusal, priorities)
            self.assertEqual((refused.reason, refused.detail), ("MISSING_BENCHMARK", "BENCHMARK_SERIES_UNAVAILABLE"))

    def test_the_entry_must_name_one_of_the_sources_it_describes(self):
        store, conventions = self.port((1, 2))
        refused = B.open_benchmark(self.entry(source_id="elsewhere"), "B", store, USD, conventions, D(2025, 1, 10))
        self.assertIsInstance(refused, B.BenchmarkRefusal)
        self.assertFalse(refused.entry_bound)  # a result must not name catalog values for a series the entry does not describe


class SourcePriorityDataTests(unittest.TestCase):
    """`SourceRecord.source_priority` (OI-R10): a positive integer or None; absent from the record's object (and so from every registry digest recorded before it existed) when None."""

    def test_validation_and_digest_stability(self):
        base = SourceRecord("s", "n", "u", "g")
        self.assertNotIn("source_priority", base.to_obj())
        self.assertEqual(source_registry_digest([base]), source_registry_digest([SourceRecord("s", "n", "u", "g", source_priority=None)]))
        prioritised = SourceRecord("s", "n", "u", "g", source_priority=1)
        self.assertEqual(prioritised.to_obj()["source_priority"], 1)
        self.assertNotEqual(source_registry_digest([prioritised]), source_registry_digest([base]))
        for bad in (0, -1, True, 1.5, "1"):
            with self.assertRaises(ManifestError, msg=bad):
                SourceRecord("s", "n", "u", "g", source_priority=bad)

    def test_the_registry_file_carries_it(self):
        text = json.dumps({"sources": [{"source_id": "s", "name": "n", "upstream_provider": "u", "independence_group": "g", "synthetic": True, "source_priority": 2},
                                       {"source_id": "t", "name": "n", "upstream_provider": "u", "independence_group": "h", "synthetic": True}]})
        registry = SourceRegistry.from_json(text)
        self.assertEqual((registry.get("s").source_priority, registry.get("t").source_priority), (2, None))


class CatalogProxyTests(unittest.TestCase):
    def row(self, **kw):
        row = {"benchmark_id": "P", "name": "proxy: X", "provider": "p", "source_id": "s", "licensing": "l", "currency": "USD", "return_basis": "TOTAL_RETURN_GROSS", "dividend_treatment": "d",
               "calendar_id": "C", "series_form": "LEVELS", "proxy_of": None, "synthetic": True}
        row.update(kw)
        return row

    def parse(self, row):
        return parse_benchmark_catalog(json.dumps({"catalog_id": "d", "entries": [row]}).encode(), allow_synthetic=True)

    def test_the_proxy_listing_is_optional_a_uuid_and_absent_from_the_digest_when_unset(self):
        plain = self.parse(self.row())
        self.assertNotIn("proxy_listing_id", plain.get("P").to_obj())
        proxy = self.parse(self.row(proxy_listing_id="c4000000-0000-4000-8000-000000000031"))
        self.assertEqual(proxy.get("P").proxy_listing_id, "c4000000-0000-4000-8000-000000000031")
        self.assertNotEqual(proxy.digest, plain.digest)
        with self.assertRaises(CatalogError):
            self.parse(self.row(proxy_listing_id="not-a-uuid"))

    def test_declared_precision_is_optional_non_negative_per_serving_source_and_absent_from_the_digest_when_unset(self):
        """Ruling 5.7 (1.9): `official_decimals` on the entry, `precision_decimals` on each serving source (the entry's own and each additional one)."""
        plain = self.parse(self.row())
        self.assertNotIn("official_decimals", plain.get("P").to_obj())
        full = self.parse(self.row(additional_sources=[{"source_id": "s2", "return_basis": "TOTAL_RETURN_GROSS", "precision_decimals": 1}], official_decimals=2, precision_decimals=2))
        entry = full.get("P")
        self.assertEqual((entry.official_decimals, entry.source_precisions), (2, (("s", 2), ("s2", 1))))
        obj = entry.to_obj()
        self.assertEqual((obj["official_decimals"], obj["precision_decimals"], obj["additional_sources"][0]["precision_decimals"]), (2, 2, 1))
        self.assertNotEqual(full.digest, plain.digest)
        for bad in (dict(official_decimals=-1), dict(official_decimals=True), dict(precision_decimals=-2), dict(precision_decimals="2")):
            with self.assertRaises(CatalogError, msg=str(bad)):
                self.parse(self.row(**bad))

    def test_additional_sources_are_optional_declared_with_a_basis_and_absent_from_the_digest_when_unset(self):
        plain = self.parse(self.row())
        self.assertNotIn("additional_sources", plain.get("P").to_obj())
        two = self.parse(self.row(additional_sources=[{"source_id": "s2", "return_basis": "TOTAL_RETURN_GROSS"}]))
        self.assertEqual(two.get("P").additional_sources, (("s2", "TOTAL_RETURN_GROSS"),))
        self.assertNotEqual(two.digest, plain.digest)
        for bad in ([{"source_id": "s", "return_basis": "TOTAL_RETURN_GROSS"}], [{"source_id": "s2", "return_basis": "NOT_A_BASIS"}], [{"source_id": "s2"}], "s2",
                    [{"source_id": "s2", "return_basis": "TOTAL_RETURN_GROSS"}, {"source_id": "s2", "return_basis": "PRICE_RETURN"}]):  # the last: one source listed twice with two bases
            with self.assertRaises(CatalogError, msg=bad):
                self.parse(self.row(additional_sources=bad))  # the primary is not an additional source; the basis is one of the three; the shape is exact


# --- the ETF proxy (Ruling 5.5 (1.2)) -------------------------------------------------------------------------------------------------------------

LISTING = k.LID


def print_reading(day, price, sha="11" * 32, source="px", group="gpx", volume="1000"):
    return k.quote_reading(day, price, volume=volume, source=source, group=group, sha=sha, listing=LISTING)


def action(kind, ex, source, group, sha, **kw):
    obs = c.CorporateActionObservation(LISTING, kind, ex, c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY), k.lineage(source, sha), **kw)
    return c.SourceReading(source, group, sha, obs)


def dividend(ex, amount, source="feed", group="gfeed", sha="22" * 32, pay=None):
    return action(c.CorporateActionType.CASH_DIVIDEND, ex, source, group, sha, amount_per_unit=Money(Decimal(amount), USD), pay_date=pay or ex + datetime.timedelta(days=7))


def split(ex, new, old, source="feed", group="gfeed", sha="22" * 32):
    return action(c.CorporateActionType.SPLIT, ex, source, group, sha, split_ratio=SplitRatio(Decimal(new), Decimal(old)))


class ProxyTests(unittest.TestCase):
    def build(self, readings, end=D(2025, 1, 31)):
        store = InMemoryMarketData(MarketDataRelease(name="p", files=(), source_precedence=()), readings=readings)
        return L.build_proxy(LISTING, store, market11_conventions(CalendarSet([])), end)

    def values(self, built):
        return [(d.day.isoformat(), d.value) for d in built.book.days]

    def test_the_base_is_the_first_close_and_a_dividend_is_reinvested_at_its_ex_date_close(self):
        built = self.build([print_reading(D(2025, 1, 6), "50.00"), print_reading(D(2025, 1, 7), "51.00"), print_reading(D(2025, 1, 8), "50.00"), dividend(D(2025, 1, 8), "0.50")])
        # TR = 50; x 51/50 = 51; x (50 + 0.50)/51 = 50.5
        self.assertEqual(self.values(built), [("2025-01-06", Fraction(50)), ("2025-01-07", Fraction(51)), ("2025-01-08", Fraction(101, 2))])
        self.assertEqual(built.currency, "USD")

    def test_a_split_multiplies_and_the_dividend_is_per_new_share(self):
        built = self.build([print_reading(D(2025, 1, 6), "100.00"), print_reading(D(2025, 1, 7), "50.00"), split(D(2025, 1, 7), 2, 1), dividend(D(2025, 1, 7), "1.00")])
        # TR_t = TR_prev x f x (P + d) / P_prev = 100 x 2 x 51 / 100 = 102
        self.assertEqual(self.values(built)[-1], ("2025-01-07", Fraction(102)))

    def test_an_ex_date_that_is_not_a_print_applies_at_the_next_print(self):
        built = self.build([print_reading(D(2025, 1, 6), "50.00"), print_reading(D(2025, 1, 8), "50.00"), dividend(D(2025, 1, 7), "0.50")])
        self.assertEqual(self.values(built)[-1], ("2025-01-08", Fraction(101, 2)))  # the 01-07 dividend lands on the 01-08 print: (50 + 0.50) / 50

    def test_a_single_source_dividend_is_used_and_not_dropped(self):
        # M-C6: a corroborated-only proxy would be a partial price return; a corroborated one (feed and filing agree) is used as well
        feed, filing = dividend(D(2025, 1, 7), "0.50"), dividend(D(2025, 1, 7), "0.50", source="filing", group="gfiling", sha="33" * 32)
        single = self.build([print_reading(D(2025, 1, 6), "50.00"), print_reading(D(2025, 1, 7), "50.00"), feed])
        both = self.build([print_reading(D(2025, 1, 6), "50.00"), print_reading(D(2025, 1, 7), "50.00"), feed, filing])
        self.assertEqual(self.values(single)[-1][1], self.values(both)[-1][1])
        self.assertEqual(self.values(single)[-1][1], Fraction(101, 2))

    def test_a_disputed_dividend_breaks_the_chain_at_its_ex_date_and_withholds_no_level(self):
        """Ruling 5.5 (1.6) item 4b: levels before the ex-date are one chain, levels from it on another; only a RATIO across it is unavailable (mutation M-C32 withheld every later level)."""
        feed, filing = dividend(D(2025, 1, 8), "0.30"), dividend(D(2025, 1, 8), "0.35", source="filing", group="gfiling", sha="33" * 32)
        built = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8, 9)] + [feed, filing])
        self.assertEqual([(d.day.day, d.value is None, d.segment) for d in built.book.days], [(6, False, 0), (7, False, 0), (8, False, 1), (9, False, 1)])
        self.assertIn("chain restarted", built.book.days[2].note)
        self.assertIn("feed=0.30", built.book.days[2].note)  # both statements stay in the lineage
        self.assertEqual(built.book.days[3].value / built.book.days[2].value, 1)  # inside the new chain a ratio is what it is without the dispute (no dividend is applied: neither statement is)

    def test_a_disputed_print_is_withheld_for_that_day_only_and_the_chain_links_around_it(self):
        """Ruling 5.5 (1.6) item 4a: no price of the disputed day is needed to link the prints on either side; a dividend dated on it applies at the next print."""
        second = print_reading(D(2025, 1, 8), "50.10", sha="66" * 32, source="px2", group="gpx2")
        built = self.build([print_reading(D(2025, 1, 6), "50.00"), print_reading(D(2025, 1, 7), "50.00"), print_reading(D(2025, 1, 8), "50.00"), second, print_reading(D(2025, 1, 9), "50.00"),
                            dividend(D(2025, 1, 8), "0.50")])
        self.assertEqual([(d.day.day, d.value, d.segment) for d in built.book.days],
                         [(6, Fraction(50), 0), (7, Fraction(50), 0), (8, None, 0), (9, Fraction(101, 2), 0)])  # 01-09: TR(01-07) x (50 + 0.50)/50, one chain
        self.assertIn("BENCHMARK_SOURCE_CONFLICT", built.book.days[2].note)
        self.assertEqual(built.book.days[2].status, L.DISAGREEMENT)
        later = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8, 9, 10, 13)] + [print_reading(D(2025, 1, 8), "50.10", sha="66" * 32, source="px2", group="gpx2")])
        self.assertEqual([d.value is None for d in later.book.days], [False, False, True, False, False, False])  # M-C33 poisoned every later print

    def test_a_print_with_no_usable_reading_is_missing_not_a_conflict(self):
        """Ruling 5.5 (1.6): a print every reading of which is unrecovered is not in the book at all (normal staleness), never a SOURCE_CONFLICT."""
        unrecovered = k.quote_reading(D(2025, 1, 8), "50.00", volume="1000", source="px", group="gpx", sha="11" * 32, listing=LISTING, recovered=False, bound="0.005")
        built = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 9)] + [unrecovered])
        self.assertEqual([(d.day.day, d.value is None) for d in built.book.days], [(6, False), (7, False), (9, False)])  # 01-08 is not in the book: a grid date falls back to 01-07 and is judged by staleness

    # -- CP4F-3: identity of a corporate action across sources (Ruling 5.5 (1.2) item 4: a difference in the amount, the ratio OR THE DATE is a disagreement) ----------------------------------

    def test_feed_and_filing_that_disagree_on_the_ex_date_are_a_disagreement_never_applied_twice(self):
        pay = D(2025, 1, 15)
        feed, filing = dividend(D(2025, 1, 8), "0.50", pay=pay), dividend(D(2025, 1, 9), "0.50", source="filing", group="gfiling", sha="33" * 32, pay=pay)
        built = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8, 9, 10)] + [feed, filing])
        self.assertEqual([(d.day.day, d.segment) for d in built.book.days], [(6, 0), (7, 0), (8, 1), (9, 2), (10, 2)])  # the chain breaks at EVERY date either statement names; before them it is one chain
        self.assertTrue(all(d.value == 50 for d in built.book.days))  # never 50.5 and never 51.005 (one dividend counted twice): neither statement is applied
        self.assertIn("feed=", built.book.days[2].note)
        self.assertIn("filing=", built.book.days[2].note)  # both statements stay in the lineage
        only_feed = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8, 9, 10)] + [feed])
        self.assertEqual(only_feed.book.days[-1].value, Fraction(101, 2))  # the same dividend from one source is used (SINGLE_SOURCE does not degrade)

    def test_a_regular_and_a_special_dividend_on_one_ex_date_from_one_source_are_two_dividends_not_a_conflict(self):
        regular, special = dividend(D(2025, 1, 8), "0.50", pay=D(2025, 1, 15)), dividend(D(2025, 1, 8), "2.00", pay=D(2025, 1, 15), sha="44" * 32)
        built = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8)] + [regular, special])
        self.assertEqual(self.values(built)[-1], ("2025-01-08", Fraction(105, 2)))  # (50 + 0.50 + 2.00) / 50 x 50
        both = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8)] + [regular, special,
                          dividend(D(2025, 1, 8), "0.50", source="filing", group="gfiling", sha="33" * 32, pay=D(2025, 1, 15)),
                          dividend(D(2025, 1, 8), "2.00", source="filing", group="gfiling", sha="34" * 32, pay=D(2025, 1, 15))])
        self.assertEqual(self.values(both)[-1], ("2025-01-08", Fraction(105, 2)))  # a source that states both, agreeing with the other: each applied once
        partial = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8)] + [regular, special, dividend(D(2025, 1, 8), "0.50", source="filing", group="gfiling", sha="33" * 32, pay=D(2025, 1, 15))])
        self.assertEqual(self.values(partial)[-1], ("2025-01-08", Fraction(105, 2)))  # the filing lacks the special: that one is SINGLE_SOURCE, used, not a conflict
        disputed = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8)] + [regular, special, dividend(D(2025, 1, 8), "2.50", source="filing", group="gfiling", sha="33" * 32, pay=D(2025, 1, 15))])
        self.assertEqual([d.segment for d in disputed.book.days], [0, 0, 1])  # a different amount for the special is a disagreement: the chain breaks at its ex-date, and neither amount is applied

    # -- Ruling 5.5 (1.7): which statements are one action ------------------------------------------------------------------------------------------------------

    @staticmethod
    def plus_sessions(day, n):
        while n:
            day += datetime.timedelta(days=1)
            n -= day.weekday() < 5
        return day

    def weekday_prints(self, first, last):
        out, day = [], first
        while day <= last:
            if day.weekday() < 5:
                out.append(print_reading(day, "50.00"))
            day += datetime.timedelta(days=1)
        return out

    def two_sided(self, gap):
        feed_ex = D(2025, 1, 8)
        filing_ex = self.plus_sessions(feed_ex, gap)
        feed = dividend(feed_ex, "0.50", pay=feed_ex + datetime.timedelta(days=5))
        filing = dividend(filing_ex, "0.50", source="filing", group="gfiling", sha="33" * 32, pay=filing_ex + datetime.timedelta(days=9))
        return self.build(self.weekday_prints(D(2025, 1, 6), D(2025, 3, 31)) + [feed, filing], end=D(2025, 3, 31)), feed_ex, filing_ex

    def test_unpaired_statements_at_most_20_sessions_apart_are_one_disputed_dividend_and_further_apart_two_dividends(self):
        """(R5-E7 and R5-E8 in the fixture; mutations M-C36 and M-C37.) Sharing no date, 2 and 20 sessions apart: one disputed action, never both applied; 21 apart: two single-source actions, both applied."""
        for gap in (2, 20):
            built, feed_ex, filing_ex = self.two_sided(gap)
            segments = {d.segment for d in built.book.days}
            self.assertEqual(segments, {0, 1, 2}, gap)  # the chain breaks at BOTH ex-dates
            self.assertTrue(all(d.value in (None, Fraction(50)) for d in built.book.days), gap)  # neither dividend is applied: no level above the flat 50
        built, feed_ex, filing_ex = self.two_sided(21)
        self.assertEqual({d.segment for d in built.book.days}, {0})
        after = [d.value for d in built.book.days if d.day >= self.plus_sessions(feed_ex, 21)]
        self.assertEqual(after[-1], Fraction(50) * Fraction(101, 100) * Fraction(101, 100))  # both dividends applied (50.5/50 each)

    def test_a_shared_record_date_makes_one_action_however_far_apart_the_ex_dates_are(self):
        record = D(2025, 1, 2)
        feed_ex = D(2025, 1, 8)
        filing_ex = self.plus_sessions(feed_ex, 40)
        def stated(day, source, group, sha, record_date):
            return action(c.CorporateActionType.CASH_DIVIDEND, day, source, group, sha, amount_per_unit=Money(Decimal("0.50"), USD), pay_date=day + datetime.timedelta(days=3), record_date=record_date)

        shared = self.build(self.weekday_prints(D(2025, 1, 6), D(2025, 3, 31)) + [stated(feed_ex, "feed", "gfeed", "22" * 32, record), stated(filing_ex, "filing", "gfiling", "33" * 32, record)], end=D(2025, 3, 31))
        different = self.build(self.weekday_prints(D(2025, 1, 6), D(2025, 3, 31)) + [stated(feed_ex, "feed", "gfeed", "22" * 32, D(2025, 1, 2)), stated(filing_ex, "filing", "gfiling", "33" * 32, D(2025, 2, 20))], end=D(2025, 3, 31))
        self.assertGreater(len({d.segment for d in shared.book.days}), 1)  # a record date in common: one action, in disagreement
        self.assertEqual({d.segment for d in different.book.days}, {0})  # different record dates and 40 sessions apart: two dividends

    def test_one_sides_own_statements_are_never_matched_with_each_other(self):
        feed_a, feed_b = dividend(D(2025, 1, 8), "0.50", pay=D(2025, 1, 15)), dividend(D(2025, 1, 10), "0.50", pay=D(2025, 1, 17), sha="44" * 32)  # one source, 2 sessions apart
        built = self.build(self.weekday_prints(D(2025, 1, 6), D(2025, 1, 31)) + [feed_a, feed_b], end=D(2025, 1, 31))
        self.assertEqual({d.segment for d in built.book.days}, {0})
        self.assertEqual(built.book.days[-1].value, Fraction(50) * Fraction(101, 100) * Fraction(101, 100))

    def test_an_equal_ratio_split_is_the_same_split_only_within_the_window(self):
        feed = split(D(2025, 1, 8), 2, 1)
        near = split(self.plus_sessions(D(2025, 1, 8), 3), 2, 1, source="filing", group="gfiling", sha="33" * 32)
        far = split(self.plus_sessions(D(2025, 1, 8), 30), 2, 1, source="filing", group="gfiling", sha="33" * 32)
        prints = self.weekday_prints(D(2025, 1, 6), D(2025, 3, 31))
        self.assertGreater(len({d.segment for d in self.build(prints + [feed, near], end=D(2025, 3, 31)).book.days}), 1)
        self.assertEqual({d.segment for d in self.build(prints + [feed, far], end=D(2025, 3, 31)).book.days}, {0})  # a different split a year-like distance apart, both applied

    # -- CP4F-12: a dividend declared in another currency ----------------------------------------------------------------------------------------------------------

    # -- CP4F-12, Ruling 5.5 (1.8): a dividend declared in another currency is CONVERTED into the price currency ----------------------------------------------------------

    def converted(self, items, rate="0.5", missed=0, outcome="FOUND"):
        """`_convert_dividends` over a stand-in port whose ECB cross is `rate` with `missed` fixings missed (the real lookup is the market-data port's; the golden R5-E9 runs it end to end)."""
        from marketdata.port import LookupOutcome  # noqa: PLC0415
        from marketdata.states import InputState  # noqa: PLC0415
        from product_contract.vocabulary import ReasonCode  # noqa: PLC0415

        calls = []

        class Port:
            def fx_on(self, base, quote, day, conventions):
                calls.append((base.code, quote.code, day))
                return SimpleNamespace(rate=Decimal(rate), date_used=day - datetime.timedelta(days=missed), missed_count=missed, consumed=(), outcome=LookupOutcome(outcome))

        def state(lookup):
            if lookup.missed_count >= 5:
                return InputState(SS.INSUFFICIENT_DATA, ReasonCode.MISSING_FX_HISTORY, "5 fixings missed")
            if lookup.missed_count >= 2:
                return InputState(SS.LIMITED, ReasonCode.STALE_DATA, "stale")
            if lookup.missed_count == 1:
                return InputState(SS.AVAILABLE, ReasonCode.STALE_DATA, "stale")
            return InputState(SS.AVAILABLE, None)

        from unittest import mock  # noqa: PLC0415

        with mock.patch("risk.levels.fx_input_state", state):
            return L._convert_dividends(items, "USD", Port(), None), calls

    def item(self, currency="CNY", value="3.60", paid=None, ex=D(2025, 3, 3)):
        return L._Item("CASH_DIVIDEND", ex, ex + datetime.timedelta(days=7), Fraction(value), currency, None, *(paid or (None, None)))

    def test_a_dividend_in_the_price_currency_is_used_as_declared_and_asks_for_no_rate(self):
        (d, notes, spans, breaks, _files), calls = self.converted([self.item("USD", "0.50")])
        self.assertEqual((d, spans, breaks, calls), ({D(2025, 3, 3): Fraction(1, 2)}, [], {}, []))

    def test_a_foreign_dividend_is_converted_at_the_ecb_cross_of_its_ex_date_never_added_unconverted(self):
        (d, notes, spans, breaks, _files), calls = self.converted([self.item("CNY", "3.60")], rate="0.5")
        self.assertEqual(d, {D(2025, 3, 3): Fraction(9, 5)})  # 3.60 x 0.5, never 3.60 added to a USD price (the TR 53.6 of the review)
        self.assertEqual(calls, [("CNY", "USD", D(2025, 3, 3))])  # the ex-date, not the pay date (M-C39)
        self.assertEqual((spans, breaks), ([], {}))  # a fresh fixing: no state attaches
        self.assertIn("converted from CNY 3.6 at the ECB fixing of 2025-03-03", notes[D(2025, 3, 3)])  # the lineage (item 5)

    def test_the_issuers_stated_payment_is_used_as_stated_and_our_fx_is_not_asked(self):
        (d, notes, spans, breaks, _files), calls = self.converted([self.item("CNY", "3.30", paid=("USD", Fraction("0.46")))], rate="0.5")
        self.assertEqual((d, calls), ({D(2025, 3, 3): Fraction(23, 50)}, []))
        self.assertIn("issuer states it paid USD 0.46", notes[D(2025, 3, 3)])
        (d2, *_rest), calls2 = self.converted([self.item("CNY", "3.30", paid=("HKD", Fraction("0.46")))], rate="0.5")  # a payment in ANOTHER currency is not the price currency's
        self.assertEqual((d2, len(calls2)), ({D(2025, 3, 3): Fraction(33, 20)}, 1))

    def test_the_fixings_staleness_attaches_to_the_ratios_spanning_the_ex_date_and_five_missed_gives_no_rate(self):
        expected = {1: (SS.AVAILABLE, "STALE_DATA"), 2: (SS.LIMITED, "STALE_DATA"), 4: (SS.LIMITED, "STALE_DATA")}
        for missed, (state, reason) in expected.items():
            (d, _n, spans, breaks, _f), _calls = self.converted([self.item("CNY", "2.00")], rate="0.5", missed=missed)
            self.assertEqual((d, breaks), ({D(2025, 3, 3): Fraction(1)}, {}), missed)  # the stale rate IS used
            self.assertEqual([(s.ex, s.state, s.reason, s.detail) for s in spans], [(D(2025, 3, 3), state, reason, "")], missed)  # no risk detail is added
        (d, _n, spans, breaks, _f), _calls = self.converted([self.item("CNY", "2.00")], rate="0.5", missed=5)
        self.assertEqual(d, {})  # no rate, no conversion, the dividend is not applied
        self.assertEqual(list(breaks), [D(2025, 3, 3)])
        self.assertEqual(spans, [])  # `build_proxy` turns the break into the INSUFFICIENT_DATA + MISSING_FX_HISTORY span (the exit test's constructed world runs it end to end)

    # -- CP4F-15: which side's stated payment applies is decided by market-data Ruling 4.5 (1.14), not by the order of the statements ------------------------------------

    def cny(self, source, group, sha, paid=None, ex=D(2025, 1, 8)):
        kw = dict(amount_per_unit=Money(Decimal("3.25"), CurrencyCode("CNY")), pay_date=ex + datetime.timedelta(days=7))
        if paid is not None:
            kw.update(paid_currency=USD, paid_amount=Decimal(paid))
        return action(c.CorporateActionType.CASH_DIVIDEND, ex, source, group, sha, **kw)

    def built_with(self, feed_paid, filing_paid):
        statements = [self.cny("feed", "gfeed", "22" * 32, feed_paid), self.cny("filing", "gfiling", "33" * 32, filing_paid)]
        return self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8, 9)] + statements)

    def test_a_payment_stated_by_either_side_alone_is_used_as_stated(self):
        for feed_paid, filing_paid in (("0.44", None), (None, "0.43")):  # R5-E10 and R5-E11: the FILING-only case is the one the statement order hid
            built = self.built_with(feed_paid, filing_paid)
            stated = Fraction(feed_paid or filing_paid)
            self.assertEqual({d.segment for d in built.book.days}, {0}, (feed_paid, filing_paid))
            self.assertEqual(built.book.days[2].value, Fraction(50) * (50 + stated) / 50, (feed_paid, filing_paid))  # TR at the ex print: (50 + stated) / 50 x 50
        both = self.built_with("0.46", "0.46")
        self.assertEqual(both.book.days[2].value, Fraction(5046, 100))  # equal payments: used once

    def test_two_different_stated_payments_are_a_disagreement_and_neither_is_used(self):
        built = self.built_with("0.46", "0.47")  # R5-E12
        self.assertEqual([(d.day.day, d.segment) for d in built.book.days], [(6, 0), (7, 0), (8, 1), (9, 1)])  # the chain breaks at the ex-date
        self.assertTrue(all(d.value == 50 for d in built.book.days))  # no payment applied
        spans = [s for s in built.book.spans if s.ex == D(2025, 1, 8)]
        self.assertEqual([(s.state, s.reason, s.detail) for s in spans], [(SS.INSUFFICIENT_DATA, "SOURCE_CONFLICT", "BENCHMARK_SOURCE_CONFLICT")])

    def test_the_reconciler_compares_the_paid_fields_only_when_both_sides_state_them(self):
        """market-data Ruling 4.5 (1.14): a one-sided statement is a single-source addition to a corroborated dividend, never a disagreement; two statements that differ are a DISAGREEMENT."""
        from marketdata.contracts import ReconciliationStatus as RS  # noqa: PLC0415

        conventions = market11_conventions(CalendarSet([]))
        one_sided = conventions.reconciler.reconcile((self.cny("feed", "gfeed", "22" * 32, "0.44"), self.cny("filing", "gfiling", "33" * 32, None)))
        self.assertEqual(one_sided.status, RS.CORROBORATED)
        same = conventions.reconciler.reconcile((self.cny("feed", "gfeed", "22" * 32, "0.46"), self.cny("filing", "gfiling", "33" * 32, "0.46")))
        self.assertEqual(same.status, RS.CORROBORATED)
        differ = conventions.reconciler.reconcile((self.cny("feed", "gfeed", "22" * 32, "0.46"), self.cny("filing", "gfiling", "33" * 32, "0.47")))
        self.assertEqual(differ.status, RS.DISAGREEMENT)

    def test_two_retrievals_of_one_record_are_one_action(self):
        a, b = dividend(D(2025, 1, 8), "0.50"), dividend(D(2025, 1, 8), "0.50", sha="55" * 32)
        built = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8)] + [a, b])
        self.assertEqual(self.values(built)[-1], ("2025-01-08", Fraction(101, 2)))

    def test_a_split_stated_on_two_dates_is_a_disagreement(self):
        feed, filing = split(D(2025, 1, 7), 2, 1), split(D(2025, 1, 8), 2, 1, source="filing", group="gfiling", sha="33" * 32)
        built = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8)] + [feed, filing])
        self.assertEqual([(d.day.day, d.segment) for d in built.book.days], [(6, 0), (7, 1), (8, 2)])  # broken at both dates; no split is applied (neither statement is settled)

    def test_a_row_that_is_not_a_print_is_not_a_level_and_a_listing_without_prints_has_no_proxy(self):
        built = self.build([print_reading(D(2025, 1, 6), "50.00"), print_reading(D(2025, 1, 7), "60.00", volume="0")])
        self.assertEqual(self.values(built), [("2025-01-06", Fraction(50))])
        self.assertIsNone(self.build([print_reading(D(2025, 1, 6), "50.00", volume="0")]))

    def test_the_series_is_read_up_to_the_end_only(self):
        built = self.build([print_reading(D(2025, 1, d), "50.00") for d in (6, 7, 8)], end=D(2025, 1, 7))
        self.assertEqual([d.day.day for d in built.book.days], [6, 7])


class CheckedResultTests(unittest.TestCase):
    """CP4F-14: a recomputation is checked against the release and the instant (or date) a view declares, in Current mode too."""

    @staticmethod
    def result(release="R1", end=D(2026, 1, 9), currency="USD", current=None):
        series = SimpleNamespace(release_id=release, reporting_currency=currency)
        return SimpleNamespace(manifest=SimpleNamespace(series=series, end=end, current=current))

    def current(self, parent, instant):
        return SimpleNamespace(parent_release_id=parent, instant=instant)

    def test_a_current_mode_result_over_another_release_or_instant_is_refused(self):
        from risk_service import groups as grp  # noqa: PLC0415

        t0, t1 = datetime.datetime(2026, 1, 9, 9, 0, tzinfo=datetime.timezone.utc), datetime.datetime(2026, 1, 12, 9, 0, tzinfo=datetime.timezone.utc)
        good = self.result(release="R1@t", current=self.current("R1", t0))
        self.assertIs(grp._checked(good, "R1", t0, "USD"), good)  # the parent release `M` is what is compared, not `M_t`
        with self.assertRaises(ValueError):
            grp._checked(self.result(release="R2@t", end=D(2026, 1, 12), current=self.current("R2", t1)), "R1", t0, "USD")  # over R2 at 01-12, declared R1 at 01-09
        with self.assertRaises(ValueError):
            grp._checked(self.result(current=self.current("R1", t1)), "R1", t0, "USD")  # the right release, the wrong instant
        with self.assertRaises(ValueError):
            grp._checked(self.result(current=self.current("R2", t0)), "R1", t0, "USD")  # the right instant, the wrong release
        with self.assertRaises(ValueError):
            grp._checked(good, "R1", D(2026, 1, 9), "USD")  # a Current result for a view declared with a date
        with self.assertRaises(ValueError):
            grp._checked(self.result(), "R1", t0, "USD")  # a historical result for a view declared with an instant

    def test_the_historical_checks_still_hold(self):
        from risk_service import groups as grp  # noqa: PLC0415

        ok = self.result()
        self.assertIs(grp._checked(ok, "R1", D(2026, 1, 9), "USD"), ok)
        for bad in (("R2", D(2026, 1, 9), "USD"), ("R1", D(2026, 1, 12), "USD"), ("R1", D(2026, 1, 9), "HKD")):
            with self.assertRaises(ValueError):
                grp._checked(ok, *bad)


class ChainBreakLegTests(unittest.TestCase):
    """Ruling 5.5 (1.6) item 4b on the leg: a ratio of levels in different chains is INSUFFICIENT_DATA + SOURCE_CONFLICT; ratios inside one chain are not touched."""

    def leg(self):
        calendar = k.calendar("C", c.CalendarKind.EXCHANGE_SESSIONS, ("XNYS",), DAYS)
        conventions = SimpleNamespace(freshness=SimpleNamespace(calendars=CalendarSet([calendar])))
        entry = LegOverSourcesTests().entry(source_id="t")
        segments = [0, 0, 1, 1, 1]  # the chain breaks between DAYS[1] and DAYS[2]
        book = L.LevelBook([L.DayLevel(d, Fraction(100 + i), L.PROXY, "", segments[i]) for i, d in enumerate(DAYS)])
        return B.BenchmarkLeg(entry, book, "t", True, (), None, USD, conventions, None)

    def test_a_converted_dividends_fixing_state_attaches_to_exactly_the_ratios_spanning_its_ex_date(self):
        """Ruling 5.5 (1.8) item 4: LIMITED + STALE_DATA (no risk detail) for a ratio across the ex-date; ratios not spanning it are untouched; five missed is INSUFFICIENT_DATA + MISSING_FX_HISTORY."""
        calendar = k.calendar("C", c.CalendarKind.EXCHANGE_SESSIONS, ("XNYS",), DAYS)
        conventions = SimpleNamespace(freshness=SimpleNamespace(calendars=CalendarSet([calendar])))
        entry = LegOverSourcesTests().entry(source_id="t")
        book = L.LevelBook([L.DayLevel(d, Fraction(100 + i), L.PROXY) for i, d in enumerate(DAYS)], [L.Span(DAYS[2], SS.LIMITED, "STALE_DATA", "", "the fixing is 2 stale")])
        leg = B.BenchmarkLeg(entry, book, "t", True, (), None, USD, conventions, None)
        across, before, after = leg.period(DAYS[1], DAYS[3]), leg.period(DAYS[0], DAYS[1]), leg.period(DAYS[2], DAYS[4])  # DAYS[2] is the ex-date: the print ON it is after the break
        self.assertEqual((across.valued.state, across.valued.reason, across.exact is not None), (SS.LIMITED, "STALE_DATA", True))
        self.assertEqual({cause.detail for cause in across.valued.causes}, {""})  # no detail name added
        self.assertEqual((before.valued.state, after.valued.state), (SS.AVAILABLE, SS.AVAILABLE))
        none = L.LevelBook([L.DayLevel(d, Fraction(100 + i), L.PROXY) for i, d in enumerate(DAYS)], [L.Span(DAYS[2], SS.INSUFFICIENT_DATA, "MISSING_FX_HISTORY", "", "no fixing")])
        gone = B.BenchmarkLeg(entry, none, "t", True, (), None, USD, conventions, None).period(DAYS[1], DAYS[3])
        self.assertEqual((gone.valued.state, gone.valued.reason, gone.exact), (SS.INSUFFICIENT_DATA, "MISSING_FX_HISTORY", None))

    def test_a_ratio_spanning_the_break_is_a_source_conflict_and_the_ratios_either_side_are_available(self):
        leg = self.leg()
        across = leg.period(DAYS[1], DAYS[2])
        self.assertEqual((across.valued.state, across.valued.reason, across.exact), (SS.INSUFFICIENT_DATA, S.SOURCE_CONFLICT, None))
        self.assertIn(S.BENCHMARK_SOURCE_CONFLICT, {cause.detail for cause in across.valued.causes})
        before, after = leg.period(DAYS[0], DAYS[1]), leg.period(DAYS[2], DAYS[4])
        self.assertEqual((before.valued.state, after.valued.state), (SS.AVAILABLE, SS.AVAILABLE))
        self.assertEqual((before.exact, after.exact), (Fraction(1, 100), Fraction(2, 102)))
        self.assertEqual(leg.period(DAYS[0], DAYS[4]).valued.state, SS.INSUFFICIENT_DATA)  # a window fact g_0 < x <= g_n
        self.assertEqual([p.state for p in leg.span_parts(DAYS)], [SS.INSUFFICIENT_DATA])  # exactly the one pair that crosses


# --- Current mode on the benchmark leg (Ruling 5.8) -----------------------------------------------------------------------------------------------

class CurrentLegTests(unittest.TestCase):
    """What exists at `t`, and what is missed: a day not yet due is neither used nor counted; a day due but absent from the book is missed."""

    def leg(self, present, instant):
        calendar = k.calendar("C", c.CalendarKind.EXCHANGE_SESSIONS, ("XNYS",), DAYS)
        conventions = SimpleNamespace(freshness=SimpleNamespace(calendars=CalendarSet([calendar])))
        entry = LegOverSourcesTests().entry(source_id="t")
        book = L.LevelBook([L.DayLevel(d, Fraction(100 + i), L.SINGLE_SOURCE) for i, d in enumerate(DAYS) if d in present])
        return B.BenchmarkLeg(entry, book, "t", True, (), None, USD, conventions, instant)

    THU = D(2025, 1, 9)

    def level(self, present, instant):
        return self.leg(present, instant).level_at(self.THU)

    def test_historically_a_missing_day_is_missed_and_stale(self):
        lv = self.level(set(DAYS[:3]), None)
        self.assertEqual((lv.date_used, lv.missed, lv.valued.state, lv.valued.reason), (DAYS[2], 1, SS.AVAILABLE, "STALE_DATA"))

    def test_at_an_instant_before_the_close_the_day_is_not_yet_due_so_not_missed(self):
        t = datetime.datetime(2025, 1, 9, 15, 0, tzinfo=datetime.timezone.utc)  # Thursday's NYSE close is 21:00 UTC
        lv = self.level(set(DAYS[:3]), t)
        self.assertEqual((lv.date_used, lv.missed, lv.valued.state, lv.valued.reason), (DAYS[2], 0, SS.AVAILABLE, None))  # `M_t` / Ruling 5.8 item 5

    def test_after_the_close_a_day_that_is_still_absent_is_missed(self):
        t = datetime.datetime(2025, 1, 9, 22, 0, tzinfo=datetime.timezone.utc)  # due, but not in the data: a late file, the ordinary consequence
        lv = self.level(set(DAYS[:3]), t)
        self.assertEqual((lv.date_used, lv.missed, lv.valued.reason), (DAYS[2], 1, "STALE_DATA"))

    def test_a_level_dated_after_the_instant_does_not_exist_at_it(self):
        t = datetime.datetime(2025, 1, 9, 15, 0, tzinfo=datetime.timezone.utc)
        lv = self.level(set(DAYS[:4]), t)  # the book holds Thursday's level, which is published at 21:00 UTC: it must not be read at 15:00
        self.assertEqual((lv.date_used, lv.missed, lv.level), (DAYS[2], 0, Fraction(102)))  # M-C1: reading it by date would be a look-ahead
        self.assertEqual(self.level(set(DAYS[:4]), None).date_used, DAYS[3])  # historically it is used

    def test_a_withheld_day_is_a_source_conflict_not_a_skipped_day(self):
        calendar = k.calendar("C", c.CalendarKind.EXCHANGE_SESSIONS, ("XNYS",), DAYS)
        conventions = SimpleNamespace(freshness=SimpleNamespace(calendars=CalendarSet([calendar])))
        book = L.LevelBook([L.DayLevel(DAYS[2], Fraction(102), L.SINGLE_SOURCE), L.DayLevel(DAYS[3], None, L.DISAGREEMENT, "sa=1; sb=2")])
        leg = B.BenchmarkLeg(LegOverSourcesTests().entry(source_id="t"), book, "t", True, (), None, USD, conventions)
        lv = leg.level_at(self.THU)
        self.assertEqual((lv.valued.state, lv.valued.reason, lv.details, lv.translated), (SS.INSUFFICIENT_DATA, "SOURCE_CONFLICT", ("BENCHMARK_SOURCE_CONFLICT",), None))
        self.assertEqual(leg.level_at(D(2025, 1, 8)).valued.state, SS.AVAILABLE)  # the day before it is unaffected


# --- the default view (Ruling 7.7 (1.2)) ----------------------------------------------------------------------------------------------------------

class DefaultViewTests(unittest.TestCase):
    def test_the_trigger_set_is_exactly_the_four_history_refusals(self):
        self.assertEqual(dv.HISTORY_REFUSALS, {S.WINDOW_BEFORE_INCEPTION, S.WINDOW_BEFORE_SNAPSHOT, S.PERIOD_INSUFFICIENT, S.ZERO_CAPITAL_PERIOD})
        self.assertEqual((dv.DEFAULT_REQUEST.rule.value, dv.DEFAULT_REQUEST.months), ("TRAILING_MONTHS", 36))

    def test_an_active_return_refused_by_its_portfolio_leg_is_a_history_refusal_whatever_the_performance_detail(self):
        """Ruling 7.7 (1.6) (CP4F-10; mutation M-C35): the leg's own state is read from the lineage, never a detail name; a benchmark-side cause with a sound leg is never a trigger."""
        def active(leg_state, state=SS.INSUFFICIENT_DATA, details=()):
            return SimpleNamespace(state=state, details=details, lineage=(("portfolio_leg_state", leg_state),))

        self.assertTrue(dv.falls_back(active("INSUFFICIENT_DATA")))  # SPLIT_NOT_APPLIED, a valuation stale by 5 or more, NON_POSITIVE_BASE: none of them is a risk detail name
        self.assertTrue(dv.falls_back(active("INSUFFICIENT_DATA", details=(S.BENCHMARK_SOURCE_CONFLICT,))))  # the leg is a history cause even when a benchmark cause is also there
        self.assertFalse(dv.falls_back(active("AVAILABLE", details=(S.BENCHMARK_SOURCE_CONFLICT,))))
        self.assertFalse(dv.falls_back(active("AVAILABLE", details=("NO_BENCHMARK_SELECTED",))))
        self.assertFalse(dv.falls_back(active("LIMITED", details=("BENCHMARK_STALE",))))
        self.assertFalse(dv.falls_back(active("INSUFFICIENT_DATA", state=SS.LIMITED)))  # only a refused result falls back
        self.assertFalse(dv.falls_back(SimpleNamespace(state=SS.INSUFFICIENT_DATA, details=("NO_BENCHMARK_SELECTED",), lineage=())))  # a metric with no portfolio leg and no history detail: shown as it is

    def metric(self, part, prefix, aid, kind, metric_id):
        r = g.shared_runner(part)
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith(prefix)]
        a = next(a for a in p["assertions"] if a["id"] == aid)
        item = next(i for i in a["expect"] if i["kind"] == kind)
        return r, p, a, item

    def view(self, part, prefix, aid, kind):
        r, p, a, item = self.metric(part, prefix, aid, kind, None)
        return g.run_default_view(r, p, a, dict(item, metric=item["kind"] if "metric" not in item else item["metric"], default_request={"rule": "TRAILING_MONTHS", "months": 36}))[0]

    def test_a_degenerate_benchmark_is_not_a_history_refusal_so_there_is_no_fallback(self):
        # R1: a FLAT benchmark: beta over the 3Y request is INSUFFICIENT_DATA + ZERO_BENCHMARK_VARIANCE; MAX_AVAILABLE would be refused for the same cause, so the view shows the 3Y result
        view = self.view(3, "R1 ", "R1-F1", "beta")
        self.assertFalse(view.fallback)
        self.assertIsNone(view.refused)
        self.assertIsNone(view.y)

    def test_a_missing_benchmark_never_triggers_the_fallback(self):
        r = g.shared_runner(3)
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("R6 ")]
        a = next(a for a in p["assertions"] if a["id"] == "R6-V0")
        item = next(i for i in a["expect"] if i["kind"] == "default_view")
        view, _ = g.run_default_view(r, p, a, item)
        self.assertEqual((view.fallback, view.shown.state, view.shown.result.reason_code.value), (False, SS.INSUFFICIENT_DATA, "MISSING_BENCHMARK"))

    def test_a_fallback_shows_the_substitute_whatever_its_state_and_keeps_the_refusal_and_both_digests(self):
        r = g.shared_runner(3)
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("R9 ")]
        a = next(a for a in p["assertions"] if a["id"] == "R9-Z1")
        item = next(i for i in a["expect"] if i["kind"] == "default_view")
        view, _ = g.run_default_view(r, p, a, item)
        self.assertTrue(view.fallback)
        self.assertEqual((view.shown.state, view.refused.state), (SS.INSUFFICIENT_DATA, SS.INSUFFICIENT_DATA))  # Y may itself be INSUFFICIENT_DATA: no number is promised (P5)
        self.assertEqual(view.shown.observation_count, 40)
        self.assertIn("WINDOW_BEFORE_INCEPTION", view.refused.details)  # the 3Y refusal stays in the evidence
        ev = view.evidence()
        self.assertEqual((ev["fallback"], ev["x_result_digest"] == ev["y_result_digest"]), (True, False))
        self.assertEqual(ev["x_manifest_id"], view.x.manifest.manifest_id)
        self.assertEqual(ev["y_manifest_id"], view.y.manifest.manifest_id)
        self.assertNotEqual(view.x.manifest.request_rule, view.y.manifest.request_rule)  # each is an ordinary result of its own question, and reproduces on its own

    def test_a_fallback_happens_only_when_the_default_request_is_refused_for_history(self):
        calls = []

        class FakeMetric:
            def __init__(self, state, details):
                self.state, self.details, self.lineage = state, details, ()

        class FakeResult:
            def __init__(self, state, details):
                self.m = FakeMetric(state, details)

            def metric(self, _id):
                return self.m

        def run(state, details):
            def compute(request):
                calls.append(request)
                return FakeResult(state, details)

            calls.clear()
            return dv.default_view(compute, "m"), list(calls)

        view, seen = run(SS.INSUFFICIENT_DATA, ("INSUFFICIENT_OBSERVATIONS",))
        self.assertFalse(view.fallback)
        self.assertEqual(len(seen), 1)  # M-C12 (always fall back) would ask twice
        view, seen = run(SS.LIMITED, ("PERIOD_INSUFFICIENT",))
        self.assertFalse(view.fallback)  # a LIMITED result is never refused, whatever its details
        for detail in sorted(dv.HISTORY_REFUSALS):
            view, seen = run(SS.INSUFFICIENT_DATA, (detail,))
            self.assertTrue(view.fallback, detail)  # M-C13 (never fall back) would not
            self.assertEqual(len(seen), 2)


if __name__ == "__main__":
    unittest.main()
