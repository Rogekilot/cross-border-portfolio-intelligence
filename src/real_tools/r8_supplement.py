"""F1 R8: the SUPPLEMENTARY-RUN RUNNER (`implementation/CP7_F1_R8_SUPPLEMENT_PLAN.md`, revision 2; `implementation/CP7_F1_R8_GUIDED_RUNNER.md`, section "The supplementary-run
runner"; PD-0087, PD-0088).

    PYTHONPATH=src uv run --no-sync --frozen --offline python -m real_tools.r8_supplement          (from the repository root; run it again to resume)

WHAT IT IS. A `Guide` subclass: the same seams, state file, append-only events log, stop latch (`--reset-stop`), `--resolve`, `--status`, clean-tree and
moved-HEAD rules, 3-retry rule for mistyped passwords, and launcher and Vite handling as the R8 runner, with its own step table and its own folder,
`~/finweb-r8-supplement/` (0700; `state.json`, `events.log`, `transcript.log`, `SUPPLEMENT_RECORD.md`). It reads `~/finweb-r8/` (the state, `events.log`, `P.json`,
`F.json`, `C2.json`) and never writes there. Its base commit is "S8", the HEAD at its first run.

WHAT IT DOES NOT DO. It opens no connection, asks for no password and has no credential route: sudo and the launcher ask at their own prompts, and the web
account password is asked by the loopback tool at its prompt. It starts the tool `real_tools.r8_http_check` ONLY as a child process (`fw(...)`) and never imports it,
so no password is ever in this process, which writes the state and the log. Everything the tool prints is an `S8 {json}` line of safe fields; the runner records them.

NOT A NEW INSTALL, PUBLISH OR LOADER WINDOW. The only writes to the real context are the create-route requests the tool sends (one new create, Y, its replays and
the expected refusals); a stop and a start of the PostgreSQL postmaster (sudo, as the cluster user) is the restart.

STOP RULES ARE CODE (plan section 4). Rule 0.3 for every create-route request: the tool holds one expected (status, code) per request and exits 2 or 4 on anything else; the
runner LATCHES on every tool exit status except 0 (done), 3 (a login typo or a refused connection: the retry gate, at most 3, or a rate limit: wait), 5 (a finding before any
create: a record and a stop, no latch) and 7 (an unusable command line: nothing sent).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path

from real_tools import r8_guide as base
from real_tools.r8_guide import (EXIT_DONE, EXIT_LATCHED, EXIT_PAUSED, EXIT_STOPPED, EXPECTED_LISTING_ID, Guide, Quit, StepDef, Stop, compare_nav, fw, real_seams)

TOOL = "real_tools.r8_http_check"
STATE_SCHEMA = "finweb.r8_supplement_state/1"
RECORD_NAME = "SUPPLEMENT_RECORD.md"
R8_DIR_NAME = "finweb-r8"
R8_INPUTS = ("P.json", "F.json", "C2.json")           # read from R8's folder, never written
CONTEXT_ID = "c6b6f499fb1b6dd35278e15bf12b096d75cd17d7e75c05489806edcda20402ee"
GENERATION = 3
FIRST_ROOT = "a51651b9-26b9-520e-a0db-46f912743153"
FIRST_OPERATION = "a454d861-dc6f-438b-ac77-d48162835ebc"
ACK_SENTENCE = "I understand the ledger is constructed by the project for testing and is not my holding."
SCREEN_ITEMS = ("the list shows A's roots and Open from the list shows the stored result (DR-R8-1)", "reproduce shows REPRODUCED", "the sign-up password-length hint (DR-R8-3)",
                "sign-out clears the typed values (DR-R8-4)")
_PID = re.compile(r"PID: (\d+)")
_USERNAME = re.compile(r"[A-Za-z0-9._@-]{1,64}\Z")


def tool_lines(text):
    """The `S8 {json}` lines of a tool's output (safe fields only), in order."""
    out = []
    for line in text.splitlines():
        if line.startswith("S8 "):
            try:
                value = json.loads(line[3:])
            except ValueError:
                continue
            if isinstance(value, dict) and isinstance(value.get("label"), str):
                out.append(value)
    return out


def name_problem(answer):
    if answer == "":
        return None
    if not 1 <= len(answer) <= 80 or answer != answer.strip() or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in answer):
        return "1 to 80 characters, no control characters (or Enter to skip)"
    return None


class Supplement(Guide):
    DIR_NAME = "finweb-r8-supplement"
    SCHEMA = STATE_SCHEMA

    def __init__(self, seams, home, repo_root, *, overrides=None):
        super().__init__(seams, home, repo_root, overrides=overrides)
        self.r8_dir = Path(home) / R8_DIR_NAME

    # ---- what it reads of R8 (read-only) --------------------------------------------------------------------------------------------------------
    def path(self, name):
        return str(self.r8_dir / name) if name in R8_INPUTS else super().path(name)

    def new_id(self):
        return str(uuid.uuid4())

    def r8_events(self):
        path = self.r8_dir / base.EVENTS_NAME
        if not path.exists():
            raise Stop("R8_STATE_MISSING", "%s does not exist: the supplementary run needs R8's folder" % path)
        return [json.loads(line) for line in path.read_text("utf8").splitlines() if line.strip()]

    def read_r8(self):
        """R8's state, checked: finished, no stop, no open window, the published context and generation 3. Refuses (no latch) otherwise."""
        path = self.r8_dir / base.STATE_NAME
        if not path.exists():
            raise Stop("R8_STATE_MISSING", "%s does not exist: the supplementary run needs R8's folder" % path)
        r8 = json.loads(path.read_text("utf8"))
        problems = []
        if r8.get("schema") != base.STATE_SCHEMA:
            problems.append("not an R8 state document")
        if "close" not in r8.get("done", {}):
            problems.append("R8 is not finished (close is not done)")
        if r8.get("latch"):
            problems.append("R8 is stopped (a latch is set)")
        if (r8.get("window") or {}).get("open"):
            problems.append("a loader window is marked open")
        done = r8.get("done", {})
        if ((done.get("publish") or {}).get("data") or {}).get("context") != CONTEXT_ID:
            problems.append("the published context is not %s" % CONTEXT_ID)
        if ((done.get("renew") or {}).get("data") or {}).get("generation") != GENERATION:
            problems.append("the renewed generation is not %d" % GENERATION)
        try:
            contexts = json.loads(Path(self.path("C2.json")).read_text("utf8"))["contexts"]
            if [(c["context_id"], c["generation"]) for c in contexts] != [(CONTEXT_ID, GENERATION)]:
                problems.append("C2.json does not carry exactly the context at generation %d" % GENERATION)
        except (OSError, ValueError, KeyError, TypeError):
            problems.append("C2.json is not readable")
        if problems:
            raise Stop("R8_PRECONDITION", "R8's folder does not meet the supplementary run's preconditions: " + "; ".join(problems))
        return r8

    def r8_username(self):
        found = [e for e in self.r8_events() if e.get("kind") == "record" and e.get("item") == "probe ids"]
        name = ((found[-1].get("value") or {}).get("username") if found else None)
        if not isinstance(name, str) or not _USERNAME.fullmatch(name):
            raise Stop("R8_PRECONDITION", "user A's username is not in R8's record (item 'probe ids')")
        return name

    @property
    def context(self):
        return self.st["r8"]["context"]

    def preconditions(self):
        super().preconditions()
        r8 = self.read_r8()
        done = self.st["done"] if self.st is not None else {}
        # The socket is required only while the cluster should be running. Once the restart has begun (`pid_before` recorded) a stop that was cut short, or that exited
        # non-zero after the postmaster went down, must be resumable: `pg_stop` asks `pg_ctl status` and continues from what it finds (TR8S2 M-1).
        begun = self.st is not None and self.st.get("pid_before") is not None
        stopped = begun and "pg_start" not in done
        sock = "%s/sock/.s.PGSQL.%d" % (r8["frozen"]["base"], r8["frozen"]["port"])
        if not stopped and not self.s.exists(sock):
            raise Stop("CLUSTER_NOT_RUNNING", "the cluster's socket %s does not exist: the supplementary run uses the cluster R8 left running" % sock)

    def first_run(self):
        r8 = self.read_r8()
        head = self.git("rev-parse", "HEAD")
        subject = self.git("log", "-1", "--format=%s")
        self.say("First run of the supplementary run. It uses R8's cluster, database and context (generation %d) and installs, publishes and loads nothing." % GENERATION)
        self.say("This commit becomes S8, the reviewed commit you run from: %s  %s" % (head.text.strip(), subject.text.strip()))
        self.confirm_word("Record this commit as S8?", "freeze")
        self.st = {"schema": self.SCHEMA, "frozen": dict(r8["frozen"]), "p8": {"commit": self.head(), "at": self.stamp(), "subject": subject.text.strip()},
                   "done": {}, "started": {}, "records": [], "commands": [], "creates": [], "create_pending": None, "window": {"n": 0, "open": False}, "latch": None,
                   "latch_history": [], "p8_history": [], "r8": {"context": CONTEXT_ID, "generation": GENERATION, "username": self.r8_username()}, "y": None, "digests": {}}
        self.record("S8 (the reviewed commit)", self.st["p8"]["commit"])
        self.record("frozen values (copied from R8)", self.st["frozen"])

    # ---- the tool, as a child process ------------------------------------------------------------------------------------------------------------
    def no_effect(self, step):
        """The step sent nothing that can write, so a later run may simply run it again (without it, `STEP_INTERRUPTED` would ask for `--resolve`)."""
        self.st["started"].pop(step, None)
        self.save()

    def run_tool(self, step, argv):
        """Run the loopback tool and record every `S8` line it prints. Returns the lines on exit 0; raises `Stop` for every other status (plan section 4).
        `argv` is a list, or a function of `retry` (False, then True after a retry) that returns it, so that a retry can ask for a corrected user name."""
        make = argv if callable(argv) else (lambda retry=False: argv)
        retry_now = False
        while True:
            result = self.exec(step, make(retry_now))
            lines = tool_lines(result.text)
            for line in lines:
                self.record("http: %s" % line["label"], line, step=step)
            code = result.code
            if code == 0:
                return lines
            tail = "\n".join(json.dumps(line, sort_keys=True) for line in lines[-6:])
            if code == 3:
                retry = next((line for line in reversed(lines) if line["label"] == "retry"), {})
                kind = str(retry.get("code") or "RETRY")
                if kind == "NO_CONNECT":
                    self.no_effect(step)
                    raise Stop("LAUNCHER_NOT_ANSWERING", "the tool could not connect to the launcher on 127.0.0.1:8004; nothing was sent. The runner starts the launcher "
                               "before every HTTP step, so look at its output above. Run again; this is not a mistyped password and is not counted.", step=step)
                if retry.get("counts_as_typo") is False:
                    self.say("The sign-in is rate limited. Nothing is counted; wait a few minutes.")
                    self.enter("When you have waited:")
                else:
                    label = "the sign-in was refused: the user name or the password is wrong" if kind == "LOGIN_REFUSED" else None
                    try:
                        self.retry_gate(step, label, None if label else kind)
                    except Stop as stop:
                        if stop.code == "PASSWORD_NOT_RETRIED":
                            self.no_effect(step)                       # nothing was sent: the rerun starts the step again
                        raise
                retry_now = True
                continue
            if code == 5:
                raise Stop("%s_FINDING" % step.upper(), "the tool found something BEFORE any create was sent; nothing was created. Record it and tell the main session; nothing is "
                           "retried.\n%s" % tail, step=step)
            if code == 7:
                self.no_effect(step)
                raise Stop("%s_USAGE" % step.upper(), "the tool refused its command line or its prompt route; nothing was sent.\n%s" % tail, step=step)
            raise Stop("%s_EXIT_%d" % (step.upper(), code), "the tool exited %d (rule 0.3 and plan section 4: an unexpected answer or an unknown outcome after a create-route request, "
                       "or an uncaught error). Nothing is re-run until the cause is found and a reviewed fix is committed.\n%s" % (code, tail), latch=True, step=step)

    def tool_argv(self, phase, *pairs, resume=False):
        argv = fw(TOOL, "--phase", phase)
        for key, value in pairs:
            argv += [key, str(value)]
        return argv + (["--resume"] if resume else [])

    def common_pairs(self):
        v = self.form_values()
        if v["listing_id"] != EXPECTED_LISTING_ID:
            raise Stop("LISTING_ID_DIFFERS", "listings[0][0] of F.json is %s, not the expected %s" % (v["listing_id"], EXPECTED_LISTING_ID))
        if v["context_id"] != self.context:
            raise Stop("CONTEXT_ID_DIFFERS", "context_id of P.json is not the published context")
        return (("--root", FIRST_ROOT), ("--root-operation", FIRST_OPERATION), ("--context", v["context_id"]), ("--release", v["release_id"]), ("--listing", v["listing_id"]))

    def acknowledge(self, step, requests):
        self.say("This phase sends the create-route requests below. Each body carries `constructed_ledger_acknowledged: true`, which is YOUR statement:")
        for item in requests:
            self.say("  - " + item)
        self.say("  \"%s\"" % ACK_SENTENCE)
        answer = self.typed("Do you make that statement for all of them? (yes / no):", check=lambda a: None if a in ("yes", "no") else "yes or no")
        if answer != "yes":
            self.no_effect(step)                      # nothing was sent: the rerun starts the step again without `--resolve`
            raise Stop("ACK_NOT_GIVEN", "the acknowledgement was not given; nothing was sent. Run the same command again when ready.")

    # ---- the steps -------------------------------------------------------------------------------------------------------------------------------
    def s_http_b(self):
        known = []

        def argv(retry=False):
            """User B's name is asked again on every retry (a wrong name and a wrong password give the same refusal): Enter keeps the last one."""
            ok = lambda a: None if _USERNAME.fullmatch(a) or (retry and a == "") else "letters, digits and . _ @ - only"      # noqa: E731
            question = "User B's username again (Enter to keep %s):" % known[-1] if retry else "User B's username (the existing account; its password is asked by the tool):"
            typed = self.typed(question, check=ok)
            known.append(typed or known[-1])
            return self.tool_argv("b", ("--user-b", known[-1]), ("--root", FIRST_ROOT), ("--root-operation", FIRST_OPERATION))
        self.say("The tool signs in as B (the password prompt is the tool's) and only reads: it sends no create-route request.")
        lines = self.run_tool("http_b", argv)
        return {"lines": len(lines)}

    def s_http_pre(self):
        pairs = self.common_pairs()
        if self.st.get("y") is None:
            self.st["y"] = {"operation_id": self.new_id(), "sent": False}
            self.event("y_id", operation_id=self.st["y"]["operation_id"])
            self.save()
        y = self.st["y"]
        self.acknowledge("http_pre", ["create Y (a new real create, rule 0.3; name 'R8 supplement', as-of 2026-09-30, quantity 10, cash 500)", "its replay (the identical command)",
                          "a conflicting reuse of Y's operation id (another name and quantity)", "a create with quantity 0 and a create naming a context the launcher does not serve",
                          "optionally, one attempt at R8's own operation id with the name you remember"])
        name = self.typed("Optional: the name you remember typing for R8's first create (Enter to skip; one attempt, a conflict writes nothing):", check=name_problem)
        argv = self.tool_argv("pre", ("--user-a", self.st["r8"]["username"]), *pairs, ("--operation-id", y["operation_id"]), ("--acknowledged", "yes"),
                              *((("--replay-name", name),) if name else ()), resume=bool(y["sent"]))
        y["sent"] = True              # BEFORE the run: from here a rerun passes --resume, so an expected 200 is never a latch
        self.save()
        lines = self.run_tool("http_pre", argv)
        digests = {}
        for line in lines:
            if line["label"] in ("read_first", "read_y") and line.get("response_sha256"):
                digests["first" if line["label"] == "read_first" else "y"] = {"response": line["response_sha256"], "issued": line["issued_sha256"]}
        if set(digests) != {"first", "y"}:
            raise Stop("HTTP_PRE_DIGESTS", "the tool finished without reporting both stored digests; tell the main session", latch=True, step="http_pre")
        self.st["digests"] = digests
        self.save()
        return {"digests": digests}

    def s_http_post(self):
        pairs = self.common_pairs()
        d = self.st["digests"]
        if not d.get("first") or not d.get("y"):
            raise Stop("HTTP_PRE_DIGESTS_MISSING", "the digests of the first root and of Y, which the tool reported in http_pre, are not in the state (was `--resolve http_pre done` used?). "
                       "Without them the post-restart comparison cannot be made. Tell the main session.")
        self.acknowledge("http_post", ["the replay of Y (the identical command)", "a conflicting reuse of Y's operation id"])
        argv = self.tool_argv("post", ("--user-a", self.st["r8"]["username"]), *pairs, ("--operation-id", self.st["y"]["operation_id"]), ("--acknowledged", "yes"),
                              ("--first-response-sha", d["first"]["response"]), ("--first-issued-sha", d["first"]["issued"]),
                              ("--y-response-sha", d["y"]["response"]), ("--y-issued-sha", d["y"]["issued"]))
        return {"lines": len(self.run_tool("http_post", argv))}

    def pid_of(self, step, result):
        found = _PID.search(result.text)
        return int(found.group(1)) if found else None

    def s_pg_stop(self):
        pg_ctl, data = self.st["frozen"]["pg_ctl"], self.d("data")
        for port in (base.LAUNCHER_PORT, base.VITE_PORT):
            if self.s.port_open(port):
                raise Stop("SERVICES_RUNNING", "port %d is open: a launcher or Vite is still running (started by hand?). Stop it, then run again; the database is not stopped while the "
                           "launcher holds connections." % port)
        before = self.sudo_as("pg_stop", pg_ctl, "-D", data, "status")
        if before.code == 0:
            pid = self.pid_of("pg_stop", before)
            if pid is None:
                raise Stop("CLUSTER_PID_UNREADABLE", "pg_ctl status did not print the postmaster's PID; nothing was stopped")
            self.st["pid_before"] = pid
            self.save()
            self.record("cluster postmaster PID before the stop", pid)
            stop = self.sudo_as("pg_stop", pg_ctl, "-D", data, "stop", "-m", "fast", "--wait")
            if stop.code != 0:
                raise Stop("CLUSTER_STOP_FAILED", "pg_ctl stop exited %d. The cluster's state is UNKNOWN: it may still be shutting down or may already be down. Run the same command "
                           "again: the runner asks `pg_ctl status` first and continues from what it finds. Read %s/server.log as the cluster user." % (stop.code, self.d("log")))
        elif self.st.get("pid_before") is None:
            raise Stop("CLUSTER_NOT_RUNNING", "pg_ctl status says the cluster is not running (exit %d), and no earlier stop was recorded" % before.code)
        after = self.sudo_as("pg_stop", pg_ctl, "-D", data, "status")
        if after.code != 3:
            raise Stop("CLUSTER_STILL_RUNNING", "pg_ctl status still says the cluster runs (exit %d)" % after.code)
        for _ in range(30):
            if not self.s.exists(self.sock):
                self.record("cluster stopped", {"status_exit": after.code, "socket_gone": True})
                return {"stopped": True}
            self.s.sleep(1)
        raise Stop("CLUSTER_SOCKET_PRESENT", "the socket %s is still there after the stop" % self.sock)

    def s_pg_start(self):
        pg_ctl, data = self.st["frozen"]["pg_ctl"], self.d("data")
        started = False
        if self.sudo_as("pg_start", pg_ctl, "-D", data, "status").code != 0:                 # the R8 runner's own start command, under this step's own name
            result = self.sudo_as("pg_start", pg_ctl, "-D", data, "-l", self.d("log") + "/server.log", "start")
            if result.code != 0:
                raise Stop("CLUSTER_START_FAILED", "pg_ctl start failed (exit %d). Read %s/server.log as the cluster user. If it says 'postmaster became multithreaded' (seen on the "
                           "development cluster, STATUS.md 2026-10-22), tell the main session. The database is down: run again to retry the start." % (result.code, self.d("log")))
            started = True
        for _ in range(30):
            if self.s.exists(self.sock):
                break
            self.s.sleep(1)
        else:
            raise Stop("CLUSTER_SOCKET", "the socket %s did not appear" % self.sock)
        status = self.sudo_as("pg_start", pg_ctl, "-D", data, "status")
        after, before = self.pid_of("pg_start", status), self.st.get("pid_before")
        if status.code != 0 or after is None or before is None or after == before:
            raise Stop("CLUSTER_NOT_RESTARTED", "the postmaster's PID after the start (%s, status exit %d) is not a new one (before: %s)" % (after, status.code, before))
        self.record("cluster postmaster PID after the start", {"before": before, "after": after, "differs": True})
        return {"started": started, "pid_before": before, "pid_after": after}

    def s_screen(self):
        self.say("In the browser, at %s, signed in as user A (the screen fixes are in this commit):" % base.SCREEN_URL)
        out = self.s_check_simple("screen", "the screen after the restart and the DR-R8 fixes", SCREEN_ITEMS)
        again = self.typed("Optional, one minute: read R8's first root on the screen once more and type its figures? (yes / skip):", check=lambda a: None if a in ("yes", "skip") else "yes or skip")
        if again == "yes":
            typed = {name: self.typed("Type the %s the screen shows:" % label, check=lambda a: None if a else "type a value") for name, label in
                     (("holding", "holding value"), ("nav", "NAV (USD)"), ("missed_sessions", "missed sessions"), ("state", "state"))}
            result = compare_nav(typed["holding"], typed["nav"], typed["missed_sessions"], typed["state"])
            self.record("check 10.1 as corrected, a FRESH observation after the restart (holding, NAV, missed sessions, state)", {"typed": typed, "equal": result,
                                                                                                                             "result": "PASS" if all(result.values()) else "FAIL"})
        return out

    def s_reeval_101(self):
        found = [e for e in self.r8_events() if e.get("kind") == "record" and str(e.get("item", "")).startswith("check 10.1")]
        if not found:
            raise Stop("R8_CHECK_MISSING", "R8's events log has no check 10.1 record")
        attempts = (found[-1].get("value") or {}).get("attempts") or []
        if not attempts:
            raise Stop("R8_CHECK_MISSING", "R8's check 10.1 record has no typed attempt")
        typed = attempts[-1]["typed"]                       # the attempt R8's own verdict used
        result = compare_nav(typed["holding"], typed["nav"], typed["missed_sessions"], typed["state"])
        verdict = "PASS" if all(result.values()) else "FAIL"
        self.say("Re-evaluation of R8's last typed values under the corrected check 10.1 (holding, NAV, missed sessions, state): %s. This is not a new observation; R8's recorded "
                 "FAIL and R8_RECORD.md are unchanged." % verdict)
        self.record("check 10.1 RE-EVALUATION of R8's typed values (attempts[-1]) under the corrected check; not a new observation; R8's recorded result and R8_RECORD.md are unchanged",
                    {"result": verdict, "equal": result, "typed": typed})
        return {"result": verdict}

    def s_close(self):
        self.stop_services(strict=False)
        surprised = self.typed("Anything that surprised you? (free text, no passwords; Enter for none):")
        self.st["surprises"] = surprised
        self.record("surprises", surprised)
        path = self.dir / RECORD_NAME
        if path.exists():
            raise Stop("RECORD_EXISTS", "%s already exists and is never overwritten" % path)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, self.record_text().encode())
        finally:
            os.close(fd)
        self.say("Wrote %s (mode 0600). It holds no password." % path)
        return {"record": str(path)}

    def resolve(self, sid, action):
        """`--resolve STEP retry|done`. `done` is refused for `http_pre`: its data (the digests the tool reported) is what `http_post` compares with after the restart, and only the
        tool's own finished run produces it (TR8S2 L-4)."""
        if sid == "http_pre" and action == "done":
            self.say("REFUSED: `--resolve http_pre done` is not allowed. The step's digests are needed after the restart and exist only if the tool finished. If the tool finished but "
                     "the runner was interrupted, use `--resolve http_pre retry`: the rerun resumes with the saved Y id and reports them again (Y is replayed, nothing new is created). "
                     "Tell the main session if that is not what happened.")
            return EXIT_STOPPED
        return super().resolve(sid, action)

    def record_text(self):
        text = super().record_text()
        text = text.replace("# R8 record (written by the guided runner)", "# R8 supplementary-run record (written by r8_supplement)", 1)
        run = []
        for e in self.read_events():
            if e["kind"] == "record" and e["item"] == "S8 (the reviewed commit)":
                run.append("- reviewed commit S8: `%s` (recorded %s)" % (e["value"], e["at"]))
            elif e["kind"] == "record" and e["item"].startswith("frozen values"):
                run.append("- frozen values (copied from R8): `%s`" % json.dumps(e["value"], sort_keys=True))
        return text.replace("## Run\n\n", "## Run\n\n" + "\n".join(run) + "\n", 1)

    def _steps(self):
        t = []

        def add(sid, fn, title, what, **kw):
            t.append((StepDef(sid, title, what, **kw), fn))
        add("start_1", lambda: {}, "Launcher and screen, before the restart", "Starts the launcher on R8's C2.json (two password prompts) and Vite.", services="C2.json")
        add("http_b", self.s_http_b, "User B's refusals (read-only, before any create)", "The tool signs in as B and reads A's root by its id, reproduces it, reads an unknown id and a malformed "
            "id; each must be the one 404 with identical bytes.", gated=True, password=True, services="C2.json")
        add("http_pre", self.s_http_pre, "User A: create Y, replay, conflict, error digests", "The tool signs in as A, checks A has 2 roots, creates Y, replays it, sends the conflict and "
            "the two refused requests, and compares everything. Rule 0.3 applies to every create-route request.", gated=True, password=True, safe=False, services="C2.json")
        add("stop_1", self.s_stop_services, "Stop the launcher and Vite", "Before the database is stopped.")
        add("pg_stop", self.s_pg_stop, "Stop the PostgreSQL cluster", "`sudo -u <cluster user> pg_ctl stop -m fast --wait`, with the PID before and after and the socket gone.", gated=True, password=True)
        add("pg_start", self.s_pg_start, "Start the PostgreSQL cluster", "The R8 runner's own start command, then a new PID is required.", gated=True, password=True)
        add("start_2", lambda: {}, "Launcher and screen, after the restart", "Two password prompts; the REAL preflight runs again.", services="C2.json")
        add("http_post", self.s_http_post, "User A after the restart: read, reproduce, replay, conflict", "The first root and Y must read with the digests recorded before the restart.",
            gated=True, password=True, services="C2.json")
        add("screen", self.s_screen, "The screen after the restart", "You look at the screen: Open from the list, reproduce, the sign-up hint, sign-out.", services="C2.json")
        add("reeval_101", self.s_reeval_101, "Check 10.1 re-evaluated", "No typing: R8's last typed figures against the corrected check.")
        add("close", self.s_close, "Close and write the record", "Writes ~/finweb-r8-supplement/SUPPLEMENT_RECORD.md.")
        return t


def _build_parser():
    parser = argparse.ArgumentParser(prog="r8_supplement", description="Runner for the R8 supplementary run. Run it from the repository root; run it again to resume.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="show progress; does nothing else")
    mode.add_argument("--reset-stop", metavar="PD-NNNN", help="lift a stop after a reviewed fix and the owner's decision record are committed")
    mode.add_argument("--resolve", nargs=2, metavar=("STEP", "ACTION"), help="tell the runner what happened to an interrupted step: retry or done")
    return parser


def main(argv=None, *, seams=None, home=None, repo_root=None):
    args = _build_parser().parse_args(argv)
    guide = Supplement(seams or real_seams(), home or Path.home(), repo_root or Path.cwd())
    if args.status:
        return guide.status_mode()
    if args.reset_stop:
        return guide.reset_stop(args.reset_stop)
    if args.resolve:
        if args.resolve[1] not in ("retry", "done"):
            print("ACTION is retry or done", file=sys.stderr)
            return EXIT_STOPPED
        return guide.resolve(*args.resolve)
    return guide.main_run()


if __name__ == "__main__":
    sys.exit(main())
