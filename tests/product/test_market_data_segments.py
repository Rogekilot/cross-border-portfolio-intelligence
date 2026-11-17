"""CP4M-7: `market-data/1.12` Ruling 0.1 (1.12), segments in the RELEASE BUILD for every kind (tech plan 17.18).

Several files of one series are admitted as segments only when their declared COVERAGE intervals are disjoint, they share one identity, the series is vintage-stable and each file passes its own checks. Overlapping
coverage is refused even when the values agree, and a vintage label is never part of the series key. This module runs

- the Quant's five release cases `cp4_golden/1.3-part3` `release_cases` (RB-1 to RB-5) against the engine, both by the cut (`MarketDataRelease.from_manifests`) and by the build of a directly constructed release;
- the reviewer's demonstrations (CP4M-7): a backfill at a segment edge, and an anchor-labelled overlapping re-download of prices and of risk-free rates, agreeing and backfilling;
- the pure rule (`marketdata.segments`).
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import cp4_golden_kit as g  # noqa: E402
import marketdata_exit_kit as x  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402
from domain.currency import CurrencyCode  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata import segments as S  # noqa: E402
from marketdata.adapters.alphavantage import AlphaVantageQuoteAdapter  # noqa: E402
from marketdata.adapters.base import AdapterRegistry  # noqa: E402
from marketdata.adapters.calendar_file import CalendarFileAdapter  # noqa: E402
from marketdata.adapters.synthetic_risk_free import PAYLOAD_FORMAT as RF_FORMAT, SOURCE_ID as RF_SOURCE, SyntheticRiskFreeAdapter, make_risk_free_payload  # noqa: E402
from marketdata.canonical import sha256_hex  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import IngestError, build_in_memory_market_data  # noqa: E402
from marketdata.manifest import DataKind, MarketDataRelease, SourceRecord, TwoVintagesError  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402
from domain.instrument import SecurityType  # noqa: E402

D = datetime.date
UTC = datetime.timezone.utc
USD = CurrencyCode("USD")
PART3 = g.load_part(3)
CASES = PART3["release_cases"]["cases"]
LISTING = "c4000000-0000-4000-8000-000000000042"
CALENDAR_ID = "SYN4_NYSE"
EXCHANGE_SOURCE = x.SRC_US


def utc(text: str) -> datetime.datetime:
    return g._utc(text)


class World:
    """One SYN42 listing on the part's own NYSE calendar, and the files a case describes. `declare` writes each file's coverage into its request (`start`, `end`); without it the build derives the coverage
    from the rows and the calendar alone (Ruling 0.1 (1.12) item 1)."""

    def __init__(self, test: unittest.TestCase, adjusted: bool = False):
        tmp = tempfile.TemporaryDirectory()
        test.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.adjusted = adjusted
        md = PART3["market_data"]
        cal = next(cc for cc in md["calendars"] if cc["calendar_id"] == CALENDAR_ID)
        self.days = g.calendar_dates(cal)
        spec = next(s for s in md["prices"]["series"] if s["listing_id"] == LISTING)
        closes = g.expand_steps(spec["steps"], spec.get("cycle"), "closes", "close")
        gap = {D.fromisoformat(d) for d in spec["gaps"]}
        self.series = [(d, g.value_on(closes, d), 1000) for d in self.days if D.fromisoformat(spec["first"]) <= d <= D.fromisoformat(spec["last"]) and d not in gap]
        x.kit.write_registry(self.root, extra=x.synthetic_registry_records() + [SourceRecord(RF_SOURCE, RF_SOURCE, "synthetic", "synthetic.riskfree", synthetic=True)])
        self.manifests = [g._write_file(self.root, utc("2026-04-01T00:00:00Z"), x.SRC_CAL, DataKind.CALENDAR, "finweb_calendar_json/1", g.calendar_payload(cal, self.days), CALENDAR_ID, "json",
                                        identifiers=(CALENDAR_ID,))]
        self.ids = cp1.Ids(randomize=False)
        feed = iter([uuid.uuid5(uuid.NAMESPACE_URL, "seg:issuer"), uuid.uuid5(uuid.NAMESPACE_URL, "seg:instrument"), self.ids(LISTING)])
        self.ident = InMemoryIdentityRegistry(lambda: next(feed))
        self.ident.register_instruments([InstrumentEntry("Synthetic issuer SYN42", SecurityType("COMMON_STOCK"), "XNYS", "XNYS", "SYN42", USD, vendor_ids=((x.SRC_US, "SYN42"),))])
        self.adapters = AdapterRegistry([CalendarFileAdapter(), AlphaVantageQuoteAdapter(x.SRC_US), SyntheticRiskFreeAdapter()])
        self.seen: set = set()

    def rows_of(self, spec) -> list:
        if spec["rows"] == "series":
            window = [D.fromisoformat(d) for d in (spec["coverage"] if spec["coverage"] is not None else spec["rows_range"])]
            rows = [r for r in self.series if window[0] <= r[0] <= window[1]]
        else:
            rows = [(D.fromisoformat(d), close, 1000) for d, close in spec["rows"].items()]
        extra = [(D.fromisoformat(d), close, 1000) for d, close in spec.get("extra_rows", {}).items()]  # rows the file ALSO holds, outside what it declares (RB-6, RB-7, RB-9)
        return sorted(rows + extra)

    def write(self, label, rows, retrieved, coverage=None, status=c.AdjustmentStatus.RAW, anchor=None, synthetic=True):
        """`coverage` is the request: `(start, end)`, either may be None (a start-only request leaves the end to the retrieval time); None states no request at all."""
        request = (("function", "TIME_SERIES_DAILY"), ("outputsize", "compact"))
        if coverage is not None:
            if coverage[0] is not None:
                request += (("start", coverage[0].isoformat()),)
            if coverage[1] is not None:
                request += (("end", coverage[1].isoformat()),)
        payload = g._distinct_payload(x.av_us_csv(rows), self.seen)
        m = g._write_file(self.root, retrieved, x.SRC_US, DataKind.QUOTE, "alphavantage_csv_daily/1", payload, label, "csv", currency=USD, adjustment=status, identifiers=("SYN42",), request=request, market="US",
                          anchor=anchor, usage_scope=c.UsageScope.SYNTHETIC_TEST if synthetic else c.UsageScope.INTERNAL_DEVELOPMENT_ONLY)
        self.manifests.append(m)
        return m

    def write_case(self, case, declare: bool):
        for f in case["files"]:
            coverage = tuple(D.fromisoformat(d) for d in f["coverage"]) if declare and f["coverage"] is not None else None  # RB-8's V2 states none, declared or not
            self.write(f["file"], self.rows_of(f), utc(f["retrieval_time"]), coverage, c.AdjustmentStatus(f["adjustment_status"]), f["anchor"], f["synthetic"])

    def cut(self):
        return MarketDataRelease.from_manifests("seg", self.manifests, [])

    def direct(self):
        """A release constructed without the cut (the build must refuse on its own: the cut is a convenience, not the gate)."""
        return MarketDataRelease(name="seg-direct", files=tuple(sorted({m.file_sha256 for m in self.manifests})), source_precedence=())

    def build(self, release, **kw):
        files = FileStore(self.root)
        return build_in_memory_market_data(release, files, files.load_registry(), self.adapters, self.ident, **dict({"catalog_calendars": {}}, **kw))


def outcome(call) -> tuple:
    """`(outcome name, overlap)` of a release build or cut that raises a `SegmentError`; ADMITTED when it does not."""
    try:
        call()
    except S.SegmentError as e:
        return e.outcome, None if e.overlap is None else tuple(d.isoformat() for d in e.overlap)
    return S.ADMITTED, None


class ReleaseCaseTests(unittest.TestCase):
    """The Quant's RB-1 to RB-5 (`release_cases`), judged on the SERIES KEY of SYN42."""

    def expected(self, case):
        e = case["expected"]
        return e["outcome"], None if e["overlap"] is None else tuple(e["overlap"])

    #: what the CUT can say: the manifests declare intervals and show no rows, so a stray row is invisible to it (the build is the gate for those); a file that states no interval cannot be shown disjoint
    CUT_SEES_NO_ROWS = {"RB-6": S.ADMITTED, "RB-7": S.ADMITTED, "RB-9": S.ADMITTED}

    def test_the_part_declares_nine_cases_with_the_seven_mutations(self):
        self.assertEqual([c_["id"] for c_ in CASES], [f"RB-{i}" for i in range(1, 10)])
        self.assertEqual(sorted(PART3["release_cases"]["mutation_catalog"]), [f"M-R{i}" for i in range(1, 8)])

    def test_every_case_by_the_cut_with_the_coverage_declared(self):
        for case in CASES:
            with self.subTest(case["id"]):
                w = World(self, adjusted=case["id"] == "RB-4")
                w.write_case(case, declare=True)
                want = self.expected(case)
                want = (self.CUT_SEES_NO_ROWS.get(case["id"], want[0]), None if case["id"] in self.CUT_SEES_NO_ROWS else want[1])
                self.assertEqual(outcome(w.cut), want, case["id"])

    def test_every_case_by_the_build_of_a_release_that_was_not_cut(self):
        # RB-5 is refused at the cut (identity); a real-scope file of a synthetic SOURCE is refused earlier still by the source gate when the build reads it (Ruling 4.8 and the registry), so the engine's refusal of that
        # file set is an `IngestError` and not a `SegmentError`: the identity rule itself is run below on the exact RB-5 files
        for case in CASES:
            if case["id"] == "RB-5":
                continue
            w = World(self, adjusted=case["id"] == "RB-4")
            w.write_case(case, declare=True)
            self.assertEqual(outcome(lambda: w.build(w.direct())), self.expected(case), case["id"])

    def test_without_a_declared_request_a_series_in_several_files_has_no_coverage_to_show_disjoint_1_13(self):
        # market-data Ruling 0.1 (1.13) item 1(b): "first row held" is a start for a FULL-HISTORY file only; the content never defines its own claim, so a file with no requested start is refused
        for case in CASES:
            if case["id"] in ("RB-4", "RB-5", "RB-8"):
                continue  # identity and segmentability come first; RB-8 states none by design
            w = World(self)
            w.write_case(case, declare=False)
            self.assertEqual(outcome(lambda: w.build(w.direct()))[0], S.REFUSED_COVERAGE_UNDETERMINED, case["id"])
            self.assertEqual(outcome(w.cut)[0], S.REFUSED_COVERAGE_UNDETERMINED, case["id"])
        w = World(self, adjusted=True)
        w.write_case(next(cc for cc in CASES if cc["id"] == "RB-4"), declare=False)
        self.assertEqual(outcome(lambda: w.build(w.direct()))[0], S.REFUSED_NOT_SEGMENTABLE)

    def test_rb6_to_rb9_the_stray_row_is_refused_never_ignored_never_widened_to_the_hull(self):
        # M-R6 would ignore the row (two readings of 2025-06-13, RB-2 back); M-R5 would widen V2's coverage to the hull (a fabricated overlap 2025-06-13..2026-01-08 in RB-6, and RB-9's row ADMITTED)
        for case_id, stray in (("RB-6", D(2025, 6, 13)), ("RB-7", D(2026, 1, 9)), ("RB-9", D(2026, 1, 9))):
            case = next(cc for cc in CASES if cc["id"] == case_id)
            w = World(self)
            w.write_case(case, declare=True)
            with self.assertRaises(S.SegmentRowsOutsideCoverageError, msg=case_id) as caught:
                w.build(w.direct())
            self.assertEqual((caught.exception.outcome, caught.exception.overlap), ("REFUSED_ROW_OUTSIDE_COVERAGE", None), case_id)
            self.assertIn(stray.isoformat(), str(caught.exception))
            self.assertIsInstance(caught.exception, TwoVintagesError)

    def test_rb8_a_segment_that_states_no_coverage_is_refused_not_given_the_hull_of_its_rows(self):
        case = next(cc for cc in CASES if cc["id"] == "RB-8")
        w = World(self)
        w.write_case(case, declare=True)
        self.assertEqual(outcome(lambda: w.build(w.direct()))[0], S.REFUSED_COVERAGE_UNDETERMINED)
        self.assertEqual(outcome(w.cut)[0], S.REFUSED_COVERAGE_UNDETERMINED)

    def test_rb5_a_real_file_among_synthetic_segments_is_refused_by_the_build_too(self):
        case = next(cc for cc in CASES if cc["id"] == "RB-5")
        w = World(self)
        w.write_case(case, declare=True)
        with self.assertRaises((S.SegmentError, IngestError)):
            w.build(w.direct())

    def test_rb1_admitted_is_one_series_with_every_row_once_and_every_file_cited(self):
        case = CASES[0]
        w = World(self)
        w.write_case(case, declare=True)
        for release in (w.cut(), w.direct()):
            built = w.build(release)
            series = built.store.quotes(w.ids(LISTING), D(2022, 12, 1), D(2026, 3, 31))
            days = [r.observation.value_date for r in series.readings]
            self.assertEqual(days, [r[0] for r in w.series])  # one reading per date, in date order
            self.assertEqual(len(series.consumed), case["expected"]["segments"])
            self.assertNotIn(D(2025, 6, 13), days)  # no print that day
            lookup = built.store.quote_on(w.ids(LISTING), D(2026, 1, 9), market11_conventions(built.calendars))
            self.assertEqual(lookup.outcome.value, "FOUND")

    def test_the_overlap_the_build_names_is_the_union_of_the_shared_intervals(self):
        for case in CASES:
            if case["expected"]["outcome"] != "REFUSED_OVERLAP":
                continue
            w = World(self)
            w.write_case(case, declare=True)
            with self.assertRaises(S.SegmentOverlapError) as caught:
                w.build(w.direct())
            self.assertEqual(tuple(d.isoformat() for d in caught.exception.overlap), tuple(case["expected"]["overlap"]), case["id"])
            self.assertIsInstance(caught.exception, TwoVintagesError)  # the family of Ruling 0.1


class DemonstrationTests(unittest.TestCase):
    """The reviewer's CP4M-7 scenarios, on prices."""

    def two_files(self, w, first_rows, second_rows, first_cov=None, second_cov=None, **second):
        w.write("a", first_rows, utc("2026-01-09T00:00:00Z"), first_cov)
        return w.write("b", second_rows, utc("2026-01-09T22:00:00Z"), second_cov, **second)

    def test_a_backfill_at_a_segment_edge_is_refused_not_merged(self):
        # V1 is retrieved after the 2026-01-08 close and has no row on 01-07 or 01-08; V2 holds 01-07..01-09. The points are disjoint; the coverage is not: V1 SAID "no print" for 01-07 and 01-08
        w = World(self)
        by_day = {r[0]: r for r in w.series}
        v1 = [by_day[d] for d in sorted(by_day) if D(2025, 12, 1) <= d <= D(2026, 1, 6)]
        v2 = [by_day[d] for d in (D(2026, 1, 7), D(2026, 1, 8), D(2026, 1, 9))]
        self.two_files(w, v1, v2, (D(2025, 12, 1), None), (D(2026, 1, 7), None))  # each states a start; the ends are what was available at each retrieval (V1: 01-08)
        self.assertEqual(outcome(lambda: w.build(w.direct())), (S.REFUSED_OVERLAP, ("2026-01-07", "2026-01-08")))

    def test_the_same_edge_with_the_first_file_declaring_it_only_asked_to_01_06_is_a_segment(self):
        # the requester's declaration is what makes it disjoint: V1 asked for nothing after 01-06, so it says nothing about 01-07 and 01-08
        w = World(self)
        by_day = {r[0]: r for r in w.series}
        v1 = [by_day[d] for d in sorted(by_day) if D(2025, 12, 1) <= d <= D(2026, 1, 6)]
        v2 = [by_day[d] for d in (D(2026, 1, 7), D(2026, 1, 8), D(2026, 1, 9))]
        self.two_files(w, v1, v2, (D(2025, 12, 1), D(2026, 1, 6)), (D(2026, 1, 7), D(2026, 1, 9)))
        built = w.build(w.cut())
        self.assertEqual(len(built.store.quotes(w.ids(LISTING), D(2025, 12, 1), D(2026, 1, 9)).consumed), 2)

    def test_an_anchor_labelled_overlapping_redownload_of_raw_prices_is_refused_agreeing_or_backfilling(self):
        w = World(self)
        v1 = [r for r in w.series if r[0] <= D(2026, 1, 8)]
        agreeing = list(v1)
        scaled = [(d, str(float(close) * 1.5), n) for d, close, n in v1]
        backfill = list(v1) + [(D(2025, 6, 13), "101.00", 1000)]
        for label, again in (("agreeing", agreeing), ("scaled by 1.5", scaled), ("backfilling a no-print date", sorted(backfill))):
            for anchor in (None, "VINTAGE_LABEL"):
                with self.subTest(label, anchor=anchor):
                    w = World(self)
                    start = (v1[0][0], None)  # a start each (a segment states one: market-data Ruling 0.1 (1.13) 1(b)); the end is what was available
                    w.write("a", v1, utc("2026-01-09T00:00:00Z"), start)
                    w.write("b", again, utc("2026-01-09T00:00:00Z") + datetime.timedelta(days=1), start, anchor=anchor)
                    got = outcome(lambda: w.build(w.direct()))
                    # the same anchor (none): two vintages of the same dates; a label in the anchor: a difference of IDENTITY, because no label may sit in a key field. Both are refused at the build.
                    self.assertEqual(got[0], S.REFUSED_OVERLAP if anchor is None else S.REFUSED_IDENTITY, (label, anchor))
                    self.assertEqual(outcome(w.cut)[0], S.REFUSED_COVERAGE_UNDETERMINED if anchor is None else S.REFUSED_IDENTITY, (label, anchor, "cut"))  # the manifests declare no interval to prove disjoint

    def test_a_raw_file_that_declares_an_anchor_is_one_series_with_the_others_not_a_new_series(self):
        # the key carries the anchor only for a vendor-adjusted series (Ruling 2.3); a label on a raw file cannot move it into a series of its own
        w = World(self)
        m1 = w.write("a", w.series[:5], utc("2026-04-01T00:00:00Z"))
        m2 = w.write("b", w.series[5:9], utc("2026-04-01T00:00:00Z"), anchor="V2")
        self.assertEqual(m1.series_keys(), m2.series_keys())

    def test_a_series_in_several_files_whose_coverage_cannot_be_stated_is_refused(self):
        # no calendar governs the exchange in this world: the end of the first file's coverage is unbounded, so it cannot be shown disjoint
        w = World(self)
        w.manifests = w.manifests[1:]  # no calendar file
        w.write("a", w.series[:5], utc("2026-04-01T00:00:00Z"))
        w.write("b", w.series[5:9], utc("2026-04-01T00:00:00Z"))
        self.assertEqual(outcome(lambda: w.build(w.direct()))[0], S.REFUSED_COVERAGE_UNDETERMINED)
        self.assertEqual(outcome(w.cut)[0], S.REFUSED_COVERAGE_UNDETERMINED)  # the manifests declare no request interval either

    def test_the_cut_refuses_declared_intervals_that_touch_and_admits_adjacent_ones(self):
        # [.., 01-08] and [01-08, ..] share 01-08; [.., 01-08] and [01-09, ..] share nothing
        by_day = {r[0]: r for r in World(self).series}
        for first_end, second_start, want in ((D(2026, 1, 8), D(2026, 1, 8), S.REFUSED_OVERLAP), (D(2026, 1, 8), D(2026, 1, 9), S.ADMITTED)):
            w = World(self)
            w.write("a", [by_day[d] for d in sorted(by_day) if D(2025, 12, 1) <= d <= first_end], utc("2026-01-09T00:00:00Z"), (D(2025, 12, 1), first_end))
            w.write("b", [by_day[d] for d in sorted(by_day) if second_start <= d <= D(2026, 1, 15)], utc("2026-04-01T00:00:00Z"), (second_start, D(2026, 1, 15)))
            self.assertEqual(outcome(w.cut)[0], want, (first_end, second_start))
            self.assertEqual(outcome(lambda: w.build(w.direct()))[0], want, (first_end, second_start, "build"))

    def test_one_file_never_needs_a_coverage(self):
        w = World(self)
        w.manifests = w.manifests[1:]
        w.write("a", w.series[:5], utc("2026-04-01T00:00:00Z"))
        self.assertEqual(outcome(w.cut)[0], S.ADMITTED)


class RiskFreeSegmentTests(unittest.TestCase):
    """The same rule for risk-free rates: a rate-publication calendar bounds each file's coverage, and a REVISED series is never segmented."""

    SERIES = "SYN4_UST13_USD"

    def world(self, files, revision="NOT_REVISED", declare=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        md = PART3["market_data"]
        s = next(s for s in md["risk_free"]["series"] if s["series_id"] == self.SERIES)
        cal = next(cc for cc in md["calendars"] if cc["calendar_id"] == s["calendar"])
        days = g.calendar_dates(cal)
        rates = g.expand_steps(s["steps"], s.get("cycle"), "rates", "rate")
        gap = {D.fromisoformat(d) for d in s["gaps"]}
        everything = [{"date": d.isoformat(), "rate": g.value_on(rates, d)} for d in days if D.fromisoformat(s["first"]) <= d <= D.fromisoformat(s["last"]) and d not in gap]
        x.kit.write_registry(root, extra=x.synthetic_registry_records() + [SourceRecord(RF_SOURCE, RF_SOURCE, "synthetic", "synthetic.riskfree", synthetic=True)])
        manifests = [g._write_file(root, utc("2026-04-01T00:00:00Z"), x.SRC_CAL, DataKind.CALENDAR, "finweb_calendar_json/1", g.calendar_payload(cal, days), cal["calendar_id"], "json",
                                   identifiers=(cal["calendar_id"],))]
        seen: set = set()
        for label, first, last, retrieved, anchor, scale, *rest in files:
            extra = set(rest[0]) if rest else set()  # dates the file ALSO holds, outside what it declares (CP4M-10)
            part = [dict(p, rate=str(float(p["rate"]) * scale)) if scale != 1 else p for p in everything if first <= D.fromisoformat(p["date"]) <= last or D.fromisoformat(p["date"]) in extra]
            payload = make_risk_free_payload(({"series_id": s["series_id"], "name": s["instrument"], "provider": "synthetic", "instrument": s["instrument"], "tenor_weeks": round(s["tenor_days"] / 7),
                                               "quote_type": s["quote_type"], "day_count_basis": s["day_count_basis"], "unit": s["unit"], "decimals_published": 2,
                                               "date_semantics": "the date the quote is FOR (synthetic)", "calendar_id": s["calendar"], "revision_policy": revision, "points": part},))
            if sha256_hex(payload) in seen:  # an agreeing re-download: the same content, different bytes (a file is identified by its hash)
                payload = json.dumps(json.loads(payload), indent=1).encode("utf-8")
            seen.add(sha256_hex(payload))
            request = (("start", first.isoformat()), ("end", last.isoformat())) if declare else (("start", first.isoformat()),)  # a segment states its start (Ruling 0.1 (1.13) 1(b)); the end is what was available
            manifests.append(g._write_file(root, retrieved, RF_SOURCE, DataKind.RISK_FREE, RF_FORMAT, payload, label, "json", currency=USD, identifiers=(s["series_id"],), request=request, anchor=anchor))
        return root, manifests

    def build(self, root, manifests):
        release = MarketDataRelease(name="rf-seg", files=tuple(sorted({m.file_sha256 for m in manifests})), source_precedence=(RF_SOURCE,))
        files = FileStore(root)
        return build_in_memory_market_data(release, files, files.load_registry(), AdapterRegistry([CalendarFileAdapter(), SyntheticRiskFreeAdapter()]), InMemoryIdentityRegistry(lambda: uuid.uuid4()), catalog_calendars={})

    def test_disjoint_segments_make_one_series_with_every_point_once(self):
        root, ms = self.world([("a", D(2025, 1, 1), D(2026, 1, 8), utc("2026-01-09T00:00:00Z"), None, 1), ("b", D(2026, 1, 9), D(2026, 3, 31), utc("2026-04-01T00:00:00Z"), None, 1)])
        built = self.build(root, ms)
        got = built.store.risk_free_series(USD, D(2025, 1, 1), D(2026, 3, 31))
        self.assertEqual((got.outcome.value, len(got.consumed)), ("FOUND", 2))
        dates = [p.value_date for p in got.series[0].points]
        self.assertEqual(dates, sorted(set(dates)))

    def test_a_backfill_at_the_edge_is_refused(self):
        # V1 retrieved after the 01-08 publication but holding no row from 01-07; V2 from 01-07: V1 said "no quote" for 01-07 and 01-08
        root, ms = self.world([("a", D(2025, 1, 1), D(2026, 1, 6), utc("2026-01-09T00:00:00Z"), None, 1), ("b", D(2026, 1, 7), D(2026, 3, 31), utc("2026-04-01T00:00:00Z"), None, 1)])
        got = outcome(lambda: self.build(root, ms))
        self.assertEqual(got[0], S.REFUSED_OVERLAP)
        self.assertEqual(got[1][0], "2026-01-07")

    def test_an_overlapping_redownload_is_refused_even_when_the_rates_agree_and_with_a_label_in_the_anchor(self):
        for anchor, want in ((None, S.REFUSED_OVERLAP), ("V2", S.REFUSED_IDENTITY)):
            for scale in (1, 3):
                with self.subTest(anchor=anchor, scale=scale):
                    root, ms = self.world([("a", D(2025, 6, 1), D(2026, 1, 8), utc("2026-01-09T00:00:00Z"), None, 1), ("b", D(2025, 6, 1), D(2026, 1, 8), utc("2026-01-10T00:00:00Z"), anchor, scale)], declare=True)
                    self.assertEqual(outcome(lambda: self.build(root, ms))[0], want)
                    self.assertEqual(outcome(lambda: MarketDataRelease.from_manifests("x", ms, []))[0], want)

    def test_a_series_the_publisher_revises_is_never_segmented(self):
        for revision in ("REVISED", "UNKNOWN"):
            root, ms = self.world([("a", D(2025, 1, 1), D(2026, 1, 8), utc("2026-01-09T00:00:00Z"), None, 1), ("b", D(2026, 1, 9), D(2026, 3, 31), utc("2026-04-01T00:00:00Z"), None, 1)], revision=revision)
            self.assertEqual(outcome(lambda: self.build(root, ms))[0], S.REFUSED_NOT_SEGMENTABLE, revision)


class PureRuleTests(unittest.TestCase):
    """`marketdata.segments`: the rule on its own, with the Quant's M-R1 to M-R4 as the tests that must fail under each mutation."""

    SHA = lambda self, n: f"{n:064x}"  # noqa: E731

    def seg(self, n, coverage, identity=(("synthetic", True),), segmentable=True, when="2026-01-09T00:00:00Z", outside=()):
        cov = None if coverage is None else (D.fromisoformat(coverage[0]), D.fromisoformat(coverage[1]))
        return S.FileSegment(self.SHA(n), utc(when), cov, identity, segmentable, tuple(D.fromisoformat(d) for d in outside))

    def test_m_r5_m_r6_a_row_outside_the_declared_coverage_is_refused_neither_ignored_nor_widened_to_the_hull(self):
        # RB-6: V2 [01-09, 01-09] holds a 2025-06-13 row; V1 covers 06-13. Ignoring the row (M-R6) admits the files; widening V2 to the hull (M-R5) would refuse with a FABRICATED overlap, not this defect
        files = [self.seg(1, ("2022-12-01", "2026-01-08")), self.seg(2, ("2026-01-09", "2026-01-09"), outside=("2025-06-13",)), self.seg(3, ("2026-01-10", "2026-03-31"))]
        with self.assertRaises(S.SegmentRowsOutsideCoverageError) as caught:
            S.admit_segments("k", files)
        self.assertIsNone(caught.exception.overlap)
        # RB-9: a row in a HOLE no file covers: the hull would admit it, so a row the file was not asked for would value that date
        with self.assertRaises(S.SegmentRowsOutsideCoverageError):
            S.admit_segments("k", [self.seg(1, ("2022-12-01", "2026-01-08")), self.seg(3, ("2026-01-10", "2026-03-31"), outside=("2026-01-09",))])

    def test_the_order_is_identity_segmentability_undetermined_row_outside_overlap(self):
        other = (("synthetic", False),)
        both = dict(outside=("2026-01-01",))
        with self.assertRaises(S.SegmentIdentityError):
            S.admit_segments("k", [self.seg(1, ("2026-01-01", "2026-01-09")), self.seg(2, ("2026-01-05", "2026-01-12"), other, **both)])
        with self.assertRaises(S.SegmentNotSegmentableError):
            S.admit_segments("k", [self.seg(1, ("2026-01-01", "2026-01-09"), segmentable=False), self.seg(2, ("2026-01-05", "2026-01-12"), segmentable=False, **both)])
        with self.assertRaises(S.SegmentCoverageUndeterminedError):  # a coverage that cannot be stated comes before a stray row
            S.admit_segments("k", [self.seg(1, None, **both), self.seg(2, ("2026-01-05", "2026-01-12"), **both)])
        with self.assertRaises(S.SegmentRowsOutsideCoverageError):  # a stray row comes before the overlap that the same files also have
            S.admit_segments("k", [self.seg(1, ("2026-01-01", "2026-01-09")), self.seg(2, ("2026-01-05", "2026-01-12"), **both)])
        with self.assertRaises(S.SegmentOverlapError):
            S.admit_segments("k", [self.seg(1, ("2026-01-01", "2026-01-09")), self.seg(2, ("2026-01-05", "2026-01-12"))])

    def test_a_read_window_is_not_a_request_but_a_request_is(self):
        # `read_start`/`read_end` say which window of a FULL-HISTORY file a human read (Ruling 1.1a item 5): the file legitimately holds rows outside it, so it is not a declared coverage to hold rows to
        w = World(self)
        read = w.write("r", w.series[:3], utc("2026-01-09T00:00:00Z"))
        read = dataclasses.replace(read, request=(("read_start", "2025-01-01"), ("read_end", "2025-01-31")))
        self.assertEqual(S.declared_request(read), (None, None))
        self.assertEqual(S.requested_interval(read)[:2], (D(2025, 1, 1), D(2025, 1, 31)))  # but it does bound a coverage
        asked = dataclasses.replace(read, request=(("start", "2025-02-01"), ("end", "2025-02-28")))
        self.assertEqual(S.declared_request(asked), (D(2025, 2, 1), D(2025, 2, 28)))
        self.assertEqual(S.declared_request(dataclasses.replace(read, request=(("start", "not-a-date"),))), (None, None))

    def test_m_r7_a_coverage_that_cannot_be_stated_is_not_given_the_hull_of_its_rows(self):
        with self.assertRaises(S.SegmentCoverageUndeterminedError):
            S.admit_segments("k", [self.seg(1, ("2022-12-01", "2026-01-08")), self.seg(2, None), self.seg(3, ("2026-01-10", "2026-03-31"))])

    def test_disjoint_coverage_is_admitted_in_coverage_order(self):
        admitted = S.admit_segments("k", [self.seg(3, ("2026-01-10", "2026-03-31")), self.seg(1, ("2022-12-01", "2026-01-08")), self.seg(2, ("2026-01-09", "2026-01-09"))])
        self.assertEqual([f.file_sha256 for f in admitted], [self.SHA(1), self.SHA(2), self.SHA(3)])

    def test_touching_is_overlap_one_shared_date_is_enough(self):
        with self.assertRaises(S.SegmentOverlapError) as caught:
            S.admit_segments("k", [self.seg(1, ("2026-01-01", "2026-01-09")), self.seg(2, ("2026-01-09", "2026-01-12"))])
        self.assertEqual(caught.exception.overlap, (D(2026, 1, 9), D(2026, 1, 9)))

    def test_m_r1_disjoint_points_are_not_disjoint_coverage(self):
        # V1 covers 2025-06-13 although it holds no row there; V1b holds that one row: the POINTS are disjoint and the coverage is not
        with self.assertRaises(S.SegmentOverlapError):
            S.admit_segments("k", [self.seg(1, ("2022-12-01", "2026-01-08")), self.seg(2, ("2025-06-13", "2025-06-13"))])

    def test_m_r2_an_adjusted_series_is_never_segmented(self):
        with self.assertRaises(S.SegmentNotSegmentableError):
            S.admit_segments("k", [self.seg(1, ("2022-12-01", "2026-01-08"), segmentable=False), self.seg(2, ("2026-01-09", "2026-03-31"), segmentable=False)])

    def test_m_r3_an_overlap_is_refused_whatever_the_values(self):
        # the rule sees no values at all: nothing it is given could make an overlap admissible
        with self.assertRaises(S.SegmentOverlapError):
            S.admit_segments("k", [self.seg(1, ("2026-01-10", "2026-03-31")), self.seg(2, ("2026-01-10", "2026-03-31"), when="2026-04-02T00:00:00Z")])

    def test_m_r4_a_series_in_several_files_is_not_always_refused(self):
        self.assertEqual(len(S.admit_segments("k", [self.seg(1, ("2022-12-01", "2026-01-08")), self.seg(2, ("2026-01-09", "2026-01-09")), self.seg(3, ("2026-01-10", "2026-03-31"))])), 3)

    def test_the_order_of_checks_is_identity_then_not_segmentable_then_coverage_then_overlap(self):
        other = (("synthetic", False),)
        with self.assertRaises(S.SegmentIdentityError):  # identity first, though the series is also not segmentable and the files overlap
            S.admit_segments("k", [self.seg(1, ("2026-01-01", "2026-01-09"), segmentable=False), self.seg(2, ("2026-01-05", "2026-01-12"), other, segmentable=False)])
        with self.assertRaises(S.SegmentNotSegmentableError):
            S.admit_segments("k", [self.seg(1, None, segmentable=False), self.seg(2, ("2026-01-05", "2026-01-12"), segmentable=False)])
        with self.assertRaises(S.SegmentCoverageUndeterminedError):
            S.admit_segments("k", [self.seg(1, None), self.seg(2, ("2026-01-05", "2026-01-12"))])
        self.assertEqual(S.admit_segments("k", [self.seg(1, None)])[0].file_sha256, self.SHA(1))  # one file never needs a coverage

    def test_a_vintage_label_in_the_identity_is_an_identity_difference_never_a_second_series(self):
        with self.assertRaises(S.SegmentIdentityError) as caught:
            S.admit_segments("k", [self.seg(1, ("2026-01-01", "2026-01-09"), (("anchor", "V1"), ("synthetic", True))), self.seg(2, ("2026-01-10", "2026-01-12"), (("anchor", "V2"), ("synthetic", True)))])
        self.assertIn("anchor", str(caught.exception))

    def test_coverage_is_the_request_to_the_earlier_of_the_requested_end_and_what_was_available(self):
        w = World(self)
        cal = next(cc for cc in PART3["market_data"]["calendars"] if cc["calendar_id"] == CALENDAR_ID)
        calendar = None
        built = w  # noqa: F841
        from marketdata.adapters.calendar_file import CalendarFileAdapter as _A  # noqa: F401, PLC0415

        files = FileStore(w.root)
        result = build_in_memory_market_data(MarketDataRelease(name="c", files=(w.manifests[0].file_sha256,), source_precedence=()), files, files.load_registry(), w.adapters, w.ident, catalog_calendars={})
        calendar = result.calendars.by_id(CALENDAR_ID)
        self.assertEqual(cal["calendar_id"], calendar.calendar_id)
        m = w.write("a", w.series[:3], utc("2026-01-09T00:00:00Z"))
        # 1.13 item 1(b): with no requested start and not a full-history file the coverage cannot be stated (the content never defines its own claim; M-R7 would give it the hull of its rows)
        self.assertIsNone(S.declared_coverage(m, calendar, [r[0] for r in w.series[:3]]))
        # a FULL-HISTORY file has no requested start and takes the first date it holds; retrieved 2026-01-09 00:00Z the 2026-01-08 close (16:00 New York = 21:00Z) is the latest available
        full = dataclasses.replace(m, payload_format="ecb_eurofxref_hist_csv/1")
        self.assertEqual(S.declared_coverage(full, calendar, [r[0] for r in w.series[:3]]), (w.series[0][0], D(2026, 1, 8)))
        marked = dataclasses.replace(m, request=m.request + (("full_history", "true"),))
        self.assertEqual(S.declared_coverage(marked, calendar, [r[0] for r in w.series[:3]]), (w.series[0][0], D(2026, 1, 8)))
        started = w.write("s", w.series[:3], utc("2026-01-09T00:00:00Z"), (D(2025, 12, 1), None))  # a requested start is kept whatever rows the file holds
        self.assertEqual(S.declared_coverage(started, calendar, [r[0] for r in w.series[:3]]), (D(2025, 12, 1), D(2026, 1, 8)))
        later = w.write("b", w.series[:3], utc("2026-01-09T20:59:00Z"))
        self.assertEqual(S.latest_available(calendar, later.retrieval_time), D(2026, 1, 8))
        self.assertEqual(S.latest_available(calendar, utc("2026-01-09T21:00:00Z")), D(2026, 1, 9))  # at the close itself it is available
        self.assertIsNone(S.latest_available(calendar, utc("2000-01-01T00:00:00Z")))
        self.assertIsNone(S.latest_available(None, later.retrieval_time))
        requested = w.write("c", w.series[:3], utc("2026-01-09T00:00:00Z"), (D(2026, 1, 2), D(2026, 1, 5)))
        self.assertEqual(S.declared_coverage(requested, calendar, []), (D(2026, 1, 2), D(2026, 1, 5)))  # the request is the earlier end
        beyond = w.write("d", w.series[:3], utc("2026-01-09T00:00:00Z"), (D(2026, 1, 2), D(2026, 3, 31)))
        self.assertEqual(S.declared_coverage(beyond, calendar, []), (D(2026, 1, 2), D(2026, 1, 8)))  # a request beyond what was published by the retrieval is cut at what was available
        self.assertIsNone(S.declared_coverage(m, calendar, []))  # nothing held and no request: no start


class RowsOutsideCoverageTests(unittest.TestCase):
    """CP4M-10: a file of a series in several files holds nothing outside the coverage it states, for EVERY kind (market-data Ruling 0.1 (1.13) item 1(c)). The reviewer's case on prices (V2 declares July and carries a
    2025-06-13 row, a date June's V1 covers with no print), then FX, risk-free rates and benchmark levels; before and after the declared interval; and never the hull."""

    def test_the_reviewers_price_case_a_july_file_with_a_june_row(self):
        w = World(self)
        by_day = {r[0]: r for r in w.series}
        june = [by_day[d] for d in sorted(by_day) if D(2025, 6, 1) <= d <= D(2025, 6, 30)]
        july = [by_day[d] for d in sorted(by_day) if D(2025, 7, 1) <= d <= D(2025, 7, 31)]
        w.write("june", june, utc("2026-01-09T00:00:00Z"), (D(2025, 6, 1), D(2025, 6, 30)))
        w.write("july", sorted(july + [(D(2025, 6, 13), "101.00", 1000)]), utc("2026-01-09T00:00:00Z"), (D(2025, 7, 1), D(2025, 7, 31)))
        self.assertNotIn(D(2025, 6, 13), by_day)  # June has no print on the 13th
        self.assertEqual(outcome(lambda: w.build(w.direct())), (S.REFUSED_ROW_OUTSIDE_COVERAGE, None))
        self.assertEqual(outcome(w.cut)[0], S.ADMITTED)  # the manifests show no rows: the cut proves the declared intervals disjoint and the build is the gate
        with self.assertRaises(TwoVintagesError):
            w.build(w.cut())
        # without the stray row the same two files are two segments of one series
        w2 = World(self)
        w2.write("june", june, utc("2026-01-09T00:00:00Z"), (D(2025, 6, 1), D(2025, 6, 30)))
        w2.write("july", july, utc("2026-01-09T00:00:00Z"), (D(2025, 7, 1), D(2025, 7, 31)))
        built = w2.build(w2.cut())
        self.assertIsNone(next((r for r in built.store.quotes(w2.ids(LISTING), D(2025, 6, 13), D(2025, 6, 13)).readings), None))

    def test_a_row_after_the_declared_end_is_refused_too(self):
        w = World(self)
        by_day = {r[0]: r for r in w.series}
        june = [by_day[d] for d in sorted(by_day) if D(2025, 6, 1) <= d <= D(2025, 6, 30)]
        july = [by_day[d] for d in sorted(by_day) if D(2025, 7, 1) <= d <= D(2025, 7, 31)]
        w.write("june", sorted(june + [by_day[D(2025, 7, 1)]]), utc("2026-01-09T00:00:00Z"), (D(2025, 6, 1), D(2025, 6, 30)))  # a July row in June's file
        w.write("july", july, utc("2026-01-09T00:00:00Z"), (D(2025, 7, 1), D(2025, 7, 31)))
        self.assertEqual(outcome(lambda: w.build(w.direct()))[0], S.REFUSED_ROW_OUTSIDE_COVERAGE)

    def test_a_derived_end_is_judged_too(self):
        # a start-only request: the coverage ends at what was available by the retrieval (01-08), so a row dated after it is outside, whatever the other file says
        w = World(self)
        by_day = {r[0]: r for r in w.series}
        w.write("a", [by_day[d] for d in sorted(by_day) if D(2025, 12, 1) <= d <= D(2026, 1, 8)] + [by_day[D(2026, 1, 12)]], utc("2026-01-09T00:00:00Z"), (D(2025, 12, 1), None))
        w.write("b", [by_day[D(2026, 1, 13)]], utc("2026-04-01T00:00:00Z"), (D(2026, 1, 13), D(2026, 1, 13)))
        self.assertEqual(outcome(lambda: w.build(w.direct()))[0], S.REFUSED_ROW_OUTSIDE_COVERAGE)

    def test_a_single_file_series_is_unchanged(self):
        # no coverage is needed for one file, and its rows are judged by Ruling 3.1 as before
        w = World(self)
        by_day = {r[0]: r for r in w.series}
        w.write("only", [by_day[d] for d in sorted(by_day) if D(2025, 6, 1) <= d <= D(2025, 7, 31)], utc("2026-01-09T00:00:00Z"), (D(2025, 7, 1), D(2025, 7, 31)))
        self.assertEqual(outcome(lambda: w.build(w.direct()))[0], S.ADMITTED)

    def fx_world(self, v2_extra=(), v1_extra=()):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        md = PART3["market_data"]
        cal = next(cc for cc in md["calendars"] if cc["calendar_id"] == "SYN4_ECB")
        days = g.calendar_dates(cal)
        x.kit.write_registry(root, extra=x.synthetic_registry_records())
        manifests = [g._write_file(root, utc("2026-04-01T00:00:00Z"), x.SRC_CAL, DataKind.CALENDAR, "finweb_calendar_json/1", g.calendar_payload(cal, days), "SYN4_ECB", "json", identifiers=("SYN4_ECB",))]
        pool = [d for d in days if D(2025, 12, 1) <= d <= D(2026, 1, 9)]

        def file(label, first, last, retrieved, extra):
            rows = [(d.isoformat(), ["1.1000"]) for d in pool if first <= d <= last or d in extra]
            payload = x.k.ecb_csv(rows, ["USD"])
            return g._write_file(root, retrieved, x.SRC_ECB, DataKind.FX, "ecb_eurofxref_hist_csv/1", payload, label, "csv", identifiers=("USD",), request=(("start", first.isoformat()), ("end", last.isoformat())))

        manifests += [file("fx1", D(2025, 12, 1), D(2026, 1, 8), utc("2026-01-09T00:00:00Z"), set(v1_extra)), file("fx2", D(2026, 1, 9), D(2026, 1, 9), utc("2026-01-09T15:00:00Z"), set(v2_extra))]
        release = MarketDataRelease(name="fx-seg", files=tuple(sorted({m.file_sha256 for m in manifests})), source_precedence=())
        files = FileStore(root)
        from marketdata.adapters.ecb_eurofxref import EcbEurofxrefFxAdapter  # noqa: PLC0415

        adapters = AdapterRegistry([CalendarFileAdapter(), EcbEurofxrefFxAdapter(x.SRC_ECB)])
        return lambda: build_in_memory_market_data(release, files, files.load_registry(), adapters, InMemoryIdentityRegistry(lambda: uuid.uuid4()), catalog_calendars={}), manifests

    def test_fx_segments_with_rows_outside_the_request_are_refused(self):
        build, _ = self.fx_world()
        built = build()  # control: two ECB segments, each inside its request
        self.assertEqual(len(built.store.fx_series(CurrencyCode("EUR"), USD, D(2025, 12, 1), D(2026, 1, 9)).consumed), 2)
        for label, kw in (("a row of the first file's range in the second file", dict(v2_extra=[D(2026, 1, 5)])), ("a row after the first file's end in the first file", dict(v1_extra=[D(2026, 1, 9)]))):
            build, _ = self.fx_world(**kw)
            self.assertEqual(outcome(build), (S.REFUSED_ROW_OUTSIDE_COVERAGE, None), label)

    def test_risk_free_segments_with_rows_outside_the_declared_interval_are_refused(self):
        helper = RiskFreeSegmentTests()
        self.addCleanup(helper.doCleanups)
        for label, extra_in_b, extra_in_a in (("a row before the second file's start", [D(2026, 1, 6)], []), ("a row after the first file's end", [], [D(2026, 1, 12)])):
            root, ms = helper.world([("a", D(2025, 1, 1), D(2026, 1, 8), utc("2026-01-09T00:00:00Z"), None, 1, extra_in_a), ("b", D(2026, 1, 9), D(2026, 3, 31), utc("2026-04-01T00:00:00Z"), None, 1, extra_in_b)], declare=True)
            self.assertEqual(outcome(lambda: helper.build(root, ms)), (S.REFUSED_ROW_OUTSIDE_COVERAGE, None), label)

    def benchmark_world(self, declared_calendar="SYN4_NYSE", stray=False, single=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        cal = next(cc for cc in PART3["market_data"]["calendars"] if cc["calendar_id"] == CALENDAR_ID)
        days = g.calendar_dates(cal)
        x.kit.write_registry(root, extra=x.synthetic_registry_records())
        manifests = [g._write_file(root, utc("2026-04-01T00:00:00Z"), x.SRC_CAL, DataKind.CALENDAR, "finweb_calendar_json/1", g.calendar_payload(cal, days), CALENDAR_ID, "json", identifiers=(CALENDAR_ID,))]
        from marketdata.adapters.mock import MOCK_FORMAT, MockSyntheticAdapter, make_synthetic_payload  # noqa: PLC0415

        def file(label, first, last, retrieved, extra=()):
            pts = [{"date": d.isoformat(), "value": "1000.5"} for d in days if first <= d <= last or d in extra]
            payload = make_synthetic_payload(benchmarks=({"benchmark_id": "BM1", "provider": "p", "value_kind": "LEVEL", "points": pts},))
            request = (("start", first.isoformat()), ("end", last.isoformat())) + ((("calendar", declared_calendar),) if declared_calendar else ())
            return g._write_file(root, retrieved, "mock.synthetic", DataKind.BENCHMARK, MOCK_FORMAT, payload, label, "json", currency=USD, identifiers=("BM1",), request=request)

        manifests += [file("b1", D(2025, 12, 1), D(2026, 1, 8), utc("2026-01-09T00:00:00Z"), [D(2026, 1, 9)] if stray else ())]
        if not single:
            manifests += [file("b2", D(2026, 1, 9), D(2026, 1, 15), utc("2026-04-01T00:00:00Z"))]
        release = MarketDataRelease(name="bm-seg", files=tuple(sorted({m.file_sha256 for m in manifests})), source_precedence=())
        files = FileStore(root)
        adapters = AdapterRegistry([CalendarFileAdapter(), MockSyntheticAdapter(DataKind.BENCHMARK, "mock.synthetic")])
        return lambda **kw: build_in_memory_market_data(release, files, files.load_registry(), adapters, InMemoryIdentityRegistry(lambda: uuid.uuid4()), **dict({"catalog_calendars": {}}, **kw)), manifests

    def test_the_catalog_calendars_are_required_on_every_release_build_path(self):
        """CP4F-8: a builder that forgets the argument must not silently skip the Ruling 0.1 (1.13) check. An explicit empty mapping is the way to say that no benchmark catalog applies."""
        from performance_service.derived_release import DerivedReleaseView  # noqa: PLC0415

        with self.assertRaises(TypeError):
            build_in_memory_market_data(None, None, None, None, None)  # type: ignore[call-arg]
        with self.assertRaises(TypeError):
            DerivedReleaseView(None, None, None, None, None)  # type: ignore[call-arg]
        with self.assertRaises(TypeError):
            build_in_memory_market_data(None, None, None, None, None, {})  # type: ignore[misc]  # keyword-only: a positional mapping is not a deliberate choice either
        build, _ = self.benchmark_world()
        self.assertEqual(outcome(lambda: build()), (S.ADMITTED, None))  # (the helper passes the explicit empty mapping)

    def test_benchmark_segments_with_a_stray_row_are_refused_and_the_declared_calendar_must_be_the_catalogs(self):
        build, _ = self.benchmark_world()
        self.assertEqual(len(build(catalog_calendars={"BM1": CALENDAR_ID}).store.benchmark("BM1", D(2025, 12, 1), D(2026, 1, 15)).consumed), 2)  # control, the entry's calendar is the declared one
        self.assertEqual(outcome(lambda: build()), (S.ADMITTED, None))  # no catalog given: nothing to compare with
        self.assertEqual(outcome(lambda: build(catalog_calendars={"BM1": "SYN4_SSE"})), (S.REFUSED_CALENDAR_MISMATCH, None))  # CP4M-10 point 3
        self.assertEqual(outcome(lambda: build(catalog_calendars={"OTHER": "SYN4_SSE"})), (S.ADMITTED, None))  # an id the catalog does not name is not compared
        undeclared, _ = self.benchmark_world(declared_calendar=None)
        self.assertEqual(outcome(lambda: undeclared(catalog_calendars={"BM1": CALENDAR_ID}))[0], S.REFUSED_CALENDAR_MISMATCH)  # nothing declared is not the entry's calendar
        alone, _ = self.benchmark_world(declared_calendar="SYN4_SSE", single=True)  # a single-file benchmark needs no coverage: its declared calendar is not compared (only a SEGMENTED file's is)
        self.assertEqual(outcome(lambda: alone(catalog_calendars={"BM1": CALENDAR_ID})), (S.ADMITTED, None))
        stray, _ = self.benchmark_world(stray=True)
        self.assertEqual(outcome(lambda: stray(catalog_calendars={"BM1": CALENDAR_ID})), (S.REFUSED_ROW_OUTSIDE_COVERAGE, None))


import pg_market_kit as pk  # noqa: E402
from persistence import market_data_store as mds  # noqa: E402

_SKIP = pk.skip_reason()


@unittest.skipIf(bool(_SKIP), _SKIP)
class SegmentedReleaseDbTests(unittest.TestCase):
    """A release of segmented series round-trips through PostgreSQL (`write_release`, then `read_release` as the least-privilege role): the projection keeps every file, every row once and the series as the in-memory
    store serves it, and a segmented release is not a second kind of release (the store holds files and rows, never a vintage label; there is no segment table and no migration)."""

    def setUp(self):  # one disposable schema per test (the identity rows are inserted once per schema)
        self.db = pk.PgSchema(prefix="finweb_it_seg_").open()
        self.addCleanup(self.db.close)
        self.app = self.db.app_connection()
        self.addCleanup(self.app.close)

    def test_the_projection_refuses_a_file_that_holds_a_row_outside_its_declared_request_cp4m_10(self):
        # the reviewer's case through PostgreSQL: the build refuses it, so contents with a stray row can only be assembled by hand; `write_release` refuses them too and stores nothing
        w = World(self)
        w.write_case(CASES[0], declare=True)
        release = w.cut()
        built = w.build(release)
        pk.insert_identity(self.db.owner, w.ident)
        contents = built.store.export()
        v2 = next(m for m in w.manifests if m.payload_filename.startswith("V2."))
        template = next(r for r in contents.readings if r.file_sha256 == v2.file_sha256)
        stray = dataclasses.replace(template, observation=dataclasses.replace(template.observation, value_date=D(2025, 6, 13)))
        bad = dataclasses.replace(contents, readings=tuple(contents.readings) + (stray,))
        with self.assertRaises(S.SegmentRowsOutsideCoverageError):
            mds.write_release(self.db.owner, release, built.manifests, bad, built.calendars)
        self.assertEqual(self.db.owner.execute("SELECT count(*) FROM md_release WHERE release_id = %s", (release.release_id,)).fetchone()[0], 0)
        mds.write_release(self.db.owner, release, built.manifests, contents, built.calendars)  # the honest contents project

    def test_a_single_file_series_is_not_judged_by_the_projection_as_before(self):
        w = World(self)
        by_day = {r[0]: r for r in w.series}
        w.write("only", [by_day[d] for d in sorted(by_day) if D(2025, 7, 1) <= d <= D(2025, 7, 31)], utc("2026-01-09T00:00:00Z"), (D(2025, 7, 1), D(2025, 7, 31)))
        release = w.direct()
        built = w.build(release)
        pk.insert_identity(self.db.owner, w.ident)
        contents = built.store.export()
        template = contents.readings[0]
        stray = dataclasses.replace(template, observation=dataclasses.replace(template.observation, value_date=D(2025, 6, 13)))  # outside its request, but it is the series' only file: unchanged
        mds.write_release(self.db.owner, release, built.manifests, dataclasses.replace(contents, readings=tuple(contents.readings) + (stray,)), built.calendars)

    def test_three_price_segments_and_two_rate_segments_come_back_as_the_in_memory_store_serves_them(self):
        # prices: the Quant's RB-1 files of SYN42
        w = World(self)
        w.write_case(CASES[0], declare=True)
        release = w.cut()
        built = w.build(release)
        pk.insert_identity(self.db.owner, w.ident)  # the listing the quotes name
        written = mds.write_release(self.db.owner, release, built.manifests, built.store.export(), built.calendars)
        back = mds.read_release(self.app, release.release_id, registry=FileStore(w.root).load_registry())
        self.assertEqual(back.projection_digest(), written.projection_digest)
        lid = w.ids(LISTING)
        mem, pg = built.store.quotes(lid, D(2022, 12, 1), D(2026, 3, 31)), back.quotes(lid, D(2022, 12, 1), D(2026, 3, 31))
        self.assertEqual([r.observation.value_date for r in pg.readings], [r[0] for r in w.series])
        self.assertEqual((len(pg.consumed), pg.consumed), (3, mem.consumed))
        self.assertEqual([(r.observation.value_date, r.observation.price) for r in pg.readings], [(r.observation.value_date, r.observation.price) for r in mem.readings])
        # risk-free rates: two segments of the part's USD series
        helper = RiskFreeSegmentTests()
        self.addCleanup(helper.doCleanups)
        root, manifests = helper.world([("a", D(2025, 1, 1), D(2026, 1, 8), utc("2026-01-09T00:00:00Z"), None, 1), ("b", D(2026, 1, 9), D(2026, 3, 31), utc("2026-04-01T00:00:00Z"), None, 1)], declare=True)
        rf_release = MarketDataRelease.from_manifests("rf-seg-db", manifests, [RF_SOURCE])
        files = FileStore(root)
        rf_built = build_in_memory_market_data(rf_release, files, files.load_registry(), AdapterRegistry([CalendarFileAdapter(), SyntheticRiskFreeAdapter()]), InMemoryIdentityRegistry(lambda: uuid.uuid4()), catalog_calendars={})
        rf_written = mds.write_release(self.db.owner, rf_release, rf_built.manifests, rf_built.store.export(), rf_built.calendars)
        rf_back = mds.read_release(self.app, rf_release.release_id, registry=files.load_registry())
        self.assertEqual(rf_back.projection_digest(), rf_written.projection_digest)
        a, b = rf_built.store.risk_free_series(USD, D(2025, 1, 1), D(2026, 3, 31)), rf_back.risk_free_series(USD, D(2025, 1, 1), D(2026, 3, 31))
        self.assertEqual((b.outcome.value, len(b.consumed), b.series[0].points), ("FOUND", 2, a.series[0].points))
        conventions = market11_conventions(rf_back.calendars())
        on_a = rf_built.store.risk_free_on(USD, D(2026, 1, 12), market11_conventions(rf_built.calendars))
        on_b = rf_back.risk_free_on(USD, D(2026, 1, 12), conventions)
        self.assertEqual((on_b.outcome, on_b.point, on_b.date_used, on_b.missed_count), (on_a.outcome, on_a.point, on_a.date_used, on_a.missed_count))


if __name__ == "__main__":
    unittest.main()
