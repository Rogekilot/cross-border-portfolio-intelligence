"""O-7 (the Quant's ruling of 2026-11-10; PD-0082): the claim record (K) and the extraction of the claim lineage from the three stored homes, proved on ENGINE-MADE,
NEVER-STORED inputs (the PD-0080 pattern).

WHAT RUNS. `performance.engine.compute` (the pure function `compute_for_portfolio` calls) over `performance_kit`'s invented worlds, then `ComputationResult.canonical_json()` (the
serialization `_stage_real` stores), parsed back the way the route parses `archive.issued`. The stored response is built by the PRODUCT's own `response_of` with (K) built by the
PRODUCT's own `build_claim_record` over that same in-memory port. Nothing here is written to a database, a file or a store. The invented readings carry the id of a real source so that
the real profile table (`profiles.source_profile`) is the one consulted for the documentation reference; they are invented numbers on an invented listing, in memory only. The response
dict says `synthetic: false` because the real origin's labels do; it is never stored, served or sealed (PD-0066 decision 8: nothing invented is ever stored as `synthetic = false`).

EXPECTED VALUES are written by hand from the ruling (its section 9.2 for the three kit cases, as superseded by the post-build note section 5.1: AVAILABLE and LIMITED on AAPL@XNAS
because of P-9, the INSUFFICIENT_DATA case on AAPL@XNAS as accepted in its section 3, and H@XHKG a P-9 refusal case; section 2 for the text forms), never read from the code's output: a test compares the
extractor's result with a literal. The two dates of the LIMITED case (price session 2025-03-28, valuation date 2025-04-02, 3 missed sessions) are the ruling's own.
"""
from __future__ import annotations

import ast
import copy
import datetime
import json
import sys
import unittest
import unittest.mock as mock
import uuid
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import marketdata_exit_kit as x  # noqa: E402
import performance_kit as pk  # noqa: E402
from domain.currency import CurrencyCode  # noqa: E402
from domain.ledger import EventType  # noqa: E402
from marketdata import claim_record, claim_render as cr, contracts as c, profiles  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from performance import engine  # noqa: E402
from persistence import real_labels  # noqa: E402
from real_service import service as svc, worlds as real_worlds  # noqa: E402
from web_api import real_scoped_contract as contract  # noqa: E402

D = datetime.date
USD, HKD = CurrencyCode("USD"), CurrencyCode("HKD")
PERF = engine.performance_conventions()
RETRIEVAL_TEXT = "2025-03-29T04:53:50Z"
RETRIEVED = datetime.datetime(2025, 3, 29, 4, 53, 50, tzinfo=datetime.timezone.utc)
SOURCE = "alphavantage.us"
LABEL_SOURCE = "PROFILE_CALL_ADJUSTMENT:alphavantage.us:TIME_SERIES_DAILY:DECLARED"
SOURCE_NAME = "Alpha Vantage free tier (US daily history)"
H_QUOTE, H_FX, H_CALENDAR, H_IDENTITY = "d" * 64, "c" * 64, "f" * 64, "a" * 64
REAL_ORIGIN = {"market_origin": "REAL_SOURCE", "ledger_origin": "PROJECT_CONSTRUCTED_NONPERSONAL_UAT", "personal_holdings": False, "synthetic": False}
ROOT, OPERATION, REVISION = uuid.UUID(int=0xA1), uuid.UUID(int=0xA2), uuid.UUID(int=0xA3)
OWNER = uuid.UUID(int=0xA4)

#: What the snapshot holds of the release (members, in their stored order, and the source records), and the release's file rows: written by hand.
SNAPSHOT = {
    "members": [{"payload_sha256": sha, "manifest_sha256": "1" * 64, "source_id": source, "acquisition_record_sha256": "2" * 64, "adapter_id": "ad", "adapter_version": "1"}
                for sha, source in ((H_QUOTE, SOURCE), (H_IDENTITY, "openfigi"), (H_CALENDAR, "calendar.manual"), (H_FX, "synthetic.ecb"))],
    "source_records": [{"source_id": SOURCE, "name": SOURCE_NAME, "upstream_provider": "Alpha Vantage Inc.", "independence_group": "alphavantage",
                       "terms_url": "https://example.invalid/terms", "terms_check": None},
                      {"source_id": "openfigi", "name": "OpenFIGI", "upstream_provider": "OpenFIGI", "independence_group": "openfigi", "terms_url": "u", "terms_check": None},
                      {"source_id": "calendar.manual", "name": "Calendar by hand", "upstream_provider": "owner", "independence_group": "calendar", "terms_url": "u",
                       "terms_check": None},
                      {"source_id": "synthetic.ecb", "name": "Invented ECB", "upstream_provider": "invented", "independence_group": "ecb", "terms_url": "u", "terms_check": None}],
}
FILES = (
    (H_QUOTE, SOURCE, "QUOTE", {"request": [["function", "TIME_SERIES_DAILY"], ["symbol", "AAPL"], ["outputsize", "compact"]], "retrieval_time": RETRIEVAL_TEXT,
                                "declared_adjustment": "UNDECLARED"}),
    (H_IDENTITY, "openfigi", "IDENTITY", {"retrieval_time": RETRIEVAL_TEXT}),
    (H_CALENDAR, "calendar.manual", "CALENDAR", {"retrieval_time": RETRIEVAL_TEXT}),
    (H_FX, "synthetic.ecb", "FX", {"retrieval_time": RETRIEVAL_TEXT}),
)
FILE_HASHES = ["QUOTE alphavantage.us " + H_QUOTE, "IDENTITY openfigi " + H_IDENTITY, "CALENDAR calendar.manual " + H_CALENDAR, "FX synthetic.ecb " + H_FX]


def reading(listing, day, price, currency, market):
    lineage = c.Lineage(SOURCE, c.AdjustmentStatus.RAW, source_id=SOURCE, file_sha256=H_QUOTE, adapter_id="ad", adapter_version="1", source_record_ref="r",
                        retrieved_at=RETRIEVED, usage_scope=c.UsageScope.SYNTHETIC_TEST, market=market, adjustment_label_source=LABEL_SOURCE,
                        label_status=c.LabelStatus.UNVERIFIABLE)
    observation = c.QuoteObservation(listing, day, Decimal(price), currency, c.SourceTiming(None, c.DataDelayStatus.END_OF_DAY), lineage, volume=Decimal("1000"),
                                     recovered=True, precision_bound=Decimal("0"))
    return c.SourceReading(SOURCE, "alphavantage", H_QUOTE, observation)


def hk_world(closes, fixings=True):
    """H@XHKG (invented closes), the ECB fixings of the kit (or none): an HKD holding in USD reporting, which P-9 refuses (post-build note 5.1)."""
    probe = x.identity()
    listing = x.lid(probe, "0700", "XHKG")
    readings = [reading(listing, day, price, HKD, "HK") for day, price in closes.items()]
    if fixings:
        readings += [pk.fixing(day, ccy, rate) for day, rates in pk.FIXINGS.items() for ccy, rate in rates.items()]
    return pk.World(readings), lambda w: w.h, HKD, 10


def hk_world_without_fixings(closes):
    return hk_world(closes, fixings=False)


def us_world(closes):
    """AAPL@XNAS in USD: no FX leg, so a withheld NAV's delay is the price's alone."""
    probe = x.identity()
    listing = x.lid(probe, "AAPL", "XNAS")
    return pk.World([reading(listing, day, price, USD, "US") for day, price in closes.items()]), lambda w: w.aapl, USD, 10


CASE_SPECS = {
    "AVAILABLE": (us_world, {D(2025, 3, 28): "150.00"}, D(2025, 3, 28)),
    "LIMITED": (us_world, {D(2025, 3, 28): "150.00"}, D(2025, 4, 2)),
    "SUPPRESSED": (us_world, {D(2025, 3, 28): "150.00"}, D(2025, 3, 27)),
}
#: the P-9 refusal worlds (post-build note 5.1): an HKD holding in USD reporting, with the kit's fixings and without any
REFUSAL_SPECS = {
    "HK_WITH_FIXINGS": (hk_world, {D(2025, 3, 28): "400.00"}, D(2025, 3, 28)),
    "HK_NO_FIXING": (hk_world_without_fixings, {D(2025, 3, 28): "400.00"}, D(2025, 3, 28)),
    "HK_SUPPRESSED": (hk_world, {D(2025, 3, 28): "400.00"}, D(2025, 3, 27)),
}
_BUILT = {}


def build_case(name):
    """The bundle of one case: the engine's issued document, the product's response with the product's (K), and the archive. Built once and never stored."""
    if name in _BUILT:
        return _BUILT[name]
    make, closes, as_of = {**CASE_SPECS, **REFUSAL_SPECS}[name]
    w, listing_of, currency, quantity = make(closes)
    listing = listing_of(w)
    ledger = pk.Ledger()
    ledger.add(pk.A1, EventType.DEPOSIT, D(2025, 3, 25), USD, amount=pk.Money(Decimal(500), USD))
    ledger.add(pk.A1, EventType.TRANSFER_IN, D(2025, 3, 25), currency, listing_id=listing, quantity=Decimal(quantity))
    result = engine.compute(ledger.rows, ledger.version, as_of, USD, w.store, w.ident, w.market, PERF, portfolio_id=ROOT, suppressions=())
    issued_bytes = result.canonical_json().encode("utf-8")
    intent = {"as_of": as_of.isoformat(), "name": "invented probe", "opening_positions": [{"listing_id": str(listing), "quantity": str(quantity), "cost_basis": None,
                                                                                         "acquired_on": None}],
              "opening_cash": {"currency": "USD", "amount": "500"}}
    record = claim_record.build_claim_record(snapshot=SNAPSHOT, files=FILES, port=w.store, conventions=w.market, listing_id=listing, as_of=as_of)
    response = svc.response_of(root=ROOT, intent=intent, origin=REAL_ORIGIN, labels=real_labels.root_labels(REAL_ORIGIN), operation_id=OPERATION, revision=REVISION,
                               pin=ledger.version, claim_record=record)
    response_bytes = canonical_json(response).encode("utf-8")
    archive = svc.Archive(issued_bytes, response_bytes, b'{"generation": 1}', "1" * 64, "2" * 64, REVISION, ledger.version)
    world = SimpleNamespace(port=w.store, resolver=w.ident, market_conventions=w.market, perf_conventions=PERF, policy=None)
    _BUILT[name] = SimpleNamespace(name=name, world=world, listing=listing, as_of=as_of, result=result, issued=json.loads(issued_bytes), issued_bytes=issued_bytes,
                                   response=response, record=record, archive=archive)
    return _BUILT[name]


def parts(name):
    case = build_case(name)
    return copy.deepcopy(case.issued), copy.deepcopy(case.response)


def nav(issued):
    return next(m for m in issued["metrics"] if m["metric_id"] == "portfolio_value" and m["view"] == "REPORTING")


def holding(issued):
    return next(m for m in issued["metrics"] if m["metric_id"] == "holding_value" and m["view"] == "REPORTING")


def lineage_pairs(row):
    return row["lineage"]


class Base(unittest.TestCase):
    def refuses(self, code, detail, issued, response, pin=2):
        with self.assertRaises(cr.ClaimRenderError) as caught:
            claim_record.lineage_from_documents(issued, response, pin)
        self.assertEqual(caught.exception.code, code, caught.exception)
        self.assertIn(detail, str(caught.exception))

    def extract(self, name="AVAILABLE"):
        issued, response = parts(name)
        return claim_record.lineage_from_documents(issued, response, 2)


# =====================================================================================================================================
# The ruling's section 9.2, by hand
# =====================================================================================================================================
class KitCaseTests(Base):
    def test_AVAILABLE_as_of_2025_03_28_every_field_is_the_stored_value(self):
        """Ruling 9.2: the last print is 2025-03-28, so the price session and the valuation date are both 2025-03-28 and the missed count is 0; freshness CURRENT, delay
        END_OF_DAY (the price leg only: no FX leg), the MIC XNAS; two ledger events give `ledger_version` 2. The rest is the stored text (section 2)."""
        self.assertEqual(Fraction(nav(build_case("AVAILABLE").issued)["exact"]), 2000)      # post-build note 5.1 by hand: 10 x 150 + 500 USD
        self.assertEqual(self.extract("AVAILABLE"), {
            "valuation_date": "2025-03-28", "price_session_date": "2025-03-28", "missed_sessions": "0", "ledger_quantity": "10", "source_name": SOURCE_NAME,
            "exchange_mic": "XNAS", "vendor_call": "TIME_SERIES_DAILY", "documentation_reference": "PD-0066 decision 3", "adjustment_label_source": LABEL_SOURCE,
            "reporting_currency": "USD", "opening_cash": "500", "metric_state": "AVAILABLE", "freshness": "CURRENT", "delay_status": ["END_OF_DAY"],
            "reconciliation_status": "SINGLE_SOURCE", "file_hashes": FILE_HASHES, "ledger_version": "2", "convention_ids": ["market-data/1.16", "performance/1.12"],
            "adjustment_label_status": "UNVERIFIABLE", "retrieval_time": RETRIEVAL_TEXT, "v1_statement": "no V1 event in M"})

    def test_LIMITED_as_of_2025_04_02_the_two_dates_are_two_fields_and_three_sessions_were_missed(self):
        """Ruling 9.2 as superseded by the post-build note 5.1 (AAPL@XNAS, P-9): the NYSE sessions after 2025-03-28 up to 2025-04-02 are 03-31, 04-01 and 04-02 (no holiday;
        Good Friday is 04-18), so 3 are missed, which is LIMITED; the price session
        2025-03-28 is NOT the valuation date 2025-04-02. This is the test that the split holds."""
        lineage = self.extract("LIMITED")
        self.assertEqual((lineage["valuation_date"], lineage["price_session_date"], lineage["missed_sessions"]), ("2025-04-02", "2025-03-28", "3"))
        self.assertEqual((lineage["metric_state"], lineage["freshness"], lineage["delay_status"], lineage["exchange_mic"]), ("LIMITED", "STALE", ["END_OF_DAY"], "XNAS"))
        self.assertNotEqual(lineage["valuation_date"], lineage["price_session_date"])
        self.assertEqual(nav(build_case("LIMITED").issued)["reason"], "STALE_DATA")

    def test_LIMITED_renders_one_block_in_which_both_sentences_are_true(self):
        issued, response = parts("LIMITED")
        block = claim_record.block_of(REAL_ORIGIN, issued, response, 2)
        text = {item["id"]: item["text"] for item in block["items"]}
        self.assertIn("The market value of the holding on 2025-04-02 is 10 x p. Here p is the close " + SOURCE_NAME + " delivered for the 2025-03-28 XNAS session through "
                      "TIME_SERIES_DAILY; 3 sessions of that exchange lie after that close, up to 2025-04-02 inclusive.", text["S1"])
        self.assertIn("as the owner read it (PD-0066 decision 3).", text["S1"])
        self.assertIn("The label source is " + LABEL_SOURCE + ".", text["S1"])
        self.assertTrue(text["S3"].startswith("The NAV in USD on 2025-04-02 is 10 x p + 500. The state is LIMITED, freshness STALE, delay END_OF_DAY."))
        self.assertIn("The reconciliation status is SINGLE_SOURCE.", text["S3"])
        self.assertIn("the convention sets market-data/1.16, performance/1.12.", text["S4"])
        for sha in H_QUOTE, H_IDENTITY, H_CALENDAR, H_FX:
            self.assertIn(sha, text["S4"])
        self.assertIn("the exposure window E(2025-03-28, 2025-03-29T04:53:50Z), whose second argument is the file's retrieval time", text["S5"])
        self.assertIn("(no V1 event in M)", text["S5"])
        self.assertEqual(cr.check_block(block, REAL_ORIGIN), [])

    def test_SUPPRESSED_before_the_first_close_is_the_withheld_variant_and_its_lineage_is_the_stored_cause(self):
        """Ruling 9.2: before the listing's first close there is no `price_date_used`; the cause is MISSING_PRICE_HISTORY; freshness and delay are UNKNOWN."""
        issued, response = parts("SUPPRESSED")
        self.assertNotIn("price_date_used", dict(holding(issued)["lineage"]))
        lineage = claim_record.lineage_from_documents(issued, response, 2)
        self.assertEqual(lineage, {
            "valuation_date": "2025-03-27", "ledger_quantity": "10", "reporting_currency": "USD", "metric_state": "INSUFFICIENT_DATA", "freshness": "UNKNOWN",
            "delay_status": ["UNKNOWN"], "file_hashes": FILE_HASHES, "ledger_version": "2", "convention_ids": ["market-data/1.16", "performance/1.12"],
            "nav_cause": "MISSING_PRICE_HISTORY"})
        block = claim_record.block_of(REAL_ORIGIN, issued, response, 2)
        text = {item["id"]: item["text"] for item in block["items"]}
        self.assertEqual(text["S1"], "No holding value on 2025-03-27 is stated: no close values the holding, and the NAV's state is INSUFFICIENT_DATA.")
        self.assertEqual(text["S2"], "No label source is stated: no reading values the holding.")
        self.assertEqual(text["S3"], "No NAV in USD on 2025-03-27 is stated. The state is INSUFFICIENT_DATA, cause MISSING_PRICE_HISTORY, freshness UNKNOWN, delay UNKNOWN.")
        self.assertEqual(text["S5"], "No label status, exposure window or V1 statement is stated: no reading values the holding.")
        self.assertEqual(text["C1"], "That any price series is verified as-traded, or that any of its labels, split or dividend component, is verified.")
        self.assertEqual(text["C2"], "That any close was used, or that any close is the exchange's official closing-cross price.")
        self.assertEqual(text["C3"], "That any close was compared with any other source. There is none for this market.")
        self.assertEqual(list(text), list(cr.ALL_ITEM_IDS))                                                 # the same twelve ids
        self.assertEqual(cr.check_block(block, REAL_ORIGIN), [])
        self.assertEqual(block["slots"]["S2"], {})
        self.assertEqual(block["slots"]["S5"], {})
        for sentence in ("x p", "RAW", "SINGLE_SOURCE", "reconciliation", "E(", "PD-0066"):
            self.assertNotIn(sentence, " ".join(text[i] for i in ("S1", "S2", "S3", "S5")))               # no price, label, window or reconciliation is stated

    def test_a_withheld_nav_with_the_normal_block_is_refused(self):
        """Ruling 9.2: a test that feeds the section 5 block over the withheld NAV must refuse. The state is edited to AVAILABLE: there is no price date to copy."""
        issued, response = parts("SUPPRESSED")
        nav(issued)["state"] = "AVAILABLE"
        self.refuses("CLAIM_RECORD_MISSING", "price_date_used", issued, response)
        lineage = self.extract("AVAILABLE")                                                                    # and a normal lineage forced to the withheld state has no cause
        with self.assertRaises(cr.ClaimRenderError):
            cr.render_claim_block(REAL_ORIGIN, dict(lineage, metric_state="INSUFFICIENT_DATA"))

    def test_the_three_blocks_pass_the_scoped_contracts_own_check(self):
        """`check_block` and the re-render equality the contract applies on every response: all three cases pass, so a root that reaches the pre-seal check cannot be refused later."""
        for name in CASE_SPECS:
            with self.subTest(name):
                issued, response = parts(name)
                block = claim_record.block_of(REAL_ORIGIN, issued, response, 2)
                payload = contract.read_payload(root_id="r", operation_id="o", revision_id="v", ledger_pin=2, origin=REAL_ORIGIN,
                                                labels={k: real_labels.root_labels(REAL_ORIGIN)[k] for k in contract.LABEL_FIELDS}, response_sha256="1" * 64,
                                                issued_sha256="2" * 64, result={"metrics": []}, claim_limits=block, created_under_generation=1)
                self.assertEqual(payload["claim_limits"], block)

    def test_the_extraction_is_deterministic_and_reads_only_the_archives_documents(self):
        archive = build_case("LIMITED").archive
        self.assertEqual(claim_record.lineage_of(archive), claim_record.lineage_of(archive))
        self.assertEqual(claim_record.lineage_of(archive), self.extract("LIMITED"))
        again = claim_record.build_claim_record(snapshot=SNAPSHOT, files=FILES, port=build_case("LIMITED").world.port, conventions=build_case("LIMITED").world.market_conventions,
                                                listing_id=build_case("LIMITED").listing, as_of=D(2025, 4, 2))
        self.assertEqual(claim_record.record_bytes(again), claim_record.record_bytes(build_case("LIMITED").record))


# =====================================================================================================================================
# (K) as built, and every structural refusal of its build
# =====================================================================================================================================
class BuildTests(Base):
    def build(self, name="AVAILABLE", **changes):
        case = build_case(name)
        kw = dict(snapshot=SNAPSHOT, files=FILES, port=case.world.port, conventions=case.world.market_conventions, listing_id=case.listing, as_of=case.as_of)
        kw.update(changes)
        return claim_record.build_claim_record(**kw)

    def test_the_record_is_exactly_the_stored_facts_of_the_reading_that_valued_the_holding(self):
        self.assertEqual(self.build("AVAILABLE"), {
            "schema": "finweb.claim_record/1",
            "members": [{"data_kind": kind, "source_id": source, "payload_sha256": sha}
                        for kind, source, sha in (("QUOTE", SOURCE, H_QUOTE), ("IDENTITY", "openfigi", H_IDENTITY), ("CALENDAR", "calendar.manual", H_CALENDAR), ("FX", "synthetic.ecb", H_FX))],
            "valuing": [{"source_id": SOURCE, "file_sha256": H_QUOTE, "price_session_date": "2025-03-28", "source_name": SOURCE_NAME, "vendor_call": "TIME_SERIES_DAILY",
                         "documentation_reference": "PD-0066 decision 3", "call_adjustment_status": "DECLARED", "adjustment_label_source": LABEL_SOURCE,
                         "adjustment_label_status": "UNVERIFIABLE", "retrieval_time": RETRIEVAL_TEXT, "reconciliation_status": "SINGLE_SOURCE"}]})

    def test_the_valuing_session_is_the_readings_not_the_valuation_date(self):
        self.assertEqual(self.build("LIMITED")["valuing"][0]["price_session_date"], "2025-03-28")

    def test_the_record_of_a_withheld_nav_has_no_valuing_reading(self):
        record = self.build("SUPPRESSED")
        self.assertEqual(record["valuing"], [])
        self.assertEqual(len(record["members"]), 4)

    def test_the_record_is_text_lists_and_objects_only(self):
        def walk(value):
            self.assertIn(type(value), (str, list, dict), value)
            if type(value) is list:
                for item in value:
                    walk(item)
            if type(value) is dict:
                for key, item in value.items():
                    self.assertIs(type(key), str)
                    walk(item)
        for name in CASE_SPECS:
            walk(build_case(name).record)

    def test_each_structural_problem_of_the_build_is_a_refusal_and_never_a_hole(self):
        files = list(FILES)

        def without(sha):
            return tuple(f for f in files if f[0] != sha)

        def changed(sha, **changes):
            out = []
            for f in files:
                if f[0] == sha:
                    manifest = copy.deepcopy(f[3])
                    manifest.update(changes)
                    out.append((f[0], f[1], f[2], manifest))
                else:
                    out.append(f)
            return tuple(out)

        def snap(**changes):
            return dict(copy.deepcopy(SNAPSHOT), **changes)

        no_function = changed(H_QUOTE, request=[["symbol", "AAPL"]])
        two_functions = changed(H_QUOTE, request=[["function", "A"], ["function", "B"]])
        other_instant = changed(H_QUOTE, retrieval_time="2025-03-29T04:53:51Z")
        naive_instant = changed(H_QUOTE, retrieval_time="2025-03-29T04:53:50")
        bad_request = changed(H_QUOTE, request="function=TIME_SERIES_DAILY")
        twice = tuple(files) + (files[0],)
        twice_record = snap(source_records=SNAPSHOT["source_records"] + [dict(SNAPSHOT["source_records"][0])])
        none_record = snap(source_records=SNAPSHOT["source_records"][1:])
        other_source = tuple((f[0], "other.source" if f[0] == H_QUOTE else f[1], f[2], f[3]) for f in files)
        no_profile = {"profile_of": lambda source_id: SimpleNamespace(call_adjustment={})}
        cases = {
            "a member with no file row": ({"files": without(H_FX)}, "CLAIM_RECORD_MISSING"),
            "the valuing file is not a file of the release": ({"files": without(H_QUOTE)}, "CLAIM_RECORD_MISSING"),
            "a member whose file row names another source": ({"files": other_source}, "CLAIM_RECORD_MISSING"),
            "a file listed twice": ({"files": twice}, "CLAIM_RECORD_AMBIGUOUS"),
            "a request with no function": ({"files": no_function}, "CLAIM_RECORD_MISSING"),
            "a request with two function pairs": ({"files": two_functions}, "CLAIM_RECORD_AMBIGUOUS"),
            "a request that is not a list of pairs": ({"files": bad_request}, "CLAIM_RECORD_SHAPE"),
            "a retrieval time that is not the reading's": ({"files": other_instant}, "CLAIM_RECORD_CROSSCHECK"),
            "a retrieval time with no zone": ({"files": naive_instant}, "CLAIM_RECORD_CROSSCHECK"),
            "two source records of the source": ({"snapshot": twice_record}, "CLAIM_RECORD_AMBIGUOUS"),
            "no source record of the source": ({"snapshot": none_record}, "CLAIM_RECORD_MISSING"),
            "a profile with no entry for the call": (no_profile, "CLAIM_RECORD_MISSING"),
            "no member at all": ({"snapshot": snap(members=[])}, "CLAIM_RECORD_MISSING"),
            "a source with no profile": ({"profile_of": unprofiled}, "CLAIM_RECORD_SHAPE"),
        }
        for label, (changes, code) in cases.items():
            with self.subTest(label):
                with self.assertRaises(cr.ClaimRenderError) as caught:
                    self.build("AVAILABLE", **changes)
                self.assertEqual(caught.exception.code, code, caught.exception)

    def test_a_lookup_with_no_reconciliation_status_or_a_reading_with_no_label_status_is_refused(self):
        case = build_case("AVAILABLE")
        lookup = case.world.port.quote_on(case.listing, case.as_of, case.world.market_conventions)
        selected = lookup.selected
        lineage_without = copy.copy(selected.observation.lineage)
        for label, patched in (("no reconciliation", dataclass_replace(lookup, reconciliation=None)),
                               ("no status", dataclass_replace(lookup, reconciliation=SimpleNamespace(status=None))),
                               ("no label status", dataclass_replace(lookup, selected=SimpleNamespace(
                                   source_id=selected.source_id, file_sha256=selected.file_sha256,
                                   observation=SimpleNamespace(value_date=selected.observation.value_date, lineage=dataclass_replace(lineage_without, label_status=None)))))):
            with self.subTest(label):
                port = SimpleNamespace(quote_on=lambda *a, p=patched: p)
                with self.assertRaises(cr.ClaimRenderError) as caught:
                    self.build("AVAILABLE", port=port)
                self.assertEqual(caught.exception.code, "CLAIM_RECORD_MISSING")


def dataclass_replace(obj, **changes):
    import dataclasses
    return dataclasses.replace(obj, **changes)


def unprofiled(source_id):
    raise profiles.ProfileNotAdmittedError("no precision profile for source %r: not admitted until one exists" % source_id)


# =====================================================================================================================================
# The preconditions of the fixed text (the ruling's 3.4): each failing alone
# =====================================================================================================================================
class PreconditionTests(Base):
    def test_the_unchanged_bundle_passes_every_precondition(self):
        for name in CASE_SPECS:
            issued, response = parts(name)
            claim_record.lineage_from_documents(issued, response, 2)

    def failing(self, name, mutate, detail, code="CLAIM_PRECONDITION"):
        issued, response = parts(name)
        mutate(issued, response)
        self.refuses(code, detail, issued, response)

    def test_P1_the_label_status_must_be_UNVERIFIABLE(self):
        for status in ("VERIFIED", "CONTRADICTED"):
            with self.subTest(status):
                self.failing("AVAILABLE", lambda i, r, s=status: r["claim_record"]["valuing"][0].update(adjustment_label_status=s), "P-1")

    def test_P2_the_label_source_must_end_DECLARED_and_the_profiles_status_must_be_DECLARED_each_on_its_own(self):
        self.failing("AVAILABLE", lambda i, r: r["claim_record"]["valuing"][0].update(call_adjustment_status="MEMORY"), "P-2")
        self.failing("AVAILABLE", lambda i, r: r["claim_record"]["valuing"][0].update(
            adjustment_label_source=LABEL_SOURCE.replace(":DECLARED", ":MEMORY")), "P-2")
        self.failing("AVAILABLE", lambda i, r: r["claim_record"]["valuing"][0].update(adjustment_label_source="DECLARED_BY_NOBODY"), "P-2")

    def test_P3_the_reconciliation_status_must_be_SINGLE_SOURCE(self):
        for status in ("CORROBORATED", "DISAGREEMENT", "IMPLAUSIBLE", "RESOLVED_BY_EVIDENCE"):
            with self.subTest(status):
                self.failing("AVAILABLE", lambda i, r, s=status: r["claim_record"]["valuing"][0].update(reconciliation_status=s), "P-3")

    def test_P4_no_member_of_M_may_be_a_corporate_action_file(self):
        def add(issued, response):
            record = response["claim_record"]
            record["members"].append({"data_kind": "CORPORATE_ACTION", "source_id": "filing.source", "payload_sha256": "9" * 64})
        self.failing("AVAILABLE", add, "P-4")
        issued, response = parts("LIMITED")
        add(issued, response)
        self.refuses("CLAIM_PRECONDITION", "P-4", issued, response)
        # the withheld variant needs P-6 to P-10 only: it still renders, and names the file
        issued, response = parts("SUPPRESSED")
        add(issued, response)
        lineage = claim_record.lineage_from_documents(issued, response, 2)
        self.assertIn("CORPORATE_ACTION filing.source " + "9" * 64, lineage["file_hashes"])

    def test_P5_the_manifest_must_still_list_Test_V4_as_not_built(self):
        def drop(issued, response):
            items = issued["manifest"]["open_items"]
            issued["manifest"]["open_items"] = [i for i in items if "Ruling 3.3, Test V4" not in i]
            self.assertEqual(len(issued["manifest"]["open_items"]), len(items) - 1)
        self.failing("AVAILABLE", drop, "P-5")
        self.failing("AVAILABLE", lambda i, r: i["manifest"].pop("open_items"), "P-5")
        # editing the line's text (the claim that no V4 record exists is then not the manifest's) is the same refusal
        self.failing("AVAILABLE", lambda i, r: i["manifest"].update(open_items=[x.replace("Test V4", "Test V9") for x in i["manifest"]["open_items"]]), "P-5")
        # removing another open item does not matter to P-5
        issued, response = parts("AVAILABLE")
        issued["manifest"]["open_items"] = [i for i in issued["manifest"]["open_items"] if "item 5" not in i]
        claim_record.lineage_from_documents(issued, response, 2)

    def test_P5_is_judged_by_the_marker_on_both_sides_not_by_the_lines_exact_text(self):
        """Post-build note 5.2: (i) the stored manifest holds exactly one `market_data: ` line with `Ruling 3.3, Test V4`; (ii) the engine's `UNBUILT_1_16` holds exactly one
        line with it. A line reworded with the marker kept still renders; a line removed refuses."""
        marker = "Ruling 3.3, Test V4"
        # (i) stored side
        issued, response = parts("AVAILABLE")
        issued["manifest"]["open_items"] = [("market_data: reworded, " + marker + " is still unbuilt") if marker in i else i for i in issued["manifest"]["open_items"]]
        claim_record.lineage_from_documents(issued, response, 2)                                              # reworded, marker kept: renders
        stored = [i for i in parts("AVAILABLE")[0]["manifest"]["open_items"] if marker in i]
        self.assertEqual(len(stored), 1)
        self.failing("AVAILABLE", lambda i, r: i["manifest"]["open_items"].append(stored[0] + " again"), "P-5")          # two stored lines
        self.failing("AVAILABLE", lambda i, r: i["manifest"].update(open_items=[x[len("market_data: "):] if marker in x else x for x in i["manifest"]["open_items"]]), "P-5")
        # (ii) engine side, with the stored manifest untouched: the engine reworded (renders), line removed (V4 built), a second marker line
        original = claim_record.market11.UNBUILT_1_16
        reworded = tuple(("reworded: " + marker + " not built") if marker in line else line for line in original)
        removed = tuple(line for line in original if marker not in line)
        twice = original + ("another line with " + marker,)
        self.assertEqual(len(removed), len(original) - 1)
        issued, response = parts("AVAILABLE")
        with mock.patch.object(claim_record.market11, "UNBUILT_1_16", reworded):
            claim_record.lineage_from_documents(issued, response, 2)
        for label, lines in (("removed", removed), ("twice", twice)):
            with self.subTest(label), mock.patch.object(claim_record.market11, "UNBUILT_1_16", lines):
                self.refuses("CLAIM_PRECONDITION", "P-5", issued, response)

    def test_P6_the_market_data_convention_set_must_be_the_claim_lists(self):
        for name in CASE_SPECS:
            with self.subTest(name):
                def change(issued, response):
                    issued["manifest"]["conventions"] = [[k, "market-data/1.15" if k == "market_data.convention_set" else v] for k, v in issued["manifest"]["conventions"]]
                self.failing(name, change, "P-6")

    def test_P7_the_origin_one_position_and_one_cash_balance(self):
        for name in CASE_SPECS:
            with self.subTest(name):
                self.failing(name, lambda i, r: r["origin"].update(market_origin="SYNTHETIC_TEST"), "P-7")
                self.failing(name, lambda i, r: r.update(origin=None), "P-7")
                self.failing(name, lambda i, r: r["opening_positions"].append(copy.deepcopy(r["opening_positions"][0])), "P-7")
                self.failing(name, lambda i, r: r.update(opening_positions=[]), "P-7")
                self.failing(name, lambda i, r: r.update(opening_cash=None), "P-7")

    def test_P8_the_NAV_state_is_one_of_the_three_and_there_is_one_NAV_row(self):
        for name in CASE_SPECS:
            for state in ("STALE", "ACTUAL", "", None, "available"):
                with self.subTest(name=name, state=state):
                    self.failing(name, lambda i, r, s=state: nav(i).update(state=s), "P-8")
            with self.subTest(name=name, rows="two"):
                def twice(issued, response):
                    issued["metrics"].append(copy.deepcopy(nav(issued)))
                self.failing(name, twice, "more than one", "CLAIM_RECORD_AMBIGUOUS")
            with self.subTest(name=name, rows="none"):
                def none(issued, response):
                    issued["metrics"] = [m for m in issued["metrics"] if not (m["metric_id"] == "portfolio_value" and m["view"] == "REPORTING")]
                self.failing(name, none, "no portfolio_value", "CLAIM_RECORD_MISSING")

    # ---- P-9 and P-10 (post-build note 5.1) ---------------------------------------------------------------------------------------------
    def test_P9_an_hkd_holding_in_usd_reporting_is_refused_whatever_its_state_before_the_variant_is_picked(self):
        """The Quant's hand value: H@XHKG as of 2025-03-28 with the kit's fixings is USD 10 x 400 x 1.08 / 8.40 + 500 = 1014.29, so "10 x p + 500" is false; the block is
        refused, not rendered. The reviewer's no-FX world is withheld (MISSING_FX_HISTORY) with a valuing reading in (K): P-9 comes first, so the refusal is P-9, not P-10."""
        for name in REFUSAL_SPECS:
            with self.subTest(name):
                issued, response = parts(name)
                self.assertEqual(next(m for m in issued["metrics"] if m["metric_id"] == "holding_value" and m["view"] == "NATIVE")["currency"], "HKD")
                self.refuses("CLAIM_PRECONDITION", "P-9", issued, response)
        issued, response = parts("HK_NO_FIXING")
        self.assertEqual(nav(issued)["state"], "INSUFFICIENT_DATA")                                           # the reviewer's world: withheld, with a reading in (K)
        self.assertEqual(len(response["claim_record"]["valuing"]), 1)

    def test_P9_the_native_row_must_be_one_and_in_the_reporting_currency_in_both_variants(self):
        def native(issued):
            return next(m for m in issued["metrics"] if m["metric_id"] == "holding_value" and m["view"] == "NATIVE")
        for name in CASE_SPECS:
            with self.subTest(name, case="currency"):
                self.failing(name, lambda i, r: native(i).update(currency="HKD"), "P-9")
                self.failing(name, lambda i, r: native(i).update(currency=None), "P-9")
            with self.subTest(name, case="two rows"):
                self.failing(name, lambda i, r: i["metrics"].append(copy.deepcopy(native(i))), "more than one", "CLAIM_RECORD_AMBIGUOUS")
            with self.subTest(name, case="no row"):
                self.failing(name, lambda i, r: i.update(metrics=[m for m in i["metrics"] if not (m["metric_id"] == "holding_value" and m["view"] == "NATIVE")]),
                             "no holding_value/NATIVE", "CLAIM_RECORD_MISSING")

    def test_P10_a_withheld_variant_is_refused_when_a_reading_values_the_holding(self):
        issued, response = parts("SUPPRESSED")
        claim_record.lineage_from_documents(issued, response, 2)                                              # the control renders
        # an injected valuing entry in a withheld record
        response["claim_record"]["valuing"] = copy.deepcopy(build_case("AVAILABLE").record["valuing"])
        self.refuses("CLAIM_PRECONDITION", "P-10", issued, response)
        # a price date used on the NATIVE row, or on the REPORTING row (either view)
        for view in ("NATIVE", "REPORTING"):
            with self.subTest(view):
                def used(i, r, v=view):
                    row = next(m for m in i["metrics"] if m["metric_id"] == "holding_value" and m["view"] == v)
                    row["lineage"].append(["price_date_used", "2025-03-28"])
                self.failing("SUPPRESSED", used, "P-10")
        # P-10 is the withheld variant's: the same documents with a normal NAV state are not refused by it
        issued, response = parts("AVAILABLE")
        claim_record.lineage_from_documents(issued, response, 2)


# =====================================================================================================================================
# The cross-checks and the ambiguity rules of the table (the ruling's section 2)
# =====================================================================================================================================
class CrossCheckTests(Base):
    def test_every_cross_check_refuses_on_a_difference(self):
        def valuation_date(i, r):
            r["as_of"] = "2025-03-27"

        def currency(i, r):
            r["reporting_currency"] = "HKD"

        def cash_currency(i, r):
            r["opening_cash"]["currency"] = "HKD"

        def manifest_currency(i, r):
            i["manifest"]["reporting_currency"] = "HKD"

        def response_pin(i, r):
            r["ledger_version"] = 3

        def manifest_pin(i, r):
            i["manifest"]["ledger_version"] = 3

        def consumed(i, r):
            i["manifest"]["data_set_refs"][0]["consumed"].append(["9" * 64, "ad", "1"])

        def session(i, r):
            r["claim_record"]["valuing"][0]["price_session_date"] = "2025-03-27"

        def listing(i, r):
            r["opening_positions"][0]["listing_id"] = str(uuid.UUID(int=77))
        for label, mutate in (("valuation date", valuation_date), ("reporting currency", currency), ("cash currency", cash_currency), ("manifest currency", manifest_currency),
                              ("response pin", response_pin), ("manifest pin", manifest_pin), ("a consumed file that is not a member", consumed),
                              ("the valuing session against the price date", session), ("the holding row against the position's listing", listing)):
            with self.subTest(label):
                issued, response = parts("AVAILABLE")
                mutate(issued, response)
                with self.assertRaises(cr.ClaimRenderError) as caught:
                    claim_record.lineage_from_documents(issued, response, 2)
                self.assertEqual(caught.exception.code, "CLAIM_RECORD_CROSSCHECK", caught.exception)
        issued, response = parts("AVAILABLE")
        self.refuses("CLAIM_RECORD_CROSSCHECK", "ledger version", issued, response, pin=3)             # the archive's own pin

    def test_a_ledger_version_that_is_not_an_integer_is_refused(self):
        for bad in ("2", 2.0, True, None, -2):
            with self.subTest(bad):
                issued, response = parts("AVAILABLE")
                issued["manifest"]["ledger_version"] = bad
                response["ledger_version"] = bad
                with self.assertRaises(cr.ClaimRenderError):
                    claim_record.lineage_from_documents(issued, response, bad if isinstance(bad, int) else 2)

    def test_two_candidates_where_one_is_required_are_refused(self):
        def two_holdings(i, r):
            i["metrics"].append(copy.deepcopy(holding(i)))

        def two_calendars(i, r):
            row = holding(i)
            row["freshness"]["entries"].append(copy.deepcopy(next(e for e in row["freshness"]["entries"] if e["kind"] == "EXCHANGE_CALENDAR")))

        def two_mics(i, r):
            next(e for e in holding(i)["freshness"]["entries"] if e["kind"] == "EXCHANGE_CALENDAR")["mics"].append("XNAS")

        def two_dates(i, r):
            holding(i)["lineage"].append(["price_date_used", "2025-03-27"])

        def two_missed(i, r):
            holding(i)["lineage"].append(["price_missed_sessions", "1"])

        def two_valuing(i, r):
            r["claim_record"]["valuing"].append(copy.deepcopy(r["claim_record"]["valuing"][0]))
        for label, mutate in (("two holding rows", two_holdings), ("two exchange-calendar entries", two_calendars), ("two MICs", two_mics),
                              ("two price dates", two_dates), ("two missed counts", two_missed), ("two valuing readings", two_valuing)):
            with self.subTest(label):
                issued, response = parts("AVAILABLE")
                mutate(issued, response)
                with self.assertRaises(cr.ClaimRenderError) as caught:
                    claim_record.lineage_from_documents(issued, response, 2)
                self.assertIn(caught.exception.code, ("CLAIM_RECORD_AMBIGUOUS", "CLAIM_RECORD_SHAPE"), caught.exception)

    def test_a_missing_source_is_refused_never_defaulted(self):
        def no_holding(i, r):
            i["metrics"] = [m for m in i["metrics"] if not (m["metric_id"] == "holding_value" and m["view"] == "REPORTING")]

        def no_date(i, r):
            row = holding(i)
            row["lineage"] = [p for p in row["lineage"] if p[0] != "price_date_used"]

        def no_missed(i, r):
            row = holding(i)
            row["lineage"] = [p for p in row["lineage"] if p[0] != "price_missed_sessions"]

        def no_calendar(i, r):
            row = holding(i)
            row["freshness"]["entries"] = [e for e in row["freshness"]["entries"] if e["kind"] != "EXCHANGE_CALENDAR"]

        def no_valuing(i, r):
            r["claim_record"]["valuing"] = []

        def no_record(i, r):
            r.pop("claim_record")

        def no_cash_amount(i, r):
            r["opening_cash"].pop("amount")

        def no_quantity(i, r):
            r["opening_positions"][0].pop("quantity")

        def no_conventions(i, r):
            i["manifest"]["conventions"] = [p for p in i["manifest"]["conventions"] if p[0] != "performance.convention_set"]
        for label, mutate in (("no holding row", no_holding), ("no price date", no_date), ("no missed count", no_missed), ("no exchange-calendar entry", no_calendar),
                              ("no valuing reading", no_valuing), ("no claim record", no_record), ("no cash amount", no_cash_amount), ("no quantity", no_quantity),
                              ("no performance convention set", no_conventions)):
            with self.subTest(label):
                issued, response = parts("AVAILABLE")
                mutate(issued, response)
                with self.assertRaises(cr.ClaimRenderError):
                    claim_record.lineage_from_documents(issued, response, 2)

    def test_a_missed_count_that_is_not_digits_is_refused(self):
        for bad in ("", "-1", "03", "1.0", "x", " 1"):
            with self.subTest(bad):
                issued, response = parts("LIMITED")
                holding(issued)["lineage"] = [[k, bad if k == "price_missed_sessions" else v] for k, v in holding(issued)["lineage"]]
                with self.assertRaises(cr.ClaimRenderError):
                    claim_record.lineage_from_documents(issued, response, 2)

    def test_a_malformed_claim_record_is_refused_field_by_field(self):
        mutations = {
            "an extra key": lambda k: k.update(extra="x"),
            "another schema": lambda k: k.update(schema="finweb.claim_record/2"),
            "not an object": lambda k: None,
            "no members": lambda k: k.update(members=[]),
            "a member with a fourth key": lambda k: k["members"][0].update(extra="x"),
            "a member with a blank value": lambda k: k["members"][0].update(data_kind=" "),
            "a member with a number": lambda k: k["members"][0].update(payload_sha256=5),
            "a valuing entry with a missing key": lambda k: k["valuing"][0].pop("retrieval_time"),
            "a valuing entry with a blank value": lambda k: k["valuing"][0].update(vendor_call=""),
            "a valuing entry with a number": lambda k: k["valuing"][0].update(source_name=1),
            "valuing is not a list": lambda k: k.update(valuing={}),
        }
        for label, mutate in mutations.items():
            with self.subTest(label):
                issued, response = parts("AVAILABLE")
                if label == "not an object":
                    response["claim_record"] = ["x"]
                else:
                    mutate(response["claim_record"])
                with self.assertRaises(cr.ClaimRenderError) as caught:
                    claim_record.lineage_from_documents(issued, response, 2)
                self.assertEqual(caught.exception.code, "CLAIM_RECORD_SHAPE", caught.exception)

    def test_the_withheld_cause_comes_from_the_reason_or_else_the_details_and_refuses_when_neither_is_stated(self):
        issued, response = parts("SUPPRESSED")
        nav(issued)["reason"] = None
        nav(issued)["details"] = ["CAUSE_A", "CAUSE_B"]
        self.assertEqual(claim_record.lineage_from_documents(issued, response, 2)["nav_cause"], ["CAUSE_A", "CAUSE_B"])
        block = claim_record.block_of(REAL_ORIGIN, issued, response, 2)
        self.assertEqual(block["slots"]["S3"]["nav_cause"], "CAUSE_A, CAUSE_B")
        for reason, details in ((None, []), (" ", []), (None, [""]), (None, "x"), (None, None)):
            with self.subTest(reason=reason, details=details):
                issued, response = parts("SUPPRESSED")
                nav(issued).update(reason=reason, details=details)
                self.refuses("CLAIM_RECORD_MISSING", "names no cause", issued, response)

    def test_an_empty_delay_list_is_refused(self):
        issued, response = parts("AVAILABLE")
        nav(issued)["freshness"]["delays"] = []
        self.refuses("CLAIM_RECORD_SHAPE", "delays", issued, response)


# =====================================================================================================================================
# The create's pre-seal check, the response shape and the reproduce comparison (service code, no connection)
# =====================================================================================================================================
class ServiceTests(Base):
    def test_response_of_is_the_document_the_create_always_wrote_and_adds_only_the_claim_record(self):
        intent = {"as_of": "2026-01-05", "name": "n", "opening_positions": [{"listing_id": str(uuid.UUID(int=5)), "quantity": "10", "cost_basis": None, "acquired_on": None}],
                  "opening_cash": {"currency": "USD", "amount": "500"}}
        origin = {"market_origin": "SYNTHETIC_TEST", "ledger_origin": "INVENTED_TEST_LEDGER", "personal_holdings": False, "synthetic": True}
        labels = real_labels.root_labels(origin)
        kw = dict(root=ROOT, intent=intent, origin=origin, labels=labels, operation_id=OPERATION, revision=REVISION, pin=2)
        # the construction `_write_root` had inline before the refactor, written out here
        expected = {"portfolio_id": str(ROOT), "as_of": "2026-01-05", "persisted": True, "reporting_currency": "USD", real_labels.FLAG_FIELD: True,
                    "origin": origin, "labels": {k: labels[k] for k in contract.LABEL_FIELDS}, "name": "n", "operation_id": str(OPERATION), "revision_id": str(REVISION),
                    "ledger_version": 2, "opening_positions": intent["opening_positions"], "opening_cash": intent["opening_cash"]}
        self.assertEqual(svc.response_of(**kw), expected)
        self.assertEqual(canonical_json(svc.response_of(**kw)), canonical_json(expected))                 # the same stored bytes
        self.assertNotIn("claim_record", svc.response_of(**kw))
        record = {"schema": "x"}
        self.assertEqual(svc.response_of(claim_record=record, **kw), dict(expected, claim_record=record))

    def test_the_stored_response_carries_the_record_and_the_canonical_form_round_trips(self):
        case = build_case("AVAILABLE")
        stored = json.loads(case.archive.response)
        self.assertEqual(stored["claim_record"], case.record)
        self.assertEqual(canonical_json(stored).encode("utf-8"), case.archive.response)

    def test_the_pre_seal_check_refuses_a_held_build_error_and_an_unrenderable_block_and_passes_a_good_bundle(self):
        case = build_case("AVAILABLE")
        issued_bytes = case.issued_bytes
        svc.RealWorkspaceService._require_claim_block(case.response, issued_bytes, 2, None)                # passes
        for label, response, error in (
                ("a held build error", case.response, cr.ClaimRenderError("CLAIM_RECORD_MISSING", "x")),
                ("no record", {k: v for k, v in case.response.items() if k != "claim_record"}, None),
                ("a failed precondition", dict(case.response, claim_record=dict(case.record, valuing=[dict(case.record["valuing"][0], reconciliation_status="CORROBORATED")])), None)):
            with self.subTest(label):
                with self.assertRaises(svc.RealWorkspaceError) as caught:
                    svc.RealWorkspaceService._require_claim_block(response, issued_bytes, 2, error)
                self.assertEqual(caught.exception.code, svc.CLAIM_RECORD_REFUSED)
        with self.assertRaises(svc.RealWorkspaceError):
            svc.RealWorkspaceService._require_claim_block(case.response, issued_bytes, 3, None)            # a wrong pin
        self.assertIn(svc.CLAIM_RECORD_REFUSED, contract.ERRORS)
        self.assertEqual(contract.refusal_payload(SimpleNamespace(code=svc.CLAIM_RECORD_REFUSED))["error"]["code"], svc.CLAIM_RECORD_REFUSED)

    def stage(self, *, record, build_error=None, refused=False):
        """`RealWorkspaceService._stage_real` itself, with its collaborators in memory: the world, the service's result, `_write_root` and `_seal` (recorders). Returns the
        service, the recorders and what `_stage_real` raised (or None)."""
        import performance_service.service as perf_service
        from persistence import real_tails
        case = build_case("AVAILABLE")
        service = svc.RealWorkspaceService("rw_test", executor_role="rw_exec", connect=lambda: None)
        intent = {"as_of": "2025-03-28", "opening_positions": [{"listing_id": str(case.listing), "quantity": "10"}]}
        write_root = mock.Mock(return_value=("revision", 2, case.response))
        seal = mock.Mock()
        claim = mock.Mock(side_effect=build_error) if build_error is not None else mock.Mock(return_value=record)
        scope = SimpleNamespace(name="REAL")
        raised = None
        with mock.patch.object(real_worlds, "build_real_world", return_value=case.world), mock.patch.object(real_worlds, "service_refused", return_value=refused), \
                mock.patch.object(perf_service, "compute_for_portfolio", return_value=case.result), mock.patch.object(svc, "real_envelope", return_value={}), \
                mock.patch.object(service, "_claim_record_of", claim), mock.patch.object(service, "_write_root", write_root), mock.patch.object(service, "_seal", seal):
            try:
                service._stage_real(object(), SimpleNamespace(context_id="c" * 64, generation=1), scope, {}, OWNER, ROOT, OPERATION, intent, None)
            except real_tails.RealWorkspaceError as error:
                raised = error
        return write_root, seal, claim, raised

    def test_the_create_hands_the_record_it_built_to_the_write_and_seals_what_passed_the_check(self):
        """The reviewer's surviving liveness mutant: dropping `claim_record=record` from `_write_root`. `_stage_real` is run here with its collaborators in memory (a recorder
        for the write and the seal): the write receives the very record `_claim_record_of` built, and the seal runs once, after the check. What is still first-run at R8 is only the
        database side of a real create that commits."""
        record = build_case("AVAILABLE").record
        write_root, seal, claim, raised = self.stage(record=record)
        self.assertIsNone(raised)
        write_root.assert_called_once()
        self.assertIs(write_root.call_args.kwargs["claim_record"], record)
        seal.assert_called_once()
        self.assertIs(seal.call_args.kwargs["response"], build_case("AVAILABLE").response)

    def test_a_held_build_error_yields_to_the_services_own_refusal_and_is_a_refusal_otherwise(self):
        """TR-O7-L-1: a create whose claim record cannot be built AND whose result the service refuses (FF1-C08) answers the SERVICE's refusal, not `RW_CLAIM_RECORD_REFUSED`
        (the reviewer's "raise at once" mutant fails this); with the service content, the held error is the refusal of the create, before the seal."""
        from persistence import real_tails
        error = cr.ClaimRenderError("CLAIM_RECORD_MISSING", "a snapshot member has no file row of its source")
        write_root, seal, claim, raised = self.stage(record=None, build_error=error, refused=True)
        self.assertIsInstance(raised, real_tails.ServiceRefusal)
        self.assertEqual(raised.code, real_worlds.REFUSAL_CODE)
        self.assertEqual(raised.code, "SYNTHETIC_MARKET_DATA_REFUSED")
        write_root.assert_called_once()                                                                       # the write happened: the build error was held, not raised
        self.assertIsNone(write_root.call_args.kwargs["claim_record"])
        seal.assert_not_called()
        write_root, seal, claim, raised = self.stage(record=None, build_error=error, refused=False)
        self.assertNotIsInstance(raised, real_tails.ServiceRefusal)
        self.assertEqual((type(raised), raised.code), (svc.RealWorkspaceError, svc.CLAIM_RECORD_REFUSED))
        seal.assert_not_called()

    def reproduce(self, name, response=None, files=FILES, record_error=None):
        case = build_case(name)
        archive = case.archive if response is None else svc.Archive(case.archive.issued, canonical_json(response).encode("utf-8"), b"{}", "1" * 64, "2" * 64, REVISION, 2)
        service = svc.RealWorkspaceService("rw_test", executor_role="rw_exec", connect=lambda: None)
        import performance_service.service as perf_service
        with mock.patch.object(real_worlds, "build_real_world", return_value=case.world), mock.patch.object(real_worlds, "read_claim_files", return_value=files), \
                mock.patch.object(perf_service, "compute_for_portfolio", return_value=case.result):
            return service._reproduce_real(None, None, None, SNAPSHOT, OWNER, ROOT, archive)

    def test_a_reproduce_rebuilds_the_record_and_compares_it_byte_for_byte(self):
        for name in CASE_SPECS:
            with self.subTest(name):
                self.assertEqual(self.reproduce(name).status, "REPRODUCED")

    def test_a_reproduce_whose_record_differs_is_RESULT_DIFFERS_in_every_field(self):
        case = build_case("AVAILABLE")
        edits = {"a member's hash": lambda k: k["members"][0].update(payload_sha256="8" * 64), "a member's kind": lambda k: k["members"][1].update(data_kind="FX"),
                 "the member order": lambda k: k["members"].reverse(), "a member dropped": lambda k: k["members"].pop(),
                 "the valuing session": lambda k: k["valuing"][0].update(price_session_date="2025-03-27"),
                 "the source name": lambda k: k["valuing"][0].update(source_name="Another name"), "the call": lambda k: k["valuing"][0].update(vendor_call="OTHER"),
                 "the reference": lambda k: k["valuing"][0].update(documentation_reference="PD-0001"),
                 "the label source": lambda k: k["valuing"][0].update(adjustment_label_source=LABEL_SOURCE + "x"),
                 "the label status": lambda k: k["valuing"][0].update(adjustment_label_status="VERIFIED"),
                 "the retrieval time": lambda k: k["valuing"][0].update(retrieval_time="2025-03-29T04:53:51Z"),
                 "the reconciliation status": lambda k: k["valuing"][0].update(reconciliation_status="CORROBORATED"),
                 "the valuing entry dropped": lambda k: k.update(valuing=[]), "the schema": lambda k: k.update(schema="x")}
        for label, edit in edits.items():
            with self.subTest(label):
                response = copy.deepcopy(case.response)
                edit(response["claim_record"])
                outcome = self.reproduce("AVAILABLE", response)
                self.assertEqual((outcome.status, outcome.detail), ("RESULT_DIFFERS", "claim record differs"))
        response = {k: v for k, v in case.response.items() if k != "claim_record"}
        self.assertEqual(self.reproduce("AVAILABLE", response).status, "RESULT_DIFFERS")                  # a stored response with no record
        self.assertEqual(self.reproduce("AVAILABLE", dict(case.response, claim_record="x")).status, "RESULT_DIFFERS")

    def test_a_reproduce_that_cannot_rebuild_the_record_is_RESULT_DIFFERS_and_the_issued_check_still_comes_first(self):
        outcome = self.reproduce("AVAILABLE", files=tuple(f for f in FILES if f[0] != H_FX))
        self.assertEqual((outcome.status, outcome.detail), ("RESULT_DIFFERS", "the claim record cannot be rebuilt"))
        case = build_case("AVAILABLE")
        archive = svc.Archive(case.archive.issued + b" ", case.archive.response, b"{}", "1" * 64, "2" * 64, REVISION, 2)
        service = svc.RealWorkspaceService("rw_test", executor_role="rw_exec", connect=lambda: None)
        import performance_service.service as perf_service
        with mock.patch.object(real_worlds, "build_real_world", return_value=case.world), mock.patch.object(real_worlds, "read_claim_files", return_value=FILES), \
                mock.patch.object(perf_service, "compute_for_portfolio", return_value=case.result):
            outcome = service._reproduce_real(None, None, None, SNAPSHOT, OWNER, ROOT, archive)
        self.assertEqual((outcome.status, outcome.detail), ("RESULT_DIFFERS", "complete canonical issued answer differs"))


# =====================================================================================================================================
# Through the real-mode app: the real extractor, the contract's own check, a fake service holding the engine-made bundles (no database)
# =====================================================================================================================================
class RouteTests(unittest.TestCase):
    def setUp(self):
        import logging
        import real_mode_kit as kit
        logging.getLogger("finweb.real_mode").setLevel(logging.CRITICAL)
        self.kit = kit
        self.app, self.service, _accounts = kit.build_app(lineage_of=claim_record.lineage_of)
        self.client = kit.Client(self.app, peer="127.0.0.94")
        self.owner = self.client.sign_up("claims_user")
        self.path = "/api/real/v1/roots"

    def store(self, archive):
        self.service.archives[(ROOT, OPERATION)] = archive
        self.service.roots[self.owner] = [(ROOT, self.kit.CONTEXT, 3)]

    def test_a_real_root_is_created_replayed_and_read_with_the_same_block_in_each_of_the_three_states(self):
        from real_service.service import Created
        for name in CASE_SPECS:
            with self.subTest(name):
                case = build_case(name)
                issued, response = parts(name)
                expected = claim_record.block_of(REAL_ORIGIN, issued, response, 2)
                self.service.create_outcome = Created(ROOT, OPERATION, case.archive, False)
                status, created, _ = self.client.post(self.path, self.kit.intent(OPERATION))
                self.assertEqual((status, created["state"]), (201, "COMMITTED"), created)
                self.assertEqual(created["claim_limits"], expected)
                self.assertEqual(created["result"], case.issued)
                self.assertEqual(created["origin"], REAL_ORIGIN)
                self.service.create_outcome = Created(ROOT, OPERATION, case.archive, True)
                status, replayed, _ = self.client.post(self.path, self.kit.intent(OPERATION))
                self.assertEqual((status, replayed["replayed"], replayed["claim_limits"]), (200, True, expected))
                self.store(case.archive)
                status, read, _ = self.client.get("%s/%s/operations/%s" % (self.path, ROOT, OPERATION))
                self.assertEqual((status, read["claim_limits"]), (200, expected))
                withheld = name == "SUPPRESSED"
                self.assertEqual("nav_cause" in read["claim_limits"]["slots"]["S3"], withheld)
                self.assertEqual(read["claim_limits"]["slots"]["S2"] == {}, withheld)

    def test_a_root_whose_record_cannot_state_its_block_is_never_shown_and_a_committed_one_is_unknown(self):
        """The defence behind the pre-seal check: even if such a root were stored, the read refuses (REAL_UNAVAILABLE) and a create's response is the unknown outcome. No
        number is sent without its block."""
        from real_service.service import Archive, Created
        case = build_case("AVAILABLE")
        broken = copy.deepcopy(case.response)
        broken["claim_record"]["valuing"][0]["reconciliation_status"] = "CORROBORATED"
        archive = Archive(case.archive.issued, canonical_json(broken).encode("utf-8"), b"{}", "1" * 64, "2" * 64, REVISION, 2)
        self.store(archive)
        status, read, raw = self.client.get("%s/%s/operations/%s" % (self.path, ROOT, OPERATION))
        self.assertEqual((status, read["error"]["code"]), (503, "REAL_UNAVAILABLE"))
        self.assertNotIn(b"result", raw)
        self.service.create_outcome = Created(ROOT, OPERATION, archive, False)
        status, unknown, _ = self.client.post(self.path, self.kit.intent(OPERATION))
        self.assertEqual((status, unknown["state"]), (503, "UNKNOWN"))


# =====================================================================================================================================
# Static: the module is pure; the launcher passes it; a test root never reads it
# =====================================================================================================================================
class StaticTests(unittest.TestCase):
    def test_the_module_is_pure_and_names_no_vendor(self):
        source = (SRC / "marketdata" / "claim_record.py").read_text()
        tree = ast.parse(source)
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertLessEqual(imported, {"__future__", "datetime", "json", "re", "marketdata", "marketdata.canonical", "marketdata.contracts", "marketdata.manifest"})
        for forbidden in ("now(", "today(", "open(", "os.environ", "getenv", "socket", "urllib", "psycopg", "random"):
            self.assertFalse(forbidden in source, forbidden)
        for vendor in ("alphavantage", "alpha vantage", "time_series", "akshare", "eastmoney", "sina"):
            self.assertFalse(vendor in source.lower(), vendor)

    def test_the_launcher_passes_the_extractor_and_the_default_still_refuses(self):
        source = (SRC / "web_api" / "real_launcher.py").read_text()
        self.assertIn("from marketdata.claim_record import lineage_of", source)
        self.assertIn("origins=origins, lineage_of=lineage_of)", source)
        from web_api import real_mode_routes
        with self.assertRaises(cr.ClaimRenderError) as caught:
            real_mode_routes.unbuilt_lineage(None)
        self.assertEqual(caught.exception.code, "CLAIM_LINEAGE_UNBUILT")

    def test_the_create_runs_the_check_before_the_seal(self):
        tree = ast.parse((SRC / "real_service" / "service.py").read_text())
        stage = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_stage_real")
        calls = [(n.lineno, n.func.attr) for n in ast.walk(stage) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        order = {name: min(line for line, attr in calls if attr == name) for name in ("_claim_record_of", "_write_root", "_require_claim_block", "_seal")}
        self.assertLess(order["_claim_record_of"], order["_write_root"])
        self.assertLess(order["_require_claim_block"], order["_seal"])
        refusal = [n.lineno for n in ast.walk(stage) if isinstance(n, ast.Attribute) and n.attr == "service_refused"]
        self.assertTrue(refusal and refusal[0] < order["_require_claim_block"])                         # the service's own refusal keeps its place (FF1-C08)


if __name__ == "__main__":
    unittest.main()
