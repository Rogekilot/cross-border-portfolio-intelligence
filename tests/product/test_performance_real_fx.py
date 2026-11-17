"""The real slice must exercise real ECB FX (PD-0035 section 3): a USD ledger reported in USD touches no rate, so the pack also reports it in EUR (a direct ECB quote) and CNY (a cross through EUR).

Every test builds its OWN file set in a temporary directory (a synthetic-free test double of the layout: files shaped like Alpha Vantage, Frankfurter, the ECB's own history file and the calendar
files, hashed and described by real manifests, with `INTERNAL_DEVELOPMENT_ONLY` scope); NO real payload under `data/marketdata/files/` is read. Only SOURCES.json (the terms attestations) is the repo's.

Cases: (A) the on-disk situation, no registered calendar and ECB data that does not cover the window: the FX views are INSUFFICIENT_DATA with an explicit cause; (B) calendars registered, ECB data
still not covering the window: INSUFFICIENT_DATA with the staleness cause, the USD view available; (C) calendars and an ECB history file covering the window (what the owner's `fetch --source ecb_eurofxref`
produces): the EUR and CNY views are numbers equal to the exact translation, with the fixing dates and instants and the freshness of each rate in the pack.
"""

import datetime
import json
import shutil
import sys
import tempfile
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(SRC))

from marketdata.canonical import sha256_hex  # noqa: E402
from performance_tools import pack, real_slice  # noqa: E402

REAL_SOURCES = real_slice.DEFAULT_ROOT / "SOURCES.json"
D = datetime.date


def weekdays(first, last):
    out, day = [], first
    while day <= last:
        if day.weekday() < 5:
            out.append(day)
        day += datetime.timedelta(days=1)
    return out


def put(root, source, kind, name, payload, fmt, *, retrieved="2026-10-01T04:53:50Z", day="2026-10-01", **fields):
    manifest = {"adjustment_anchor": fields.get("anchor"), "coverage": [], "data_kind": kind, "declared_adjustment": fields.get("adjustment", "RAW"),
                "declared_currency": fields.get("currency"), "declared_delay": "END_OF_DAY", "file_sha256": sha256_hex(payload), "libraries": [], "market": fields.get("market"),
                "payload_filename": name, "payload_format": fmt, "request": fields.get("request", []), "retrieval_time": retrieved, "retrieved_by": "human",
                "schema": "finweb.marketdata.file_manifest/1", "script": {"name": "marketdata_tools.download", "script_sha256": "0" * 64, "version": "0.1.1"}, "size_bytes": len(payload),
                "source_id": source, "source_identifiers": fields.get("identifiers", []), "usage_scope": "INTERNAL_DEVELOPMENT_ONLY"}
    directory = root / "files" / source / kind.lower() / day
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(payload)
    (directory / f"{name}.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def prices_csv(days):
    rows = ["timestamp,open,high,low,close,volume"]
    for i, d in sorted(enumerate(days), key=lambda t: -t[0]):
        close = Decimal("200.0000") + Decimal(i) / 2
        rows.append(f"{d.isoformat()},{close},{close + 1},{close - 1},{close},1000000")
    return ("\n".join(rows) + "\n").encode("utf-8")


def frankfurter_json():  # Jan 2025 only: the file on disk today
    rates = {d.isoformat(): {"CNY": 7.5, "HKD": 8.0, "USD": 1.03} for d in weekdays(D(2025, 1, 2), D(2025, 1, 8))}
    return json.dumps({"amount": 1.0, "base": "EUR", "start_date": "2025-01-02", "end_date": "2025-01-08", "rates": rates}).encode("utf-8")


def frankfurter_window_json(days):
    """Frankfurter's time series for the price window (USD and CNY per EUR), the route that is admitted today."""
    rates = {d.isoformat(): {"CNY": float(Decimal("7.9000") + Decimal(i) / 100), "USD": float(Decimal("1.1000") + Decimal(i) / 1000)} for i, d in enumerate(days)}
    return json.dumps({"amount": 1.0, "base": "EUR", "start_date": days[0].isoformat(), "end_date": days[-1].isoformat(), "rates": rates}).encode("utf-8")


def ecb_hist_csv(days):
    rows = ["Date,USD,CNY,"]
    for i, d in sorted(enumerate(days), key=lambda t: -t[0]):
        rows.append(f"{d.isoformat()},{Decimal('1.1000') + Decimal(i) / 1000},{Decimal('7.9000') + Decimal(i) / 100},")
    return ("\n".join(rows) + "\n").encode("utf-8")


def calendar_json(calendar_id, kind, applies_to, zone, days):
    obj = {"schema": "finweb.marketdata.calendar/1", "calendar_id": calendar_id, "kind": kind, "applies_to": applies_to, "timezone": zone,
           "coverage": {"from": "2025-01-01", "to": "2026-12-31"}, "dates": [d.isoformat() for d in days], "actual_through": "2026-09-30",
           "evidence": "test double: every weekday is a session (no holiday list)", "prepared_by": "test", "prepared_on": "2026-10-02", "version": "test-1"}
    if kind == "EXCHANGE_SESSIONS":
        obj["close"] = {"default": "16:00", "overrides": []}
    else:
        obj["fixing"] = {"time": "14:10", "publication": "16:00"}
    return json.dumps(obj).encode("utf-8")


FIRST, LAST = D(2026, 5, 8), D(2026, 6, 30)


JANUARY_SHA = sha256_hex(frankfurter_json())  # the Jan-2025 Frankfurter file (the one on disk today is shaped like it)


def build_store(root, *, calendars, ecb_history=False, frankfurter_window=False, january=True, quote_revision=False):
    shutil.copy(REAL_SOURCES, root / "SOURCES.json")
    days = weekdays(FIRST, LAST)
    if quote_revision:  # a second Alpha Vantage file (a later retrieval) whose last close is revised: a second vintage of the same series
        revised = prices_csv(days).replace(f"{LAST.isoformat()},".encode(), f"{LAST.isoformat()},".encode())
        lines = revised.decode().split("\n")
        lines[1] = f"{LAST.isoformat()},210.0000,211.0000,209.0000,210.0000,1000000"
        put(root, "alphavantage.us", "QUOTE", "AAPL_compact_2.csv", ("\n".join(lines)).encode(), "alphavantage_csv_daily/1", adjustment="UNDECLARED", currency="USD", market="US",
            identifiers=["AAPL"], request=[["function", "TIME_SERIES_DAILY"], ["symbol", "AAPL"], ["outputsize", "compact"]], anchor="TIME_SERIES_DAILY as returned; label unverified",
            retrieved="2026-10-03T04:53:50Z", day="2026-10-03")
    if frankfurter_window:  # what `fetch --source frankfurter_fx --symbols USD,CNY --start 2026-05-08 --end 2026-06-30` saves
        put(root, "frankfurter.ecb", "FX", "EUR_2026-05-08_2026-06-30.json", frankfurter_window_json(days), "frankfurter_json_timeseries/1", identifiers=["USD", "CNY"], day="2026-10-02",
            retrieved="2026-10-02T09:00:00Z", request=[["base", "EUR"], ["symbols", "USD,CNY"], ["start", FIRST.isoformat()], ["end", LAST.isoformat()], ["endpoint", "https://api.frankfurter.dev/v1"]])
    put(root, "alphavantage.us", "QUOTE", "AAPL_compact.csv", prices_csv(days), "alphavantage_csv_daily/1", adjustment="UNDECLARED", currency="USD", market="US", identifiers=["AAPL"],
        request=[["function", "TIME_SERIES_DAILY"], ["symbol", "AAPL"], ["outputsize", "compact"]], anchor="TIME_SERIES_DAILY as returned; label unverified")
    if january:
        put(root, "frankfurter.ecb", "FX", "EUR_2025-01-02_2025-01-08.json", frankfurter_json(), "frankfurter_json_timeseries/1", identifiers=["USD", "HKD", "CNY"],
            request=[["base", "EUR"], ["symbols", "USD,HKD,CNY"], ["start", "2025-01-02"], ["end", "2025-01-08"], ["endpoint", "https://api.frankfurter.dev/v1"]])
    if calendars:
        sessions = weekdays(D(2025, 1, 1), D(2026, 12, 31))
        put(root, "calendar.manual", "CALENDAR", "NYSE_2026.json", calendar_json("NYSE_SESSIONS", "EXCHANGE_SESSIONS", ["XNYS", "XNAS"], "America/New_York", sessions),
            "finweb_calendar_json/1", identifiers=["NYSE_SESSIONS"], day="2026-10-02")
        put(root, "calendar.manual", "CALENDAR", "ECB_2026.json", calendar_json("ECB", "ECB_FIXINGS", ["ECB"], "Europe/Berlin", sessions), "finweb_calendar_json/1", identifiers=["ECB"],
            day="2026-10-02")
    if ecb_history:  # what `fetch --source ecb_eurofxref --start 2026-05-08 --end 2026-06-30 --symbols USD,CNY` saves: source `ecb.eurofxref`, kind FX, format ecb_eurofxref_hist_csv/1
        put(root, "ecb.eurofxref", "FX", "eurofxref-hist.csv", ecb_hist_csv(weekdays(D(2026, 4, 1), LAST)), "ecb_eurofxref_hist_csv/1", day="2026-10-02", retrieved="2026-10-02T09:00:00Z",
            identifiers=["USD", "CNY"], request=[["file", "eurofxref-hist"], ["endpoint", "test"], ["read_start", FIRST.isoformat()], ["read_end", LAST.isoformat()], ["symbols", "USD,CNY"]])


def run(root, **selection):
    subject, report = real_slice.build_real_subject(root, **selection)
    assert subject is not None, report
    return subject, report, pack.run_all(subject)


def view(computed, ccy):
    s = computed.subject
    return computed.get(f"fx_valuation:{ccy}@{s.as_of.isoformat()}"), pack._fx_views(computed)["views"]


def total(res):
    return next(m for m in res.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING")


class RealFxTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_a_no_calendar_and_ecb_data_that_does_not_cover_the_window_gives_no_number_and_names_the_cause(self):
        build_store(self.root, calendars=False, ecb_history=False)
        subject, report, computed = run(self.root)
        self.assertEqual(subject.as_of, LAST)
        self.assertEqual({c.code for c in subject.extra_reporting}, {"EUR", "CNY"})
        self.assertEqual(computed.detection, "NOT_RUN_NO_CALENDARS")
        for ccy in ("EUR", "CNY"):
            res, views = view(computed, ccy)
            m = total(res)
            self.assertEqual((m.result.value, m.result.sufficiency_state.value), (None, "INSUFFICIENT_DATA"), ccy)
            self.assertTrue(any("CALENDAR_COVERAGE_GAP" in c.note for c in m.causes), ccy)  # explicit cause, not a silent gap
            self.assertTrue(res.manifest.synthetic is False)
            v = next(x for x in views if x["reporting_currency"] == ccy)
            self.assertTrue(v["rates_asked_of_the_port"])
            self.assertTrue(all(p["rate"] is None and p["outcome"].value == "FRESHNESS_UNKNOWN" for p in v["rates_asked_of_the_port"]))
        need = " ".join(report["requirements"])
        self.assertIn("fetch --source frankfurter_fx --symbols USD,CNY --start 2026-05-08 --end 2026-06-30", need)  # the exact command of the route that is admitted
        self.assertIn("frankfurter.ecb", need)
        self.assertIn("ecb.eurofxref", need)  # the ECB's own file is named too, with why it is not read yet
        self.assertIn("MD-OI-12", need)

    def test_b_with_calendars_but_ecb_data_that_ends_in_january_2025_the_fx_views_are_stale_not_numbers_and_usd_stays_available(self):
        build_store(self.root, calendars=True, ecb_history=False)
        subject, report, computed = run(self.root)
        self.assertEqual(computed.detection, "F8B_DRY_RUN")
        usd = total(computed.get(f"valuation@{subject.as_of.isoformat()}"))
        self.assertEqual(usd.result.sufficiency_state.value, "AVAILABLE")  # the USD view needs no rate
        for ccy in ("EUR", "CNY"):
            res, views = view(computed, ccy)
            m = total(res)
            self.assertEqual((m.result.value, m.result.sufficiency_state.value), (None, "INSUFFICIENT_DATA"), ccy)
            self.assertTrue(m.causes and any("fx:USD->" in c.ref or "FX" in (c.note or "") or c.reason for c in m.causes), ccy)
            v = next(x for x in views if x["reporting_currency"] == ccy)
            outcomes = {p["outcome"].value for p in v["rates_asked_of_the_port"]}
            self.assertTrue(outcomes <= {"STALE_BEYOND_LIMIT", "NO_HISTORY", "NOT_IN_RELEASE", "NO_OBSERVATION"}, outcomes)
            self.assertTrue(all(p["rate"] is None for p in v["rates_asked_of_the_port"]))
        self.assertTrue(any("FX FOR THE PRICE WINDOW" in r for r in report["requirements"]))

    def test_d_the_ecb_own_history_file_is_listed_not_admitted_by_name_and_never_read_and_the_build_does_not_crash(self):
        build_store(self.root, calendars=True, ecb_history=True)
        subject, report, computed = run(self.root)
        rows = [r for r in report["files"] if r["source_id"] == "ecb.eurofxref"]
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["admitted"])
        self.assertIn("PROFILE_NOT_ADMITTED", rows[0]["reason"])
        eur, _views = view(computed, "EUR")
        self.assertIsNone(total(eur).result.value)  # nothing from the unprofiled file reaches a number

    def test_c_with_calendars_and_an_admitted_fx_file_covering_the_window_the_views_are_the_exact_translation(self):
        build_store(self.root, calendars=True, frankfurter_window=True)
        # the January 2025 file and the window file are two vintages of one series: the OPERATOR names the file set (market-data Ruling 0.1); the tool does not pick the latest
        subject, report, computed = run(self.root, exclude=[JANUARY_SHA])
        self.assertFalse(any("FX FOR THE PRICE WINDOW" in r for r in report["requirements"]))
        self.assertEqual(report["vintage_conflicts"], [])
        self.assertEqual(report["file_set_chosen_by_operator"]["exclude"], [JANUARY_SHA])
        excluded = [r for r in report["files"] if r["file_sha256"] == JANUARY_SHA]
        self.assertTrue(excluded and "EXCLUDED_BY_OPERATOR" in excluded[0]["reason"])
        usd = total(computed.get(f"valuation@{subject.as_of.isoformat()}"))
        self.assertEqual(usd.result.sufficiency_state.value, "AVAILABLE")
        # the file's own numbers for the as-of date (units per EUR, as the file states them)
        days = weekdays(FIRST, LAST)
        i = days.index(LAST)
        usd_per_eur, cny_per_eur = Fraction(Decimal(str(float(Decimal("1.1000") + Decimal(i) / 1000)))), Fraction(Decimal(str(float(Decimal("7.9000") + Decimal(i) / 100))))
        eur, views_eur = view(computed, "EUR")
        cny, views_cny = view(computed, "CNY")
        self.assertEqual(total(eur).exact, usd.exact / usd_per_eur)  # USD -> EUR is a direct ECB quote, inverted exactly
        self.assertEqual(total(cny).exact, usd.exact / usd_per_eur * cny_per_eur)  # a cross through EUR: two legs
        for views, ccy, legs in ((views_eur, "EUR", 1), (views_cny, "CNY", 2)):
            v = next(x for x in views if x["reporting_currency"] == ccy)
            last = next(p for p in v["rates_asked_of_the_port"] if p["on"] == LAST)
            self.assertEqual(last["outcome"].value, "FOUND")
            self.assertEqual(last["fixing_date_used"], LAST)  # the fixing date
            self.assertEqual(len(last["legs"]), legs)
            for leg in last["legs"]:
                self.assertEqual(leg["fixing_date"], LAST)
                self.assertEqual((leg["observed_at"].hour, leg["observed_at"].minute), (14, 10))  # the fixing instant: 14:10 Europe/Berlin
                self.assertEqual(leg["source"], "frankfurter.ecb")
            self.assertTrue(last["leg_freshness"] and all(f.state.value == "CURRENT" for f in last["leg_freshness"]))  # the freshness of each rate
        self.assertTrue(any("PARITY_CHECK_NOT_RUN" in n for p in next(x for x in views_cny if x["reporting_currency"] == "CNY")["rates_asked_of_the_port"] for n in p["lineage_notes"]))  # the CNY caveat
        self.assertFalse(total(eur).synthetic)
        # CP3-13: an AVAILABLE value computed from Frankfurter rates carries `provenance: UNCONFIRMED` in its lineage, and the CNY cross carries PARITY_CHECK_NOT_RUN (lineage notes, not reason codes)
        for res, parity in ((eur, False), (cny, True)):
            self.assertEqual(total(res).result.sufficiency_state.value, "AVAILABLE")
            for m in (m for m in res.metrics if m.view in ("REPORTING",)):  # holding, cash and portfolio value alike
                lin = dict(m.lineage)
                self.assertIn("UNCONFIRMED (frankfurter.ecb)", lin.get("fx_note:provenance", ""), (m.metric_id, parity))
                self.assertEqual("fx_note:parity" in lin, parity, (m.metric_id, parity))
            self.assertIsNone(total(res).result.reason_code)  # no reason code: the notes change no state (PD-0036)
        for kind in ("fx_window",):
            for c in [c for c in computed.results if c.kind == kind]:
                for m in c.result.metrics:
                    if m.result.value is not None:
                        self.assertIn("UNCONFIRMED (frankfurter.ecb)", dict(m.lineage).get("fx_note:provenance", ""), (c.key, m.metric_id))
        usd_val = computed.get(f"valuation@{subject.as_of.isoformat()}")
        self.assertFalse([m for m in usd_val.metrics if "fx_note:provenance" in dict(m.lineage)])  # a USD view uses no rate: no note

    def test_f_two_vintages_of_one_series_fail_closed_with_both_files_named_and_no_number_that_depends_on_them(self):
        build_store(self.root, calendars=True, frankfurter_window=True)  # the January 2025 file and the window file contribute to the same Frankfurter series
        subject, report, computed = run(self.root)
        (conflict,) = [c for c in report["vintage_conflicts"] if c["series"][2] == "USD"]
        self.assertEqual(len(conflict["files"]), 2)
        self.assertIn(JANUARY_SHA, {f["file_sha256"] for f in conflict["files"]})  # named by source, retrieval time and sha256
        for f in conflict["files"]:
            self.assertTrue(f["source_id"] and f["retrieval_time"] and len(f["file_sha256"]) == 64)
        rows = [r for r in report["files"] if r["source_id"] == "frankfurter.ecb"]
        self.assertTrue(rows and all(not r["admitted"] and "VINTAGE_CONFLICT" in r["reason"] for r in rows))  # NEITHER is in M: no silent choice of the latest
        for ccy in ("EUR", "CNY"):
            res, _views = view(computed, ccy)
            self.assertIsNone(total(res).result.value)  # nothing that depends on the series has a number
        self.assertEqual(total(computed.get(f"valuation@{subject.as_of.isoformat()}")).result.sufficiency_state.value, "AVAILABLE")  # the USD view needs no rate
        self.assertTrue(any("TWO VINTAGES" in r for r in report["requirements"]) or subject.vintage_conflicts)
        with tempfile.TemporaryDirectory() as out:
            pack.build_pack(subject, Path(out))
            summary = (Path(out) / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("Vintage conflicts", summary)
            self.assertIn(JANUARY_SHA, summary)
            inputs = json.loads((Path(out) / "00_inputs.json").read_text(encoding="utf-8"))
            self.assertTrue(inputs["vintage_conflicts"])

    def test_g_a_quote_series_with_two_vintages_is_not_built_and_the_revised_close_is_never_shown(self):
        build_store(self.root, calendars=True, quote_revision=True)
        subject, report = real_slice.build_real_subject(self.root)
        self.assertIsNone(subject)  # the reviewer's revised-close scenario: it used to show AAPL AVAILABLE at the revised 210.00
        self.assertEqual(report["status"], "VINTAGE_CONFLICT")
        text = " ".join(report["requirements"])
        quote = [r for r in report["files"] if r["source_id"] == "alphavantage.us"]
        self.assertEqual(len(quote), 2)
        for r in quote:
            self.assertIn(r["file_sha256"], text)  # both files named by sha256, source and retrieval time
            self.assertIn(str(r["retrieval_time"]), text)
            self.assertIn("alphavantage.us", text)
        self.assertIn("--exclude-file", text)

    def test_h_an_explicit_selection_builds_with_exactly_the_selected_files_and_records_them(self):
        build_store(self.root, calendars=True, quote_revision=True)
        files = [r for r in real_slice.classify_files(self.root) if r["source_id"] == "alphavantage.us"]
        revised = next(r for r in files if r["payload_filename"] == "AAPL_compact_2.csv")
        original = next(r for r in files if r["payload_filename"] == "AAPL_compact.csv")
        everything_else = [r["file_sha256"] for r in real_slice.classify_files(self.root) if r["admitted"] and r["file_sha256"] != original["file_sha256"]]  # the calendars, FX and the revised file
        for mode, kwargs, keep, drop in (("exclude", {"exclude": [revised["file_sha256"]]}, original, revised), ("only", {"only": everything_else}, revised, original)):
            subject, report, computed = run(self.root, **kwargs)
            self.assertEqual(report["vintage_conflicts"], [], mode)
            in_m = {r["file_sha256"] for r in report["files"] if r["admitted"]}
            self.assertIn(keep["file_sha256"], in_m)
            self.assertNotIn(drop["file_sha256"], in_m)
            sel = report["file_set_chosen_by_operator"]
            self.assertTrue(sel and {f["file_sha256"] for f in sel["files_in_m"]} == in_m, mode)  # recorded: exactly the files of M
            holding = next(m for m in computed.get(f"valuation@{subject.as_of.isoformat()}").metrics if m.metric_id == "holding_value" and m.view == "REPORTING")
            self.assertEqual(holding.exact, 7 * (210 if keep is revised else Decimal("200") + Decimal(len(weekdays(FIRST, LAST)) - 1) / 2))  # the SELECTED vintage's close, at 7 units held
            with tempfile.TemporaryDirectory() as out:
                pack.build_pack(subject, Path(out))
                inputs = json.loads((Path(out) / "00_inputs.json").read_text(encoding="utf-8"))
                self.assertEqual(sorted(inputs["file_set_chosen_by_operator"][mode]), sorted(kwargs[mode]))
                self.assertIn("File set chosen by the operator", (Path(out) / "SUMMARY.md").read_text(encoding="utf-8"))

    def test_i_an_unknown_sha256_in_the_selection_is_reported_not_ignored(self):
        build_store(self.root, calendars=True)
        subject, report = real_slice.build_real_subject(self.root, exclude=["0" * 64])
        self.assertIsNone(subject)
        self.assertEqual(report["status"], "SELECTION_UNKNOWN_FILE")

    def test_cp3_19_the_conflict_report_says_whether_the_vintages_disagree_and_on_which_dates(self):
        build_store(self.root, calendars=True, quote_revision=True)
        _subject, report = real_slice.build_real_subject(self.root)
        (conflict,) = [c for c in report["vintage_conflicts"] if c["series"][0] == "alphavantage.us"]
        d = conflict["disagreement"]
        self.assertTrue(d["comparable"])
        self.assertEqual([x["date"] for x in d["disagree"]], [LAST.isoformat()])  # only the revised close differs; the other shared dates agree
        self.assertGreater(d["shared_dates"], 1)
        self.assertIn("210.0000", d["disagree"][0]["values"].values())  # both values are shown, neither is chosen
        self.assertEqual(len(set(d["disagree"][0]["values"].values())), 2)
        text = " ".join(report["requirements"])
        self.assertIn("DISAGREE on 1 of", text)
        self.assertIn(LAST.isoformat(), text)
        # two vintages that cover different dates of the Frankfurter series share no date, and the report says so
        build_store(self.root, calendars=True, frankfurter_window=True)
        _subject, report = real_slice.build_real_subject(self.root)
        (fx,) = [c for c in report["vintage_conflicts"] if c["series"][2] == "USD"]
        self.assertEqual(fx["disagreement"]["shared_dates"], 0)
        self.assertIn("share no (subject, date) point", real_slice.conflict_text(fx))

    def second_vintage(self, rewrite):
        """A second AAPL file whose every close is written with a different number of decimals (two instead of four); `rewrite(date_text, close_text)` may change a value."""
        days = weekdays(FIRST, LAST)
        rows = ["timestamp,open,high,low,close,volume"]
        for i, d in sorted(enumerate(days), key=lambda t: -t[0]):
            close = Decimal("200.0000") + Decimal(i) / 2
            text = rewrite(d.isoformat(), f"{close:.2f}")
            rows.append(f"{d.isoformat()},{text},{text},{text},{text},1000000")
        put(self.root, "alphavantage.us", "QUOTE", "AAPL_compact_2.csv", ("\n".join(rows) + "\n").encode(), "alphavantage_csv_daily/1", adjustment="UNDECLARED", currency="USD", market="US",
            identifiers=["AAPL"], request=[["function", "TIME_SERIES_DAILY"], ["symbol", "AAPL"], ["outputsize", "compact"]], anchor="TIME_SERIES_DAILY as returned; label unverified",
            retrieved="2026-10-03T04:53:50Z", day="2026-10-03")

    def test_cp3_21_the_same_value_written_with_other_trailing_zeros_is_not_a_disagreement(self):
        build_store(self.root, calendars=True)
        self.second_vintage(lambda day, text: text)  # 200.00 against 200.0000, 200.50 against 200.5000, on every date
        subject, report = real_slice.build_real_subject(self.root)
        (conflict,) = [c for c in report["vintage_conflicts"] if c["series"][0] == "alphavantage.us"]
        d = conflict["disagreement"]
        self.assertTrue(d["comparable"])
        self.assertGreater(d["shared_dates"], 1)
        self.assertEqual(d["disagree"], [])  # equal as decimals (market-data Ruling 1.1a item 3)
        self.assertIsNone(subject)  # reporting only: both vintages are still excluded from M, equal or not

    def test_cp3_21_a_genuine_difference_is_still_reported_beside_equal_values_written_differently(self):
        build_store(self.root, calendars=True)
        self.second_vintage(lambda day, text: "210.00" if day == LAST.isoformat() else text)
        _subject, report = real_slice.build_real_subject(self.root)
        (conflict,) = [c for c in report["vintage_conflicts"] if c["series"][0] == "alphavantage.us"]
        d = conflict["disagreement"]
        self.assertEqual([x["date"] for x in d["disagree"]], [LAST.isoformat()])  # only the revised date; the 200.00 / 200.0000 dates are not listed
        self.assertEqual(len(set(d["disagree"][0]["values"].values())), 2)

    def test_cp3_21_the_comparison_key_is_the_decimal_value(self):
        self.assertEqual(real_slice.decimal_value("200.00"), real_slice.decimal_value("200.0000"))
        self.assertNotEqual(real_slice.decimal_value("200.00"), real_slice.decimal_value("200.01"))
        self.assertEqual(real_slice.decimal_value("0.50"), real_slice.decimal_value("0.5"))
        self.assertNotEqual(real_slice.decimal_value("n/a"), real_slice.decimal_value("200"))

    def test_cp3_19_files_in_m_is_exactly_m_and_a_named_file_that_is_refused_is_reported_with_its_reason(self):
        build_store(self.root, calendars=True, quote_revision=True, ecb_history=True)
        rows = real_slice.classify_files(self.root)
        by_name = {r["payload_filename"]: r for r in rows}
        original, revised, ecb = by_name["AAPL_compact.csv"], by_name["AAPL_compact_2.csv"], by_name["eurofxref-hist.csv"]
        rest = [r["file_sha256"] for r in rows if r["admitted"] and r["source_id"] != "alphavantage.us"]
        # --use-file names both vintages AND the file whose profile is not admitted: M holds neither vintage, and the record says so
        subject, report = real_slice.build_real_subject(self.root, only=rest + [original["file_sha256"], revised["file_sha256"], ecb["file_sha256"]])
        sel = report["file_set_chosen_by_operator"]
        in_m = {r["file_sha256"] for r in report["files"] if r["admitted"]}
        self.assertEqual({f["file_sha256"] for f in sel["files_in_m"]}, in_m)  # the record of M is M
        self.assertNotIn(original["file_sha256"], in_m)
        self.assertNotIn(revised["file_sha256"], in_m)
        named = {f["file_sha256"]: f for f in sel["named_files"]}
        self.assertFalse(named[ecb["file_sha256"]]["in_m"])
        self.assertIn("PROFILE_NOT_ADMITTED", named[ecb["file_sha256"]]["reason"])
        for r in (original, revised):
            self.assertFalse(named[r["file_sha256"]]["in_m"])
            self.assertIn("VINTAGE_CONFLICT", named[r["file_sha256"]]["reason"])
        self.assertIsNone(subject)  # with both vintages out there is no price file: the status says why
        self.assertEqual(report["status"], "VINTAGE_CONFLICT")
        # a named file that is in M is reported as such, and the pack summary lists the named files with their reasons
        subject, report, _computed = run(self.root, exclude=[revised["file_sha256"]], only=rest + [original["file_sha256"], ecb["file_sha256"]])
        named = {f["file_sha256"]: f for f in report["file_set_chosen_by_operator"]["named_files"]}
        self.assertTrue(named[original["file_sha256"]]["in_m"])
        self.assertFalse(named[ecb["file_sha256"]]["in_m"])
        with tempfile.TemporaryDirectory() as out:
            pack.build_pack(subject, Path(out))
            summary = (Path(out) / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn(f"named by `--use-file`: `ecb.eurofxref` (eurofxref-hist.csv) sha256 `{ecb['file_sha256']}`: NOT in M: PROFILE_NOT_ADMITTED", summary)  # the named file, with its reason
            self.assertIn(f"named by `--use-file`: `alphavantage.us` (AAPL_compact.csv) sha256 `{original['file_sha256']}`: in M", summary)

    def test_the_pack_writes_the_fx_views_file_and_the_summary_table(self):
        build_store(self.root, calendars=True, frankfurter_window=True)
        subject, _report, _computed = run(self.root, exclude=[JANUARY_SHA])
        with tempfile.TemporaryDirectory() as out:
            result = pack.build_pack(subject, Path(out))
            self.assertIn("17_fx_views.json", result["files"])
            # CP3-13: every place that names the FX source says what it is
            label = "ECB reference rates as republished by Frankfurter"
            doc17 = json.loads((Path(out) / "17_fx_views.json").read_text(encoding="utf-8"))
            self.assertTrue(all(label in v["fx_source"] and "UNCONFIRMED" in v["fx_source"] for v in doc17["data"]["views"]))
            self.assertTrue(all("a direct ECB quote" not in v["route"] and "two ECB legs" not in v["route"] for v in doc17["data"]["views"]))
            doc05 = json.loads((Path(out) / "05_historical_fx.json").read_text(encoding="utf-8"))
            self.assertIn(label, doc05["data"]["fx_sources_in_m"][0]["what_it_is"])
            summary = (Path(out) / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn(label, summary)
            self.assertIn("Qualification for the FX in this pack", summary)  # the PD-0035 caveat is followed by the qualification
            self.assertLess(summary.index("ECB FX only"), summary.index("Qualification for the FX in this pack"))  # the owner's words stay, with the qualification AFTER them
            self.assertIn("UNCONFIRMED", doc05["data"]["fx_sources_in_m"][0]["what_it_is"])
            self.assertTrue(json.loads((Path(out) / "00_open_items.json").read_text(encoding="utf-8"))["pd_0035_caveat"].count("Qualification") == 1)
            doc = json.loads((Path(out) / "17_fx_views.json").read_text(encoding="utf-8"))
            self.assertEqual([v["reporting_currency"] for v in doc["data"]["views"]], ["EUR", "CNY"])
            summary = (Path(out) / "SUMMARY.md").read_text(encoding="utf-8")
            self.assertIn("Reporting views in other currencies", summary)
            self.assertTrue(all(r["reproduced"] for r in result["reproduced"]))  # the FX views reproduce too


if __name__ == "__main__":
    unittest.main()
