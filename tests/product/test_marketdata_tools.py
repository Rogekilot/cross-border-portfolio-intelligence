"""The human-run download tool v0: guards, lazy vendor imports, key hygiene, immutability and
the manifest it writes. Nothing here touches the network (every HTTP call is replaced) and
nothing runs a real fetch: the tool is untested against the network by design, and agents
never run it (PD-0027 condition 2)."""

import contextlib
import io
import os
import stat
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode  # noqa: E402
from marketdata.contracts import AdjustmentStatus, UsageScope  # noqa: E402
from marketdata.files import FileHashMismatchError, FileStore  # noqa: E402
from marketdata.manifest import DataKind  # noqa: E402

VENDORS = ("akshare", "baostock", "pandas")
_before = {v for v in VENDORS if v in sys.modules}
from marketdata_tools import download as dl  # noqa: E402

_after = {v for v in VENDORS if v in sys.modules}

KEY = "SECRET-KEY-VALUE-123"
USD = CurrencyCode("USD")
WHEN = dl.datetime.datetime(2025, 1, 10, 9, 0, tzinfo=dl.datetime.timezone.utc)


class GuardTests(unittest.TestCase):
    def test_importing_the_tool_imports_no_vendor_library(self):
        self.assertEqual(_after - _before, set())

    def test_it_refuses_without_the_human_opt_in_or_a_terminal(self):
        for env, tty in (({}, True), ({dl.HUMAN_ENV: "1"}, False), ({dl.HUMAN_ENV: "0"}, True),
                         ({dl.HUMAN_ENV: "yes"}, True)):
            with self.assertRaises(dl.HumanOnlyError):
                dl.require_human(env, tty)
        dl.require_human({dl.HUMAN_ENV: "1"}, True)  # the only accepted combination

    def test_network_commands_refuse_to_run_for_an_agent(self):
        env = {k: v for k, v in os.environ.items() if k != dl.HUMAN_ENV}
        for argv in (["probe"], ["fetch", "--source", "frankfurter_fx"],
                     ["register-file", "--path", "x", "--source", "s", "--kind", "QUOTE",
                      "--format", "f", "--adjustment", "RAW", "--label", "l"]):
            err = io.StringIO()
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(err), \
                    mock.patch.object(dl.urllib.request, "urlopen", side_effect=AssertionError("network!")):
                self.assertEqual(dl.main(argv), 2, argv)
            self.assertIn("human-only", err.getvalue())

    def test_a_missing_vendor_library_fails_with_the_install_instruction(self):
        with self.assertRaises(dl.ToolDependencyError) as ctx:
            dl.import_vendor("definitely_not_an_installed_package_xyz")
        self.assertIn("marketdata-download", str(ctx.exception))
        self.assertIn(".venv-download", str(ctx.exception))


class KeyHygieneTests(unittest.TestCase):
    def test_a_key_is_read_only_from_the_environment_and_never_reaches_a_manifest(self):
        seen = {}

        def fake_http(request, what, key_bearing=False, secrets=()):
            seen["url"] = request.full_url  # the real URL carries the key; nothing else may
            return b"timestamp,open,high,low,close,volume\n2025-01-02,1,2,0.5,1.5,10\n"

        with mock.patch.object(dl, "_http", fake_http):
            fetched = dl.fetch_alphavantage("AAPL", USD, {"FINWEB_ALPHAVANTAGE_KEY": KEY})
        self.assertIn(KEY, seen["url"])  # the call needs it ...
        with tempfile.TemporaryDirectory() as tmp:
            path, manifest = dl.save_file(Path(tmp), fetched, WHEN)
            blob = manifest.to_json() + path.read_text(encoding="utf-8") + repr(fetched.request)
            for p in Path(tmp).rglob("*"):
                if p.is_file():
                    blob += p.read_text(encoding="utf-8")
        self.assertNotIn(KEY, blob)  # ... and nothing saved may contain it
        self.assertNotIn("apikey", blob.lower())

    def test_a_missing_key_names_the_variable_not_a_file(self):
        with self.assertRaises(dl.FetchError) as ctx:
            dl.fetch_alphavantage("AAPL", USD, {})
        self.assertIn("FINWEB_ALPHAVANTAGE_KEY", str(ctx.exception))

    def test_a_network_error_never_echoes_the_url_or_the_key(self):
        boom = urllib.error.URLError(f"https://x/query?apikey={KEY}")
        with mock.patch.object(dl.urllib.request, "urlopen", side_effect=boom):
            with self.assertRaises(dl.FetchError) as ctx:
                dl.fetch_alphavantage("AAPL", USD, {"FINWEB_ALPHAVANTAGE_KEY": KEY})
        self.assertNotIn(KEY, str(ctx.exception))
        self.assertIn("URLError", str(ctx.exception))

    def test_a_json_error_body_from_the_source_saves_nothing(self):
        with mock.patch.object(dl, "_http", lambda r, w, key_bearing=False, secrets=(): b'{"Note": "rate limit"}'):
            with self.assertRaises(dl.FetchError):
                dl.fetch_alphavantage("AAPL", USD, {"FINWEB_ALPHAVANTAGE_KEY": KEY})

    def test_the_tool_has_no_key_argument(self):
        parser = dl.build_parser()
        text = parser.format_help() + "".join(
            sp.format_help() for sp in parser._subparsers._group_actions[0].choices.values())
        self.assertNotIn("key", text.lower())


class SaveFileTests(unittest.TestCase):
    def fetched(self, payload=b"a,b\n1,2\n"):
        return dl.Fetched(
            payload=payload, ext="csv", payload_format="x_csv/1", source_id="x.cn", data_kind=DataKind.QUOTE,
            request=(("symbol", "600519"),), declared_adjustment=AdjustmentStatus.UNDECLARED,
            adjustment_anchor="x adjust=qfq", declared_currency=USD, market="CN",
            source_identifiers=("600519",), libraries=(("somelib", "1.0"),), label="600519 2025/01 raw")

    def test_files_are_written_hashed_read_only_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, manifest = dl.save_file(root, self.fetched(), WHEN, script_sha256="c" * 64)
            self.assertEqual(path.read_bytes(), b"a,b\n1,2\n")
            self.assertEqual(manifest.size_bytes, 8)
            self.assertEqual(manifest.retrieved_by, "human")
            self.assertIs(manifest.usage_scope, UsageScope.INTERNAL_DEVELOPMENT_ONLY)  # PD-0028
            self.assertEqual((manifest.script_name, manifest.script_version), (dl.TOOL_NAME, dl.TOOL_VERSION))
            self.assertEqual(manifest.request, (("symbol", "600519"),))
            self.assertEqual(path.parent.name, "2025-01-10")
            self.assertEqual(path.parent.parent.name, "quote")
            self.assertFalse(stat.S_IMODE(path.stat().st_mode) & stat.S_IWUSR)  # read-only
            with self.assertRaises(FileExistsError):  # exclusive create: no replacement
                dl.save_file(root, self.fetched(), WHEN)
            self.assertEqual(path.read_bytes(), b"a,b\n1,2\n")

    def test_what_the_tool_saves_is_what_the_platform_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, manifest = dl.save_file(root, self.fetched(), WHEN)
            store = FileStore(root)
            self.assertEqual(store.read_by_hash(manifest.file_sha256).payload, b"a,b\n1,2\n")
            os.chmod(path, 0o644)
            path.write_bytes(b"a,b\n1,3\n")  # a human (or a bug) edits it afterwards
            with self.assertRaises(FileHashMismatchError):
                store.read_by_hash(manifest.file_sha256)

    def test_verify_command_is_offline_and_needs_no_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            dl.save_file(Path(tmp), self.fetched(), WHEN)
            out = io.StringIO()
            env = {k: v for k, v in os.environ.items() if k != dl.HUMAN_ENV}
            env["FINWEB_MARKETDATA_DIR"] = tmp
            with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(out), \
                    mock.patch.object(dl.urllib.request, "urlopen", side_effect=AssertionError("network!")):
                self.assertEqual(dl.main(["verify"]), 0)
            self.assertIn("1 file(s) checked, 0 failed", out.getvalue())

    def test_an_adjusted_pull_is_never_declared_raw(self):
        status, anchor = dl._adjust_fields("qfq", "lib.func")
        self.assertIs(status, AdjustmentStatus.UNDECLARED)
        self.assertIn("qfq", anchor)
        self.assertEqual(dl._adjust_fields("raw", "lib.func"), (AdjustmentStatus.RAW, None))

    def test_data_dir_defaults_inside_the_repository_and_can_be_overridden(self):
        self.assertEqual(dl.data_dir({}).parts[-2:], ("data", "marketdata"))
        self.assertEqual(dl.data_dir({"FINWEB_MARKETDATA_DIR": "/x/y"}), Path("/x/y"))

    def test_probe_steps_are_small_and_cover_the_planned_sources(self):
        names = [s.name for s in dl.probe_steps({})]
        for part in ("akshare.cn", "baostock", "alphavantage", "frankfurter", "akshare_sina.cn",
                     "akshare_sina.hk", "akshare_sina.us", "openfigi"):
            self.assertTrue(any(part in n for n in names), part)
        self.assertLessEqual(len(names), 12)
        alpha = next(s for s in dl.probe_steps({}) if "alphavantage" in s.name)
        self.assertTrue(alpha.key_bearing)
        with self.assertRaises(dl.SkipStep):  # no key set: a SKIP, not a FAIL
            alpha.run()


class FakeFrame:
    """Stands in for a pandas DataFrame: the tool only calls `to_csv`."""

    def __init__(self, text):
        self.text = text

    def to_csv(self, index=False):
        return self.text


class ErrorReportingTests(unittest.TestCase):
    def test_a_key_free_call_reports_class_message_and_http_status(self):
        err = urllib.error.HTTPError("https://api.frankfurter.dev/v1/x", 404, "Not Found", {}, io.BytesIO(b'{"message":"not found"}'))
        with mock.patch.object(dl.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(dl.FetchError) as ctx:
                dl._http(dl.urllib.request.Request("https://x.example/"), "frankfurter")
        self.assertIn("HTTP 404 Not Found", str(ctx.exception))
        self.assertIn("not found", str(ctx.exception))

    def test_other_key_free_errors_keep_their_message(self):
        with mock.patch.object(dl.urllib.request, "urlopen", side_effect=ConnectionResetError("reset by peer")):
            with self.assertRaises(dl.FetchError) as ctx:
                dl._http(dl.urllib.request.Request("https://x.example/"), "src")
        self.assertIn("ConnectionResetError: reset by peer", str(ctx.exception))

    def test_a_key_bearing_http_error_reports_the_class_only(self):
        err = urllib.error.HTTPError(f"https://x/?apikey={KEY}", 403, f"bad {KEY}", {}, io.BytesIO(KEY.encode()))
        with mock.patch.object(dl.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(dl.FetchError) as ctx:
                dl._http(dl.urllib.request.Request("https://x.example/"), "av", key_bearing=True)
        self.assertNotIn(KEY, str(ctx.exception))
        self.assertNotIn("403", str(ctx.exception))

    def test_sanitize_masks_known_secrets_and_bounds_length(self):
        text = dl.sanitize(f"line one\nkey={KEY}\t" + "x" * 1000, [KEY], 100)
        self.assertNotIn(KEY, text)
        self.assertNotIn("\n", text)
        self.assertLessEqual(len(text), 103)

    def test_every_request_carries_an_explicit_user_agent(self):
        seen = {}

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return b"{}"

        def fake_urlopen(request, timeout=None):
            seen["ua"] = request.get_header("User-agent")
            return Resp()

        with mock.patch.object(dl.urllib.request, "urlopen", fake_urlopen):
            dl._http(dl.urllib.request.Request("https://x.example/"), "src")
        self.assertIn("finweb-marketdata-tools", seen["ua"])
        self.assertNotIn("Python-urllib", seen["ua"])

    def test_frankfurter_tries_the_next_endpoint_and_records_which_answered(self):
        calls = []

        def fake_http(request, what, key_bearing=False, secrets=()):
            calls.append(request.full_url)
            if "frankfurter.dev" in request.full_url:
                raise dl.FetchError("frankfurter: HTTP 404 Not Found")
            return b'{"base":"EUR","rates":{"2025-01-02":{"USD":1.03}}}'

        with mock.patch.object(dl, "_http", fake_http):
            fetched = dl.fetch_frankfurter("2025-01-02", "2025-01-08", ("USD",))
        self.assertEqual(len(calls), 2)
        self.assertIn("..", calls[0])  # range syntax
        self.assertIn(("endpoint", "https://api.frankfurter.app"), fetched.request)
        self.assertIn("base=EUR", calls[0])  # EUR-based only, never re-based
        with mock.patch.object(dl, "_http", side_effect=dl.FetchError("down")):
            with self.assertRaises(dl.FetchError) as ctx:
                dl.fetch_frankfurter("2025-01-02", "2025-01-08", ("USD",))
        self.assertIn("every endpoint failed", str(ctx.exception))


class BaostockTests(unittest.TestCase):
    def test_login_failure_reports_code_message_and_the_network_hint(self):
        class Login:
            error_code, error_msg = "10001001", "login failed"

        fake = mock.Mock()
        fake.login.return_value = Login()
        with mock.patch.object(dl, "import_vendor", return_value=fake):
            with self.assertRaises(dl.FetchError) as ctx:
                dl.fetch_baostock("sh.600519", "2025-01-02", "2025-01-08", "raw", USD)
        text = str(ctx.exception)
        self.assertIn("10001001", text)
        self.assertIn("login failed", text)
        self.assertIn("unreachable from some", text)


class SinaTests(unittest.TestCase):
    FULL = "date,open,high,low,close,volume\n2024-12-31,1,2,1,1.5,10\n2025-01-02,1,2,1,1.6,11\n2025-01-08,1,2,1,1.7,12\n2025-02-01,1,2,1,1.8,13\n"

    def test_sina_functions_are_separate_sources_with_rows_filtered_to_the_range(self):
        fake = mock.Mock()
        fake.stock_hk_daily.return_value = FakeFrame(self.FULL)
        fake.stock_us_daily.return_value = FakeFrame(self.FULL)
        with mock.patch.object(dl, "import_vendor", return_value=fake):
            hk = dl.fetch_akshare_sina("hk", "00700", "2025-01-02", "2025-01-08", "raw", USD)
            us = dl.fetch_akshare_sina("us", "AAPL", "2025-01-02", "2025-01-08", "qfq", USD)
        fake.stock_hk_daily.assert_called_once_with(symbol="00700", adjust="")
        fake.stock_us_daily.assert_called_once_with(symbol="AAPL", adjust="qfq")
        self.assertEqual((hk.source_id, us.source_id), ("akshare_sina.hk", "akshare_sina.us"))
        self.assertEqual(hk.payload.decode().splitlines()[1:], ["2025-01-02,1,2,1,1.6,11", "2025-01-08,1,2,1,1.7,12"])
        self.assertIn(("row_filter", "date in [start, end] applied by the tool"), hk.request)
        self.assertIs(hk.declared_adjustment, AdjustmentStatus.RAW)
        self.assertIs(us.declared_adjustment, AdjustmentStatus.UNDECLARED)
        self.assertEqual(dl.check_fetched(hk), (2, "2025-01-02", "2025-01-08"))

    def test_eastmoney_functions_are_kept_with_their_own_source_ids(self):
        fake = mock.Mock()
        fake.stock_hk_hist.return_value = FakeFrame("日期,收盘\n2025-01-02,1\n")
        with mock.patch.object(dl, "import_vendor", return_value=fake):
            hk = dl.fetch_akshare("hk", "00700", "2025-01-02", "2025-01-08", "raw", USD)
        self.assertEqual(hk.source_id, "akshare.hk")
        fake.stock_hk_hist.assert_called_once()


class ResponseCheckTests(unittest.TestCase):
    def identity(self, body):
        return dl.Fetched(
            payload=body.encode(), ext="json", payload_format="openfigi_json_mapping/1", source_id="openfigi",
            data_kind=DataKind.IDENTITY, request=(), declared_adjustment=AdjustmentStatus.RAW,
            adjustment_anchor=None, declared_currency=None, market=None, source_identifiers=(), libraries=(),
            label="x")

    def test_an_openfigi_warning_or_error_or_empty_data_is_a_failure_never_ok(self):
        for body in ('[{"warning":"No identifier found."}]', '[{"error":"Invalid idType"}]',
                     '[{"data":[]}]', "[]", "{}", "not json"):
            with self.assertRaises(dl.FetchError, msg=body):
                dl.check_fetched(self.identity(body))
        self.assertEqual(dl.check_fetched(self.identity('[{"data":[{"figi":"BBG000B9XRY4"},{"figi":"BBG000B9Y5X2"}]}]')),
                         (2, None, None))

    def test_the_warning_text_is_reported(self):
        with self.assertRaises(dl.FetchError) as ctx:
            dl.check_fetched(self.identity('[{"warning":"No identifier found."}]'))
        self.assertIn("No identifier found.", str(ctx.exception))

    def test_openfigi_request_uses_exch_code_and_only_adds_mic_when_asked(self):
        sent = {}

        def fake_http(request, what, key_bearing=False, secrets=()):
            sent["body"] = request.data
            sent["key_bearing"] = key_bearing
            return b'[{"data":[{"figi":"X"}]}]'

        with mock.patch.object(dl, "_http", fake_http):
            f = dl.fetch_openfigi("AAPL", {})
            self.assertEqual(dl.json.loads(sent["body"]), [{"idType": "TICKER", "idValue": "AAPL",
                                                           "exchCode": "US", "marketSecDes": "Equity"}])
            self.assertFalse(sent["key_bearing"])
            self.assertNotIn(("micCode", "XNAS"), f.request)
            dl.fetch_openfigi("AAPL", {"FINWEB_OPENFIGI_KEY": KEY}, mic="XNAS")
            self.assertEqual(dl.json.loads(sent["body"])[0]["micCode"], "XNAS")
            self.assertTrue(sent["key_bearing"])

    def test_openfigi_mic_query_sends_mic_code_only_unless_exch_code_is_explicit(self):
        sent = []

        def fake_http(request, what, key_bearing=False, secrets=()):
            sent.append(dl.json.loads(request.data)[0])
            return b'[{"data":[{"figi":"X"}]}]'

        with mock.patch.object(dl, "_http", fake_http):
            f_mic = dl.fetch_openfigi("AAPL", {}, mic="XNGS")
            f_both = dl.fetch_openfigi("AAPL", {}, exch_code="UW", mic="XNGS")
            f_exch = dl.fetch_openfigi("700", {}, exch_code="HK")
            f_none = dl.fetch_openfigi("AAPL", {})
        self.assertEqual(sent[0], {"idType": "TICKER", "idValue": "AAPL", "marketSecDes": "Equity",
                                   "micCode": "XNGS"})
        self.assertNotIn("exchCode", sent[0])
        self.assertNotIn(("exchCode", "US"), f_mic.request)
        self.assertEqual((sent[1]["exchCode"], sent[1]["micCode"]), ("UW", "XNGS"))
        self.assertEqual(sent[2]["exchCode"], "HK")
        self.assertNotIn("micCode", sent[2])
        self.assertEqual(sent[3]["exchCode"], "US")
        self.assertEqual([f.label for f in (f_mic, f_both, f_exch, f_none)],
                         ["AAPL_XNGS", "AAPL_UW_XNGS", "700_HK", "AAPL_US"])

    def test_cli_exch_code_defaults_to_unset_so_mic_alone_is_possible(self):
        parsed = dl.build_parser().parse_args(["fetch", "--source", "openfigi", "--symbol", "AAPL",
                                               "--mic", "XNGS"])
        self.assertIsNone(parsed.exch_code)
        self.assertEqual(parsed.mic, "XNGS")

    def test_empty_or_header_only_files_are_failures_and_ok_lines_have_rows_and_range(self):
        def csv_fetched(text):
            return dl.Fetched(
                payload=text.encode(), ext="csv", payload_format="x/1", source_id="x", data_kind=DataKind.QUOTE,
                request=(), declared_adjustment=AdjustmentStatus.RAW, adjustment_anchor=None,
                declared_currency=USD, market=None, source_identifiers=(), libraries=(), label="x")

        for text in ("", "日期,收盘\n"):
            with self.assertRaises(dl.FetchError):
                dl.check_fetched(csv_fetched(text))
        self.assertEqual(dl.check_fetched(csv_fetched("日期,收盘\n2025-01-03,2\n2025-01-02,1\n")),
                         (2, "2025-01-02", "2025-01-03"))
        self.assertEqual(dl.check_fetched(csv_fetched("timestamp,close\n2025-01-03,2\n")), (1, "2025-01-03", "2025-01-03"))

    def test_the_probe_prints_rows_and_range_and_counts_skips_separately_from_failures(self):
        def good():
            return dl.Fetched(payload="日期,收盘\n2025-01-02,1\n2025-01-03,2\n".encode(), ext="csv",
                              payload_format="x/1", source_id="x.cn", data_kind=DataKind.QUOTE, request=(),
                              declared_adjustment=AdjustmentStatus.RAW, adjustment_anchor=None,
                              declared_currency=USD, market=None, source_identifiers=(), libraries=(), label="a")

        def empty():
            return dl.Fetched(payload="日期,收盘\n".encode(), ext="csv", payload_format="x/1", source_id="x.cn",
                              data_kind=DataKind.QUOTE, request=(), declared_adjustment=AdjustmentStatus.RAW,
                              adjustment_anchor=None, declared_currency=USD, market=None, source_identifiers=(),
                              libraries=(), label="b")

        def boom():
            raise ConnectionError(f"reset url=https://e/x?apikey={KEY}")

        def skip():
            raise dl.SkipStep("no key")

        steps = [dl.ProbeStep("good", good), dl.ProbeStep("empty", empty), dl.ProbeStep("boom", boom),
                 dl.ProbeStep("keyed", boom, key_bearing=True), dl.ProbeStep("skip", skip)]
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(dl, "probe_steps", return_value=steps), \
                contextlib.redirect_stdout(out):
            code = dl.run_probe({"FINWEB_ALPHAVANTAGE_KEY": KEY}, Path(tmp), sleep=lambda s: None,
                                gate=lambda source_id: None)  # about reporting, not terms: the gate is injected open
        text = out.getvalue()
        self.assertEqual(code, 1)
        self.assertIn("OK    good: rows=2 range=2025-01-02..2025-01-03", text)
        self.assertIn("FAIL  empty", text)
        self.assertIn("SKIP  skip: no key", text)
        self.assertIn("ConnectionError: reset", text)  # key-free: class and message
        self.assertNotIn(KEY, text)  # even a key-free message is masked if it holds a known key
        self.assertIn("details withheld", text)  # key-bearing: class only


if __name__ == "__main__":
    unittest.main()
