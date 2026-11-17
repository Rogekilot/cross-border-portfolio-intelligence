"""market-data/1.3 behaviours (methodology/CP2_MARKET_DATA_CONVENTIONS.md, change note 1.2 -> 1.3 and section
9B), one test group per ruling. Every expected value is derived by hand from the inputs shown, with the arithmetic
in the comments, or is a figure of the Quant's worked examples (cited). No expected value is read from the code
under test. All data is synthetic."""

import ast
import datetime
import inspect
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_cp2c1_kit as k  # noqa: E402

from marketdata import contracts as c  # noqa: E402
from marketdata.adapters.alphavantage import AlphaVantageQuoteAdapter  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.ingest import fx_file_window  # noqa: E402
from marketdata.manifest import DataKind, FileManifest  # noqa: E402
from marketdata.market11 import (  # noqa: E402
    PARITY_NOT_RUN,
    market11_conventions,
    market11_conventions_with_injected_parity_for_tests,
)
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.precision import field_bound  # noqa: E402
from marketdata.profiles import SOURCES  # noqa: E402
from marketdata.states import fx_input_state, price_input_state  # noqa: E402
from marketdata.store import FXFileWindow, SeriesExclusion  # noqa: E402
from marketdata.verification import PriceRow, verify_adjustment_v2  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
S, R = SufficiencyState, ReasonCode
SRC = Path(__file__).resolve().parents[2] / "src"


def pair(state):
    return state.state, state.reason


class UnrecoveredReadingsTests(unittest.TestCase):
    """Ruling 2.4 item 4a (1.3 clarification) and section 9B #1: unrecovered readings, agreeing or not, are no
    admissible print: no value, no reconciliation status; the session counts as missed (the last good print, aged);
    agreement is lineage only."""

    DAYS = [D(2025, 4, 29), D(2025, 4, 30)]

    def conv(self):
        return market11_conventions(CalendarSet([k.exchange_calendar("NY", ("XNYS",), self.DAYS, covers=(D(2025, 4, 28), D(2025, 4, 30)))]))

    def pair_of_unrecovered(self, day):
        # two upstreams, each a value off the grid: bounds 0.001 each, values 10.0004 and 10.0006 differ by 0.0002 <= 0.002
        return [k.quote_reading(day, "10.0004", recovered=False, bound="0.001", source="a", group="a", sha=k.SHA),
                k.quote_reading(day, "10.0006", recovered=False, bound="0.001", source="b", group="b", sha=k.SHA2)]

    def test_two_agreeing_unrecovered_readings_are_no_value_no_status_and_missing_price_history(self):
        lk = k.store(self.pair_of_unrecovered(self.DAYS[1]), mic="XNYS").quote_on(k.LID, self.DAYS[1], self.conv())
        self.assertEqual((lk.outcome, lk.selected, lk.reconciliation), (LookupOutcome.NO_HISTORY, None, None))
        self.assertEqual(pair(price_input_state(lk)), (S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY))
        causes = [n.split(":")[0] for n in lk.lineage_notes]
        self.assertEqual(causes, ["ONLY_UNRECOVERED_READINGS", "UNRECOVERED_READINGS_AGREE"])  # separate causes, lineage only

    def test_the_session_counts_as_missed_and_the_last_good_print_is_used_aged(self):
        # 29 April: a recovered print 100.00. 30 April: only the two agreeing unrecovered readings.
        # Sessions d with 29 April < d <= 30 April: {30 April} -> 1 missed -> AVAILABLE + STALE_DATA (Ruling 5.2).
        good = k.quote_reading(self.DAYS[0], "100.00")
        lk = k.store([good] + self.pair_of_unrecovered(self.DAYS[1]), mic="XNYS").quote_on(k.LID, self.DAYS[1], self.conv())
        self.assertEqual((lk.outcome, lk.date_used, lk.missed_count, lk.selected.observation.price),
                         (LookupOutcome.FOUND, self.DAYS[0], 1, Decimal("100.00")))
        self.assertEqual(pair(price_input_state(lk)), (S.AVAILABLE, R.STALE_DATA))
        self.assertEqual(lk.reconciliation.status, c.ReconciliationStatus.SINGLE_SOURCE)  # the one recovered print is used

    def test_unrecovered_readings_that_disagree_are_not_an_agreement_note(self):
        far = [k.quote_reading(self.DAYS[1], "10.00", recovered=False, bound="0.001", source="a", group="a", sha=k.SHA),
               k.quote_reading(self.DAYS[1], "10.50", recovered=False, bound="0.001", source="b", group="b", sha=k.SHA2)]
        lk = k.store(far, mic="XNYS").quote_on(k.LID, self.DAYS[1], self.conv())
        self.assertEqual(lk.outcome, LookupOutcome.NO_HISTORY)
        self.assertEqual([n.split(":")[0] for n in lk.lineage_notes], ["ONLY_UNRECOVERED_READINGS"])

    def test_the_no_history_causes_stay_apart(self):
        conv = self.conv()
        # (1) nothing on or before the date, readings only after it
        later = k.store([k.quote_reading(self.DAYS[1], "10.00")], mic="XNYS").quote_on(k.LID, self.DAYS[0], conv)
        self.assertEqual((later.outcome, [n.split(":")[0] for n in later.lineage_notes]),
                         (LookupOutcome.NO_HISTORY, ["NO_PRINT_ON_OR_BEFORE_AS_OF"]))
        # (2) a reading with no volume is not a print
        silent = k.store([k.quote_reading(self.DAYS[1], "10.00", volume=None)], mic="XNYS").quote_on(k.LID, self.DAYS[1], conv)
        self.assertEqual((silent.outcome, [n.split(":")[0] for n in silent.lineage_notes]),
                         (LookupOutcome.NO_HISTORY, ["NO_PRINT"]))
        # (3) a market with no admitted source
        hk = k.store([], mic="XHKG").quote_on(k.LID, self.DAYS[1], conv)
        self.assertEqual((hk.outcome, [n.split(":")[0] for n in hk.lineage_notes]),
                         (LookupOutcome.NO_HISTORY, ["NO_ADMITTED_SOURCE"]))
        # (4) every series CONTRADICTED
        excl = SeriesExclusion(k.LID, k.SHA, "V0", "2 date(s) are not sessions of NY")
        gone = k.store([], mic="XNYS", exclusions=[excl]).quote_on(k.LID, self.DAYS[1], conv)
        self.assertEqual((gone.outcome, [n.split(":")[0] for n in gone.lineage_notes]),
                         (LookupOutcome.NO_HISTORY, ["SERIES_CONTRADICTED"]))
        # one pair for all four, and never folded into a conflict
        for lk in (later, silent, hk, gone):
            self.assertEqual(pair(price_input_state(lk)), (S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY))
        # a US listing the version holds NOTHING for, with no cause, is NOT_IN_RELEASE: the same pair
        none = k.store([], mic="XNYS").quote_on(k.LID, self.DAYS[1], conv)
        self.assertEqual((none.outcome, none.lineage_notes), (LookupOutcome.NOT_IN_RELEASE, ()))
        self.assertEqual(pair(price_input_state(none)), (S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY))


class V2PerFieldBoundTests(unittest.TestCase):
    """Test V2 (a'), 1.3 (section 9B #2): delta_r is per field, from that field's own profile. A recovered close
    is 0; open, high and low (never grid-checked) are half a unit of the delivered decimals for a text or float64
    field and half an ulp for a float32 field. The close's 0 is not copied to them."""

    DAYS = [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7), D(2025, 1, 8)]
    REF = ("200.00", "210.00", "248.00", "230.50", "225.25")  # lo = 200.00, hi = 248.00, Delta = 48
    HALF_CENT = Fraction(1, 200)

    def rows(self, closes, bound, shift=Decimal(0), field_bounds=None):
        out = []
        for day, close in zip(self.DAYS, closes):
            v = Decimal(close)
            out.append(PriceRow(day, v - shift, v + 1 - shift, v - 1 - shift, v - shift, bound, field_bounds))
        return out

    def test_a_residual_inside_the_per_field_bound_but_outside_the_closes_zero_is_a_valid_series(self):
        # adjusted = reference - 7.50 on every field, except the OPEN of 3 January, 0.012 higher (202.512 for 202.50).
        # Anchors by the reference close: lo 200.00, hi 248.00; a = ((248-7.5) - (200-7.5)) / 48 = 1; b = 248 - 240.5 = 7.5.
        # delta_j = 0.005 (the adjusted series delivers 2 decimals). Reference open/high/low: 0.005 each (2 delivered
        # decimals, never grid-checked); the reference close is recovered: 0.
        #   per field (1.3): e_open = delta_j + |a| x delta_r(open) = 0.005 + 0.005 = 0.010; anchor error
        #     max(e_lo, e_hi) = 0.005 + 0 = 0.005 -> allowed 0.015 >= 0.012: the series is valid.
        #   close bound copied (1.2): e_open = 0.005 + 0 = 0.005 -> allowed 0.010 < 0.012: wrongly CONTRADICTED.
        # u_b = e_lo + |ref_lo| x u_a = 0.005 + 200 x (0.010 / 48) = 0.0466...; b = 7.5 is far above it: SUBTRACTIVE.
        adj = self.rows(self.REF, self.HALF_CENT, shift=Decimal("7.50"))
        adj[1] = PriceRow(adj[1].date, adj[1].open + Decimal("0.012"), adj[1].high, adj[1].low, adj[1].close, self.HALF_CENT)
        per_field = self.rows(self.REF, Fraction(0), field_bounds=(Fraction(1, 200),) * 3)
        copied = self.rows(self.REF, Fraction(0))
        ok = verify_adjustment_v2(per_field, adj, [], D(2026, 10, 1))
        self.assertEqual((ok.method, ok.status), (c.AdjustmentMethod.SUBTRACTIVE, c.LabelStatus.UNVERIFIABLE))
        wrong = verify_adjustment_v2(copied, adj, [], D(2026, 10, 1))
        self.assertEqual((wrong.method, wrong.status), (c.AdjustmentMethod.UNKNOWN, c.LabelStatus.CONTRADICTED))

    def test_a_residual_beyond_even_the_per_field_bound_is_still_contradicted(self):
        adj = self.rows(self.REF, self.HALF_CENT, shift=Decimal("7.50"))
        adj[1] = PriceRow(adj[1].date, adj[1].open + Decimal("0.016"), adj[1].high, adj[1].low, adj[1].close, self.HALF_CENT)
        per_field = self.rows(self.REF, Fraction(0), field_bounds=(Fraction(1, 200),) * 3)
        # 0.016 > 0.015
        self.assertIs(verify_adjustment_v2(per_field, adj, [], D(2026, 10, 1)).status, c.LabelStatus.CONTRADICTED)

    def test_field_bounds_come_from_each_fields_own_profile(self):
        av = SOURCES["alphavantage.us"].fields
        self.assertEqual(Fraction(field_bound(av["open"], Decimal("100.0000"))), Fraction(1, 2 * 10 ** 4))  # delivered_dp 4
        sina = SOURCES["akshare_sina.hk"].fields
        # FLOAT32, no delivered_dp: half an ulp in binary32. 473.6 lies in [256, 512): ulp = 2^(8-23) = 2^-15, half 2^-16
        self.assertEqual(Fraction(field_bound(sina["open"], Decimal("473.6"))), Fraction(1, 2 ** 16))
        east = SOURCES["akshare.cn"].fields
        # C2-10 (market-data/1.4 V2 (a'), section 9C item 4): FLOAT64 with NO declared delivered_dp has NO bound (None):
        # half an ulp of binary64 (2^-43 at 1288.0; this assertion used to expect it) bounds only the float rendering,
        # not a decimal rounding the source applied first, so it is not a substitute and V2 stops (PROFILE_INCOMPLETE)
        # 1.5 (A.3, A.4 item 7): Eastmoney (2) and Sina-US (4) now DECLARE delivered_dp, so half a unit of it is the bound
        self.assertEqual(Fraction(field_bound(east["open"], Decimal("1288.0"))), Fraction(1, 200))
        self.assertEqual(Fraction(field_bound(SOURCES["akshare_sina.us"].fields["open"], Decimal("233.85"))), Fraction(1, 20000))
        import dataclasses  # noqa: PLC0415
        undeclared = dataclasses.replace(east["open"], delivered_dp=None)  # the 1.4 profile: still no bound at all
        self.assertIsNone(field_bound(undeclared, Decimal("1288.0")))
        declared = dataclasses.replace(east["open"], delivered_dp=2)
        self.assertEqual(Fraction(field_bound(declared, Decimal("1288.0"))), Fraction(1, 200))
        # FLOAT32 keeps half an ulp of binary32 even where a delivered_dp were declared
        self.assertEqual(Fraction(field_bound(dataclasses.replace(sina["open"], delivered_dp=3), Decimal("473.6"))),
                         Fraction(1, 2 ** 16))

    def test_the_adapter_supplies_per_field_bounds_on_raw_reference_rows(self):
        payload = k.av_csv([("2025-01-02", "100.0000", "101.5000", "99.2500", "100.5000", "1000"),
                            ("2025-01-03", "100.5000", "102.0000", "100.0000", "101.2500", "1100")])
        manifest = FileManifest(
            file_sha256="a" * 64, size_bytes=len(payload), payload_filename="x.csv", payload_format="alphavantage_csv_daily/1",
            source_id="alphavantage.us", data_kind=DataKind.QUOTE, retrieval_time=k.NOW, retrieved_by="synthetic",
            declared_adjustment=c.AdjustmentStatus.UNDECLARED, usage_scope=c.UsageScope.SYNTHETIC_TEST,
            declared_currency=k.USD, source_identifiers=("AAPL",), request=(("function", "TIME_SERIES_DAILY"),), market="US")
        out = AlphaVantageQuoteAdapter().translate(manifest, payload)
        self.assertEqual(len(out.reference), 2)
        for ref in out.reference:
            self.assertEqual(ref.precision_bound, Decimal(0))  # the closes are on the cent grid: recovered
            self.assertEqual([Fraction(b) for b in ref.field_bounds], [Fraction(1, 20000)] * 3)  # 0.00005 each

    def test_a_raw_label_read_from_the_profile_says_so_and_a_declared_one_does_not(self):
        # section 9B #4 (a): an UNDECLARED manifest of TIME_SERIES_DAILY is read as RAW through the profile (status
        # DECLARED since 1.16: PD-0066 decision 3; MEMORY before it); the lineage records that, so the label is never mistaken for
        # one the file declared. Re-recorded 2026-10-25 (F1 R4a, 1.16 section 11 item 23): the string below ended `:MEMORY`; nothing else moved.
        payload = k.av_csv([("2025-01-02", "100.0000", "101.0000", "99.0000", "100.0000", "1000")])

        def translate(declared):
            manifest = FileManifest(
                file_sha256="a" * 64, size_bytes=len(payload), payload_filename="x.csv", payload_format="alphavantage_csv_daily/1",
                source_id="alphavantage.us", data_kind=DataKind.QUOTE, retrieval_time=k.NOW, retrieved_by="synthetic",
                declared_adjustment=declared, usage_scope=c.UsageScope.SYNTHETIC_TEST, declared_currency=k.USD,
                source_identifiers=("AAPL",), request=(("function", "TIME_SERIES_DAILY"),), market="US")
            return AlphaVantageQuoteAdapter().translate(manifest, payload)

        (q,) = translate(c.AdjustmentStatus.UNDECLARED).quotes
        self.assertEqual((q.lineage.adjustment_status, q.lineage.adjustment_label_source),
                         (c.AdjustmentStatus.RAW, "PROFILE_CALL_ADJUSTMENT:alphavantage.us:TIME_SERIES_DAILY:DECLARED"))
        (declared,) = translate(c.AdjustmentStatus.RAW).quotes
        self.assertIsNone(declared.lineage.adjustment_label_source)

    def test_a_reference_row_without_field_bounds_makes_v2_unverifiable_not_wrongly_bounded(self):
        # tested through the build path in the ingest tests; here the contract: absent bounds are None, not zero
        row = c.UnresolvedAdjustedQuote(
            c.ExternalIdentifiers(vendor_id="X", source_id="s"), D(2025, 1, 2), Decimal(1), Decimal(1), Decimal(1), Decimal(1),
            k.USD, c.AdjustmentLabel(c.AdjustmentStatus.RAW, c.AdjustmentMethod.UNKNOWN, None, k.NOW),
            c.SourceTiming(), k.lineage(), Decimal(0))
        self.assertIsNone(row.field_bounds)


class FxCoverageWindowTests(unittest.TestCase):
    """Ruling 1.1a item 5 (1.3): `[start, end]`; start the requested start (a full-history file: the first date held
    for the currency), end = min(requested end, D_ret), D_ret the latest fixing f of the ECB calendar with f at
    16:00 Europe/Berlin <= the retrieval time. January is UTC+1, so 16:00 Berlin = 15:00 UTC."""

    FIXINGS = [D(2025, 1, 2), D(2025, 1, 3), D(2025, 1, 6), D(2025, 1, 7), D(2025, 1, 8), D(2025, 1, 9), D(2025, 1, 10)]

    def calendars(self):
        return CalendarSet([k.ecb_calendar(self.FIXINGS, covers=(D(2025, 1, 1), D(2025, 1, 31)))])

    def manifest(self, retrieved, request):
        return FileManifest(
            file_sha256="b" * 64, size_bytes=1, payload_filename="f.json", payload_format="x/1", source_id="s",
            data_kind=DataKind.FX, retrieval_time=retrieved, retrieved_by="synthetic",
            declared_adjustment=c.AdjustmentStatus.RAW, usage_scope=c.UsageScope.SYNTHETIC_TEST, request=request)

    def at(self, day, hour, minute=0, second=0):
        return datetime.datetime(2025, 1, day, hour, minute, second, tzinfo=datetime.timezone.utc)

    def window(self, retrieved, request):
        w = fx_file_window(self.manifest(retrieved, request), self.calendars())
        return w.start, w.end

    def test_a_fixing_not_yet_published_at_retrieval_is_never_counted_as_missing(self):
        req = (("start", "2025-01-01"), ("end", "2025-01-08"))
        # retrieved 8 January 12:00 UTC = 13:00 Berlin: the 8th's 16:00 publication is still ahead; the 7th's was
        # 15:00 UTC on the 7th -> D_ret = 7 January; end = min(8, 7) = 7 January
        self.assertEqual(self.window(self.at(8, 12), req), (D(2025, 1, 1), D(2025, 1, 7)))
        # one second before 15:00 UTC on the 8th: still the 7th
        self.assertEqual(self.window(self.at(8, 14, 59, 59), req), (D(2025, 1, 1), D(2025, 1, 7)))
        # exactly 15:00 UTC = 16:00 Berlin on the 8th: published (<=) -> D_ret = 8 January; end = min(8, 8) = 8
        self.assertEqual(self.window(self.at(8, 15), req), (D(2025, 1, 1), D(2025, 1, 8)))
        # retrieved on the 10th at 09:00 UTC: the 9th was published (15:00 UTC on the 9th), the 10th (15:00 UTC) was not
        self.assertEqual(self.window(self.at(10, 9), req), (D(2025, 1, 1), D(2025, 1, 8)))  # end = min(8, D_ret 9) = 8

    def test_a_full_history_file_has_no_requested_start_or_end_and_ends_at_d_ret(self):
        self.assertEqual(self.window(self.at(10, 9), (("file", "eurofxref-hist"),)), (None, D(2025, 1, 9)))
        # a read window the human declared bounds the end like a requested end
        self.assertEqual(self.window(self.at(10, 9), (("read_start", "2025-01-02"), ("read_end", "2025-01-08"))),
                         (D(2025, 1, 2), D(2025, 1, 8)))

    def test_when_d_ret_cannot_be_determined_the_end_is_unknown(self):
        req = (("start", "2025-01-01"), ("end", "2025-01-08"))
        # retrieved before the first fixing was published: no fixing is publishable
        self.assertEqual(self.window(self.at(1, 12), req), (D(2025, 1, 1), None))
        # no ECB calendar in the version
        w = fx_file_window(self.manifest(self.at(10, 9), req), CalendarSet())
        self.assertEqual((w.start, w.end), (D(2025, 1, 1), None))

    def test_a_retrieval_after_the_calendar_coverage_is_capped_at_the_last_listed_fixing(self):
        req = (("start", "2025-01-01"), ("end", "2025-02-28"))
        later = datetime.datetime(2025, 3, 1, 12, tzinfo=datetime.timezone.utc)
        self.assertEqual(self.window(later, req), (D(2025, 1, 1), D(2025, 1, 10)))  # beyond it nothing can be checked


class PartialRefutedAndVersionTests(unittest.TestCase):
    """Ruling 1.1a item 6: a refuted re-server file is in M and supplies no rate; Ruling 1.5a; ids."""

    def test_the_product_convention_builder_takes_no_parity_mapping_and_says_the_check_did_not_run(self):
        self.assertEqual(list(inspect.signature(market11_conventions).parameters), ["calendars"])
        cal = k.ecb_calendar([D(2025, 1, 2)], covers=(D(2025, 1, 1), D(2025, 1, 10)))
        readings = [k.fx_reading(D(2025, 1, 2), "USD", "1.0823"), k.fx_reading(D(2025, 1, 2), "CNY", "7.8243")]
        lk = k.store(readings).fx_on(k.USD, k.CNY, D(2025, 1, 2), market11_conventions(CalendarSet([cal])))
        self.assertEqual(lk.checks, (("CNY_PARITY_BAND", "UNVERIFIABLE"),))
        self.assertIn(PARITY_NOT_RUN, lk.lineage_notes)
        self.assertTrue(PARITY_NOT_RUN.startswith("PARITY_CHECK_NOT_RUN"))
        # a test-injected mapping (tests only) runs the check and the note is gone
        injected = market11_conventions_with_injected_parity_for_tests(CalendarSet([cal]), {D(2025, 1, 2): Decimal("7.2")})
        lk2 = k.store(readings).fx_on(k.USD, k.CNY, D(2025, 1, 2), injected)
        self.assertEqual(lk2.checks, (("CNY_PARITY_BAND", "PASS"),))
        self.assertNotIn(PARITY_NOT_RUN, lk2.lineage_notes)

    def test_an_injected_parity_mapping_cannot_reach_a_product_path(self):
        """No module of src/ other than market11 itself names the test-only builder or keyword."""
        for path in sorted(SRC.rglob("*.py")):
            if path.name == "market11.py":
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("_test_central_parity", text, str(path))
            self.assertNotIn("injected_parity_for_tests", text, str(path))
        tree = ast.parse((SRC / "marketdata" / "market11.py").read_text(encoding="utf-8"))
        callers = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and any(
            isinstance(x, ast.keyword) and x.arg == "_test_central_parity" for y in ast.walk(n) for x in
            (y.keywords if isinstance(y, ast.Call) else []))]
        self.assertEqual(callers, ["market11_conventions_with_injected_parity_for_tests"])

    def test_a_refuted_file_alone_gives_no_history_never_a_rate(self):
        refuted = k.fx_reading(D(2025, 1, 2), "USD", "1.0823", source="frankfurter.ecb", sha=k.SHA2, provenance="REFUTED")
        cal = k.ecb_calendar([D(2025, 1, 2)], covers=(D(2025, 1, 1), D(2025, 1, 10)))
        lk = k.store([refuted]).fx_on(k.EUR, k.USD, D(2025, 1, 2), market11_conventions(CalendarSet([cal])))
        self.assertEqual((lk.outcome, lk.rate), (LookupOutcome.NO_HISTORY, None))
        self.assertEqual(pair(fx_input_state(lk)), (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY))
        # it is still evidence in M: the series lists it, flagged
        series = k.store([refuted]).fx_series(k.EUR, k.USD, D(2025, 1, 1), D(2025, 1, 31))
        self.assertEqual([r.observation.lineage.provenance for r in series.readings], ["REFUTED"])


class TypedOutcomeTests(unittest.TestCase):
    """Section 9B, the typed lookup outcomes: each maps to exactly one (state, reason) pair, and a number is
    withheld only at INSUFFICIENT_DATA."""

    SESSIONS = [D(2025, 4, 1), D(2025, 4, 2), D(2025, 4, 3), D(2025, 4, 4), D(2025, 4, 7), D(2025, 4, 8), D(2025, 4, 9),
                D(2025, 4, 10)]

    def test_price_missed_sessions_zero_to_seven(self):
        cal = k.exchange_calendar("NY", ("XNYS",), self.SESSIONS, covers=(D(2025, 4, 1), D(2025, 4, 10)))
        conv = market11_conventions(CalendarSet([cal]))
        store = k.store([k.quote_reading(D(2025, 4, 1), "100.00")], mic="XNYS")
        # sessions d with 1 April < d <= as_of: 1 April itself 0; then 2, 3, 4, 7, 8, 9, 10 April are 1, 2, 3, 4, 5, 6, 7
        expected = {
            0: (S.AVAILABLE, None, True), 1: (S.AVAILABLE, R.STALE_DATA, True), 2: (S.LIMITED, R.STALE_DATA, True),
            3: (S.LIMITED, R.STALE_DATA, True), 4: (S.LIMITED, R.STALE_DATA, True),
            5: (S.INSUFFICIENT_DATA, R.STALE_DATA, False), 6: (S.INSUFFICIENT_DATA, R.STALE_DATA, False),
            7: (S.INSUFFICIENT_DATA, R.STALE_DATA, False)}
        days = [D(2025, 4, 1)] + self.SESSIONS[1:]
        for missed, day in enumerate(days):
            lk = store.quote_on(k.LID, day, conv)
            st = price_input_state(lk)
            self.assertEqual((st.state, st.reason, lk.selected is not None), expected[missed], f"{missed} missed")
            self.assertEqual(lk.missed_count, missed)

    def test_fx_missed_fixings_the_withheld_rate_is_missing_fx_history_not_stale_data(self):
        fixings = [D(2025, 4, 1), D(2025, 4, 2), D(2025, 4, 3), D(2025, 4, 4), D(2025, 4, 7), D(2025, 4, 8)]
        conv = market11_conventions(CalendarSet([k.ecb_calendar(fixings, covers=(D(2025, 4, 1), D(2025, 4, 10)))]))
        store = k.store([k.fx_reading(D(2025, 4, 1), "USD", "1.0800")])
        want = {0: (S.AVAILABLE, None), 1: (S.AVAILABLE, R.STALE_DATA), 2: (S.LIMITED, R.STALE_DATA),
                3: (S.LIMITED, R.STALE_DATA), 4: (S.LIMITED, R.STALE_DATA), 5: (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY)}
        for missed, day in enumerate(fixings):
            lk = store.fx_on(k.EUR, k.USD, day, conv)
            self.assertEqual((pair(fx_input_state(lk)), lk.rate is not None), (want[missed], missed < 5), f"{missed} missed")

    def test_freshness_unknown_is_insufficient_with_no_code_for_price_and_fx(self):
        none = market11_conventions(CalendarSet())
        p = k.store([k.quote_reading(D(2025, 4, 1), "100.00")], mic="XNYS").quote_on(k.LID, D(2025, 4, 3), none)
        f = k.store([k.fx_reading(D(2025, 4, 1), "USD", "1.08")]).fx_on(k.EUR, k.USD, D(2025, 4, 3), none)
        self.assertEqual((p.outcome, pair(price_input_state(p))), (LookupOutcome.FRESHNESS_UNKNOWN, (S.INSUFFICIENT_DATA, None)))
        self.assertEqual((f.outcome, pair(fx_input_state(f))), (LookupOutcome.FRESHNESS_UNKNOWN, (S.INSUFFICIENT_DATA, None)))
        self.assertTrue(any("CALENDAR_COVERAGE_GAP" in n for n in p.lineage_notes + f.lineage_notes))

    def test_cnh_disagreement_and_implausibility_are_never_folded_into_no_history(self):
        cal = k.ecb_calendar([D(2025, 1, 2)], covers=(D(2025, 1, 1), D(2025, 1, 10)))
        conv = market11_conventions(CalendarSet([cal]))
        base = [k.fx_reading(D(2025, 1, 2), "USD", "1.0823"), k.fx_reading(D(2025, 1, 2), "HKD", "8.6000")]
        store = k.store(base + [k.fx_reading(D(2025, 1, 2), "CNH", "7.9")])
        cnh = store.fx_on(k.CNH, k.USD, D(2025, 1, 2), conv)
        self.assertEqual((cnh.outcome, pair(fx_input_state(cnh))), (LookupOutcome.NOT_IN_RELEASE, (S.INSUFFICIENT_DATA, R.MISSING_FX_HISTORY)))
        implausible = store.fx_on(k.USD, k.HKD, D(2025, 1, 2), conv)  # 8.6000 / 1.0823 = 7.946: outside 7.75..7.85
        self.assertNotEqual(implausible.outcome, LookupOutcome.NO_HISTORY)
        self.assertEqual(pair(fx_input_state(implausible)), (S.INSUFFICIENT_DATA, R.SOURCE_CONFLICT))
        two = k.store([k.quote_reading(D(2025, 4, 1), "100.00", source="a", group="a", sha=k.SHA),
                       k.quote_reading(D(2025, 4, 1), "101.00", source="b", group="b", sha=k.SHA2)], mic="XNYS")
        lk = two.quote_on(k.LID, D(2025, 4, 1), market11_conventions(CalendarSet()))
        self.assertNotEqual(lk.outcome, LookupOutcome.NO_HISTORY)
        self.assertEqual(pair(price_input_state(lk)), (S.INSUFFICIENT_DATA, R.SOURCE_CONFLICT))


if __name__ == "__main__":
    unittest.main()
