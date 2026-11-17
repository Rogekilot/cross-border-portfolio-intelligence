"""market-data/1.15 section 7A: the Alpha Vantage A-share route, PENDING OBSERVATION and NOT ADMITTED.

Every file here is SYNTHETIC (invented numbers and codes; none derived from a real file). The expected values are the hand-derived
numbers of the methodology's Examples 7A-G1 to 7A-G4 (Ruling 7A.1 to 7A.3), written out below from those examples, never taken from
this code's output. The synthetic calendar `SYN_CN` is the one the examples assume (not asserted as fact about any real exchange).

Also pinned: the `alphavantage.us` adapter output on an existing fixture (US behaviour is unchanged by the parameterization), the
admission gate (a terms attestation alone admits nothing: SOURCE_PENDING_OBSERVATION / SOURCE_NOT_IN_PRIMARY_ORDER), and the
duplicate-session-date refusal that Ruling 7A.3 (c) 3 requires for CN.
"""

import dataclasses
import datetime
import sys
import tempfile
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_cp2c1_kit as k  # noqa: E402

kit = k.kit

from domain.instrument import SecurityType  # noqa: E402
from marketdata import contracts as c  # noqa: E402
from marketdata import profiles as prof  # noqa: E402
from marketdata.adapters.alphavantage import (  # noqa: E402
    AlphaVantageQuoteAdapter,
    parse_cn_vendor_id,
)
from marketdata.adapters.base import AdapterRegistry, IssueCode  # noqa: E402
from marketdata.adapters.calendar_file import CalendarFileAdapter  # noqa: E402
from marketdata.calendars import CalendarSet  # noqa: E402
from marketdata.canonical import sha256_hex  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data, ingest_file  # noqa: E402
from marketdata.manifest import (  # noqa: E402
    DataKind,
    FileManifest,
    MarketDataRelease,
    SourceRecord,
    TermsCheck,
)
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.files import VerifiedFile  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.profiles import ProfileNotAdmittedError  # noqa: E402
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry  # noqa: E402
from marketdata.states import price_input_state  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

D = datetime.date
S, R = SufficiencyState, ReasonCode
UTC = datetime.timezone.utc
CN_FUNCTION = (("function", "TIME_SERIES_DAILY"), ("outputsize", "compact"))
SYN_SOURCE = "synthetic.alphavantage.cn"
FORMAT = "alphavantage_csv_daily/1"
SYN_REC = SourceRecord(SYN_SOURCE, SYN_SOURCE, "synthetic", "synthetic", synthetic=True)
CAL_REC = SourceRecord("calendar.manual", "calendar.manual", "calendar", "calendar", synthetic=True)

# --- the examples' synthetic calendar SYN_CN: every weekday in 2026-09-01..2026-10-31 except the closures ------------------------
CLOSED = {D(2026, 9, 25), D(2026, 10, 1), D(2026, 10, 2), D(2026, 10, 5), D(2026, 10, 6), D(2026, 10, 7)}


def syn_cn_sessions():
    day, out = D(2026, 9, 1), []
    while day <= D(2026, 10, 31):
        if day.weekday() < 5 and day not in CLOSED:
            out.append(day.isoformat())
        day += datetime.timedelta(days=1)
    return out


# --- the examples' files ---------------------------------------------------------------------------------------------------
G1_ROWS = [  # oldest first; av_csv writes them newest first, as the vendor does
    ("2026-09-24", "10.0000", "10.1800", "9.9500", "10.1200", "1100300"),
    ("2026-09-28", "10.1000", "10.1500", "9.9800", "10.0500", "987600"),
    ("2026-09-29", "10.0500", "10.2200", "10.0000", "10.2000", "1310000"),
    ("2026-09-30", "10.2000", "10.3500", "10.1100", "10.3000", "1523400"),
    ("2026-10-08", "10.3500", "10.6000", "10.2800", "10.5500", "2034500"),
]
G2_ROWS = [  # 09-29 is a suspended day written as a zero-volume row
    ("2026-09-28", "8.0500", "8.1500", "8.0100", "8.1200", "912000"),
    ("2026-09-29", "8.1200", "8.1200", "8.1200", "8.1200", "0"),
    ("2026-09-30", "8.1500", "8.2400", "8.0800", "8.2000", "845000"),
]
G3A_ROWS = [
    ("2026-09-28", "1.2300", "1.2330", "1.2260", "1.2300", "45500000"),
    ("2026-09-29", "1.2280", "1.2350", "1.2250", "1.2345", "48000000"),
    ("2026-09-30", "1.2310", "1.2400", "1.2290", "1.2340", "50123400"),
]
G3C_ROWS = [
    ("2026-09-29", "10.0000", "10.1200", "9.9900", "10.1000", "650000"),
    ("2026-09-30", "10.1000", "10.1500", "10.0500", "10.1250", "700000"),
]
R_G1 = datetime.datetime(2026, 10, 8, 8, 0, tzinfo=UTC)
R_0930 = datetime.datetime(2026, 9, 30, 8, 0, tzinfo=UTC)
R_0930_MIDDAY = datetime.datetime(2026, 9, 30, 5, 0, tzinfo=UTC)  # 13:00 in Shanghai: before the 15:00 close


def manifest(vendor_ids, currency=k.CNY, retrieved=R_G1, source=SYN_SOURCE, scope=c.UsageScope.SYNTHETIC_TEST,
             request=CN_FUNCTION, payload=b"x", adjustment=c.AdjustmentStatus.UNDECLARED):
    return FileManifest(
        file_sha256=sha256_hex(payload), size_bytes=len(payload), payload_filename="x.csv", payload_format=FORMAT,
        source_id=source, data_kind=DataKind.QUOTE, retrieval_time=retrieved, retrieved_by="synthetic",
        declared_adjustment=adjustment, usage_scope=scope, declared_currency=currency, source_identifiers=tuple(vendor_ids),
        declared_delay=c.DataDelayStatus.END_OF_DAY, request=request)


def translate(vendor_id, rows=None, payload=None, **kw):
    payload = payload if payload is not None else k.av_csv(rows)
    return AlphaVantageQuoteAdapter(SYN_SOURCE).translate(manifest((vendor_id,), payload=payload, **kw), payload)


def csv_with(*lines):
    return ("timestamp,open,high,low,close,volume\n" + "\n".join(lines) + "\n").encode("utf-8")


ONE_ROW = [("2026-09-29", "10.0000", "10.1200", "9.9900", "10.1000", "650000")]  # a valid row: low <= open <= close <= high, 10.1 on the 2-decimal grid


def ingest_one(vendor_id, ident, currency=k.CNY, rows=None):
    """The PRODUCT path for one synthetic one-row file: manifest -> `ingest_file` (the adapter, then the identity resolver)."""
    payload = k.av_csv(rows or ONE_ROW)
    m = manifest((vendor_id,), currency=currency, payload=payload)
    return ingest_file(VerifiedFile(m, payload, Path("x")), AlphaVantageQuoteAdapter(SYN_SOURCE), ident, SYN_REC)


# --- the synthetic identity table L1..L6 (Examples, shared set-up) --------------------------------------------------------------
class IdentityWithNullType(InMemoryIdentityRegistry):
    """L4 has `SecurityType` null in the example; the domain enum cannot hold that, so the resolver reports None for it."""

    NULL_TYPE_CODES = ("569998",)

    def security_type(self, listing_id):
        if self.listing(listing_id).ticker in self.NULL_TYPE_CODES:
            return None
        return super().security_type(listing_id)


def identity():
    reg = IdentityWithNullType(kit.SequentialIds())
    cn, usd = k.CNY, k.USD
    reg.register_instruments([
        InstrumentEntry("L1", SecurityType.COMMON_STOCK, "XSHG", "SSE", "609999", cn),
        InstrumentEntry("L2", SecurityType.COMMON_STOCK, "XSHE", "SZSE", "009999", cn),
        InstrumentEntry("L3", SecurityType.ETF, "XSHG", "SSE", "569999", cn),
        InstrumentEntry("L4", SecurityType.ETF, "XSHG", "SSE", "569998", cn),  # reported as type None by the subclass
        InstrumentEntry("L5", SecurityType.COMMON_STOCK, "XSHE", "SZSE", "009997", cn),
        InstrumentEntry("L6", SecurityType.COMMON_STOCK, "XSHG", "SSE", "909999", usd),  # a B-share
    ])
    return reg


class Vendor(unittest.TestCase):
    """Example 7A-G4 and Ruling 7A.1: vendor id -> MIC, and resolution by (MIC, code), never by the code alone."""

    def setUp(self):
        self.ident = identity()

    def listing(self, ticker, mic):
        return kit.listing_id(self.ident, ticker, mic)

    def test_example_7a_g4_table_through_the_product_path(self):
        """The G4 table of the methodology, run through `ingest_file` (the adapter and the identity resolver the build path uses),
        not through a test-only helper. 'unresolved' is a row that becomes no reading: either the adapter reads nothing and says
        VENDOR_ID_UNRECOGNIZED, or the resolver finds no single listing and the row is a ResolutionException (UNRESOLVED_IDENTITY)."""
        RANGE, UNREC = IssueCode.VENDOR_CODE_RANGE_UNEXPECTED, IssueCode.VENDOR_ID_UNRECOGNIZED
        cases = [  # vendor id, parsed MIC or None, resolved listing (ticker, mic) or None, flags (informational issues)
            ("609999.SHH", "XSHG", ("609999", "XSHG"), ()),
            ("009999.SHZ", "XSHE", ("009999", "XSHE"), ()),
            ("569999.SHH", "XSHG", ("569999", "XSHG"), ()),
            ("009997.SHH", "XSHG", None, (RANGE,)),  # the 000001 hazard: L5 is on XSHE, so (XSHG, 009997) is nothing
            ("009997.SHZ", "XSHE", ("009997", "XSHE"), ()),
            ("609999.SHZ", "XSHE", None, (RANGE,)),  # a .SHZ code starting with 6
            ("609999.SS", None, None, (UNREC,)),
            ("609999", None, None, (UNREC,)),
            ("60999.SHH", None, None, (UNREC,)),
            ("609999.shh", None, None, (UNREC,)),
        ]
        for vendor_id, mic, want, flags in cases:
            parsed = parse_cn_vendor_id(vendor_id)
            self.assertEqual(None if parsed is None else parsed.mic, mic, vendor_id)
            result = ingest_one(vendor_id, self.ident)
            codes = sorted(i.code.value for i in result.issues if i.code is not IssueCode.UNRESOLVED_IDENTITY)
            self.assertEqual(codes, sorted(f.value for f in flags), vendor_id)
            if want is None:
                self.assertEqual(result.readings, (), vendor_id)  # unresolved: no reading for any listing
                if mic is not None:  # a well-formed id that names no listing is a resolution exception, never a guess
                    self.assertEqual([e.status for e in result.exceptions], [c.ResolutionStatus.UNRESOLVED], vendor_id)
            else:
                self.assertEqual([r.observation.listing_id for r in result.readings], [self.listing(*want)], vendor_id)
                self.assertEqual(result.exceptions, (), vendor_id)
        # 909999.SHH: (XSHG, 909999) is L6, the USD B-share, so it RESOLVES; the route does not take it. A file declared CNY is refused
        # by the currency mismatch of Ruling 4.1a (the message names the listing's own currency, which proves it resolved to L6) ...
        b = ingest_one("909999.SHH", self.ident)
        self.assertEqual(b.readings, ())
        mismatch = [i for i in b.issues if i.code is IssueCode.TRADING_CURRENCY_MISMATCH]
        self.assertEqual(len(mismatch), 1)
        self.assertIn("declared CNY, listing trades in USD", mismatch[0].detail)
        self.assertEqual(b.exceptions, ())
        # ... and a USD or HKD declaration is not allowed on this route at all (Ruling 7A.1 item 7)
        for ccy in (k.USD, k.HKD):
            refused = ingest_one("909999.SHH", self.ident, currency=ccy)
            self.assertEqual((refused.readings, [i.code for i in refused.issues]), ((), [IssueCode.CURRENCY_MISMATCH]), ccy)

    def test_only_the_mic_is_inferred_and_the_exact_grammar_is_required(self):
        for bad in ("609999.SHH\n", " 609999.SHH", "609999.SHH ", "６09999.SHH", "6099999.SHH", "609999.SH", "609999.BJ", "609999.SZ", ""):
            self.assertIsNone(parse_cn_vendor_id(bad), repr(bad))
        p = parse_cn_vendor_id("609999.SHH")
        self.assertEqual((p.code, p.suffix, p.mic), ("609999", "SHH", "XSHG"))

    def test_the_code_alone_never_resolves_and_a_stored_vendor_row_cannot_stand_in_for_mic_and_code(self):
        """Ruling 7A.1 item 4 (review M-2): resolution is by (MIC, code) and nothing else. A vendor-id row, scoped to the route's source
        or to the real `alphavantage.cn`, that points at ANOTHER listing is not a key, whichever listing it points at. Each case is
        run through the product path (`ingest_file`); the identity table is changed before the file is read."""
        for scope in (SYN_SOURCE, "alphavantage.cn"):
            ident = identity()
            # (a) the 7A-G4 hazard row: L5 is XSHE 009997, and a row maps `009997.SHH` to it. (XSHG, 009997) is still nothing.
            ident.add_vendor_id(kit.listing_id(ident, "009997", "XSHE"), scope, "009997.SHH")
            a = ingest_one("009997.SHH", ident)
            self.assertEqual(a.readings, (), scope)
            self.assertEqual([e.status for e in a.exceptions], [c.ResolutionStatus.UNRESOLVED], scope)
            self.assertIn(IssueCode.VENDOR_CODE_RANGE_UNEXPECTED, [i.code for i in a.issues], scope)
            # (b) a row on the RIGHT exchange but the wrong code: `609998.SHH` is not L1 (XSHG 609999) because a row says so
            ident.add_vendor_id(kit.listing_id(ident, "609999", "XSHG"), scope, "609998.SHH")
            b = ingest_one("609998.SHH", ident)
            self.assertEqual((b.readings, [e.status for e in b.exceptions]), ((), [c.ResolutionStatus.UNRESOLVED]), scope)
            # (c) a row that CONTRADICTS the (MIC, code) lookup does not make it a conflict either: (XSHG, 609999) is L1 whatever it says
            ident.add_vendor_id(kit.listing_id(ident, "569999", "XSHG"), scope, "609999.SHH")
            r = ingest_one("609999.SHH", ident)
            self.assertEqual([x.observation.listing_id for x in r.readings], [kit.listing_id(ident, "609999", "XSHG")], scope)
            self.assertEqual(r.exceptions, (), scope)

    def test_the_adapter_hands_over_mic_and_code_only_and_the_vendor_id_stays_in_the_row_reference(self):
        out = translate("609999.SHH", G1_ROWS)
        ids = out.quotes[0].identifiers
        self.assertEqual((ids.mic, ids.ticker, ids.vendor_id, ids.source_id, ids.figi), ("XSHG", "609999", None, None, None))
        # the vendor id is a label of the row (lineage and every issue), scoped to the file's source; it is not offered as a key
        self.assertEqual({q.lineage.source_record_ref.split("@")[0] for q in out.quotes}, {"609999.SHH"})
        self.assertEqual({q.lineage.source_id for q in out.quotes}, {SYN_SOURCE})

    def test_a_vendor_id_outside_the_grammar_reads_nothing(self):
        for bad in ("609999.SS", "609999", "60999.SHH", "609999.shh"):
            out = translate(bad, G1_ROWS)
            self.assertEqual((out.quotes, out.adjusted, out.reference), ((), (), ()), bad)
            self.assertEqual([i.code for i in out.issues], [IssueCode.VENDOR_ID_UNRECOGNIZED], bad)

    def test_a_code_range_mismatch_is_flagged_and_still_read(self):
        out = translate("609999.SHZ", G1_ROWS)  # a .SHZ code starting with 6
        self.assertEqual(len(out.quotes), 5)
        self.assertEqual([i.code for i in out.issues], [IssueCode.VENDOR_CODE_RANGE_UNEXPECTED])

    def test_b_shares_are_out_of_route_a_manifest_may_not_declare_usd_or_hkd(self):
        for ccy in (k.USD, k.HKD):
            out = translate("909999.SHH", G1_ROWS, currency=ccy)
            self.assertEqual((out.quotes, [i.code for i in out.issues]), ((), [IssueCode.CURRENCY_MISMATCH]), ccy)
        self.assertEqual(translate("609999.SHH", G1_ROWS, currency=None).issues[0].code, IssueCode.UNDECLARED_CURRENCY)


class AdapterExamples(unittest.TestCase):
    """Examples 7A-G1 to 7A-G3: the adapter's output, derived by hand in the methodology."""

    def test_g1_five_quotes_ascending_with_verbatim_close_text(self):
        out = translate("609999.SHH", G1_ROWS)
        self.assertEqual(out.issues, ())
        want = [  # value_date, close, volume
            (D(2026, 9, 24), "10.12", "1100300"), (D(2026, 9, 28), "10.05", "987600"), (D(2026, 9, 29), "10.2", "1310000"),
            (D(2026, 9, 30), "10.3", "1523400"), (D(2026, 10, 8), "10.55", "2034500")]
        self.assertEqual([(q.value_date, q.price, q.volume) for q in out.quotes],
                         [(d, Decimal(p), Decimal(v)) for d, p, v in want])
        self.assertEqual({(q.recovered, q.precision_bound, q.currency) for q in out.quotes}, {(True, Decimal(0), k.CNY)})
        self.assertEqual([q.lineage.source_value_text for q in out.quotes], ["10.1200", "10.0500", "10.2000", "10.3000", "10.5500"])
        self.assertEqual({q.lineage.source_record_ref.split("@")[0] for q in out.quotes}, {"609999.SHH"})  # the vendor id is the row's label
        # the input order is not assumed
        oldest_first = translate("609999.SHH", payload=k.av_csv(G1_ROWS, newest_first=False))
        self.assertEqual([(q.value_date, q.price) for q in oldest_first.quotes], [(q.value_date, q.price) for q in out.quotes])
        # open/high/low are not grid-checked: each carries its V2 bound of half of 10^-4
        self.assertEqual({r.field_bounds for r in out.reference}, {(Decimal("0.00005"),) * 3})

    def test_g1_label_is_read_as_raw_from_the_profile_and_stays_unverifiable(self):
        q = translate("609999.SHH", G1_ROWS).quotes[0]
        self.assertIs(q.lineage.adjustment_status, c.AdjustmentStatus.RAW)
        # re-recorded 2026-10-25 (F1 R4a, market-data/1.16 section 11 item 23): the label source's status is profile data and is DECLARED
        # (PD-0066 decision 3: the owner read the vendor's documentation on 2026-10-24; it names .SHH/.SHZ on the same call). It was MEMORY.
        # The label STATUS below the source is unchanged: UNVERIFIABLE is set by ingestion, and a vendor's declaration is not a verification.
        self.assertEqual(q.lineage.adjustment_label_source, "PROFILE_CALL_ADJUSTMENT:alphavantage.cn:TIME_SERIES_DAILY:DECLARED")
        self.assertEqual(q.lineage.precision_profile_id, f"{prof.PROFILE_SET_VERSION}:alphavantage.cn:close")
        self.assertEqual(q.lineage.volume_unit_status, "DECLARED_UNVERIFIED")  # PROVISIONAL volume: no magnitude rule may use it

    def test_g2_a_zero_volume_row_is_an_observation_with_volume_zero_and_g2_b_omits_it(self):
        a = translate("009999.SHZ", G2_ROWS, retrieved=R_0930)
        self.assertEqual(a.issues, ())
        self.assertEqual([(q.value_date, q.price, q.volume) for q in a.quotes],
                         [(D(2026, 9, 28), Decimal("8.12"), Decimal(912000)), (D(2026, 9, 29), Decimal("8.12"), Decimal(0)),
                          (D(2026, 9, 30), Decimal("8.2"), Decimal(845000))])
        self.assertTrue(all(q.recovered for q in a.quotes))
        b = translate("009999.SHZ", [G2_ROWS[0], G2_ROWS[2]], retrieved=R_0930)
        self.assertEqual([q.value_date for q in b.quotes], [D(2026, 9, 28), D(2026, 9, 30)])

    def test_g3_a_with_the_class_unknown_strict_two_decimals_applies_at_the_adapter(self):
        out = translate("569999.SHH", G3A_ROWS, retrieved=R_0930)
        by_day = {q.value_date: q for q in out.quotes}
        self.assertEqual((by_day[D(2026, 9, 28)].price, by_day[D(2026, 9, 28)].recovered, by_day[D(2026, 9, 28)].precision_bound),
                         (Decimal("1.23"), True, Decimal(0)))
        for day, price in ((D(2026, 9, 29), "1.2345"), (D(2026, 9, 30), "1.234")):
            q = by_day[day]
            self.assertEqual((q.price, q.recovered, q.precision_bound), (Decimal(price), False, Decimal("0.00005")), day)
        self.assertEqual(sorted(i.row_ref for i in out.issues if i.code is IssueCode.PRICE_NOT_RECOVERED),
                         ["569999.SHH@2026-09-29", "569999.SHH@2026-09-30"])

    def test_g3_c_an_off_grid_a_share_close_is_not_recovered_and_trailing_zeros_carry_no_decimals(self):
        by_day = {q.value_date: q for q in translate("609999.SHH", G3C_ROWS, retrieved=R_0930).quotes}
        self.assertEqual((by_day[D(2026, 9, 29)].price, by_day[D(2026, 9, 29)].recovered), (Decimal("10.1"), True))
        self.assertEqual((by_day[D(2026, 9, 30)].price, by_day[D(2026, 9, 30)].recovered, by_day[D(2026, 9, 30)].precision_bound),
                         (Decimal("10.125"), False, Decimal("0.00005")))

    def test_g3_d_a_float_rendering_in_a_text_field_fails_the_profile_check_and_is_not_repaired(self):
        rows = list(G1_ROWS)
        rows[3] = ("2026-09-30", "10.2000", "10.3500", "10.1100", "10.300000000000001", "1523400")
        out = translate("609999.SHH", rows)
        self.assertEqual((out.quotes, out.adjusted, out.reference), ((), (), ()))
        self.assertEqual([i.code for i in out.issues], [IssueCode.PROFILE_CHECK_FAILED])

    def test_a_row_failing_the_ohlc_check_is_not_admitted(self):
        rows = [("2026-09-29", "10.0000", "10.1000", "10.2000", "10.0500", "10")]  # low above open
        out = translate("609999.SHH", rows)
        self.assertEqual((out.quotes, [i.code for i in out.issues]), ((), [IssueCode.ROW_INCONSISTENT]))

    def test_ruling_7a_3_two_rows_for_one_date_refuse_the_whole_file(self):
        dup = csv_with("2026-09-29,10.0500,10.2200,10.0000,10.2000,1310000",
                       "2026-09-29,10.0500,10.2200,10.0000,10.2000,1310000",  # even an identical repeat
                       "2026-09-28,10.1000,10.1500,9.9800,10.0500,987600")
        # RE-RECORDED 2026-10-25 (review fix round, Addendum A.4): the adapter no longer judges the duplicate; it LISTS what each row states and INGESTION
        # counts them per listing after identity resolution (the unit is the listing, not the vendor symbol). The refusal itself is tested through the real path
        # in test_marketdata_r4a_inputs and in `World.test_g2_*` below.
        out = translate("609999.SHH", payload=dup)
        self.assertEqual([s.ref for s in out.dated_statements], ["609999.SHH@2026-09-28", "609999.SHH@2026-09-29", "609999.SHH@2026-09-29"])
        self.assertEqual(out.issues, ())
        # also when the repeated row would fail its own row check: it still states the session (Addendum A.2 (iv)), and the failure is its own issue
        bad_dup = csv_with("2026-09-29,10.0000,10.1000,10.2000,10.0500,10", "2026-09-29,10.0500,10.2200,10.0000,10.2000,1")
        bad = translate("609999.SHH", payload=bad_dup)
        self.assertEqual([s.ref for s in bad.dated_statements], ["609999.SHH@2026-09-29", "609999.SHH@2026-09-29"])
        self.assertEqual([i.code for i in bad.issues], [IssueCode.ROW_INCONSISTENT])

    def test_ruling_7a_3_the_date_decides_not_its_spelling_review_l1(self):
        """The row parser reads every `date.fromisoformat` form, so two spellings of one date are two rows for one date. Hand-derived:
        1 January 2026 is a Thursday, so ISO week 1 begins on Monday 2025-12-29; week 40 begins 39 weeks later, Monday 2026-09-28; the
        week-date 2026-W40-2 (Tuesday) is 2026-09-29, and the basic form 20260929 is the same day."""
        first = "2026-09-29,10.0500,10.2200,10.0000,10.2000,1310000"
        other_day = "2026-09-28,10.1000,10.1500,9.9800,10.0500,987600"
        for spelling in ("20260929", "2026-W40-2"):
            alone = translate("609999.SHH", payload=csv_with(f"{spelling},10.0500,10.2200,10.0000,10.2000,1310000", other_day))
            self.assertEqual([q.value_date for q in alone.quotes], [D(2026, 9, 28), D(2026, 9, 29)], spelling)  # the spelling is accepted by itself
            for close in ("10.2000", "10.1000"):  # identical to the first row's close, and different from it
                dup = csv_with(first, f"{spelling},10.0500,10.2200,10.0000,{close},1310000", other_day)
                out = translate("609999.SHH", payload=dup)
                # re-recorded 2026-10-25 (Addendum A.4): the adapter lists the two statements, under the PARSED date; ingestion refuses the series
                self.assertEqual([s.ref for s in out.dated_statements],
                                 ["609999.SHH@2026-09-28", "609999.SHH@2026-09-29", "609999.SHH@2026-09-29"], (spelling, close))
        # an ordinary file with one row per date is untouched
        self.assertEqual(len(translate("609999.SHH", G1_ROWS).quotes), 5)


class UsAdapterIsUnchanged(unittest.TestCase):
    """The parameterization must not move `alphavantage.us` by a byte. The values below are written by hand from the fixture rows."""

    ROWS = [
        ("2025-01-02", "100.0000", "101.5000", "99.2500", "100.5000", "1000"),
        ("2025-01-03", "100.5000", "102.0000", "100.0000", "101.2500", "1100"),
        ("2025-01-06", "101.2500", "101.7500", "100.1234", "100.7500", "900"),
    ]

    def run_us(self, payload):
        m = FileManifest(
            file_sha256="d" * 64, size_bytes=1, payload_filename="x", payload_format=FORMAT, source_id="alphavantage.us",
            data_kind=DataKind.QUOTE, retrieval_time=kit.RETRIEVED, retrieved_by="synthetic",
            declared_adjustment=c.AdjustmentStatus.UNDECLARED, usage_scope=c.UsageScope.SYNTHETIC_TEST, declared_currency=k.USD,
            source_identifiers=("AAPL",), declared_delay=c.DataDelayStatus.END_OF_DAY, request=CN_FUNCTION)
        return AlphaVantageQuoteAdapter().translate(m, payload)

    def test_the_us_output_is_pinned_field_by_field(self):
        out = self.run_us(k.av_csv(self.ROWS))
        self.assertEqual(out.issues, ())
        self.assertEqual(
            [(q.value_date, q.price, q.volume, q.recovered, q.precision_bound, q.currency) for q in out.quotes],
            [(D(2025, 1, 2), Decimal("100.5"), Decimal(1000), True, Decimal(0), k.USD),
             (D(2025, 1, 3), Decimal("101.25"), Decimal(1100), True, Decimal(0), k.USD),
             (D(2025, 1, 6), Decimal("100.75"), Decimal(900), True, Decimal(0), k.USD)])
        for q in out.quotes:
            self.assertEqual((q.identifiers.vendor_id, q.identifiers.source_id, q.identifiers.mic, q.identifiers.ticker,
                              q.identifiers.figi), ("AAPL", "alphavantage.us", None, None, None))
            self.assertEqual((q.lineage.precision_profile_id, q.lineage.adjustment_status, q.lineage.volume_unit_status,
                              q.lineage.adjustment_label_source),
                             (f"{prof.PROFILE_SET_VERSION}:alphavantage.us:close", c.AdjustmentStatus.RAW, "DECLARED_UNVERIFIED",
                              # re-recorded 2026-10-25 (F1 R4a, 1.16 item 23, PD-0066 decision 3): the label source's status was MEMORY; nothing else moved
                              "PROFILE_CALL_ADJUSTMENT:alphavantage.us:TIME_SERIES_DAILY:DECLARED"))
        self.assertEqual([r.field_bounds for r in out.reference], [(Decimal("0.00005"),) * 3] * 3)
        self.assertEqual((len(out.adjusted), len(out.reference)), (0, 3))

    def test_the_us_route_has_the_us_profile_and_the_us_grid_whatever_the_source_id_says(self):
        self.assertEqual(AlphaVantageQuoteAdapter().route, "alphavantage.us")
        self.assertEqual(AlphaVantageQuoteAdapter("synthetic.alphavantage_us").route, "alphavantage.us")
        # 100.0250 has 3 decimals at >= 1.00: off the US grid (kept, not recovered)
        q = self.run_us(k.av_csv([("2025-01-02", "100.0000", "101.0000", "99.0000", "100.0250", "10")])).quotes[0]
        self.assertEqual((q.recovered, q.precision_bound), (False, Decimal("0.00005")))

    def test_the_us_adapter_refuses_two_rows_for_one_date_since_1_16(self):
        """RE-RECORDED 2026-10-25 (F1 R4a, market-data/1.16 section 11 item 25). This was `test_known_gap_the_us_adapter_does_not_refuse_two_rows_for_one_date`:
        it pinned that the US adapter kept both rows (Ruling 7A.3 (c) 3 asked the refusal for CN only; the Quant was to decide). 1.16 decided: Test V0
        applies in every market, even for identical rows. The adapter now outputs no reading and names the series (`contradicted`); ingestion turns
        that into the exclusion (see test_marketdata_r4a_inputs.DuplicateSessionDateTests)."""
        dup = csv_with("2025-01-02,100.0000,101.0000,99.0000,100.5000,10", "2025-01-02,100.0000,101.0000,99.0000,100.5000,10")
        # Re-recorded again 2026-10-25 (review fix round, Addendum A.4): the adapter LISTS the two statements (`dated_statements`) and ingestion refuses the
        # series per listing after identity resolution, so a route cannot forget the rule and an alias is the same series.
        out = self.run_us(dup)
        self.assertEqual([(s.ref, s.value_date, s.identifiers.vendor_id) for s in out.dated_statements], [("AAPL@2025-01-02", D(2025, 1, 2), "AAPL")] * 2)
        self.assertEqual((out.issues, out.contradicted), ((), ()))


# --- the examples through the REAL path (files -> adapter -> resolver -> V0 -> store), synthetic world ----------------------------


class World(unittest.TestCase):
    def build(self, vendor_id, rows=None, payload=None, retrieved=R_G1, ident=None, currency=k.CNY):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=[SYN_REC, CAL_REC])
        payload = payload if payload is not None else k.av_csv(rows)
        directory = root / "files" / SYN_SOURCE / "quote" / "2026-10-08"
        directory.mkdir(parents=True)
        m = manifest((vendor_id,), currency=currency, retrieved=retrieved, payload=payload)
        m = dataclasses.replace(m, payload_filename="q.csv")
        (directory / "q.csv").write_bytes(payload)
        (directory / "q.csv.manifest.json").write_text(m.to_json(), encoding="utf-8")
        cal = k.calendar_json("SYN_CN", "EXCHANGE_SESSIONS", ("XSHG", "XSHE"), "Asia/Shanghai",
                              coverage=("2026-09-01", "2026-10-31"), dates=syn_cn_sessions(),
                              close={"default": "15:00", "overrides": []})
        cdir = root / "files" / "calendar.manual" / "calendar" / "2026-10-08"
        cdir.mkdir(parents=True)
        cm = FileManifest(file_sha256=sha256_hex(cal), size_bytes=len(cal), payload_filename="cal.json",
                          payload_format="finweb_calendar_json/1", source_id="calendar.manual", data_kind=DataKind.CALENDAR,
                          retrieval_time=retrieved, retrieved_by="synthetic", declared_adjustment=c.AdjustmentStatus.RAW,
                          usage_scope=c.UsageScope.SYNTHETIC_TEST, source_identifiers=("SYN_CN",),
                          declared_delay=c.DataDelayStatus.END_OF_DAY)
        (cdir / "cal.json").write_bytes(cal)
        (cdir / "cal.json.manifest.json").write_text(cm.to_json(), encoding="utf-8")
        files = FileStore(root)
        release = MarketDataRelease(name="r", files=tuple(sorted((m.file_sha256, cm.file_sha256))), source_precedence=())
        ident = ident or identity()
        built = build_in_memory_market_data(
            release, files, files.load_registry(),
            AdapterRegistry([AlphaVantageQuoteAdapter(SYN_SOURCE), CalendarFileAdapter()]), ident, catalog_calendars={})
        return built, ident, market11_conventions(built.calendars)

    def look(self, built, ident, ticker, mic, day, conv):
        lk = built.store.quote_on(kit.listing_id(ident, ticker, mic), day, conv)
        return lk, price_input_state(lk)

    def test_g1_holidays_are_not_staleness(self):
        built, ident, conv = self.build("609999.SHH", G1_ROWS)
        self.assertEqual([i for _sha, i in built.issues if i.code is not IssueCode.SECURITY_CLASS_UNRESOLVED], [])
        lk, st = self.look(built, ident, "609999", "XSHG", D(2026, 10, 8), conv)
        self.assertEqual((lk.outcome, lk.selected.observation.price, lk.missed_count, st.state, st.reason),
                         (LookupOutcome.FOUND, Decimal("10.55"), 0, S.AVAILABLE, None))
        lk, st = self.look(built, ident, "609999", "XSHG", D(2026, 10, 5), conv)  # a closure: s(D) = 09-30, no sessions in between
        self.assertEqual((lk.date_used, lk.selected.observation.price, lk.missed_count, st.state, st.reason),
                         (D(2026, 9, 30), Decimal("10.3"), 0, S.AVAILABLE, None))
        self.assertEqual(Decimal(300) * lk.selected.observation.price, Decimal("3090.00"))
        lk, st = self.look(built, ident, "609999", "XSHG", D(2026, 9, 25), conv)
        self.assertEqual((lk.date_used, lk.selected.observation.price, lk.missed_count, st.state), (D(2026, 9, 24), Decimal("10.12"), 0, S.AVAILABLE))
        self.assertTrue(lk.synthetic)  # a synthetic version marks every result (Ruling 4.8)

    def test_g2_a_and_b_a_suspension_written_either_way_resolves_identically(self):
        for rows in (G2_ROWS, [G2_ROWS[0], G2_ROWS[2]]):
            built, ident, conv = self.build("009999.SHZ", rows, retrieved=R_0930)
            lk, st = self.look(built, ident, "009999", "XSHE", D(2026, 9, 29), conv)
            self.assertEqual((lk.date_used, lk.selected.observation.price, lk.missed_count, st.state, st.reason),
                             (D(2026, 9, 28), Decimal("8.12"), 1, S.AVAILABLE, R.STALE_DATA), len(rows))
            lk, st = self.look(built, ident, "009999", "XSHE", D(2026, 9, 30), conv)
            self.assertEqual((lk.date_used, lk.selected.observation.price, lk.missed_count, st.state, st.reason),
                             (D(2026, 9, 30), Decimal("8.2"), 0, S.AVAILABLE, None), len(rows))

    def test_g2_c_a_holiday_filled_row_fails_v0_and_supplies_no_reading(self):
        rows = G2_ROWS + [("2026-09-25", "8.0500", "8.0500", "8.0500", "8.0500", "0")]
        built, ident, conv = self.build("009999.SHZ", sorted(rows), retrieved=R_0930)
        lk, st = self.look(built, ident, "009999", "XSHE", D(2026, 9, 30), conv)
        self.assertEqual((lk.outcome, lk.selected, st.state, st.reason),
                         (LookupOutcome.NO_HISTORY, None, S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY))
        self.assertTrue(any(n.startswith("SERIES_CONTRADICTED: V0") and "2026-09-25" in n for n in lk.lineage_notes), lk.lineage_notes)
        # RE-RECORDED 2026-10-25 (F1 R4a, market-data/1.16 item 28, Ruling 4.7 item 1): the lineage used to list NO_ADMITTED_SOURCE beside it (A.5 CN is
        # empty even in this synthetic world). Now M holds a series of the listing, an excluded one, and that exclusion is the cause: V0 only, as Example
        # 7A-G2 (c) states. The freshness stays UNKNOWN (the market still has no admitted source).
        self.assertFalse(any(n.startswith("NO_ADMITTED_SOURCE") for n in lk.lineage_notes), lk.lineage_notes)
        self.assertEqual(len(lk.lineage_notes), 1)

    def test_g2_dup_a_session_date_written_twice_in_a_cn_file_reaches_the_lookup_lineage_as_v0(self):
        """market-data/1.16 item 25, the CN case. The CN route already output no reading for two rows of one date; what is new is the CAUSE: it used to
        reach the lookup as 'NO_ADMITTED_SOURCE' alone (the file was refused whole, nothing of it remained in M). Now the series is excluded and the lookup
        names V0, DUPLICATE_SESSION_DATE and the date, and not NO_ADMITTED_SOURCE (item 28). Identical rows count (09-30 is written twice, equal)."""
        rows = sorted(G2_ROWS + [G2_ROWS[2]])
        built, ident, conv = self.build("009999.SHZ", rows, retrieved=R_0930)
        for day in (D(2026, 9, 28), D(2026, 9, 30)):  # the WHOLE series is excluded, not only the repeated date
            lk, st = self.look(built, ident, "009999", "XSHE", day, conv)
            self.assertEqual((lk.outcome, lk.selected, st.state, st.reason),
                             (LookupOutcome.NO_HISTORY, None, S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY), day)
        (note,) = lk.lineage_notes
        self.assertTrue(note.startswith("SERIES_CONTRADICTED: V0 on file "), note)
        self.assertIn("DUPLICATE_SESSION_DATE", note)
        self.assertIn("2026-09-30", note)
        self.assertEqual([(r.test, r.status, r.admitted) for r in built.label_results if r.test == "V0"], [("V0", c.LabelStatus.CONTRADICTED, False)])

    def test_g2_d_a_file_retrieved_during_the_session_contradicts_the_whole_series(self):
        built, ident, conv = self.build("009999.SHZ", G2_ROWS, retrieved=R_0930_MIDDAY)
        for day in (D(2026, 9, 29), D(2026, 9, 30)):
            lk, st = self.look(built, ident, "009999", "XSHE", day, conv)
            self.assertEqual((lk.outcome, lk.selected, st.state, st.reason),
                             (LookupOutcome.NO_HISTORY, None, S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY), day)  # no fall-back to 09-28

    def test_g3_a_the_class_from_the_identity_record_admits_the_three_decimal_etf_close(self):
        built, ident, conv = self.build("569999.SHH", G3A_ROWS, retrieved=R_0930)
        lk, st = self.look(built, ident, "569999", "XSHG", D(2026, 9, 29), conv)
        self.assertEqual((lk.date_used, lk.selected.observation.price, lk.missed_count, st.state, st.reason),
                         (D(2026, 9, 28), Decimal("1.23"), 1, S.AVAILABLE, R.STALE_DATA))  # 1.2345 has 4 decimals: never an admissible print
        lk, st = self.look(built, ident, "569999", "XSHG", D(2026, 9, 30), conv)
        self.assertEqual((lk.date_used, lk.selected.observation.price, lk.missed_count, st.state, st.reason),
                         (D(2026, 9, 30), Decimal("1.234"), 0, S.AVAILABLE, None))
        self.assertEqual(Decimal(10000) * lk.selected.observation.price, Decimal("12340.00"))

    def test_g3_b_an_unknown_class_costs_freshness_and_never_admits_an_off_grid_price(self):
        built, ident, conv = self.build("569998.SHH", G3A_ROWS, retrieved=R_0930)
        lk, st = self.look(built, ident, "569998", "XSHG", D(2026, 9, 30), conv)
        self.assertEqual((lk.date_used, lk.selected.observation.price, lk.missed_count, st.state, st.reason),
                         (D(2026, 9, 28), Decimal("1.23"), 2, S.LIMITED, R.STALE_DATA))
        self.assertIn(IssueCode.SECURITY_CLASS_UNRESOLVED, [i.code for _sha, i in built.issues])

    def test_g3_c_an_off_grid_a_share_close_ages_the_last_admissible_print(self):
        built, ident, conv = self.build("609999.SHH", G3C_ROWS, retrieved=R_0930)
        lk, st = self.look(built, ident, "609999", "XSHG", D(2026, 9, 30), conv)
        self.assertEqual((lk.date_used, lk.selected.observation.price, lk.missed_count, st.state, st.reason),
                         (D(2026, 9, 29), Decimal("10.1"), 1, S.AVAILABLE, R.STALE_DATA))

    def test_g1_g4_a_cny_file_of_a_usd_b_share_is_refused_at_ingest_by_the_currency_mismatch(self):
        rows = [("2026-09-29", "1.0000", "1.1000", "0.9000", "1.0500", "10")]
        built, ident, conv = self.build("909999.SHH", rows, retrieved=R_0930)
        self.assertIn(IssueCode.TRADING_CURRENCY_MISMATCH, [i.code for _sha, i in built.issues])
        lk, st = self.look(built, ident, "909999", "XSHG", D(2026, 9, 30), conv)
        self.assertEqual((lk.outcome, lk.selected), (LookupOutcome.NO_HISTORY, None))


# --- the admission gate: a terms attestation alone admits nothing (Ruling 7A.3) ---------------------------------------------------
PERMITTING = TermsCheck("owner", D(2026, 10, 23), True, "synthetic test record of a PERMITTING terms check")
REAL_CN = SourceRecord("alphavantage.cn", "Alpha Vantage CN", "alphavantage", "alphavantage", terms_check=PERMITTING)


class AdmissionGate(unittest.TestCase):
    def real_manifest(self, kind=DataKind.QUOTE):
        m = manifest(("609999.SHH",), source="alphavantage.cn", scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY)
        return dataclasses.replace(m, data_kind=kind)

    def test_the_profile_is_pending_and_a_cn_has_no_admitted_source(self):
        p = prof.SOURCES["alphavantage.cn"]
        self.assertEqual((p.status, p.upstream, p.markets, p.admitted), (prof.TO_OBSERVE, "alphavantage", ("CN",), False))
        self.assertEqual({f.status for f in p.fields.values()}, {prof.PROVISIONAL_UNOBSERVED})
        self.assertEqual(prof.PRIMARY_ORDER["CN"], ())
        self.assertEqual(prof.PRIMARY_ORDER["HK"], ())
        self.assertFalse(prof.market_has_admitted_source("CN"))
        self.assertTrue(any("alphavantage.cn" in i and "pending observation" in i for i in prof.profile_open_items()))
        self.assertFalse(any("alphavantage.us" in i for i in prof.profile_open_items()))  # the US profile is still OBSERVED and admitted

    def test_require_admitted_refuses_with_the_pending_code(self):
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            prof.require_admitted("alphavantage.cn")
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_PENDING_OBSERVATION)
        self.assertIn("SOURCE_PENDING_OBSERVATION", str(cm.exception))
        self.assertTrue(prof.require_admitted("alphavantage.us").admitted)  # US unchanged

    def test_a_real_file_with_a_permitting_terms_check_is_refused_before_its_payload_is_parsed(self):
        self.assertTrue(REAL_CN.terms_attested)  # the terms barrier alone would let it through
        for kind in (DataKind.QUOTE, DataKind.CALENDAR):
            m = self.real_manifest(kind)
            verified = VerifiedFile(m, b"this is never parsed", Path("x"))

            class Spy:  # an adapter that must not be called
                source_id, data_kind, payload_formats, adapter_id, adapter_version = "alphavantage.cn", kind, (FORMAT,), "spy", "0"

                def translate(self, manifest, payload):
                    raise AssertionError("the payload was parsed")

            with self.assertRaises(ProfileNotAdmittedError) as cm:
                ingest_file(verified, Spy(), identity(), REAL_CN)
            self.assertEqual(cm.exception.gate_code, prof.SOURCE_PENDING_OBSERVATION, kind)

    def test_the_build_path_refuses_a_real_cn_file_even_though_the_registry_attests_the_terms(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        kit.write_registry(root, extra=[REAL_CN])
        payload = k.av_csv(G1_ROWS)
        directory = root / "files" / "alphavantage.cn" / "quote" / "2026-10-08"
        directory.mkdir(parents=True)
        m = dataclasses.replace(self.real_manifest(), file_sha256=sha256_hex(payload), size_bytes=len(payload),
                                payload_filename="q.csv")
        (directory / "q.csv").write_bytes(payload)
        (directory / "q.csv.manifest.json").write_text(m.to_json(), encoding="utf-8")
        files = FileStore(root)
        registry = files.load_registry()
        self.assertTrue(registry.require_attested("alphavantage.cn").terms_attested)  # the terms gate passes
        release = MarketDataRelease(name="r", files=(m.file_sha256,), source_precedence=())
        with self.assertRaises(ProfileNotAdmittedError) as cm:
            build_in_memory_market_data(release, files, registry, AdapterRegistry([AlphaVantageQuoteAdapter("alphavantage.cn")]),
                                        identity(), catalog_calendars={})
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_PENDING_OBSERVATION)

    def test_the_cn_listing_then_still_resolves_to_no_admitted_source(self):
        for mic in ("XSHG", "XSHE"):
            store = k.store([], mic=mic)
            lk = store.quote_on(k.LID, D(2026, 10, 8), market11_conventions(CalendarSet()))
            st = price_input_state(lk)
            self.assertEqual((lk.outcome, lk.selected, st.state, st.reason),
                             (LookupOutcome.NO_HISTORY, None, S.INSUFFICIENT_DATA, R.MISSING_PRICE_HISTORY), mic)
            self.assertIn("NO_ADMITTED_SOURCE: market CN", lk.lineage_notes[0])
            self.assertIs(lk.freshness.state, c.FreshnessState.UNKNOWN)

    def test_a_directly_built_store_refuses_a_real_reading_of_the_pending_source(self):
        """Review M-1: the store holds the gate itself, from construction, so no lookup can serve the reading (it used to be refused
        only when the registry records were pinned, after `quote_on` could already have returned the number)."""
        real = k.quote_reading(D(2026, 10, 8), "10.55", source="alphavantage.cn", group="alphavantage",
                               usage=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, ccy=k.CNY)
        from marketdata.store import InMemoryMarketData  # noqa: PLC0415

        with self.assertRaises(ProfileNotAdmittedError) as cm:
            InMemoryMarketData(k.RELEASE, [real], exchange_of=lambda lid: "XSHG", source_records=[REAL_CN])
        self.assertEqual(cm.exception.gate_code, prof.SOURCE_PENDING_OBSERVATION)
        synthetic = k.quote_reading(D(2026, 10, 8), "10.55", source=SYN_SOURCE, group="synthetic", ccy=k.CNY)
        ok = InMemoryMarketData(k.RELEASE, [synthetic], exchange_of=lambda lid: "XSHG", source_records=[SYN_REC])
        self.assertEqual([r.source_id for r in ok.source_registry_records()], [SYN_SOURCE])  # a made-up source is not gated

    def test_status_alone_is_not_enough_a5_must_list_the_upstream_for_the_market(self):
        observed = dataclasses.replace(prof.SOURCES["alphavantage.cn"], status=prof.OBSERVED)  # a hypothetical profile flip
        self.assertEqual(observed.gate_refusal[0], prof.SOURCE_NOT_IN_PRIMARY_ORDER)
        self.assertFalse(observed.admitted)
        with mock.patch.dict(prof.SOURCES, {"alphavantage.cn": observed}):
            with self.assertRaises(ProfileNotAdmittedError) as cm:
                prof.require_admitted("alphavantage.cn")
            self.assertEqual(cm.exception.gate_code, prof.SOURCE_NOT_IN_PRIMARY_ORDER)
            self.assertIn("SOURCE_NOT_IN_PRIMARY_ORDER", str(cm.exception))
            # only the data change an owner decision makes (status AND A.5) opens it
            with mock.patch.dict(prof.PRIMARY_ORDER, {"CN": ("alphavantage",)}):
                self.assertTrue(prof.require_admitted("alphavantage.cn").admitted)
        self.assertEqual(prof.PRIMARY_ORDER["CN"], ())


if __name__ == "__main__":
    unittest.main()
