"""Probe behaviour of download tool v0.1.1: politeness, EXISTS, throttle hint, the Sina CN route.
No network: every fetch is replaced."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode  # noqa: E402
from marketdata.contracts import AdjustmentStatus  # noqa: E402
from marketdata.manifest import DataKind  # noqa: E402
from marketdata_tools import download as dl  # noqa: E402

CNY = CurrencyCode("CNY")


def fetched_for(target):
    return dl.Fetched(
        payload="日期,收盘\n2025-01-02,1\n".encode(), ext=target.ext, payload_format="x/1",
        source_id=target.source_id, data_kind=target.kind, request=(),
        declared_adjustment=AdjustmentStatus.RAW, adjustment_anchor=None, declared_currency=CNY, market=None,
        source_identifiers=(), libraries=(), label=target.label)


class ProbePoliteness(unittest.TestCase):
    def run_probe(self, steps, root, sleeps):
        out = io.StringIO()
        with mock.patch.object(dl, "probe_steps", return_value=steps), contextlib.redirect_stdout(out):
            # these tests are about politeness, not terms: the (new, default-on) terms gate is injected open
            code = dl.run_probe({}, root, sleep=sleeps.append, gate=lambda source_id: None)
        return code, out.getvalue()

    def test_a_step_whose_file_exists_today_is_reported_exists_and_makes_no_request(self):
        target = dl.ProbeTarget("x.cn", DataKind.QUOTE, "600519_a_raw", "csv")
        calls = []

        def run():
            calls.append(1)
            return fetched_for(target)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            step = dl.ProbeStep("x raw", run, target=target)
            code, text = self.run_probe([step], root, [])
            self.assertEqual((code, calls), (0, [1]))
            self.assertIn("OK    x raw", text)
            path = dl.expected_path(root, target, dl._now())
            self.assertTrue(path.exists())
            code, text = self.run_probe([step], root, [])
            self.assertEqual((code, calls), (0, [1]))  # not fetched again
            self.assertIn("EXISTS x raw", text)
            self.assertNotIn("FAIL", text)

    def test_one_request_per_step_a_pause_between_requests_and_no_pause_for_skips(self):
        t1 = dl.ProbeTarget("a", DataKind.QUOTE, "l1", "csv")
        t2 = dl.ProbeTarget("b", DataKind.QUOTE, "l2", "csv")
        counts = {"a": 0, "b": 0}

        def make(t, key):
            def run():
                counts[key] += 1
                return fetched_for(t)
            return run

        sleeps = []
        with tempfile.TemporaryDirectory() as tmp:
            steps = [dl.ProbeStep("a", make(t1, "a"), target=t1),
                     dl.ProbeStep("s", lambda: None, skip_reason="no key"),  # type: ignore[arg-type,return-value]
                     dl.ProbeStep("b", make(t2, "b"), target=t2)]
            _, text = self.run_probe(steps, Path(tmp), sleeps)
        self.assertEqual(counts, {"a": 1, "b": 1})  # exactly one request each, no retry loop
        self.assertEqual(sleeps, [dl.PROBE_PAUSE_SECONDS])  # one pause between the two requests; none for the skip
        self.assertIn("SKIP  s: no key", text)

    def test_a_failing_step_is_not_retried(self):
        calls = []

        def boom():
            calls.append(1)
            raise ConnectionError("RemoteDisconnected('Remote end closed connection without response')")

        with tempfile.TemporaryDirectory() as tmp:
            code, text = self.run_probe([dl.ProbeStep("e", boom, eastmoney=True)], Path(tmp), [])
        self.assertEqual((code, len(calls)), (1, 1))

    def test_eastmoney_disconnects_get_the_throttling_hint_and_others_do_not(self):
        def boom():
            raise ConnectionError("RemoteDisconnected('Remote end closed connection without response')")

        with tempfile.TemporaryDirectory() as tmp:
            _, east = self.run_probe([dl.ProbeStep("e", boom, eastmoney=True)], Path(tmp), [])
            _, other = self.run_probe([dl.ProbeStep("o", boom)], Path(tmp), [])
        self.assertIn("usually means the upstream is throttling", east)
        self.assertNotIn("throttling", other)

    def test_the_real_probe_plan_marks_the_eastmoney_steps_and_names_every_target(self):
        steps = dl.probe_steps({})
        east = [s.name for s in steps if s.eastmoney]
        self.assertEqual(len(east), 4)
        self.assertTrue(all("eastmoney" in n for n in east))
        self.assertTrue(all(s.target is not None for s in steps))
        cn = next(s for s in steps if s.name.startswith("akshare_sina.cn"))
        self.assertEqual(cn.target.source_id, "akshare_sina.cn")


class SinaCnRoute(unittest.TestCase):
    def test_stock_zh_a_daily_is_called_once_with_iso_dates_and_the_source_id_is_separate(self):
        text = ("date,open,high,low,close,volume,amount,outstanding_share,turnover\n"
                "2024-12-31,1,2,1,1.5,100,1000,1000000,0.0001\n"
                "2025-01-02,1,2,1,1.6,110,1100,1000000,0.00011\n")

        class Frame:
            def to_csv(self, index=False):
                return text

        fake = mock.Mock()
        fake.stock_zh_a_daily.return_value = Frame()
        with mock.patch.object(dl, "import_vendor", return_value=fake):
            f = dl.fetch_akshare_sina("cn", "sh600519", "2025-01-02", "2025-01-08", "raw", CNY)
        fake.stock_zh_a_daily.assert_called_once_with(
            symbol="sh600519", start_date="2025-01-02", end_date="2025-01-08", adjust="")
        self.assertEqual(f.source_id, "akshare_sina.cn")
        self.assertEqual(f.payload_format, "akshare_sina_csv_cn_daily/1")
        self.assertEqual(dl.check_fetched(f), (1, "2025-01-02", "2025-01-02"))
        self.assertIn(("function", "stock_zh_a_daily"), f.request)

    def test_the_cli_accepts_the_new_route(self):
        args = dl.build_parser().parse_args(["fetch", "--source", "akshare_sina_cn", "--symbol", "sh600519",
                                             "--currency", "CNY"])
        self.assertEqual(args.source, "akshare_sina_cn")


if __name__ == "__main__":
    unittest.main()
