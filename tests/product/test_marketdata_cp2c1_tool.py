"""CP2c-1 download tool: the TERMS GATE (PD-0031/PD-0032) and the ECB-direct route. No network: every
HTTP call is replaced, and a call that reaches the network fails the test. Agents never run the tool."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode  # noqa: E402
from marketdata.contracts import AdjustmentStatus  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.manifest import DataKind, SourceRegistry  # noqa: E402
from marketdata_tools import download as dl  # noqa: E402

USD = CurrencyCode("USD")


def entry(source_id, permits, **extra):
    item = {"source_id": source_id, "name": source_id, "upstream_provider": "x", "independence_group": source_id}
    if permits is not None:
        item["terms_check"] = {"checked_by": "owner", "checked_on": "2026-10-01",
                               "permits_internal_development_use": permits}
    item.update(extra)
    return item


REGISTRY = {"sources": [
    entry("akshare.cn", False), entry("akshare_sina.hk", False), entry("baostock.cn", None),
    entry("alphavantage.us", True), entry("frankfurter.ecb", True), entry("openfigi", True),
]}


def write_registry(root: Path, doc=REGISTRY):
    (root / "SOURCES.json").write_text(json.dumps(doc), encoding="utf-8")


def fetched(source_id, kind=DataKind.QUOTE, label="x"):
    return dl.Fetched(
        payload=b"timestamp,close\n2025-01-02,1\n", ext="csv", payload_format="x/1", source_id=source_id,
        data_kind=kind, request=(), declared_adjustment=AdjustmentStatus.RAW, adjustment_anchor=None,
        declared_currency=USD, market=None, source_identifiers=(), libraries=(), label=label)


class GateDecisionTests(unittest.TestCase):
    def registry(self):
        return SourceRegistry.from_json(json.dumps(REGISTRY))

    def test_only_a_recorded_permitting_check_opens_the_gate(self):
        reg = self.registry()
        self.assertIsNone(dl.terms_refusal(reg, "alphavantage.us"))
        self.assertIsNone(dl.terms_refusal(reg, "frankfurter.ecb"))
        self.assertIn("does not permit", dl.terms_refusal(reg, "akshare.cn"))
        self.assertIn("not attested", dl.terms_refusal(reg, "baostock.cn"))
        self.assertIn("not in SOURCES.json", dl.terms_refusal(reg, "ecb.eurofxref"))  # unknown: owner must add it
        self.assertIn("no source", dl.terms_refusal(reg, None))
        self.assertIn("fail closed", dl.terms_refusal(None, "alphavantage.us"))

    def test_an_unreadable_or_missing_registry_refuses_everything(self):
        with tempfile.TemporaryDirectory() as tmp:
            gate = dl.make_gate(Path(tmp))  # no SOURCES.json
            self.assertIn("fail closed", gate("alphavantage.us"))
            (Path(tmp) / "SOURCES.json").write_text("not json", encoding="utf-8")
            self.assertIn("fail closed", dl.make_gate(Path(tmp))("alphavantage.us"))

    def test_every_fetchable_source_maps_to_a_registry_id(self):
        parser_choices = {a.dest: a for a in dl.build_parser()._subparsers._group_actions[0].choices["fetch"]._actions}
        for choice in parser_choices["source"].choices:
            if choice != "cfets":  # no route exists yet
                self.assertIn(choice, dl.FETCH_SOURCE_IDS)


class ProbeGateTests(unittest.TestCase):
    def run_probe(self, steps, root, **kw):
        out = io.StringIO()
        with mock.patch.object(dl, "probe_steps", return_value=steps), contextlib.redirect_stdout(out), \
                mock.patch.object(dl.urllib.request, "urlopen", side_effect=AssertionError("network!")):
            code = dl.run_probe({}, root, sleep=lambda s: None, **kw)
        return code, out.getvalue()

    def steps(self, calls):
        def make(source_id):
            def run():
                calls.append(source_id)
                return fetched(source_id, label=source_id)
            return dl.ProbeStep(f"{source_id} step", run, target=dl.ProbeTarget(source_id, DataKind.QUOTE, source_id, "csv"))
        return [make(s) for s in ("akshare.cn", "akshare_sina.hk", "baostock.cn", "alphavantage.us", "ecb.eurofxref")]

    def test_refused_steps_print_refused_and_make_no_request_admitted_steps_run(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root)
            code, text = self.run_probe(self.steps(calls), root)
            self.assertEqual(calls, ["alphavantage.us"])  # the only admitted step made its one request
            for refused in ("akshare.cn", "akshare_sina.hk", "baostock.cn", "ecb.eurofxref"):
                self.assertTrue(any(line.startswith("REFUSED (terms: PD-0031/PD-0032)") and f"{refused} step" in line
                                    for line in text.splitlines()), refused)
            self.assertIn("OK    alphavantage.us step", text)
            self.assertEqual(code, 0)  # a refusal is not a failure
            self.assertNotIn("FAIL", text)

    def test_the_refusal_comes_before_a_missing_key_and_before_an_existing_file(self):
        calls = []
        steps = [dl.ProbeStep("av", lambda: calls.append(1), True,  # type: ignore[arg-type,return-value]
                              target=dl.ProbeTarget("akshare.cn", DataKind.QUOTE, "f", "csv"),
                              skip_reason="FINWEB_ALPHAVANTAGE_KEY is not set")]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root)
            _, text = self.run_probe(steps, root)
        self.assertIn("REFUSED (terms: PD-0031/PD-0032) av", text)
        self.assertNotIn("SKIP", text)
        self.assertEqual(calls, [])

    def test_no_registry_means_every_step_is_refused(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            code, text = self.run_probe(self.steps(calls), Path(tmp))
        self.assertEqual((calls, code), ([], 0))
        self.assertEqual(text.count("REFUSED (terms: PD-0031/PD-0032)"), 5)

    def test_the_committed_probe_plan_names_a_source_for_every_step(self):
        # a step with no source could not be gated: the real plan has none
        self.assertTrue(all(s.target is not None for s in dl.probe_steps({})))

    def test_the_real_plan_against_a_registry_that_admits_only_the_three_sources_makes_no_other_request(self):
        doc = {"sources": [entry(s, False) for s in (
            "akshare.cn", "akshare.hk", "akshare.us", "akshare_sina.cn", "akshare_sina.hk", "akshare_sina.us")]
            + [entry("baostock.cn", None), entry("alphavantage.us", True), entry("frankfurter.ecb", True),
               entry("openfigi", True)]}
        requested = []

        def fake_http(request, what, key_bearing=False, secrets=()):
            requested.append(what)
            if what == "frankfurter":
                return b'{"base":"EUR","amount":1.0,"rates":{"2025-01-02":{"USD":1.03}}}'
            return b'[{"data":[{"figi":"BBG0SYNTH001"}]}]'

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root, doc)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), mock.patch.object(dl, "_http", fake_http), \
                    mock.patch.object(dl, "import_vendor", side_effect=AssertionError("a vendor library was imported")):
                dl.run_probe({}, root, sleep=lambda s: None)
        text = out.getvalue()
        # six AKShare routes + BaoStock = 7 sources; akshare.cn has two steps (raw and qfq): 8 steps
        self.assertEqual(text.count("REFUSED (terms: PD-0031/PD-0032)"), 8)
        self.assertEqual(sorted(set(requested)), ["frankfurter", "openfigi"])  # alphavantage: admitted, but no key: SKIP
        self.assertIn("SKIP  alphavantage.us", text)


class FetchGateTests(unittest.TestCase):
    def args(self, **kw):
        base = dict(source="akshare_cn", symbol="600519", symbols="USD,HKD,CNY", exch_code="US", mic="",
                    start="2025-01-02", end="2025-01-08", adjust="raw", currency="CNY")
        base.update(kw)
        return mock.Mock(**base)

    def test_fetch_of_a_refused_source_raises_before_any_fetch_function_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root)
            for source in ("akshare_cn", "akshare_sina_hk", "baostock_cn", "ecb_eurofxref"):
                with mock.patch.object(dl, "import_vendor", side_effect=AssertionError("vendor imported")), \
                        mock.patch.object(dl, "_http", side_effect=AssertionError("network!")):
                    with self.assertRaises(dl.TermsRefusedError) as ctx:
                        dl.run_fetch(self.args(source=source), {}, root)
                self.assertIn("REFUSED (terms: PD-0031/PD-0032)", str(ctx.exception), source)

    def test_main_exits_2_with_a_clear_message_and_makes_no_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_registry(Path(tmp))
            env = {dl.HUMAN_ENV: "1", "FINWEB_MARKETDATA_DIR": tmp}
            err = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys.stdin, "isatty", return_value=True), \
                    contextlib.redirect_stderr(err), \
                    mock.patch.object(dl.urllib.request, "urlopen", side_effect=AssertionError("network!")):
                code = dl.main(["fetch", "--source", "akshare_sina_hk", "--symbol", "00700", "--currency", "HKD"])
            self.assertEqual(code, 2)
            self.assertIn("REFUSED (terms: PD-0031/PD-0032) akshare_sina_hk", err.getvalue())
            self.assertIn("does not permit internal development use", err.getvalue())

    def test_an_admitted_source_still_fetches_and_saves(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root)
            with mock.patch.object(dl, "_http", lambda r, w, key_bearing=False, secrets=():
                                   b'{"base":"EUR","amount":1.0,"rates":{"2025-01-02":{"USD":1.03}}}'), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(dl.run_fetch(self.args(source="frankfurter_fx"), {}, root), 0)
            self.assertEqual(len(FileStore(root).manifest_paths()), 1)

    def test_register_file_and_verify_are_not_gated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_registry(root)  # calendar.manual is not in the registry: register-file must still work
            source = root / "cal.json"
            source.write_bytes(b'{"x": 1}\n')
            env = {dl.HUMAN_ENV: "1", "FINWEB_MARKETDATA_DIR": tmp}
            out = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(sys.stdin, "isatty", return_value=True), \
                    contextlib.redirect_stdout(out), \
                    mock.patch.object(dl.urllib.request, "urlopen", side_effect=AssertionError("network!")):
                code = dl.main(["register-file", "--path", str(source), "--source", "calendar.manual",
                                "--kind", "CALENDAR", "--format", "finweb_calendar_json/1", "--adjustment", "RAW",
                                "--label", "NYSE_2026", "--ext", "json", "--identifiers", "NYSE_SESSIONS"])
                self.assertEqual(code, 0)
                self.assertEqual(dl.main(["verify"]), 0)
            manifest = FileStore(root).read_verified(FileStore(root).manifest_paths()[0]).manifest
            self.assertEqual((manifest.source_id, manifest.data_kind, manifest.source_identifiers),
                             ("calendar.manual", DataKind.CALENDAR, ("NYSE_SESSIONS",)))
            self.assertEqual(manifest.retrieved_by, "human")


ECB_CSV = (b"Date,USD,JPY,CNY,\n2025-01-03,1.0299,161.25,7.5189,\n2025-01-02,1.0321,162.50,7.5338,\n")


class EcbRouteTests(unittest.TestCase):
    def test_the_csv_is_saved_exactly_as_published_with_a_declared_read_window(self):
        calls = []

        def fake_http(request, what, key_bearing=False, secrets=()):
            calls.append(request.full_url)
            return ECB_CSV

        with mock.patch.object(dl, "_http", fake_http):
            f = dl.fetch_ecb_eurofxref("2025-01-02", "2025-01-03", ("USD", "CNY"))
        self.assertEqual(f.payload, ECB_CSV)  # byte for byte
        self.assertEqual((f.source_id, f.data_kind, f.payload_format), ("ecb.eurofxref", DataKind.FX, "ecb_eurofxref_hist_csv/1"))
        self.assertEqual(f.source_identifiers, ("USD", "CNY"))
        self.assertIn(("read_start", "2025-01-02"), f.request)
        self.assertEqual(len(calls), 1)
        self.assertEqual(dl.check_fetched(f), (2, "2025-01-02", "2025-01-03"))  # the 'Date' header is understood

    def test_a_zip_container_is_unpacked_to_its_single_csv_member_unchanged(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("eurofxref-hist.csv", ECB_CSV)

        def fake_http(request, what, key_bearing=False, secrets=()):
            if request.full_url.endswith(".csv"):
                raise dl.FetchError("HTTP 404")
            return buffer.getvalue()

        with mock.patch.object(dl, "_http", fake_http):
            f = dl.fetch_ecb_eurofxref("2025-01-02", "2025-01-03", ("USD",))
        self.assertEqual(f.payload, ECB_CSV)
        self.assertTrue(any(v.endswith(".zip") for k, v in f.request if k == "endpoint"))

    def test_a_response_that_is_not_the_file_is_a_failure_and_nothing_is_saved(self):
        with mock.patch.object(dl, "_http", lambda r, w, key_bearing=False, secrets=(): b"<html>moved</html>"):
            with self.assertRaises(dl.FetchError) as ctx:
                dl.fetch_ecb_eurofxref("2025-01-02", "2025-01-03", ("USD",))
        self.assertIn("every endpoint failed", str(ctx.exception))

    def test_the_cli_accepts_the_route_and_the_gate_covers_it(self):
        args = dl.build_parser().parse_args(["fetch", "--source", "ecb_eurofxref"])
        self.assertEqual(args.source, "ecb_eurofxref")
        self.assertEqual(dl.FETCH_SOURCE_IDS["ecb_eurofxref"], "ecb.eurofxref")


if __name__ == "__main__":
    unittest.main()
