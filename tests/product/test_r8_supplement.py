"""F1 R8 supplementary run: the runner (`src/real_tools/r8_supplement.py`), with the R8 runner's mocked world (`test_r8_guide.World`): no cluster, no sudo, no network,
no database. The loopback tool is a scripted child; its real behaviour is tested in `test_r8_http_check`. R8's folder is a real temporary directory with a
finished R8 state, so that "the runner writes nothing there" is checked on real files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
for entry in (str(REPO / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from real_tools import r8_guide as g  # noqa: E402
from real_tools import r8_supplement as s  # noqa: E402
import test_r8_guide as tg  # noqa: E402

CTX = s.CONTEXT_ID
D = {"first": ("1" * 64, "2" * 64), "y": ("3" * 64, "4" * 64)}


def lines_text(*lines):
    return ("\n".join("S8 " + json.dumps(line, sort_keys=True) for line in lines) + "\n").encode()


def pre_ok():
    return g.Result(0, lines_text({"label": "login", "status": 200}, {"label": "read_first", "status": 200, "response_sha256": D["first"][0], "issued_sha256": D["first"][1]},
                                  {"label": "read_y", "status": 200, "response_sha256": D["y"][0], "issued_sha256": D["y"][1]}))


class SWorld(tg.World):
    def __init__(self, home):
        super().__init__(home)
        self.running, self.pid, self.same_pid, self.stop_exit = True, 4000, False, 0
        self.tool_results = {}                         # phase -> [Result, ...] consumed in order, then the default
        self.ports_at_tool = []                        # the open ports at each call of the tool (a launcher must be up when it runs)
        self.rules[:0] = [["User B's username", "bob"], ["Do you make that statement", "yes"], ["Optional: the name you remember", ""], ["Optional, one minute", "skip"],
                          ["Is it true?", "yes"], ["pass or fail?", "pass"], ["(type freeze)", "freeze"]]

    def tool_phase(self, argv):
        return argv[argv.index("--phase") + 1]

    def default(self, call):
        if call.key == "r8_http_check":
            phase = self.tool_phase(call.argv)
            self.ports_at_tool.append(set(self.open_ports))
            queued = self.tool_results.get(phase)
            if queued:
                return queued.pop(0)
            return pre_ok() if phase == "pre" else g.Result(0, lines_text({"label": "login", "status": 200}))
        return super().default(call)

    def system(self, call):
        a = call.argv
        rest = a[3:] if a[1] == "-u" else a[1:]
        if rest[0].endswith("/pg_ctl"):
            if "status" in rest:
                return g.Result(0, b"pg_ctl: server is running (PID: %d)\n" % self.pid) if self.running else g.Result(3, b"pg_ctl: no server running\n")
            if "stop" in rest:
                if self.stop_exit == 0:
                    self.running = False
                return g.Result(self.stop_exit, b"")
            if "start" in rest:
                self.running = True
                if not self.same_pid:
                    self.pid += 1
                return g.Result(0, b"")
        return super().system(call)


class SupplementCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="r8supp"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.w = SWorld(self.home)
        self.r8 = self.home / "finweb-r8"
        self.sup = self.home / "finweb-r8-supplement"
        self.write_r8()

    def write_r8(self, **changes):
        self.r8.mkdir(exist_ok=True)
        state = {"schema": g.STATE_SCHEMA, "latch": None, "window": {"n": 2, "open": False}, "frozen": {"base": "/Users/Shared/finweb-r8-pg", "port": 5433, "cluster_user": "finwebpg",
                 "superuser": "finweb_su", "release_name": "hg4-aapl-2026-09-30", "pg_ctl": "/opt/homebrew/bin/pg_ctl", "psql": "/opt/homebrew/bin/psql", "initdb": "/opt/homebrew/bin/initdb"},
                 "done": {"publish": {"data": {"context": CTX, "generation": 1}}, "renew": {"data": {"generation": 3}}, "close": {"data": {}}}}
        state.update(changes)
        (self.r8 / "state.json").write_text(json.dumps(state))
        attempts = [{"typed": {"close": "not shown", "holding": "1234.5", "missed_sessions": "0", "nav": "1734.5", "state": "AVAILABLE"}}]
        events = [{"kind": "record", "item": "probe ids", "value": {"owner_id": tg.OWNER, "root_id": s.FIRST_ROOT, "username": "alice"}, "at": "x"},
                  {"kind": "record", "item": "check 10.1 NAV against the Quant's figure", "value": {"result": "FAIL", "attempts": attempts}, "at": "x"}]
        (self.r8 / "events.log").write_text("\n".join(json.dumps(e) for e in events) + "\n")
        (self.r8 / "P.json").write_text(json.dumps({"context_id": CTX, "snapshot": {"release": {"release_id": "r" * 64}}}))
        (self.r8 / "F.json").write_text(json.dumps({"listings": [[g.EXPECTED_LISTING_ID, "x"]]}))
        (self.r8 / "C2.json").write_text(json.dumps({"contexts": [{"context_id": CTX, "generation": 3}]}))

    def go(self, *argv):
        return s.main(list(argv), seams=self.w.seams(), home=self.home, repo_root=REPO)

    def state(self):
        return json.loads((self.sup / "state.json").read_text())

    STEP_ORDER = ["start_1", "http_b", "http_pre", "stop_1", "pg_stop", "pg_start", "start_2", "http_post", "screen", "reeval_101", "close"]

    def done(self):
        done = self.state()["done"]                        # the state file is written with sorted keys: report in the runner's step order
        return [sid for sid in self.STEP_ORDER if sid in done]

    def tool_calls(self, phase=None):
        out = [c for c in self.w.calls if c.key == "r8_http_check"]
        return [c for c in out if phase is None or self.w.tool_phase(c.argv) == phase]

    def r8_snapshot(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(self.r8.iterdir()) if p.is_file()}

    def events(self):
        return [json.loads(line) for line in (self.sup / "events.log").read_text().splitlines() if line.strip()]


class HappyRunTests(SupplementCase):
    def test_the_whole_run_in_order_and_nothing_is_written_to_r8s_folder(self):
        before = self.r8_snapshot()
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.done(), ["start_1", "http_b", "http_pre", "stop_1", "pg_stop", "pg_start", "start_2", "http_post", "screen", "reeval_101", "close"])
        self.assertEqual(self.r8_snapshot(), before)
        self.assertEqual(sorted(p.name for p in self.r8.iterdir()), sorted(before))
        self.assertTrue((self.sup / "SUPPLEMENT_RECORD.md").exists())
        self.assertEqual(oct((self.sup / "SUPPLEMENT_RECORD.md").stat().st_mode & 0o777), "0o600")
        self.assertIn("supplementary-run record", (self.sup / "SUPPLEMENT_RECORD.md").read_text())

    def test_the_restart_is_a_stop_then_a_start_with_a_new_pid_and_the_launcher_is_down_first(self):
        self.go()
        verbs = [next(v for v in ("status", "stop", "start") if v in c.argv) for c in self.w.calls if c.key == "sudo:pg_ctl"]
        self.assertEqual(verbs, ["status", "stop", "status", "status", "start", "status"])        # before, stop, down; then (the R8 start step) status, start, new PID
        stop =next(c for c in self.w.calls if c.key == "sudo:pg_ctl" and "stop" in c.argv)
        self.assertEqual(stop.argv[stop.argv.index("stop"):], ["stop", "-m", "fast", "--wait"])
        self.assertEqual(stop.argv[:3], ["/usr/bin/sudo", "-u", "finwebpg"])
        self.assertEqual(stop.argv[3], "/opt/homebrew/bin/pg_ctl")
        records = [e["value"] for e in self.events() if e["kind"] == "record" and e["item"].startswith("cluster postmaster PID")]
        self.assertEqual(records, [4000, {"before": 4000, "after": 4001, "differs": True}])
        launchers = [c for c in self.w.calls if c.argv and c.argv[:7] == tg.FW and c.argv[7] == "web_api.real_launcher"]
        self.assertEqual(len(launchers), 2)
        self.assertEqual(self.w.open_ports, set())
        phases = [self.w.tool_phase(c.argv) for c in self.tool_calls()]
        self.assertEqual(phases, ["b", "pre", "post"])

    def test_the_tool_is_started_only_as_a_child_with_the_expected_arguments(self):
        self.go()
        b, pre, post = (self.tool_calls(p)[0].argv for p in ("b", "pre", "post"))
        self.assertEqual(b[:8], tg.FW + ["real_tools.r8_http_check"])
        self.assertEqual(b[8:], ["--phase", "b", "--user-b", "bob", "--root", s.FIRST_ROOT, "--root-operation", s.FIRST_OPERATION])
        y = self.state()["y"]["operation_id"]
        self.assertEqual(pre[pre.index("--operation-id") + 1], y)
        self.assertEqual(pre[pre.index("--user-a") + 1], "alice")
        self.assertEqual(pre[pre.index("--context") + 1], CTX)
        self.assertEqual(pre[pre.index("--release") + 1], "r" * 64)
        self.assertEqual(pre[pre.index("--acknowledged") + 1], "yes")
        self.assertNotIn("--resume", pre)
        self.assertNotIn("--replay-name", pre)
        self.assertEqual(post[post.index("--first-response-sha") + 1], D["first"][0])
        self.assertEqual(post[post.index("--y-issued-sha") + 1], D["y"][1])
        for argv in (b, pre, post):
            self.assertFalse(any("password" in a.lower() or "cookie" in a.lower() for a in argv))

    def test_b_runs_before_any_create_and_y_is_saved_before_the_create_run(self):
        self.go()
        phases = [self.w.tool_phase(c.argv) for c in self.tool_calls()]
        self.assertLess(phases.index("b"), phases.index("pre"))
        kinds = [e["kind"] for e in self.events()]
        self.assertLess(kinds.index("y_id"), [i for i, e in enumerate(self.events()) if e["kind"] == "command" and e["step"] == "http_pre"][0])

    def test_the_optional_name_is_passed_when_given_and_the_tools_lines_are_recorded(self):
        self.w.rules[:0] = [["Optional: the name you remember", "my name"]]
        self.go()
        pre = self.tool_calls("pre")[0].argv
        self.assertEqual(pre[pre.index("--replay-name") + 1], "my name")
        items = [e["item"] for e in self.events() if e["kind"] == "record"]
        self.assertIn("http: read_first", items)
        self.assertIn("http: read_y", items)

    def test_the_clean_tree_rule_applies_before_every_password_step(self):
        self.w.clean = False
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.tool_calls(), [])


class StopRuleTests(SupplementCase):
    def stopped_with(self, phase, result, expect_latch):
        self.w.tool_results[phase] = [result]
        code = self.go()
        latch = self.state()["latch"]
        self.assertEqual(bool(latch), expect_latch, (phase, result.code))
        return code, latch

    def test_every_status_except_0_3_5_and_7_latches(self):
        for code in (1, 2, 4, 6, 127):
            with self.subTest(code):
                self.tearDown_world()
                exit_code, latch = self.stopped_with("pre", g.Result(code, lines_text({"label": "finding", "code": "X"})), True)
                self.assertEqual(exit_code, g.EXIT_STOPPED)
                self.assertEqual(latch["code"], "HTTP_PRE_EXIT_%d" % code)
                self.assertEqual(self.go(), g.EXIT_LATCHED)                  # a plain re-run refuses
                self.assertEqual(len(self.tool_calls("pre")), 1)

    def tearDown_world(self):
        shutil.rmtree(str(self.sup), True)
        self.w = SWorld(self.home)

    def test_a_finding_before_any_create_stops_without_a_latch_and_the_rerun_resumes(self):
        exit_code, latch = self.stopped_with("pre", g.Result(5, lines_text({"label": "finding", "code": "COUNT_UNEXPECTED", "verdict": "BEFORE_ANY_CREATE"})), False)
        self.assertEqual(exit_code, g.EXIT_STOPPED)
        self.assertEqual(self.done(), ["start_1", "http_b"])
        y = self.state()["y"]
        self.assertTrue(y["sent"])
        self.assertEqual(self.go(), g.EXIT_STOPPED)   # the step is not safe to run again blindly (it was started)
        self.assertIn("STEP_INTERRUPTED", "\n".join(self.w.said))
        self.assertEqual(self.go("--resolve", "http_pre", "retry"), g.EXIT_DONE)
        self.assertEqual(self.go(), g.EXIT_DONE)
        runs = self.tool_calls("pre")
        self.assertNotIn("--resume", runs[0].argv)
        self.assertIn("--resume", runs[1].argv)                                          # the saved id is passed again, so the expected 200 is not a latch
        self.assertEqual(runs[0].argv[runs[0].argv.index("--operation-id") + 1], runs[1].argv[runs[1].argv.index("--operation-id") + 1])

    def test_a_usage_refusal_stops_without_a_latch(self):
        exit_code, latch = self.stopped_with("b", g.Result(7, lines_text({"label": "usage", "code": "USAGE"})), False)
        self.assertEqual(exit_code, g.EXIT_STOPPED)

    def test_a_mistyped_password_is_retried_three_times_and_the_fourth_failure_latches(self):
        typo = g.Result(3, lines_text({"label": "retry", "code": "LOGIN_REFUSED", "counts_as_typo": True}))
        self.w.tool_results["b"] = [typo, typo, typo, typo]
        self.w.rules[:0] = [["Retry after a mistyped password", "y"]]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.state()["latch"]["code"], "PASSWORD_RETRIES_EXHAUSTED")
        self.assertEqual(len(self.tool_calls("b")), 4)

    def test_declining_the_retry_pauses_without_a_latch_and_rate_limiting_is_not_counted(self):
        typo = g.Result(3, lines_text({"label": "retry", "code": "LOGIN_REFUSED", "counts_as_typo": True}))
        busy = g.Result(3, lines_text({"label": "retry", "code": "AUTH_RATE_LIMITED", "counts_as_typo": False}))
        self.w.tool_results["b"] = [busy, busy, busy, busy, busy, typo]
        self.w.rules[:0] = [["Retry after a mistyped password", "n"], ["When you have waited", ""]]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIsNone(self.state()["latch"])
        self.assertEqual(len(self.tool_calls("b")), 6)
        self.assertEqual(self.state().get("pw_failures", {}).get("http_b"), 1)         # only the typo counted

    def test_the_acknowledgement_is_asked_per_phase_and_a_no_sends_nothing(self):
        self.w.rules[:0] = [["Do you make that statement", "no"]]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.tool_calls("pre"), [])
        self.assertEqual(self.done(), ["start_1", "http_b"])
        asked = [p for p in self.w.prompts if "Do you make that statement" in p]
        self.assertEqual(len(asked), 1)
        self.assertTrue(any(s.ACK_SENTENCE in line for line in self.w.said))
        self.assertTrue(any("create Y" in line for line in self.w.said))

    def test_phase_post_asks_the_acknowledgement_again(self):
        self.go()
        asked = [p for p in self.w.prompts if "Do you make that statement" in p]
        self.assertEqual(len(asked), 2)

    def test_the_cluster_steps_refuse_without_a_latch(self):
        for name, setup, code in (("stop fails", lambda w: setattr(w, "stop_exit", 1), "CLUSTER_STOP_FAILED"),
                                  ("same pid", lambda w: setattr(w, "same_pid", True), "CLUSTER_NOT_RESTARTED")):
            with self.subTest(name):
                self.tearDown_world()
                setup(self.w)
                self.assertEqual(self.go(), g.EXIT_STOPPED)
                self.assertIsNone(self.state()["latch"])
                self.assertIn(code, "\n".join(self.w.said))

    def test_a_launcher_refusal_after_the_restart_latches(self):
        self.w.launcher_script = [(None, b"ready\n"), (3, b"REFUSED PF_PREFLIGHT_REFUSED\n")]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertTrue(self.state()["latch"]["code"].startswith("LAUNCHER_EXIT"))
        self.assertIn("pg_start", self.done())


class ResumeTests(SupplementCase):
    """TR8S2 H-1, M-1, L-1, L-4, L-5, L-7: every way a step can end early, and what the next run does."""

    def tool_ports(self):
        return self.w.ports_at_tool

    def launcher_spawns(self):
        return [i for i, c in enumerate(self.w.calls) if c.argv and len(c.argv) > 7 and c.argv[:7] == tg.FW and c.argv[7] == "web_api.real_launcher"]

    def assert_rerun_has_a_launcher_before_the_tool(self, mark, phase):
        """After `mark` (an index into the calls) a launcher is spawned before the tool's first call of `phase`, and port 8004 was open when the tool ran."""
        later = [i for i in self.launcher_spawns() if i >= mark]
        tool = [i for i, c in enumerate(self.w.calls) if i >= mark and c.key == "r8_http_check" and self.w.tool_phase(c.argv) == phase]
        self.assertTrue(later and tool, (later, tool))
        self.assertLess(later[0], tool[0])
        self.assertIn(8004, self.w.ports_at_tool[-1])

    TYPO = g.Result(3, lines_text({"label": "retry", "code": "LOGIN_REFUSED", "counts_as_typo": True}))

    def test_a_rerun_that_resumes_at_http_b_starts_the_launcher_first_after_each_way_of_stopping(self):
        def decline():
            self.w.tool_results["b"] = [self.TYPO]
            self.w.rules[:0] = [["Retry after a mistyped password", "n"]]

        def quit_at_retry():
            self.w.tool_results["b"] = [self.TYPO]
            self.w.rules[:0] = [["Retry after a mistyped password", lambda: (_ for _ in ()).throw(EOFError())]]

        def ctrl_c():
            self.w.raise_on["r8_http_check"] = KeyboardInterrupt()
        for name, arrange in (("typo then n", decline), ("quit at the retry question", quit_at_retry), ("Ctrl-C while the tool runs", ctrl_c)):
            with self.subTest(name):
                shutil.rmtree(str(self.sup), True)
                self.w = SWorld(self.home)
                arrange()
                self.assertNotEqual(self.go(), g.EXIT_DONE)
                self.assertEqual(self.done(), ["start_1"])
                self.assertIsNone(self.state()["latch"])
                self.w.rules = [r for r in self.w.rules if r[0] != "Retry after a mistyped password"]
                mark = len(self.w.calls)
                self.assertEqual(self.go(), g.EXIT_DONE, "\n".join(self.w.said[-6:]))
                self.assert_rerun_has_a_launcher_before_the_tool(mark, "b")
                self.assertEqual(len(self.tool_calls("pre")), 1)                  # the run went on to the create exactly once

    def test_every_resumed_password_step_has_a_launcher_after_a_stop_before_it(self):
        """The same for http_pre (finding before any create, then `--resolve retry`) and http_post (acknowledgement declined)."""
        self.w.tool_results["pre"] = [g.Result(5, lines_text({"label": "finding", "code": "COUNT_UNEXPECTED"}))]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.go("--resolve", "http_pre", "retry"), g.EXIT_DONE)
        mark = len(self.w.calls)
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assert_rerun_has_a_launcher_before_the_tool(mark, "pre")
        shutil.rmtree(str(self.sup), True)
        self.w = SWorld(self.home)
        self.w.rules[:0] = [["Do you make that statement", lambda r=iter(["yes", "no", "yes", "yes"]): next(r)]]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.done()[-1], "start_2")
        mark = len(self.w.calls)
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assert_rerun_has_a_launcher_before_the_tool(mark, "post")

    def test_a_declined_acknowledgement_and_a_usage_refusal_rerun_without_resolve_and_are_not_interrupted(self):
        self.w.rules[:0] = [["Do you make that statement", "no"]]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("Run the same command again", "\n".join(self.w.said))
        self.w.rules = [r for r in self.w.rules if r[0] != "Do you make that statement"] + [["Do you make that statement", "yes"]]
        self.w.said.clear()
        self.w.tool_results["b"] = []
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertNotIn("STEP_INTERRUPTED", "\n".join(self.w.said))
        shutil.rmtree(str(self.sup), True)
        self.w = SWorld(self.home)
        self.w.tool_results["b"] = [g.Result(7, lines_text({"label": "usage", "code": "USAGE"}))]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.w.said.clear()
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertNotIn("STEP_INTERRUPTED", "\n".join(self.w.said))

    def test_a_declined_retry_at_a_create_step_and_exit_7_there_rerun_without_resolve_and_without_step_interrupted(self):
        """TR8S3 N-L3: `http_pre` is unsafe, so a stop that sent nothing must clear its `started` mark, or the rerun meets STEP_INTERRUPTED."""
        typo = g.Result(3, lines_text({"label": "retry", "code": "LOGIN_REFUSED", "counts_as_typo": True}))
        usage = g.Result(7, lines_text({"label": "usage", "code": "USAGE"}))
        for name, first, rule in (("declined retry at A's login", typo, ["Retry after a mistyped password", "n"]), ("exit 7", usage, None)):
            with self.subTest(name):
                shutil.rmtree(str(self.sup), True)
                self.w = SWorld(self.home)
                self.w.tool_results["pre"] = [first]
                if rule:
                    self.w.rules[:0] = [rule]
                self.assertEqual(self.go(), g.EXIT_STOPPED)
                self.assertIsNone(self.state()["latch"])
                self.assertNotIn("http_pre", self.state()["started"])
                self.w.rules = [r for r in self.w.rules if r[0] != "Retry after a mistyped password"]
                self.w.said.clear()
                self.assertEqual(self.go(), g.EXIT_DONE, "\n".join(self.w.said[-5:]))
                self.assertNotIn("STEP_INTERRUPTED", "\n".join(self.w.said))
                self.assertEqual(len(self.tool_calls("pre")), 2)

    def test_a_connection_refused_before_any_request_is_a_stop_that_is_not_counted_and_not_latched(self):
        self.w.tool_results["b"] = [g.Result(3, lines_text({"label": "retry", "code": "NO_CONNECT", "counts_as_typo": False}))]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIsNone(self.state()["latch"])
        self.assertIn("LAUNCHER_NOT_ANSWERING", "\n".join(self.w.said))
        self.assertEqual(self.state().get("pw_failures", {}).get("http_b", 0), 0)
        self.assertEqual(self.go(), g.EXIT_DONE)

    def test_b_is_asked_for_the_username_again_on_a_retry_and_the_message_is_accurate(self):
        self.w.tool_results["b"] = [self.TYPO]
        self.w.rules[:0] = [["User B's username again", "bobby"], ["Retry after a mistyped password", "y"]]
        self.assertEqual(self.go(), g.EXIT_DONE)
        first, second = [c.argv[c.argv.index("--user-b") + 1] for c in self.tool_calls("b")]
        self.assertEqual((first, second), ("bob", "bobby"))
        text = "\n".join(self.w.prompts + self.w.said)
        self.assertIn("the user name or the password is wrong", text)
        self.assertEqual(len([p for p in self.w.prompts if "User B's username" in p]), 2)

    def test_pressing_enter_at_the_retry_keeps_the_last_username(self):
        self.w.tool_results["b"] = [self.TYPO]
        self.w.rules[:0] = [["User B's username again", ""], ["Retry after a mistyped password", "y"]]
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual({c.argv[c.argv.index("--user-b") + 1] for c in self.tool_calls("b")}, {"bob"})

    # ---- M-1: the database stop ----------------------------------------------------------------------------------------------------------------
    def test_a_stop_that_exits_non_zero_after_the_database_went_down_is_resumable_and_says_the_state_is_unknown(self):
        real_system = self.w.system

        def stop_fails_but_works(call):
            if "stop" in call.argv:
                self.w.running = False
                return g.Result(1, b"pg_ctl: server does not shut down\n")
            return real_system(call)
        self.w.system = stop_fails_but_works
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIsNone(self.state()["latch"])
        said = "\n".join(self.w.said)
        self.assertIn("CLUSTER_STOP_FAILED", said)
        self.assertIn("UNKNOWN", said)
        self.assertNotIn("is still running", said)
        self.assertEqual(self.state()["pid_before"], 4000)
        self.w.system = real_system
        self.assertEqual(self.go(), g.EXIT_DONE, "\n".join(self.w.said[-6:]))        # the rerun asks status, finds it down, goes on: the socket check is skipped
        after = self.state()
        self.assertEqual([e["value"] for e in self.events() if e["kind"] == "record" and e["item"].startswith("cluster postmaster PID after")][0]["after"], 4001)
        self.assertTrue(after["done"]["pg_stop"])

    def test_a_stop_cut_short_and_a_cluster_still_up_are_both_resumable(self):
        self.w.stop_exit = 1                                  # the cluster stays up: pg_ctl failed and did nothing
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.w.stop_exit = 0
        self.assertEqual(self.go(), g.EXIT_DONE, "\n".join(self.w.said[-6:]))

    def test_the_database_is_not_stopped_while_the_launcher_or_vite_port_is_open(self):
        for port in (8004, 5175):
            with self.subTest(port):
                shutil.rmtree(str(self.sup), True)
                self.w = SWorld(self.home)
                self.w.stop_exit = 0
                original = s.Supplement.s_stop_services

                def leave_open(guide, port=port, w=self.w):
                    out = original(guide)
                    w.open_ports.add(port)
                    return out
                s.Supplement.s_stop_services = leave_open
                try:
                    self.assertEqual(self.go(), g.EXIT_STOPPED)
                finally:
                    s.Supplement.s_stop_services = original
                self.assertIn("SERVICES_RUNNING", "\n".join(self.w.said))
                self.assertFalse([c for c in self.w.calls if c.key == "sudo:pg_ctl" and "stop" in c.argv])

    # ---- L-4, L-7 ------------------------------------------------------------------------------------------------------------------------------
    def test_resolve_http_pre_done_is_refused_and_http_post_without_digests_stops_cleanly(self):
        self.w.tool_results["pre"] = [g.Result(5, lines_text({"label": "finding", "code": "COUNT_UNEXPECTED"}))]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.go("--resolve", "http_pre", "done"), g.EXIT_STOPPED)
        self.assertIn("is not allowed", "\n".join(self.w.said))
        self.assertNotIn("http_pre", self.state()["done"])
        # a state that nevertheless reaches http_post without digests stops with a message and no traceback, and no latch
        shutil.rmtree(str(self.sup), True)
        self.w = SWorld(self.home)
        self.assertEqual(self.go(), g.EXIT_DONE)
        state = self.state()
        for key in ("http_post", "screen", "reeval_101", "close"):
            state["done"].pop(key)
        state["digests"] = {}
        state["started"] = {}
        (self.sup / "state.json").write_text(json.dumps(state))
        (self.sup / "SUPPLEMENT_RECORD.md").unlink()
        self.w.said.clear()
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("HTTP_PRE_DIGESTS_MISSING", "\n".join(self.w.said))
        self.assertIsNone(self.state()["latch"])

    def test_the_record_has_a_filled_run_section_and_pg_starts_commands_sit_under_their_own_step(self):
        self.assertEqual(self.go(), g.EXIT_DONE)
        text = (self.sup / "SUPPLEMENT_RECORD.md").read_text()
        run = text.split("## Run\n\n", 1)[1].split("\n## ", 1)[0]
        self.assertIn("reviewed commit S8", run)
        self.assertIn("frozen values (copied from R8)", run)
        by_step = {}
        for e in self.events():
            if e["kind"] == "command":
                by_step.setdefault(e["step"], []).append(e)
        starts = [e for e in by_step["pg_start"] if "start" in json.dumps(e)]
        self.assertTrue(starts)
        self.assertFalse(any("-l" in json.dumps(e) and "start" in json.dumps(e) for e in by_step.get("pg_stop", [])))

    def test_phase_b_checks_for_roots_of_the_other_user_in_the_tool_not_the_runner(self):
        """The runner only passes the first root's ids; the list check itself is the tool's (`test_r8_http_check`)."""
        self.go()
        argv = self.tool_calls("b")[0].argv
        self.assertEqual((argv[argv.index("--root") + 1], argv[argv.index("--root-operation") + 1]), (s.FIRST_ROOT, s.FIRST_OPERATION))


class PreconditionTests(SupplementCase):
    def test_r8_must_be_finished_unlatched_closed_at_the_context_and_generation_3(self):
        cases = {"unfinished": dict(done={"publish": {"data": {"context": CTX}}, "renew": {"data": {"generation": 3}}}),
                 "latched": dict(latch={"code": "X"}), "window open": dict(window={"n": 2, "open": True}),
                 "wrong context": dict(done={"publish": {"data": {"context": "e" * 64}}, "renew": {"data": {"generation": 3}}, "close": {}}),
                 "wrong generation": dict(done={"publish": {"data": {"context": CTX}}, "renew": {"data": {"generation": 2}}, "close": {}})}
        for name, changes in cases.items():
            with self.subTest(name):
                shutil.rmtree(str(self.sup), True)
                self.w = SWorld(self.home)
                self.write_r8(**changes)
                self.assertEqual(self.go(), g.EXIT_STOPPED)
                self.assertFalse((self.sup / "state.json").exists())
                self.assertEqual(self.tool_calls(), [])

    def test_c2_json_must_carry_exactly_the_context_at_generation_3(self):
        (self.r8 / "C2.json").write_text(json.dumps({"contexts": [{"context_id": CTX, "generation": 2}]}))
        self.assertEqual(self.go(), g.EXIT_STOPPED)

    def test_a_missing_r8_folder_and_a_stopped_cluster_refuse(self):
        shutil.rmtree(str(self.r8))
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.write_r8()
        self.w.running = False
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("CLUSTER_NOT_RUNNING", "\n".join(self.w.said))

    def test_a_moved_head_beyond_decision_records_is_refused_like_in_r8(self):
        self.go()
        shutil.rmtree(str(self.sup))
        self.w = SWorld(self.home)
        self.assertEqual(self.go(), g.EXIT_DONE)                       # a fresh S8 on the same commit
        self.w.changed = ["src/x.py"]
        self.w.head = "b" * 40
        state = self.state()
        self.assertEqual(state["p8"]["commit"], tg.HEAD0)
        (self.sup / "state.json").write_text(json.dumps(dict(state, done={"start_1": {}}, latch=None)))
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("HEAD_MOVED", "\n".join(self.w.said))


class ReevaluationTests(SupplementCase):
    def attempts(self, attempts):
        events = [{"kind": "record", "item": "probe ids", "value": {"username": "alice"}, "at": "x"},
                  {"kind": "record", "item": "check 10.1 NAV against the Quant's figure", "value": {"result": "FAIL", "attempts": attempts}, "at": "x"}]
        (self.r8 / "events.log").write_text("\n".join(json.dumps(e) for e in events) + "\n")

    def run_reeval(self):
        self.go()
        return [e for e in self.events() if e["kind"] == "record" and "RE-EVALUATION" in e["item"]]

    def test_it_uses_the_last_attempt_is_labelled_and_never_rewrites_r8s_record(self):
        good = {"typed": {"holding": "1234.5", "missed_sessions": "0", "nav": "1734.5", "state": "AVAILABLE"}}
        bad = {"typed": {"holding": "1234.5", "missed_sessions": "0", "nav": "1734.6", "state": "AVAILABLE"}}
        for attempts, expected in (([bad, good], "PASS"), ([good, bad], "FAIL")):
            with self.subTest(expected):
                shutil.rmtree(str(self.sup), True)
                self.w = SWorld(self.home)
                self.attempts(attempts)
                before = self.r8_snapshot()
                (record,) = self.run_reeval()
                self.assertEqual(record["value"]["result"], expected)
                self.assertIn("not a new observation", record["item"])
                self.assertIn("unchanged", record["item"])
                self.assertEqual(self.r8_snapshot(), before)

    def test_the_corrected_comparator_ignores_the_close(self):
        self.assertEqual(g.compare_nav("1,234.50", "1734.5", "0", "available"), {"holding": True, "nav": True, "missed_sessions": True, "state": True})
        self.assertNotIn("close", dict(g.QUANT_NUMBERS))
        self.assertEqual(g.compare_nav("1234.5", "1734.6", "1", "LIMITED"), {"holding": True, "nav": False, "missed_sessions": False, "state": False})

    def test_a_missing_r8_check_record_refuses(self):
        (self.r8 / "events.log").write_text(json.dumps({"kind": "record", "item": "probe ids", "value": {"username": "alice"}, "at": "x"}) + "\n")
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("R8_CHECK_MISSING", "\n".join(self.w.said))

    def test_the_optional_fresh_observation_is_labelled_and_uses_the_corrected_check(self):
        self.w.rules[:0] = [["Optional, one minute", "yes"], ["Type the holding value", "1234.5"], ["Type the NAV", "1734.5"], ["Type the missed sessions", "0"], ["Type the state", "AVAILABLE"]]
        self.go()
        fresh = [e for e in self.events() if e["kind"] == "record" and "FRESH observation" in e["item"]]
        self.assertEqual(len(fresh), 1)
        self.assertEqual(fresh[0]["value"]["result"], "PASS")


class GuideRefactorTests(unittest.TestCase):
    def test_the_r8_runner_keeps_its_folder_and_schema_and_the_supplement_has_its_own(self):
        self.assertEqual((g.Guide.DIR_NAME, g.Guide.SCHEMA), ("finweb-r8", g.STATE_SCHEMA))
        self.assertEqual((s.Supplement.DIR_NAME, s.Supplement.SCHEMA), ("finweb-r8-supplement", s.STATE_SCHEMA))
        self.assertNotEqual(s.STATE_SCHEMA, g.STATE_SCHEMA)

    def test_the_supplement_reads_r8s_inputs_from_r8s_folder_only(self):
        guide = s.Supplement(tg.World(Path("/nonexistent")).seams(), Path("/h"), REPO)
        self.assertEqual(guide.path("C2.json"), "/h/finweb-r8/C2.json")
        self.assertEqual(guide.path("transcript.log"), "/h/finweb-r8-supplement/transcript.log")

    def test_the_tool_lines_parser_keeps_only_s8_json_lines(self):
        text = "noise\nS8 {\"label\": \"a\", \"status\": 1}\nS8 not json\nS8 [1]\nS8 {\"x\": 1}\n"
        self.assertEqual(s.tool_lines(text), [{"label": "a", "status": 1}])

    def test_the_status_mode_shows_progress_and_the_parser_has_no_other_options(self):
        parser = s._build_parser()
        options = {o for a in parser._actions for o in a.option_strings} - {"-h", "--help"}
        self.assertEqual(options, {"--status", "--reset-stop", "--resolve"})


if __name__ == "__main__":
    unittest.main()
