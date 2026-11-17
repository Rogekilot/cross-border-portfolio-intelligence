"""F1 R8: the guided runner (`src/real_tools/r8_guide.py`), with a mocked world: no cluster, no sudo, no network, no database.

Subprocess, input, clock, ports and the file facts of the cluster are behind the runner's seams (`Seams`); the state directory is a real temporary directory
so that file modes are real. The expected command lines below are typed out from `reviews/R8_RUNBOOK.md` (not built with the runner's helpers).
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SRC = REPO / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from real_tools import r8_guide as g  # noqa: E402

HEAD0 = "a" * 40
VITE_BIN = str(Path(__file__).resolve().parents[2] / "web" / "node_modules" / ".bin" / "vite")
RESET_PD = "decisions/product/PD-0090-r8-reset.md"
CTX = "c" * 64
OWNER = "11111111-1111-4111-8111-111111111111"
ROOT = "22222222-2222-4222-8222-222222222222"
SOCKDIR = "/Users/Shared/finweb-r8-pg/sock"
SOCK = SOCKDIR + "/.s.PGSQL.5433"
S1 = "data/marketdata/sidecars/alphavantage.us/quote/2026-10-01/AAPL_compact.csv.sidecar.json"
S2 = "data/marketdata/sidecars/openfigi/identity/2026-10-23/AAPL_UW.json.sidecar.json"
S3 = "data/marketdata/sidecars/calendar.manual/calendar/2026-10-02/NYSE_2025_2026.json.sidecar.json"
H1, H2, H3 = ("066c65e6e7ce61c06f1f413b3e313f1b797fc9fff632ce2a2f2ca4b8b1b9d1fb", "b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc",
              "4f21b26b5f8b4d88e665808f6488424c088b91733621869192784efb3d5f72ef")
INPUTS = ["--store-root", "data/marketdata", "--release-name", "hg4-aapl-2026-09-30", "--file", H1, "--file", H2, "--file", H3, "--sidecar", S1, "--sidecar", S2,
          "--sidecar", S3, "--registered-check", H3]
FW = ["uv", "run", "--no-sync", "--frozen", "--offline", "python", "-m"]
PD_PATHS = {"publish": "decisions/product/PD-0084-r8-publish.md", "withdraw": "decisions/product/PD-0085-r8-withdraw.md", "renew": "decisions/product/PD-0086-r8-renew.md"}
EVIDENCE_FILES = {"decisions/product/PD-0066-hg4-single-date-check-morning-decisions.md": ("1" * 40, b"pd66 text"),
                  "decisions/product/PD-0068-f1-design-open-questions.md": ("2" * 40, b"pd68 text"),
                  PD_PATHS["publish"]: ("3" * 40, b"publish record"), PD_PATHS["withdraw"]: ("4" * 40, b"withdraw record"), PD_PATHS["renew"]: ("5" * 40, b"renew record"), RESET_PD: ("6" * 40, b"reset record")}
NOT_LOGIN = b"REFUSED LOADER_CONNECT_FAILED PF_CONNECT_FAILED. Nothing was sent.\n"       # what a connect to a NOLOGIN loader prints


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Call:
    def __init__(self, argv, env, cwd, stdin_data):
        self.argv, self.env, self.cwd, self.stdin_data = list(argv), env, cwd, stdin_data

    @property
    def module(self):
        return self.argv[7] if self.argv[:7] == FW else None

    @property
    def key(self):
        a = self.argv
        if a[0] == "git":
            return "git"
        if a[:7] == FW:
            module = a[7]
            if module in ("persistence.real_install", "real_tools.loader_window", "real_tools.r8_files"):
                return module.split(".")[-1] + ":" + a[8]
            if module == "persistence.real_workspace_store":
                return "store:" + next(x for x in a if x in ("publish", "withdraw", "renew", "status"))
            return module.split(".")[-1]
        if a[0].endswith("/psql"):
            return "psql:" + (os.path.basename(a[-1]) if "-f" in a else "version")
        return os.path.basename(a[0]) if a[0] != "/usr/bin/sudo" else "sudo:" + os.path.basename(a[3] if a[1] == "-u" else a[1])


class Proc:
    def __init__(self, world, port, code=None, text=b"launcher output\n"):
        self.world, self.port, self.code, self.text = world, port, code, text
        if code is None:
            world.open_ports.add(port)

    def poll(self):
        return self.code

    def terminate(self):
        if self.code is None:
            self.code = -15
            self.world.open_ports.discard(self.port)

    def output(self):
        return self.text


class World:
    """The mocked world: git, the tools, psql, the macOS commands, ports, the clock and the keyboard."""

    def __init__(self, home, environ=None):
        self.home = home
        self.calls = []
        self.said = []
        self.prompts = []
        self.environ = dict(environ if environ is not None else {"HOME": str(home), "PATH": "/usr/bin:/bin"})
        self.head, self.clean, self.changed, self.not_ancestor = HEAD0, True, [], False
        self.open_ports = set()
        self.launcher_exit = None
        self.launcher_script = []         # (exit code, output) per spawn, consumed in order
        self.loader_login = False         # the loader role: LOGIN after window_open.sql, NOLOGIN after window_close.sql
        self.vite_installed = True
        self.range_log = []               # (path, "BASE..HEAD") of every added-after check
        self.added = set(PD_PATHS.values()) | {RESET_PD}       # files ADDED after P8 (git log --diff-filter=A P8..HEAD); the evidence PDs are older
        self.script = {}                  # key -> list of Results (consumed in order); then the default
        self.tick = 0
        self.user_exists, self.user_admin, self.dirs, self.initdb_done, self.hba, self.conf, self.running = False, False, {}, False, "", "# stock\n", False
        self.existing = set()
        self.rules = []
        self.raise_on = {}                # key -> exception raised instead of running
        self.default_rules()

    # ---- the keyboard ---------------------------------------------------------------------------------------------------------------------
    def default_rules(self):
        self.rules = [["[Enter to go on", ""], ["(type freeze)", "freeze"], ["(type approve)", "approve"],
                      ["Path of the committed file", [PD_PATHS["publish"], PD_PATHS["withdraw"], PD_PATHS["renew"]]],
                      ["Status of the create's response", ["201", "409", "201"]], ["Code of the response", ["-", "RW_WITHDRAWN", "-"]],
                      ["Is that exactly", "yes"], ["Did you click Create in that earlier run", "no"], ["What did you correct", "the listing id"],
                      ["Type the holding value", "1,234.50"], ["Type the NAV", "1734.5"], ["Type the missed sessions", "0"],
                      ["Type the state", "AVAILABLE"], ["Retype?", "no"], ["pass or fail?", "pass"], ["A note for the record", ""],
                      ["User A's username", "alice"], ["The root id of A's root", ROOT], ["Is it true?", "yes"], ["Anything that surprised", ""],
                      ["Run the close again?", ""], ["(type RESET R8 STOP)", "RESET R8 STOP"], ["(type retry)", "retry"], ["(type done)", "done"]]

    def answer(self, value):
        self.prompts.append(value)
        for rule in self.rules:
            if rule[0] in value:
                v = rule[1]
                if isinstance(v, list):
                    if not v:
                        raise EOFError()
                    return v.pop(0)
                if callable(v):
                    return v()
                return v
        raise AssertionError("no answer for the prompt: " + value)

    def seams(self):
        return g.Seams(run=self.run, spawn=self.spawn, ask=self.answer, say=self.said.append, now=self.now, sleep=lambda s: None, port_open=lambda p: p in self.open_ports,
                       environ=lambda: dict(self.environ), which=lambda name: "/opt/homebrew/bin/" + name, realpath=lambda p: p, stat=lambda p: self.dirs.get(p),
                       can_write=lambda p: False, can_read=lambda p: False, exists=self.exists)

    def now(self):
        self.tick += 1
        return dt.datetime(2026, 11, 15, 10, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=8), "CST")) + dt.timedelta(seconds=self.tick)

    def exists(self, path):
        if path == VITE_BIN:
            return self.vite_installed
        return path in self.existing or ("/.s.PGSQL." in path and self.running)

    # ---- children -------------------------------------------------------------------------------------------------------------------------
    def spawn(self, argv, env, cwd, stdin_null=False):
        self.calls.append(Call(argv, env, cwd, None))
        self.calls[-1].stdin_null = stdin_null
        if argv[0] == VITE_BIN:
            return Proc(self, 5175)
        if self.launcher_script:
            code, text = self.launcher_script.pop(0)
            return Proc(self, 8004, code=code, text=text)
        if self.launcher_exit is not None:
            return Proc(self, 8004, code=self.launcher_exit)
        return Proc(self, 8004)

    def run(self, argv, *, env, cwd=None, stdin_data=None, echo=True):
        call = Call(argv, env, cwd, stdin_data)
        self.calls.append(call)
        if call.key in self.raise_on:
            raise self.raise_on.pop(call.key)
        queued = self.script.get(call.key)
        if queued:
            return queued.pop(0)
        return self.default(call)

    def count(self, key):
        return sum(1 for c in self.calls if c.key == key)

    def tools(self, key):
        return [c for c in self.calls if c.key == key]

    # ---- defaults -------------------------------------------------------------------------------------------------------------------------
    def default(self, call):
        key, a = call.key, call.argv
        if key == "git":
            return self.git(a[1:])
        if key.startswith("psql"):
            return self.psql(key, a)
        if key.startswith("sudo") or key in ("id",):
            return self.system(call)
        if key.startswith("loader_window:") and not self.loader_login:
            return g.Result(2, NOT_LOGIN)
        if key == "qualify_run":
            Path(a[a.index("--proposal-out") + 1]).write_text(json.dumps({"context_id": CTX, "snapshot": {"scope": "REAL", "release": {"release_id": "r" * 64, "release_digest": "d" * 64},
                                                                    "projection_digest": "p" * 64, "identity_digest": "i" * 64,
                                                                    "members": [{"source_id": s, "payload_sha256": h, "manifest_sha256": "m" * 64} for s, h in
                                                                                (("alphavantage.us", H1), ("openfigi", H2), ("calendar.manual", H3))]}}))
            Path(a[a.index("--seed-out") + 1]).write_text(json.dumps({"listings": [[g.EXPECTED_LISTING_ID, "x"]]}))
            return g.Result(0, b"member alphavantage.us O5 pass\nmember openfigi O5 pass\nmember calendar.manual O5 pass\nwrote the proposal\n")
        if key == "store:publish":
            return g.Result(0, ("published context %s at generation 1\nscope REAL; valid_until 2027-08-31T16:00:00Z\n" % CTX).encode())
        if key == "store:withdraw":
            return g.Result(0, b"drain mark 7 recorded at x\ndone: generation 2 names drain mark 7; all four rights are off\n")
        if key == "store:renew":
            return g.Result(0, ("renewed context %s: generation 3 recorded\nvalid_until x\n" % CTX).encode())
        if key == "store:status":
            return g.Result(0, ("context %s generation 3 kind LEASE valid_until x rights a=true\n" % CTX).encode())
        if key == "admission_probe":
            generation = int(a[a.index("--generation") + 1])
            if generation == 2:
                return g.Result(1, ("direct gateway admission, not a product route\nREFUSED RW_WITHDRAWN purpose=ARCHIVE_EXPORT context=%s generation=2\n" % CTX).encode())
            return g.Result(0, ("ADMITTED purpose=ARCHIVE_EXPORT context=%s generation=%d complete_by=x\n" % (CTX, generation)).encode())
        return g.Result(0, b"ok\n")

    def psql(self, key, a):
        if key == "psql:version":
            return g.Result(0, b"psql (PostgreSQL) 17.11 (Homebrew)\n")
        name = key.split(":")[1]
        if name == "window_open.sql":
            self.loader_login = True
            return g.Result(0, b"R8_MARK login_set_at=2026-11-15T02:00:00Z\n")
        if name == "window_close.sql":
            self.loader_login = False
            return g.Result(0,b"R8_MARK loader_sessions_left=0 at=2026-11-15T02:05:00Z\n")
        if name == "owner_id.sql":
            return g.Result(0, ("R8_MARK owner_id=%s\n" % OWNER).encode())
        return g.Result(0, b"")

    def git(self, a):
        if a[:2] == ["status", "--porcelain"]:
            return g.Result(0, b"" if self.clean else b" M src/x.py\n")
        if a == ["rev-parse", "HEAD"]:
            return g.Result(0, (self.head + "\n").encode())
        if a == ["rev-parse", "--show-toplevel"]:
            return g.Result(0, (str(REPO) + "\n").encode())
        if a[:3] == ["log", "-1", "--format=%s"]:
            return g.Result(0, b"the reviewed commit\n")
        if a[:2] == ["merge-base", "--is-ancestor"]:
            return g.Result(1 if self.not_ancestor else 0, b"")
        if a[:2] == ["diff", "--name-only"]:
            return g.Result(0, "\n".join(self.changed).encode())
        if a[:2] == ["diff", "--stat"]:
            return g.Result(0, b" decisions/product/PD-0084-r8-publish.md | 3 +++\n")
        if a[:3] == ["log", "--diff-filter=A", "--format=%H"]:
            self.range_log.append((a[-1], a[3]))
            return g.Result(0, (EVIDENCE_FILES[a[-1]][0] + "\n").encode() if a[-1] in self.added and a[-1] in EVIDENCE_FILES else b"")
        if a[:3] == ["log", "-1", "--format=%H"]:
            entry = EVIDENCE_FILES.get(a[-1])
            return g.Result(0, (entry[0] + "\n").encode() if entry else b"")
        if a[0] == "show":
            commit, path = a[1].split(":", 1)
            entry = EVIDENCE_FILES.get(path)
            return g.Result(0 if entry and entry[0] == commit else 128, entry[1] if entry else b"")
        if a[:2] == ["ls-files", "--"]:
            return g.Result(0, "\n".join(p for p in EVIDENCE_FILES if fnmatch.fnmatch(p, a[2])).encode())
        raise AssertionError("unexpected git call %r" % (a,))

    def system(self, call):
        a = call.argv
        base = "/Users/Shared/finweb-r8-pg"
        if a[0] == "/usr/bin/id":
            if a[1] == "-u":
                return g.Result(0 if self.user_exists else 1, b"")
            return g.Result(0, b"staff everyone admin\n" if self.user_admin else b"staff everyone\n")
        rest = a[3:] if a[1] == "-u" else a[1:]
        if rest[0] == "/usr/sbin/sysadminctl":
            self.user_exists = True
        elif rest[0] == "/bin/mkdir":
            for p in rest[2:]:
                self.dirs[p] = ("root", 0o755)
            self.dirs[base] = ("root", 0o755)
        elif rest[0] == "/usr/sbin/chown":
            owner = rest[2].split(":")[0]
            for p in list(self.dirs):
                self.dirs[p] = (owner, self.dirs[p][1])
        elif rest[0] == "/bin/chmod":
            for p in rest[2:]:
                self.dirs[p] = (self.dirs[p][0], int(rest[1], 8))
        elif rest[0].endswith("/initdb"):
            self.initdb_done = True
        elif rest[0] == "/bin/test":
            return g.Result(0 if self.initdb_done else 1, b"")
        elif rest[0] == "/bin/cat":
            return g.Result(0, (self.hba if rest[1].endswith("pg_hba.conf") else self.conf).encode())
        elif rest[0] == "/usr/bin/tee":
            if rest[1] == "-a":
                self.conf += call.stdin_data.decode()
            else:
                self.hba = call.stdin_data.decode()
        elif rest[0].endswith("/pg_ctl"):
            if "status" in rest:
                return g.Result(0 if self.running else 3, b"")
            self.running = True
        return g.Result(0, b"")


class GuideCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="r8guide"))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.w = World(self.home)
        self.state_dir = self.home / "finweb-r8"
        self.preset_cluster()

    def preset_cluster(self):
        pass

    def go(self, *argv, world=None):
        w = world or self.w
        return g.main(list(argv), seams=w.seams(), home=self.home, repo_root=REPO)

    def state(self):
        return json.loads((self.state_dir / "state.json").read_text())

    def done(self):
        return list(self.state()["done"])

    def events(self):
        return [json.loads(line) for line in (self.state_dir / "events.log").read_text().splitlines()]

    def tool_calls(self, key):
        return self.w.tools(key)


class HappyPathTests(GuideCase):
    def test_the_whole_run_completes_and_writes_the_record(self):
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertIn("close", self.done())
        self.assertEqual(len(self.done()), len(self.w and g.Guide(self.w.seams(), self.home, REPO).steps))
        record = (self.state_dir / "R8_RECORD.md").read_text()
        for needle in ("reviewed commit P8: `%s`" % HEAD0, "window 1 LOGIN set", "window 2 closed, zero loader sessions", "publish", "withdraw", "renew",
                       "create_a: status 201", "create_withdrawn: status 409, code RW_WITHDRAWN", "check 10.1 NAV against the Quant's figure", "I held the executor's"):
            self.assertIn(needle, record)
        self.assertEqual(self.go(), g.EXIT_DONE)        # a re-run of a finished run does nothing more
        self.assertEqual(self.w.count("store:publish"), 1)

    def test_the_command_lines_equal_the_runbooks(self):
        self.go()
        su, db = "finweb_su", "finweb_real"
        d = str(self.state_dir)
        P, F, E, E2 = d + "/P.json", d + "/F.json", d + "/E.json", d + "/E2.json"
        store = FW + ["persistence.real_workspace_store", "--socket", SOCK, "--database", db, "--user", "finweb_real_publisher", "--schema", "finweb"]
        loader = FW + ["real_tools.loader_window"]
        loader_tail = ["--socket", SOCK, "--database", db, "--user", "finweb_real_loader", "--schema", "finweb"] + INPUTS + ["--proposal", P]
        pd = {k: (v, EVIDENCE_FILES[v][0], sha(EVIDENCE_FILES[v][1])) for k, v in PD_PATHS.items()}
        evidence = FW + ["real_tools.r8_files", "evidence", "--alphavantage-pd", "PD-0066", "--alphavantage-commit", "1" * 40, "--alphavantage-sha", sha(b"pd66 text"),
                         "--openfigi-pd", "PD-0068", "--openfigi-commit", "2" * 40, "--openfigi-sha", sha(b"pd68 text"),
                         "--calendar-pd", "PD-0068", "--calendar-commit", "2" * 40, "--calendar-sha", sha(b"pd68 text")]
        probe = lambda gen: FW + ["real_tools.admission_probe", "--socket", SOCK, "--database", db, "--user", "finweb_real_executor", "--schema", "finweb", "--purpose",
                                  "ARCHIVE_EXPORT", "--owner-id", OWNER, "--root-id", ROOT, "--context", CTX, "--generation", str(gen)]
        contexts = lambda gen, out: FW + ["real_tools.r8_files", "contexts"] + INPUTS + ["--proposal", P, "--generation", str(gen), "--out", d + "/" + out]
        launcher = lambda c: FW + ["web_api.real_launcher", "--socket", SOCK, "--database", db, "--user", "finweb_real_executor", "--schema", "finweb", "--account-user",
                                   "finweb_real_account", "--contexts-file", d + "/" + c, "--port", "8004"]
        actor = ["--actor", "designated human product owner"]
        expected = {
            "real_install:phase0": [FW + ["persistence.real_install", "phase0", "--socket", SOCK, "--user", su]],
            "real_install:phase1": [FW + ["persistence.real_install", "phase1", "--socket", SOCK, "--user", su, "--loader-login", "nologin"]],
            "real_install:phase2": [FW + ["persistence.real_install", "phase2", "--socket", SOCK, "--user", su]],
            "real_install:check": [FW + ["persistence.real_install", "check", "--socket", SOCK, "--user", su]] * 2,
            "qualify_run": [FW + ["real_tools.qualify_run"] + INPUTS + ["--proposal-out", P, "--seed-out", F]],
            "identity_seed": [FW + ["real_tools.identity_seed", "--socket", SOCK, "--user", su, "--seed-file", F, "--proposal", P]],
            "loader_window:load": [loader + ["load"] + loader_tail],
            "loader_window:register-bound": [loader + ["register-bound"] + loader_tail],
            "r8_files:evidence": [evidence + ["--out", E], evidence + ["--out", E2]],
            "r8_files:contexts": [contexts(1, "C.json"), contexts(2, "C1.json"), contexts(3, "C2.json")],
            "store:publish": [store + ["publish", "--proposal", P, "--sidecar", S1, "--sidecar", S2, "--sidecar", S3, "--valid-until", "2027-08-31T16:00:00Z", "--evidence-file", E]
                              + actor + ["--pd", "PD-0084", "--commit", pd["publish"][1], "--sha", pd["publish"][2]]],
            "store:withdraw": [store + ["withdraw", "--context", CTX, "--generation", "1"] + actor + ["--pd", "PD-0085", "--commit", pd["withdraw"][1], "--sha", pd["withdraw"][2]]],
            "store:renew": [store + ["renew", "--context", CTX, "--generation", "2", "--valid-until", "2027-08-31T16:00:00Z", "--evidence-file", E2] + actor
                            + ["--pd", "PD-0086", "--commit", pd["renew"][1], "--sha", pd["renew"][2]]],
            "admission_probe": [probe(1), probe(2), probe(3)],
        }
        for key, lines in expected.items():
            self.assertEqual([c.argv for c in self.w.tools(key)], lines, key)
        self.assertEqual([c.argv for c in self.w.calls if c.argv[0] == VITE_BIN], [[VITE_BIN, "--config", "vite.real.config.ts"]] * 3)
        self.assertEqual([c.cwd for c in self.w.calls if c.argv[0] == VITE_BIN], [str(REPO / "web")] * 3)
        self.assertFalse(any("npx" in c.argv[0] for c in self.w.calls))
        self.assertEqual([c.argv for c in self.w.calls if c.argv[:8] == FW + ["web_api.real_launcher"]], [launcher("C.json"), launcher("C1.json"), launcher("C2.json")])

    def test_every_tool_command_parses_with_the_tools_own_parser(self):
        """The options the runner passes are ones the reviewed tools accept (a changed tool would refuse the runbook's command line)."""
        from persistence import real_install, real_workspace_store as store
        from real_tools import admission_probe, identity_seed, loader_window, qualify_run, r8_files
        from web_api import real_launcher
        parsers = {"persistence.real_install": real_install._build_parser, "persistence.real_workspace_store": store._build_parser, "real_tools.identity_seed": identity_seed._build_parser,
                   "real_tools.loader_window": loader_window._build_parser, "real_tools.qualify_run": qualify_run._build_parser, "real_tools.r8_files": r8_files._build_parser,
                   "real_tools.admission_probe": admission_probe._build_parser, "web_api.real_launcher": real_launcher._build_parser}
        self.go()
        seen = set()
        for call in self.w.calls:
            if call.argv[:7] == FW:
                parsers[call.argv[7]]().parse_args(call.argv[8:])         # SystemExit on an option the tool does not have
                seen.add(call.argv[7])
        self.assertEqual(seen, set(parsers))
        for call in self.w.tools("loader_window:reconcile"):
            parsers["real_tools.loader_window"]().parse_args(call.argv[8:])

    def test_the_psql_sessions_and_their_scripts(self):
        self.go()
        psql = "/opt/homebrew/bin/psql"
        base = lambda script: [psql, "-X", "-v", "ON_ERROR_STOP=1", "-v", "HISTFILE=/dev/null", "-h", SOCKDIR, "-p", "5433", "-U", "finweb_su", "-d", "finweb_real", "-f",
                               str(self.state_dir / "scripts" / script)]
        runs = [c.argv for c in self.w.calls if c.argv[0] == psql and "-f" in c.argv]
        self.assertEqual(runs[0], base("passwords.sql"))
        self.assertEqual([r[-1].rsplit("/", 1)[1] for r in runs], ["passwords.sql", "window_open.sql", "window_close.sql", "window_open.sql", "window_close.sql", "owner_id.sql"])
        owner_run = runs[-1]
        self.assertEqual(owner_run, [psql, "-X", "-v", "ON_ERROR_STOP=1", "-v", "HISTFILE=/dev/null", "-v", "username=alice", "-h", SOCKDIR, "-p", "5433", "-U", "finweb_su", "-d",
                                     "finweb_real", "-f", str(self.state_dir / "scripts" / "owner_id.sql")])
        scripts = self.state_dir / "scripts"
        self.assertEqual((scripts / "passwords.sql").read_text(), "\\password finweb_real_publisher\n\\password finweb_real_executor\n\\password finweb_real_account\n")
        opened = (scripts / "window_open.sql").read_text()
        self.assertTrue(opened.startswith("ALTER ROLE finweb_real_loader LOGIN;\n"))
        self.assertTrue(opened.endswith("\\password finweb_real_loader\n"))
        closed = (scripts / "window_close.sql").read_text()
        self.assertTrue(closed.startswith("ALTER ROLE finweb_real_loader NOLOGIN;\n"))
        self.assertIn("pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = 'finweb_real_loader'", closed)
        self.assertIn("\\watch i=1 c=30 min_rows=1", closed)
        owner_sql = (scripts / "owner_id.sql").read_text()
        self.assertIn("user_id", owner_sql)
        self.assertNotIn("password_hash", owner_sql)

    def test_the_cluster_commands_are_fixed_argument_lists(self):
        self.go()
        user, base = "finwebpg", "/Users/Shared/finweb-r8-pg"
        sudo = [c.argv for c in self.w.calls if c.argv[0] == "/usr/bin/sudo"]
        self.assertEqual(sudo[0], ["/usr/bin/sudo", "/usr/sbin/sysadminctl", "-addUser", user, "-fullName", "FinWeb R8 Postgres", "-password", "-"])
        self.assertIn(["/usr/bin/sudo", "/bin/mkdir", "-p", base + "/data", base + "/sock", base + "/log"], sudo)
        self.assertIn(["/usr/bin/sudo", "/usr/sbin/chown", "-R", "finwebpg:staff", base], sudo)
        self.assertIn(["/usr/bin/sudo", "/bin/chmod", "755", base, base + "/sock"], sudo)
        self.assertIn(["/usr/bin/sudo", "/bin/chmod", "700", base + "/data", base + "/log"], sudo)
        initdb = ["/usr/bin/sudo", "-u", user, "/opt/homebrew/bin/initdb", "-D", base + "/data", "--auth-local=scram-sha-256", "--auth-host=scram-sha-256", "--pwprompt", "-U",
                  "finweb_su", "-E", "UTF8", "--locale=C"]
        self.assertIn(initdb, sudo)
        self.assertIn(["/usr/bin/sudo", "-u", user, "/opt/homebrew/bin/pg_ctl", "-D", base + "/data", "-l", base + "/log/server.log", "start"], sudo)
        tee = [c for c in self.w.calls if c.argv[:4] == ["/usr/bin/sudo", "-u", user, "/usr/bin/tee"]]
        self.assertEqual(tee[0].argv[4:], [base + "/data/pg_hba.conf"])
        self.assertEqual(tee[0].stdin_data, b"local   all   all   scram-sha-256\n")
        self.assertEqual(tee[1].argv[4:], ["-a", base + "/data/postgresql.conf"])
        for line in (b"listen_addresses = ''", b"port = 5433", b"unix_socket_directories = '%s'" % SOCKDIR.encode(), b"password_encryption = scram-sha-256",
                     b"max_prepared_transactions = 0", b"log_statement = 'none'", b"log_min_duration_statement = -1"):
            self.assertIn(line, tee[1].stdin_data)
        for call in self.w.calls:
            if call.argv[:2] == ["/usr/bin/sudo", "-u"]:
                self.assertEqual(call.cwd, "/")
                self.assertFalse(any(ch in part for part in call.argv for ch in ";|&`$<>"), call.argv)
        recorded = self.state()["records"]
        self.assertTrue(any(r["item"] == "cluster owners and modes" for r in recorded))
        self.assertIs(next(r for r in recorded if r["item"] == "owner's account can write the data directory")["value"], False)

    def test_every_child_runs_with_no_pg_variable_and_pythonpath_src_and_nothing_secret(self):
        self.w.environ.update({"HOME": str(self.home), "PATH": "/usr/bin", "LANG": "C", "SOME_OTHER": "x"})
        self.go()
        self.assertGreater(len(self.w.calls), 50)
        for call in self.w.calls:
            if call.env is None:
                continue
            self.assertFalse([k for k in call.env if k.upper().startswith("PG")], call.argv)
            self.assertEqual(call.env["PYTHONPATH"], "src")
            self.assertEqual(call.env["PSQL_HISTORY"], "/dev/null")
            self.assertEqual(call.env["SOME_OTHER"], "x")
        text = json.dumps([c.argv for c in self.w.calls]) + (self.state_dir / "state.json").read_text() + (self.state_dir / "transcript.log").read_text()
        for word in ("PGPASSWORD", "passfile", "--password", "PASSWORD '"):
            self.assertNotIn(word, text)
        # no prompt of the runner asks for a password; the only question about one is the warning not to type it
        for prompt in self.w.prompts:
            self.assertNotIn("Password for", prompt)
            self.assertNotIn("Enter password", prompt)

    def test_file_modes(self):
        self.go()
        self.assertEqual(stat.S_IMODE(self.state_dir.stat().st_mode), 0o700)
        for name in ("state.json", "transcript.log", "R8_RECORD.md", "scripts/passwords.sql", "scripts/window_close.sql"):
            self.assertEqual(stat.S_IMODE((self.state_dir / name).stat().st_mode), 0o600, name)
        self.assertEqual(stat.S_IMODE((self.state_dir / "scripts").stat().st_mode), 0o700)
        self.assertFalse((self.state_dir / "state.json.tmp").exists())

    def test_nothing_is_written_inside_the_repository(self):
        before = {p: p.stat().st_mtime_ns for p in (REPO / "src" / "real_tools").glob("*.py")}
        self.go()
        after = {p: p.stat().st_mtime_ns for p in (REPO / "src" / "real_tools").glob("*.py")}
        self.assertEqual(before, after)
        written = [c for c in self.w.calls if c.argv[0] == "git" and c.argv[1] not in ("status", "rev-parse", "log", "merge-base", "diff", "show", "ls-files")]
        self.assertEqual(written, [])


class ResumeTests(GuideCase):
    def test_a_run_interrupted_at_each_prompt_resumes_and_never_repeats_a_write(self):
        total = 0
        probe = World(self.home / "scratch")
        (self.home / "scratch").mkdir()
        # count the Enter prompts of a whole run first
        w = World(self.tmp / "count")
        (self.tmp / "count").mkdir()
        os.makedirs(self.tmp / "count" / "finweb-r8", mode=0o700)
        g.main([], seams=w.seams(), home=self.tmp / "count", repo_root=REPO)
        total = sum(1 for p in w.prompts if "[Enter to go on" in p)
        self.assertGreater(total, 40)
        for n in range(1, total + 1, 3):
            home = self.tmp / ("h%d" % n)
            home.mkdir()
            world = World(home)
            seen = {"n": 0}

            def enter(world=world, seen=seen, n=n):
                seen["n"] += 1
                if seen["n"] == n:
                    raise EOFError()
                return ""
            world.rules[0] = ["[Enter to go on", enter]
            self.assertEqual(g.main([], seams=world.seams(), home=home, repo_root=REPO), g.EXIT_PAUSED, n)
            world.rules[0] = ["[Enter to go on", ""]
            self.assertEqual(g.main([], seams=world.seams(), home=home, repo_root=REPO), g.EXIT_DONE, n)
            for key in ("real_install:phase1", "store:publish", "store:withdraw", "store:renew", "qualify_run", "identity_seed", "loader_window:load", "loader_window:register-bound"):
                self.assertEqual(world.count(key), 1, (n, key))
            self.assertEqual(world.count("real_install:phase0"), 1, n)

    def test_resume_from_the_state_file_alone_skips_what_is_done(self):
        self.w.rules[0] = ["[Enter to go on", self._quit_at("w1_open")]
        self.assertEqual(self.go(), g.EXIT_PAUSED)
        self.assertEqual(self.done()[-1], "seed")
        calls_before = len(self.w.calls)
        self.w.rules[0] = ["[Enter to go on", ""]
        self.assertEqual(self.go(), g.EXIT_DONE)
        later = [c for c in self.w.calls[calls_before:] if c.key in ("real_install:phase0", "real_install:phase1", "qualify_run", "identity_seed")]
        self.assertEqual(later, [])

    def _quit_at(self, sid):
        def enter():
            title = [p for p in self.w.prompts if "[Enter to go on" in p][-1]
            if "Open loader window 1" in title and sid == "w1_open":
                raise EOFError()
            return ""
        return enter

    def test_an_interrupted_unsafe_step_is_not_re_run_blindly(self):
        self.w.raise_on["real_install:phase1"] = KeyboardInterrupt()
        self.assertEqual(self.go(), g.EXIT_PAUSED)
        self.assertIn("phase1", self.state()["started"])
        n = len(self.w.calls)
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.w.count("real_install:phase1"), 1)
        self.assertIn("STEP_INTERRUPTED", "\n".join(self.w.said))
        self.assertEqual(self.go("--resolve", "phase1", "retry"), g.EXIT_DONE)
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.w.count("real_install:phase1"), 2)

    def test_resolve_done_for_the_renew_reads_the_generation_from_status(self):
        self.w.rules.insert(0, ["__never__", ""])
        original = self.w.script.setdefault("store:renew", [])
        self.w.raise_on["store:renew"] = KeyboardInterrupt()
        self.assertEqual(self.go(), g.EXIT_PAUSED)
        self.assertEqual(self.go("--resolve", "renew", "done"), g.EXIT_DONE)
        self.assertEqual(self.state()["done"]["renew"]["data"]["generation"], 3)
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.w.count("store:renew"), 1)
        del original


class StopTests(GuideCase):
    def stop_run(self, key, result, *, expect=g.EXIT_STOPPED):
        self.w.script[key] = [result]
        self.assertEqual(self.go(), expect)

    def assert_latched(self):
        latch = self.state()["latch"]
        self.assertIsNotNone(latch)
        n = len(self.w.calls)
        self.assertEqual(self.go(), g.EXIT_LATCHED)             # a plain re-run cannot pass the latch
        self.assertEqual(self.go(), g.EXIT_LATCHED)
        self.assertEqual(len(self.w.calls), n)                  # and runs nothing at all
        return latch

    def test_phase0_refusal_stops_without_a_latch_and_a_rerun_checks_again(self):
        self.stop_run("real_install:phase0", g.Result(2, b"PF_X\n"))
        self.assertIsNone(self.state()["latch"])
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.w.count("real_install:phase0"), 2)

    def test_installer_refusals_and_unknown_statuses_latch(self):
        for key, code, step in (("real_install:phase1", 4, "phase1"), ("real_install:phase1", 2, "phase1"), ("real_install:phase2", 2, "phase2"), ("identity_seed", 2, "seed"),
                                ("qualify_run", 2, "qualify"), ("store:publish", 2, "publish"), ("store:publish", 9, "publish"), ("loader_window:load", 9, "w1_load")):
            with self.subTest(key=key, code=code):
                self.setUp()
                self.w.script[key] = [g.Result(code, b"REFUSED something\n")]
                self.assertEqual(self.go(), g.EXIT_STOPPED)
                self.assertEqual(self.assert_latched()["step"], step)

    def test_a_refused_check_closes_the_window_then_latches(self):
        self.w.script["real_install:check"] = [g.Result(2, b"PF_REFUSED\n")]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.w.count("loader_window:load"), 0)
        self.assertEqual(self.w.count("psql:window_close.sql"), 1)
        self.assertFalse(self.state()["window"]["open"])
        self.assertEqual(self.assert_latched()["step"], "w1_check")

    def test_loader_exit_2_closes_the_window_and_latches(self):
        self.w.script["loader_window:load"] = [g.Result(2, b"REFUSED LOADER_INPUT\n")]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.w.count("psql:window_close.sql"), 1)
        self.assert_latched()

    def test_loader_exit_5_runs_the_identical_command_again(self):
        self.w.script["loader_window:load"] = [g.Result(5, b"LOCK_TIMEOUT\n"), g.Result(5, b"LOCK_TIMEOUT\n")]
        self.assertEqual(self.go(), g.EXIT_DONE)
        loads = [c.argv for c in self.w.tools("loader_window:load")]
        self.assertEqual(len(loads), 3)
        self.assertEqual(loads[0], loads[1])
        self.assertEqual(loads[1], loads[2])

    def test_loader_exit_4_after_a_registration_runs_the_reconcile_the_tool_printed_with_the_window_open(self):
        text = b"THE LOAD COMMITTED; ... or `reconcile --candidate unbound`.\nRun `loader_window reconcile --candidate unbound` with the same inputs\n"
        self.w.script["loader_window:load"] = [g.Result(4, text)]
        self.w.script["loader_window:reconcile"] = [g.Result(0, b"unbound reconciled\n")]
        self.assertEqual(self.go(), g.EXIT_DONE)
        rec = self.w.tools("loader_window:reconcile")[0].argv
        self.assertEqual(rec[7:9], ["real_tools.loader_window", "reconcile"])
        self.assertEqual(rec[-2:], ["--candidate", "unbound"])
        from real_tools import loader_window
        loader_window._build_parser().parse_args(rec[8:])
        self.assertEqual(rec[:-2], [c.argv for c in self.w.tools("loader_window:load")][0][:8] + ["reconcile"] + [c.argv for c in self.w.tools("loader_window:load")][0][9:])
        # the window was open during all of it: the close came after the reconcile
        order = [c.key for c in self.w.calls if c.key in ("loader_window:load", "loader_window:reconcile", "psql:window_close.sql")]
        self.assertEqual(order[:3], ["loader_window:load", "loader_window:reconcile", "psql:window_close.sql"])

    def test_exit_4_then_reconcile_finds_nothing_then_the_identical_load(self):
        self.w.script["loader_window:load"] = [g.Result(4, b"Run `loader_window reconcile --candidate unbound`\n")]
        self.w.script["loader_window:reconcile"] = [g.Result(4, b"no registration found; run the identical `loader_window load` command again\n")]
        self.assertEqual(self.go(), g.EXIT_DONE)
        order = [c.key for c in self.w.calls if c.key in ("loader_window:load", "loader_window:reconcile", "psql:window_close.sql")]
        self.assertEqual(order[:4], ["loader_window:load", "loader_window:reconcile", "loader_window:load", "psql:window_close.sql"])

    def test_exit_4_of_a_load_with_an_unknown_outcome_reruns_the_identical_load(self):
        self.w.script["loader_window:load"] = [g.Result(4, b"the load: the outcome is not known; run the identical command again\n")]
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.w.count("loader_window:reconcile"), 0)
        loads = [c.argv for c in self.w.tools("loader_window:load")]
        self.assertEqual(loads[0], loads[1])

    def test_an_answer_that_never_becomes_definite_leaves_the_window_open_and_says_so_without_a_latch(self):
        self.w.script["loader_window:load"] = [g.Result(4, b"identical load again\n")] * 10
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIsNone(self.state()["latch"])
        self.assertTrue(self.state()["window"]["open"])
        self.assertEqual(self.w.count("psql:window_close.sql"), 0)
        self.assertIn("STILL OPEN", "\n".join(self.w.said))

    def test_register_bound_has_the_same_handling_for_the_bound_candidate(self):
        self.w.script["loader_window:register-bound"] = [g.Result(4, b"Run `loader_window reconcile --candidate bound`\n")]
        self.w.script["loader_window:reconcile"] = [g.Result(0, b"bound reconciled\n")]
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.w.tools("loader_window:reconcile")[0].argv[-2:], ["--candidate", "bound"])
        self.w.script["loader_window:register-bound"] = []

    def test_a_window_that_cannot_be_confirmed_closed_stops_loudly(self):
        self.w.script["psql:window_close.sql"] = [g.Result(0, b"R8_MARK loader_sessions_left=1 at=x\n")]
        self.w.rules = [r for r in self.w.rules if r[0] != "Run the close again?"] + [["Run the close again?", "stop"]]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertTrue(self.state()["window"]["open"])
        self.assertIn("NOT CONFIRMED CLOSED", "\n".join(self.w.said))

    def test_the_close_repeats_until_zero_rows(self):
        self.w.script["psql:window_close.sql"] = [g.Result(0, b"R8_MARK loader_sessions_left=2 at=x\n")]
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.w.count("psql:window_close.sql"), 3)       # window 1 twice, window 2 once

    def test_withdraw_exit_3_runs_the_identical_command_and_exit_2_latches(self):
        self.w.script["store:withdraw"] = [g.Result(3, b"not yet effective\n")]
        self.assertEqual(self.go(), g.EXIT_DONE)
        withdraws = [c.argv for c in self.w.tools("store:withdraw")]
        self.assertEqual(len(withdraws), 2)
        self.assertEqual(withdraws[0], withdraws[1])
        self.setUp()
        self.w.script["store:withdraw"] = [g.Result(2, b"REFUSED\n")]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.assert_latched()["step"], "withdraw")

    def test_the_publish_context_must_equal_the_proposals(self):
        self.w.script["store:publish"] = [g.Result(0, ("published context %s at generation 1\n" % ("d" * 64)).encode())]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.assert_latched()["code"], "PUBLISH_CONTEXT_DIFFERS")

    def test_probe_exit_codes_that_the_runbook_does_not_cover_latch(self):
        self.w.script["admission_probe"] = [g.Result(1, b"REFUSED RW_X purpose=ARCHIVE_EXPORT\n")]          # the control must be admitted
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.assert_latched()["step"], "probe_control")

    def test_a_probe_refusal_after_the_withdraw_that_is_not_withdrawn_is_recorded_as_not_showing_it(self):
        self.w.script["admission_probe"] = [g.Result(0, b"ADMITTED\n"), g.Result(1, b"REFUSED RW_CONTEXT_CHANGED purpose=ARCHIVE_EXPORT context=x generation=2\n")]
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertIs(self.state()["done"]["probe_n1"]["data"]["shows_the_withdrawal"], False)
        self.assertIs(self.state()["done"]["probe_n1"]["data"]["code"] == "RW_CONTEXT_CHANGED", True)

    def test_a_launcher_that_refuses_to_start_latches(self):
        self.w.launcher_exit = 2
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.assert_latched()["code"], "LAUNCHER_EXIT_2")

    def test_close_window_works_through_a_latch_and_status_too(self):
        self.w.script["loader_window:load"] = [g.Result(2, b"REFUSED\n")]
        self.go()
        self.state_edit(lambda s: s["window"].update({"n": 1, "open": True}))
        self.assertEqual(self.go("--status"), g.EXIT_DONE)
        self.assertEqual(self.go("--close-window"), g.EXIT_DONE)
        self.assertFalse(self.state()["window"]["open"])

    def state_edit(self, fn):
        s = self.state()
        fn(s)
        (self.state_dir / "state.json").write_text(json.dumps(s))

    def test_reset_stop_needs_a_newer_clean_head_a_committed_decision_record_and_the_phrase(self):
        self.w.script["loader_window:load"] = [g.Result(2, b"REFUSED\n")]
        self.go()
        self.assert_latched()
        self.assertEqual(self.go("--reset-stop", "PD-0084"), g.EXIT_STOPPED)       # same HEAD: no fix committed (and PD-0084 is not under that number yet)
        self.assertIsNotNone(self.state()["latch"])
        self.w.head = "b" * 40
        self.assertEqual(self.go("--reset-stop", "PD-0099"), g.EXIT_STOPPED)       # no such record
        self.w.clean = False
        self.assertEqual(self.go("--reset-stop", "PD-0084"), g.EXIT_STOPPED)       # dirty tree
        self.w.clean = True
        self.w.rules = [r for r in self.w.rules if r[0] != "(type RESET R8 STOP)"] + [["(type RESET R8 STOP)", "no"]]
        self.assertEqual(self.go("--reset-stop", "PD-0090"), g.EXIT_STOPPED)       # a wrong phrase is not accepted (it asks again, then gives up)
        self.assertIsNotNone(self.state()["latch"])
        self.w.default_rules()
        self.assertEqual(self.go("--reset-stop", "PD-0066"), g.EXIT_STOPPED)       # TR8G-M-4: an OLD record (not added after the stop) is refused
        self.assertIsNotNone(self.state()["latch"])
        self.assertEqual(self.go("--reset-stop", "PD-0090"), g.EXIT_DONE)
        state = self.state()
        self.assertIsNone(state["latch"])
        self.assertEqual(state["p8"]["commit"], "b" * 40)
        self.assertEqual(state["p8_history"][0]["commit"], HEAD0)
        self.assertEqual(state["latch_history"][0]["lifted_by"], "PD-0090")
        self.assertEqual(self.go(), g.EXIT_DONE)             # the new P8 is the baseline, and the run continues at the step that stopped
        self.assertEqual(self.w.count("loader_window:load"), 2)          # the refused one, then one against a LOGIN loader (the model refuses a NOLOGIN one)
        self.assertEqual(self.w.count("psql:window_open.sql"), 3)        # TR8G-M-2: window 1 was opened AGAIN after the reset (and window 2 once)
        self.assertIn("window_reopen", [e["kind"] for e in self.events()])


class CreateTests(GuideCase):
    def test_the_classification_table(self):
        c = g.classify_create
        for status, code, verdict in (("201", "-", "SUCCESS"), ("200", "", "SUCCESS"), ("201", "OK", "SUCCESS"), ("201", "RW_X", "STOP"), ("422", "REAL_REQUEST_INVALID", "RETRY"),
                                      ("422", "real_request_invalid", "RETRY"), ("422", "REAL_OTHER", "STOP"), ("404", "-", "RETRY"), ("404", "ANYTHING", "RETRY"),
                                      ("503", "-", "STOP"), ("UNKNOWN", "-", "STOP"), ("unknown", "-", "STOP"), ("409", "RW_WITHDRAWN", "STOP"), ("500", "-", "STOP"),
                                      ("", "", "STOP"), ("403", "REAL_REQUEST_INVALID", "STOP"), ("400", "REAL_REQUEST_INVALID", "STOP")):
            self.assertEqual(c(status, code), verdict, (status, code))

    def set_create(self, statuses, codes):
        self.w.rules = [r for r in self.w.rules if r[0] not in ("Status of the create's response", "Code of the response")] + [
            ["Status of the create's response", list(statuses)], ["Code of the response", list(codes)]]

    def test_422_and_404_are_recorded_and_retried_then_success_continues(self):
        self.set_create(["422", "404", "201", "409", "201"], ["REAL_REQUEST_INVALID", "NOT_FOUND", "-", "RW_WITHDRAWN", "-"])
        self.assertEqual(self.go(), g.EXIT_DONE)
        creates = self.state()["creates"]
        self.assertEqual([(c["label"], c["status"], c["verdict"]) for c in creates], [("create_a", "422", "RETRY"), ("create_a", "404", "RETRY"), ("create_a", "201", "SUCCESS"),
                                                                                    ("create_withdrawn", "409", "EXPECTED_REFUSAL"), ("create_c2", "201", "SUCCESS")])
        self.assertEqual(creates[0]["note"], "the listing id")

    def test_every_other_outcome_stops_r8_and_latches(self):
        for status, code in (("503", "RW_UNAVAILABLE"), ("UNKNOWN", "-"), ("422", "REAL_PROVENANCE"), ("409", "RW_CONTEXT_CHANGED"), ("500", "-"), ("403", "RW_ANY")):
            with self.subTest(status=status, code=code):
                self.setUp()
                self.set_create([status], [code])
                self.assertEqual(self.go(), g.EXIT_STOPPED)
                latch = self.state()["latch"]
                self.assertEqual(latch["step"], "create")
                self.assertIn("rule 0.3", latch["message"])
                self.assertEqual(self.go(), g.EXIT_LATCHED)
                self.assertNotIn("check_nav", self.done())
                self.assertEqual(self.w.count("store:withdraw"), 0)

    def test_a_retried_create_that_then_stops_still_latches_and_keeps_the_attempts(self):
        self.set_create(["404", "503"], ["-", "-"])
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual([c["verdict"] for c in self.state()["creates"]], ["RETRY", "STOP"])

    def test_redo_retypes_without_recording(self):
        self.set_create(["503", "201", "409", "201"], ["-", "-", "RW_WITHDRAWN", "-"])
        answers = ["redo", "yes", "yes", "yes", "yes", "yes"]
        self.w.rules = [r for r in self.w.rules if r[0] != "Is that exactly"] + [["Is that exactly", answers]]
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.state()["creates"][0]["status"], "201")

    def test_a_create_under_the_withdrawal_that_is_not_the_withdrawal_stops(self):
        self.set_create(["201", "409"], ["-", "RW_CONTEXT_CHANGED"])
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.state()["latch"]["step"], "c1_refusals")

    def test_the_form_values_come_from_the_files_and_the_listing_id_is_checked(self):
        self.go()
        shown = "\n".join(self.w.said)
        self.assertIn(CTX, shown)
        self.assertIn("r" * 64, shown)
        self.assertIn(g.EXPECTED_LISTING_ID, shown)
        for fixed in ("2026-09-30", "Quantity", "500"):
            self.assertIn(fixed, shown)

    def test_a_listing_id_other_than_the_expected_latches_before_the_create(self):
        self.w.script["qualify_run"] = [g.Result(0, b"x\n")]
        (self.state_dir).mkdir(parents=True, exist_ok=True)
        os.chmod(self.state_dir, 0o700)
        (self.state_dir / "P.json").write_text(json.dumps({"context_id": CTX, "snapshot": {"scope": "REAL", "release": {"release_id": "r" * 64, "release_digest": "d" * 64},
                                                                                             "projection_digest": "p", "identity_digest": "i",
                                                                                             "members": [{"source_id": "s", "payload_sha256": h, "manifest_sha256": "m"} for h in (H1, H2, H3)]}}))
        (self.state_dir / "F.json").write_text(json.dumps({"listings": [["00000000-0000-4000-8000-000000000000"]]}))
        self.assertEqual(self.go(), g.EXIT_STOPPED)         # qualify refuses to start: it never overwrites... here the fake does not write, so the run goes on to the check
        self.assertEqual(self.state()["latch"]["code"], "LISTING_ID_DIFFERS")


class CheckTests(GuideCase):
    def test_numeric_comparison_ignores_trailing_zeros_and_grouping(self):
        eq = g.numbers_equal
        D = g.Decimal
        for typed, expected in (("123.4500", D("123.45")), ("123.45", D("123.45")), ("1,234.50", D("1234.50")), ("1234.5", D("1234.50")), ("1734.5", D("1734.50")),
                                ("1,734.500", D("1734.50")), ("0", D("0")), ("0.0", D("0")), ("+123.45", D("123.45"))):
            self.assertTrue(eq(typed, expected), typed)
        for typed, expected in (("123.46", D("123.45")), ("1,234.51", D("1234.50")), ("1734", D("1734.50")), ("", D("0")), ("abc", D("0")), ("1,23.45", D("1234.50")),
                                ("12 345", D("1234.50")), ("1", D("0")), ("1734.5x", D("1734.50")), ("1.734,50", D("1734.50"))):
            self.assertFalse(eq(typed, expected), typed)

    def test_the_expected_values_are_the_quants_ruling_9_1(self):
        self.assertEqual(dict(g.QUANT_NUMBERS), {"holding": g.Decimal("1234.50"), "nav": g.Decimal("1734.50"), "missed_sessions": g.Decimal("0")})
        self.assertEqual(g.QUANT_STATE, "AVAILABLE")
        ruling = (REPO / "methodology" / "CP7_F1_O7_CLAIM_LINEAGE_RULING_2026-11-10.md").read_text()
        # public copy (PD-0083): the ruling's vendor figures are redacted to symbols and the constants are invented; check the
        # ruling's symbolic form and that the constants keep its arithmetic (holding = 10 x a two-decimal close; NAV = holding + 500)
        self.assertIn("redacted in the public copy, PD-0083", ruling)
        self.assertIn("- holding = 10 × c;", ruling)
        self.assertIn("- NAV = 10 × c + 500 USD.", ruling)
        q = dict(g.QUANT_NUMBERS)
        self.assertEqual(q["nav"], q["holding"] + 500)
        self.assertEqual((q["holding"] / 10).quantize(g.Decimal("0.01")), q["holding"] / 10)
        self.assertIn("`AVAILABLE`", ruling)
        # the constants are cited next to their definition
        source = (SRC / "real_tools" / "r8_guide.py").read_text()
        self.assertIn("RULING_2026-11-10.md` section 9.1", source)

    def test_compare_nav(self):
        self.assertEqual(g.compare_nav("1,234.50", "1734.5", "0", "available"), {"holding": True, "nav": True, "missed_sessions": True, "state": True})
        self.assertEqual(g.compare_nav("1234.5", "1734.6", "1", "LIMITED"), {"holding": True, "nav": False, "missed_sessions": False, "state": False})

    def test_the_close_is_not_asked_and_not_compared_pd_0087_item_2(self):
        """The screen shows `10 x p` and no price (ruling section 8 item 4; DR-R8-2), so check 10.1 compares only the figures the screen states."""
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertFalse(any("last close" in p for p in self.w.prompts))
        self.assertTrue(any("The close is not asked" in line for line in self.w.said))
        rec = next(r for r in self.state()["records"] if r["item"].startswith("check 10.1"))
        self.assertEqual(rec["value"]["result"], "PASS")
        self.assertEqual(set(rec["value"]["attempts"][0]["typed"]), {"holding", "nav", "missed_sessions", "state"})

    def test_a_nav_mismatch_is_recorded_as_a_failure_and_does_not_stop(self):
        self.w.rules = [r for r in self.w.rules if r[0] != "Type the NAV"] + [["Type the NAV", "1734.6"]]
        self.assertEqual(self.go(), g.EXIT_DONE)
        data = self.state()["done"]["check_nav"]["data"]
        self.assertEqual(data["result"], "FAIL")
        self.assertIn("NOT equal", "\n".join(self.w.said))
        rec = next(r for r in self.state()["records"] if r["item"].startswith("check 10.1"))
        self.assertFalse(rec["value"]["attempts"][0]["equal"]["nav"])

    def test_a_retyped_nav_keeps_every_attempt(self):
        self.w.rules = [r for r in self.w.rules if r[0] not in ("Type the NAV", "Retype?")] + [["Type the NAV", ["1734.6", "1734.50"]], ["Retype?", "yes"]]
        self.assertEqual(self.go(), g.EXIT_DONE)
        rec = next(r for r in self.state()["records"] if r["item"].startswith("check 10.1"))
        self.assertEqual(len(rec["value"]["attempts"]), 2)
        self.assertEqual(rec["value"]["result"], "PASS")


class PreconditionAndFrozenTests(GuideCase):
    def test_a_dirty_tree_refuses_the_first_run_and_writes_no_state(self):
        self.w.clean = False
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertFalse((self.state_dir / "state.json").exists())
        self.assertEqual(self.w.count("real_install:phase0"), 0)

    def test_a_dirty_tree_before_a_password_step_refuses_before_the_tool_starts(self):
        def dirty_at_phase1():
            if "Phase 1" in [p for p in self.w.prompts if "[Enter to go on" in p][-1]:
                self.w.clean = False
            return ""
        self.w.rules[0] = ["[Enter to go on", dirty_at_phase1]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.w.count("real_install:phase1"), 0)
        self.assertIn("TREE_NOT_CLEAN", "\n".join(self.w.said))
        self.assertIsNone(self.state()["latch"])
        self.w.clean = True
        self.w.default_rules()
        self.assertEqual(self.go(), g.EXIT_DONE)

    def test_a_dirty_tree_before_an_unsafe_step_does_not_block_its_rerun(self):
        def dirty_before_evidence():
            if "Expiry-evidence file" in [p for p in self.w.prompts if "[Enter to go on" in p][-1]:
                self.w.clean = False
            return ""
        self.w.rules[0] = ["[Enter to go on", dirty_before_evidence]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.w.count("r8_files:evidence"), 0)
        self.assertNotIn("pub_evidence", self.state()["started"])
        self.w.clean = True
        self.w.default_rules()
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.w.count("r8_files:evidence"), 2)

    def test_every_password_step_rechecks_the_tree(self):
        statuses_before = []
        original = self.w.run

        def spy(argv, **kw):
            statuses_before.append(argv)
            return original(argv, **kw)
        w = self.w
        w.run = spy
        self.go()
        for index, argv in enumerate(statuses_before):
            if argv[:7] == FW and argv[7] in ("persistence.real_install", "real_tools.identity_seed", "real_tools.loader_window", "persistence.real_workspace_store",
                                                 "real_tools.admission_probe") or (argv[0].endswith("/psql") and "-f" in argv):
                recent = [a for a in statuses_before[max(0, index - 6):index] if a[:2] == ["git", "status"]]
                self.assertTrue(recent, argv)

    def test_head_may_move_by_decision_records_only(self):
        self.w.rules[0] = ["[Enter to go on", self._move_head_at("Phase 1", ["decisions/product/PD-0084-x.md"])]
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.setUp()
        self.w.rules[0] = ["[Enter to go on", self._move_head_at("Phase 1", ["decisions/product/PD-0084-x.md", "src/persistence/real_install.py"])]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("HEAD_MOVED", "\n".join(self.w.said))
        self.assertEqual(self.w.count("real_install:phase1"), 0)

    def _move_head_at(self, title, changed):
        def enter():
            if title in [p for p in self.w.prompts if "[Enter to go on" in p][-1]:
                self.w.head, self.w.changed = "b" * 40, changed
            return ""
        return enter

    def test_a_head_that_is_not_a_descendant_of_p8_is_refused(self):
        def rewind():
            if "Phase 1" in [p for p in self.w.prompts if "[Enter to go on" in p][-1]:
                self.w.head, self.w.not_ancestor = "b" * 40, True
            return ""
        self.w.rules[0] = ["[Enter to go on", rewind]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("not a descendant", "\n".join(self.w.said))

    def test_pg_variables_and_stored_credentials_are_refused_and_never_unset(self):
        for name in ("PGPASSWORD", "PGOPTIONS", "pgservice"):
            self.w.environ[name] = "x"
            self.assertEqual(self.go(), g.EXIT_STOPPED, name)
            self.assertIn("ENV_HAS_LIBPQ_VARIABLES", "\n".join(self.w.said))
            self.assertNotIn("x", [m for m in self.w.said if "=" in m and name in m] or [""])      # names only, never values
            del self.w.environ[name]
        self.w.existing.add(str(self.home / ".pgpass"))
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("STORED_CREDENTIAL_FILE_PRESENT", "\n".join(self.w.said))

    def test_strip_pg(self):
        env = g.strip_pg({"PGPASSWORD": "a", "pgservice": "b", "PGOPTIONS": "c", "HOME": "/h", "PATH": "/p", "PYTHONPATH": "other", "PSQLRC": "d"})
        self.assertEqual(env, {"HOME": "/h", "PATH": "/p", "PSQLRC": "d", "PYTHONPATH": "src", "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1",
                               "PSQL_HISTORY": "/dev/null"})

    def test_the_first_run_freezes_the_values_and_a_different_value_later_is_refused(self):
        self.w.rules[0] = ["[Enter to go on", self._quit_after_first_step()]
        self.assertEqual(self.go("--cluster-user", "pgfin", "--port", "5444", "--release-name", "rel-1"), g.EXIT_PAUSED)
        frozen = self.state()["frozen"]
        self.assertEqual((frozen["cluster_user"], frozen["port"], frozen["release_name"], frozen["superuser"], frozen["base"]),
                         ("pgfin", 5444, "rel-1", "finweb_su", "/Users/Shared/finweb-r8-pg"))
        self.assertEqual(frozen["psql"], "/opt/homebrew/bin/psql")
        self.assertEqual(frozen["initdb"], "/opt/homebrew/bin/initdb")
        self.assertEqual(frozen["pg_ctl"], "/opt/homebrew/bin/pg_ctl")
        for argv in (["--release-name", "other"], ["--port", "5433"], ["--cluster-user", "finwebpg"], ["--base", "/Users/Shared/x"], ["--superuser", "root1"]):
            self.assertEqual(self.go(*argv), g.EXIT_STOPPED, argv)
            self.assertIn("FROZEN_CHANGED", "\n".join(self.w.said))
        self.w.rules[0] = ["[Enter to go on", ""]
        self.assertEqual(self.go("--release-name", "rel-1", "--port", "5444"), g.EXIT_DONE)       # the same values are accepted
        self.assertTrue(any("--release-name" in c.argv and "rel-1" in c.argv for c in self.w.calls))
        self.assertTrue(any(c.argv[:2] == ["/opt/homebrew/bin/psql", "-X"] and "5444" in c.argv for c in self.w.calls))

    def _quit_after_first_step(self):
        count = {"n": 0}

        def enter():
            count["n"] += 1
            if count["n"] == 2:
                raise EOFError()
            return ""
        return enter

    def test_unusable_values_are_refused_on_the_first_run(self):
        for argv in (["--port", "80"], ["--base", str(REPO / "x")], ["--base", "relative/dir"], ["--base", "/tmp/finweb"], ["--cluster-user", "Bad User"], ["--release-name", "Bad Name"],
                     ["--superuser", "x;y"]):
            self.assertEqual(self.go(*argv), g.EXIT_STOPPED, argv)
            self.assertFalse((self.state_dir / "state.json").exists(), argv)

    def test_an_existing_cluster_is_verified_not_recreated(self):
        self.w.user_exists = True
        base = "/Users/Shared/finweb-r8-pg"
        self.w.dirs = {base: ("finwebpg", 0o755), base + "/data": ("finwebpg", 0o700), base + "/sock": ("finwebpg", 0o755), base + "/log": ("finwebpg", 0o700)}
        self.w.initdb_done, self.w.hba, self.w.running = True, g.HBA_CONTENT, True
        self.w.conf = "# stock\n" + g.conf_block(5433, base + "/sock")
        self.go()
        keys = [c.key for c in self.w.calls]
        for absent in ("sudo:sysadminctl", "sudo:mkdir", "sudo:chown", "sudo:chmod", "sudo:initdb", "sudo:tee"):
            self.assertNotIn(absent, keys)
        self.assertEqual(self.state()["done"]["cluster_user"]["data"], {"created": False})

    def test_an_administrator_cluster_user_and_a_foreign_base_directory_are_refused(self):
        self.w.user_exists, self.w.user_admin = True, True
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("CLUSTER_USER_ADMIN", "\n".join(self.w.said))
        self.w.user_admin = False
        self.w.dirs = {"/Users/Shared/finweb-r8-pg": ("someoneelse", 0o755)}
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("CLUSTER_DIR_OWNER", "\n".join(self.w.said))
        self.assertEqual(self.w.count("sudo:chown"), 0)

    def test_a_data_directory_the_owners_account_can_write_is_refused(self):
        seams = self.w.seams()
        seams.can_write = lambda p: True
        self.assertEqual(g.main([], seams=seams, home=self.home, repo_root=REPO), g.EXIT_STOPPED)
        self.assertIn("CAN write the data directory", "\n".join(self.w.said))
        self.assertIsNone(self.state()["latch"])

    def test_a_failed_pg_ctl_start_says_what_to_tell_the_pm_and_does_not_latch(self):
        self.w.script["sudo:pg_ctl"] = [g.Result(3, b""), g.Result(1, b"postmaster became multithreaded\n")]
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("multithreaded", "\n".join(self.w.said))
        self.assertIsNone(self.state()["latch"])


class DecisionRecordTests(GuideCase):
    def test_git40_and_doc64_are_computed_from_the_committed_file(self):
        self.go()
        pd = self.state()["done"]["pub_pd"]["data"]
        self.assertEqual(pd["commit"], "3" * 40)
        self.assertEqual(pd["sha256"], sha(b"publish record"))
        self.assertEqual(pd["pd"], "PD-0084")
        git = [c.argv for c in self.w.calls if c.argv[0] == "git"]
        self.assertIn(["git", "log", "-1", "--format=%H", "--", PD_PATHS["publish"]], git)
        self.assertIn(["git", "show", "3" * 40 + ":" + PD_PATHS["publish"]], git)
        self.assertIn(["git", "diff", "--stat", HEAD0, "HEAD"], git)
        self.assertIn(["git", "ls-files", "--", "decisions/product/PD-0066-*.md"], git)

    def test_a_path_outside_decisions_product_or_not_committed_is_not_accepted(self):
        self.w.rules = [r for r in self.w.rules if r[0] != "Path of the committed file"] + [
            ["Path of the committed file", ["src/x.py", "decisions/product/PD-0090-nothing.md", "../decisions/product/PD-0084-x.md", PD_PATHS["publish"], PD_PATHS["withdraw"], PD_PATHS["renew"]]]]
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.state()["done"]["pub_pd"]["data"]["path"], PD_PATHS["publish"])
        self.assertIn("no commit holds", "\n".join(self.w.said))

    def test_a_record_already_used_for_another_stage_is_not_accepted(self):
        self.w.rules = [r for r in self.w.rules if r[0] != "Path of the committed file"] + [
            ["Path of the committed file", [PD_PATHS["publish"], PD_PATHS["publish"], PD_PATHS["withdraw"], PD_PATHS["renew"]]]]
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertIn("already used", "\n".join(self.w.said))


class PromptAndLatchHardeningTests(GuideCase):
    """Added in the review of the draft: the stdin of the children, the password-step list, and a create whose outcome may be lost."""

    set_create = CreateTests.set_create

    def test_vite_has_no_terminal_stdin_and_the_launcher_keeps_it(self):
        self.go()
        spawned = [c for c in self.w.calls if hasattr(c, "stdin_null")]
        self.assertTrue(spawned)
        for call in spawned:
            self.assertEqual(call.stdin_null, call.argv[0] == VITE_BIN, call.argv)

    def test_the_default_spawn_gives_vite_devnull_and_the_launcher_the_terminal(self):
        seen = []

        class FakePopen:
            def __init__(self, argv, **kw):
                seen.append(kw["stdin"])
                self.stdout = mock.Mock(fileno=lambda: 99)
        with mock.patch.object(g.subprocess, "Popen", FakePopen), mock.patch.object(g.os, "read", lambda fd, n: b""), mock.patch.object(g.sys, "stdout"):
            g._Spawned(["a"], {}, None)
            g._Spawned(["b"], {}, None, True)
        self.assertEqual(seen, [None, g.subprocess.DEVNULL])

    def test_the_cluster_user_and_initdb_steps_recheck_the_tree(self):
        steps = {d.sid: d for d, _ in g.Guide(self.w.seams(), self.home, REPO).steps}
        for sid in ("cluster_user", "cluster_initdb"):
            self.assertTrue(steps[sid].password, sid)

    def test_a_quit_after_the_create_may_have_happened_is_not_forgotten(self):
        self.w.rules = [r for r in self.w.rules if r[0] != "Status of the create's response"] + [["Status of the create's response", lambda: (_ for _ in ()).throw(EOFError())]]
        self.assertEqual(self.go(), g.EXIT_PAUSED)
        self.assertEqual(self.state()["create_pending"], "create_a")
        self.w.default_rules()
        asked = []
        self.w.rules.insert(0, ["Did you click Create in that earlier run", lambda: asked.append(1) or "yes"])
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(asked, [1])
        self.assertIsNone(self.state()["create_pending"])

    def test_a_stop_outcome_without_its_latch_latches_on_the_next_run(self):
        self.set_create(["503"], ["-"])
        self.go()
        self.state_edit(lambda s: s.update({"latch": None}))
        self.assertEqual(self.go(), g.EXIT_LATCHED)
        self.assertIsNotNone(self.state()["latch"])

    def state_edit(self, fn):
        s = self.state()
        fn(s)
        (self.state_dir / "state.json").write_text(json.dumps(s))



class MistypedPasswordTests(GuideCase):
    """PM 2026-11-15: a mistyped password may be retried (sudo, psql login, psql \\password), at most 3 times per step, by the owner's choice; every other
    failure, including each reviewed tool's connect failure (none prints the server's text), still latches."""

    AUTH = g.Result(2, b'psql: error: connection to server on socket "/x/.s.PGSQL.5433" failed: FATAL:  password authentication failed for user "finweb_su"\n')
    MISMATCH = g.Result(3, b"Passwords didn't match.\n")
    DOWN = g.Result(2, b'psql: error: connection to server on socket "/x/.s.PGSQL.5433" failed: No such file or directory\n')
    SUDO = g.Result(1, b"Sorry, try again.\nSorry, try again.\nsudo: 3 incorrect password attempts\n")

    def answers(self, values):
        self.w.rules.insert(0, ["Retry after a mistyped password", list(values)])

    def test_a_refused_login_and_a_password_mismatch_may_be_retried_and_are_recorded_without_content(self):
        self.w.script["psql:passwords.sql"] = [self.AUTH, self.MISMATCH]
        self.answers(["y", "y"])
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.w.count("psql:passwords.sql"), 3)
        failed = [r for r in self.state()["records"] if r["item"].startswith("failed attempt")]
        self.assertEqual([r["item"] for r in failed], ["failed attempt 1 at passwords", "failed attempt 2 at passwords"])
        for r in failed:
            self.assertTrue(r["at"])
            self.assertEqual(set(r), {"item", "value", "at", "step"})
        self.assertIn("failed attempt 1 at passwords", (self.state_dir / "R8_RECORD.md").read_text())

    def test_sudo_after_three_wrong_passwords_may_be_retried(self):
        self.w.script["sudo:mkdir"] = [self.SUDO]
        self.answers(["y"])
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.w.count("sudo:mkdir"), 2)

    def test_declining_the_retry_stops_without_a_latch(self):
        self.w.script["psql:passwords.sql"] = [self.AUTH]
        self.answers(["n"])
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIsNone(self.state()["latch"])
        self.assertEqual(self.w.count("psql:passwords.sql"), 1)

    def test_a_connect_failure_that_is_not_an_authentication_failure_is_not_retried(self):
        self.w.script["psql:passwords.sql"] = [self.DOWN]
        self.answers(["y"])
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.w.count("psql:passwords.sql"), 1)       # no retry offered
        self.assertFalse(any("Retry after" in p for p in self.w.prompts))

    def test_a_reviewed_tool_connect_failure_still_latches(self):
        text = b"REFUSED PF_CONNECT_FAILED (OperationalError): the installer's own connection failed; nothing was changed by this step\n"
        self.w.script["real_install:phase1"] = [g.Result(2, text)]
        self.answers(["y"])
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIsNotNone(self.state()["latch"])
        self.assertFalse(any("Retry after" in p for p in self.w.prompts))

    def test_the_fourth_failure_latches(self):
        self.w.script["psql:passwords.sql"] = [self.AUTH] * 4
        self.answers(["y"] * 3)
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.state()["latch"]["code"], "PASSWORD_RETRIES_EXHAUSTED")
        self.assertEqual(self.w.count("psql:passwords.sql"), 4)
        self.assertEqual(self.go(), g.EXIT_LATCHED)

    # ---- the reviewed tools: "own connection failed, nothing was sent" (PM, 2026-11-15) ----
    TOOL_LINES = {
        "real_install:phase0": b"REFUSED PF_CONNECT_FAILED (OperationalError): the installer's own connection failed; nothing was changed by this step\n",
        "real_install:check": b"REFUSED PF_CONNECT_FAILED (OperationalError): the installer's own connection failed; nothing was changed by this step\n",
        "identity_seed": b"REFUSED PF_CONNECT_FAILED (OperationalError): the seed's connection or statement failed; the seed is one transaction, so nothing was written\n",
        "real_install:phase2": b"REFUSED PF_CONNECT_FAILED (OperationalError): the installer's own connection failed; nothing was changed by this step\n",
        "loader_window:load": b"REFUSED LOADER_CONNECT_FAILED PF_CONNECT_FAILED. Nothing was sent.\n",
        "loader_window:register-bound": b"REFUSED LOADER_CONNECT_FAILED PF_CONNECT_FAILED. Nothing was sent.\n",
        "admission_probe": b"REFUSED PROBE_CONNECT_FAILED PF_CONNECT_FAILED. Nothing was sent.\n",
        "store:publish": b"refused: RW_CONNECT_FAILED  (PF_CONNECT_FAILED OperationalError)\nnothing was recorded\n",
        "store:withdraw": b"refused: RW_CONNECT_FAILED  (PF_CONNECT_FAILED OperationalError)\nnothing was recorded\n",
        "store:renew": b"refused: RW_CONNECT_FAILED  (PF_CONNECT_FAILED OperationalError)\nnothing was recorded\n",
    }

    def test_each_tool_family_may_retry_its_own_connection_failure(self):
        for key, text in self.TOOL_LINES.items():
            with self.subTest(key=key):
                self.setUp()
                self.w.script[key] = [g.Result(2, text)]
                self.answers(["y"])
                self.assertEqual(self.go(), g.EXIT_DONE)
                self.assertEqual(self.w.count(key), {"real_install:check": 3, "admission_probe": 4}.get(key, 2))       # check: one per window; the probe runs three times
                self.assertIsNone(self.state()["latch"])
                failed = [r for r in self.state()["records"] if r["item"].startswith("failed attempt")]
                self.assertEqual(len(failed), 1)
                self.assertIn("CONNECT_FAILED", failed[0]["value"])
                said = "\n".join(self.w.said)
                if key == "identity_seed":          # TR8G-L-1: the seed's line does not say nothing was sent; the question says it was rolled back
                    self.assertIn("failed and was rolled back", said)
                    self.assertNotIn("nothing was sent", said)
                else:
                    self.assertIn("nothing was sent", said)
                self.assertIn("A mistyped password is the usual cause", said)

    def test_pf_require_auth_is_a_refusal_not_a_typo_and_latches(self):
        line = b"REFUSED PF_REQUIRE_AUTH (OperationalError): the installer's own connection failed; nothing was changed by this step\n"
        self.assertIsNone(g.own_connection_failure(FW + ["persistence.real_install", "check"], 2, line.decode()))
        self.w.script["real_install:check"] = [g.Result(2, line)]
        self.answers(["y"])
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIsNotNone(self.state()["latch"])
        self.assertFalse(any("Retry after" in p for p in self.w.prompts))

    def test_the_launcher_may_retry_its_own_connection_failure(self):
        self.w.launcher_script = [(2, b"REFUSED LAUNCH_CONNECT_FAILED. Nothing was started and nothing was written.\nPF_CONNECT_FAILED\n")]
        self.answers(["y"])
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(sum(1 for c in self.w.calls if hasattr(c, "stdin_null") and c.argv[0] != VITE_BIN) >= 2, True)
        self.assertIsNone(self.state()["latch"])

    def test_the_launcher_account_role_connect_failure_may_be_retried_but_a_role_refusal_latches(self):
        self.w.launcher_script = [(2, b"REFUSED LAUNCH_ACCOUNT_ROLE. Nothing was started and nothing was written.\nOperationalError\n")]
        self.answers(["y"])
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertIsNone(self.state()["latch"])
        self.setUp()
        self.w.launcher_script = [(2, b"REFUSED LAUNCH_ACCOUNT_ROLE. Nothing was started and nothing was written.\nUNSAFE_DATABASE_ROLE\n")]
        self.answers(["y"])
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.state()["latch"]["step"], "create")

    def test_a_started_launcher_does_not_count(self):
        self.assertIsNone(g.own_connection_failure(FW + ["web_api.real_launcher", "--socket", "x"], 2, "real-mode app: x\nREFUSED LAUNCH_CONNECT_FAILED. Nothing was started and "
                                                   "nothing was written.\nPF_CONNECT_FAILED"))

    def test_phase1_latches_on_a_connect_failure(self):
        for key, text in (("real_install:phase1", self.TOOL_LINES["real_install:phase0"]),):
            with self.subTest(key=key):
                self.setUp()
                self.w.script[key] = [g.Result(2, text)]
                self.answers(["y"])
                self.assertEqual(self.go(), g.EXIT_STOPPED)
                self.assertIsNotNone(self.state()["latch"])
                self.assertFalse(any("Retry after" in p for p in self.w.prompts))

    def test_a_code_that_is_not_the_tools_own_connect_failure_line_does_not_count(self):
        f = g.own_connection_failure
        loader = ["uv", "run", "--no-sync", "--frozen", "--offline", "python", "-m", "real_tools.loader_window", "load"]
        line = "REFUSED LOADER_CONNECT_FAILED PF_CONNECT_FAILED. Nothing was sent."
        self.assertEqual(f(loader, 2, line + "\n"), "LOADER_CONNECT_FAILED PF_CONNECT_FAILED")
        for code, text in ((2, "note: " + line), (2, line + " and more"), (4, line), (0, line), (2, "REFUSED LOADER_CONNECT_FAILED PF_OTHER. Nothing was sent."),
                           (2, "REFUSED PROBE_CONNECT_FAILED PF_CONNECT_FAILED. Nothing was sent.")):
            self.assertIsNone(f(loader, code, text), (code, text))
        install_phase1 = loader[:7] + ["persistence.real_install", "phase1"]
        self.assertIsNone(f(install_phase1, 2, "REFUSED PF_CONNECT_FAILED (OperationalError): the installer's own connection failed; nothing was changed by this step"))

    def test_the_fourth_tool_connect_failure_latches(self):
        self.w.script["loader_window:load"] = [g.Result(2, self.TOOL_LINES["loader_window:load"])] * 4
        self.answers(["y"] * 3)
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.state()["latch"]["code"], "PASSWORD_RETRIES_EXHAUSTED")
        self.assertEqual(self.w.count("loader_window:load"), 4)
        self.assertEqual(self.go(), g.EXIT_LATCHED)

    def test_the_classifier_is_narrow(self):
        f = g.Guide.mistyped_password
        self.assertIsNotNone(f(["/x/psql"], self.AUTH))
        self.assertIsNone(f(["/x/psql"], g.Result(1, b"password authentication failed")))
        self.assertIsNone(f(["uv", "run"], self.AUTH))
        self.assertIsNone(f(["/usr/bin/sudo", "x"], g.Result(1, b"anything else")))


class ReviewFindingsTests(GuideCase):
    """TR8G-H-1, M-1, M-2, M-4, L-2 and L-3 (the independent review of the runner)."""

    set_create = CreateTests.set_create

    def state_edit(self, fn):
        s = self.state()
        fn(s)
        (self.state_dir / "state.json").write_text(json.dumps(s))

    # ---- H-1 ----
    def test_h1_an_interrupt_or_eof_during_the_window_close_leaves_the_latch_saved(self):
        for exc in (KeyboardInterrupt(), EOFError()):
            with self.subTest(exc=type(exc).__name__):
                self.setUp()
                self.w.script["loader_window:load"] = [g.Result(2, b"REFUSED\n")]
                self.w.raise_on["psql:window_close.sql"] = exc
                self.assertEqual(self.go(), g.EXIT_STOPPED)
                self.assertIsNotNone(self.state()["latch"])
                self.assertTrue(self.state()["window"]["open"])
                self.assertIn("latch", [e["kind"] for e in self.events()])
                self.assertIn(g.CLOSE_COMMAND, "\n".join(self.w.said))                 # M-1: prominent, with the exact command
                self.w.said.clear()
                self.assertEqual(self.go(), g.EXIT_LATCHED)                              # a plain re-run refuses
                self.assertEqual(self.w.count("loader_window:load"), 1)
                self.assertIn(g.CLOSE_COMMAND, "\n".join(self.w.said))
                self.w.said.clear()
                self.go("--status")
                self.assertIn(g.CLOSE_COMMAND, "\n".join(self.w.said))

    # ---- M-1 ----
    def test_m1_exhausted_retries_at_a_window_step_close_the_window_then_latch(self):
        self.w.script["loader_window:load"] = [g.Result(2, NOT_LOGIN)] * 4
        self.w.rules.insert(0, ["Retry after a mistyped password", ["y", "y", "y"]])
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.state()["latch"]["code"], "PASSWORD_RETRIES_EXHAUSTED")
        self.assertEqual(self.w.count("psql:window_close.sql"), 1)
        self.assertFalse(self.state()["window"]["open"])
        self.assertFalse(self.w.loader_login)

    # ---- M-2 ----
    def test_m2_a_step_that_needs_the_window_never_runs_against_a_closed_one(self):
        quit_once = {"done": False}

        def enter():
            if not quit_once["done"] and "The load" in [p for p in self.w.prompts if "[Enter to go on" in p][-1]:
                quit_once["done"] = True
                raise EOFError()
            return ""
        self.w.rules[0] = ["[Enter to go on", enter]
        self.assertEqual(self.go(), g.EXIT_PAUSED)
        self.assertTrue(self.w.loader_login)
        self.w.default_rules()
        self.assertEqual(self.go("--close-window"), g.EXIT_DONE)
        self.assertFalse(self.w.loader_login)
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertEqual(self.w.count("psql:window_open.sql"), 3)         # window 1, window 1 again, window 2
        self.assertEqual(self.w.count("real_install:check"), 3)
        self.assertEqual([e["window"] for e in self.events() if e["kind"] == "window_reopen"], [1])

    # ---- M-4 ----
    def test_m4_a_decision_record_that_existed_before_p8_is_refused_for_each_stage(self):
        old = "decisions/product/PD-0066-hg4-single-date-check-morning-decisions.md"
        self.w.rules = [r for r in self.w.rules if r[0] != "Path of the committed file"] + [
            ["Path of the committed file", [old, PD_PATHS["publish"], old, PD_PATHS["withdraw"], old, PD_PATHS["renew"]]]]
        self.assertEqual(self.go(), g.EXIT_DONE)
        shown = "\n".join(self.w.said)
        self.assertEqual(shown.count("not accepted: " + old + " was not added in a commit after P8"), 3)
        self.assertEqual(self.state()["done"]["pub_pd"]["data"]["path"], PD_PATHS["publish"])

    def test_re_review_l1_l3_a_reset_record_is_not_a_stage_record_and_stage_records_use_the_first_p8(self):
        self.w.script["loader_window:load"] = [g.Result(2, b"REFUSED\n")]
        self.go()
        self.w.head = "b" * 40
        self.assertEqual(self.go("--reset-stop", "PD-0090"), g.EXIT_DONE)
        self.assertEqual(self.state()["p8"]["commit"], "b" * 40)
        self.w.rules = [r for r in self.w.rules if r[0] != "Path of the committed file"] + [
            ["Path of the committed file", [RESET_PD, PD_PATHS["publish"], PD_PATHS["withdraw"], PD_PATHS["renew"]]]]
        self.w.range_log.clear()
        self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertIn("%s was already used for an earlier stage" % RESET_PD, "\n".join(self.w.said))
        self.assertEqual(self.state()["done"]["pub_pd"]["data"]["path"], PD_PATHS["publish"])
        stage = [r for p, r in self.w.range_log if p in PD_PATHS.values()]
        self.assertEqual(set(stage), {HEAD0 + "..HEAD"})                   # the FIRST P8, not the one after the reset

    def test_re_review_l2_a_log_without_a_state_file_is_never_started_over(self):
        self.w.rules.insert(0, ["Type the holding value", lambda: (_ for _ in ()).throw(EOFError())])
        self.go()
        (self.state_dir / "state.json").unlink()
        calls = len(self.w.calls)
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("STATE_MISSING", "\n".join(self.w.said))
        self.assertFalse((self.state_dir / "state.json").exists())
        self.assertEqual(len(self.w.calls), calls)                          # no child was started
        self.assertEqual(self.go("--status"), g.EXIT_STOPPED)

    def test_re_review_l2_status_with_a_missing_log_reports_it_plainly(self):
        self.w.rules.insert(0, ["Type the holding value", lambda: (_ for _ in ()).throw(EOFError())])
        self.go()
        (self.state_dir / "events.log").unlink()
        self.w.said.clear()
        self.assertEqual(self.go("--status"), g.EXIT_STOPPED)
        self.assertIn("EVENTS_LOG_MISSING", "\n".join(self.w.said))

    def test_m4_the_decision_record_path_pattern_is_exact(self):
        for good in ("decisions/product/PD-0084-r8-publish.md", "decisions/product/PD-0001-a.md"):
            self.assertIsNotNone(g._PD_PATH.fullmatch(good), good)
        for bad in ("decisions/product/PD-84-x.md", "decisions/product/PD-0084-x.md.bak", "decisions/product/sub/PD-0084-x.md", "decisions/product/PD-0084-.md",
                    "decisions/product/../src/PD-0084-x.md", "/decisions/product/PD-0084-x.md", "decisions/product/PD-0084-x.md\n", "docs/PD-0084-x.md", "decisions/product/PD-0084.md"):
            self.assertIsNone(g._PD_PATH.fullmatch(bad), bad)

    # ---- L-2 ----
    def test_l2a_a_2xx_under_the_withdrawal_is_a_stop(self):
        self.set_create(["201", "201"], ["-", "RW_WITHDRAWN"])
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.state()["latch"]["step"], "c1_refusals")
        self.assertIn("rights were not revoked", self.state()["latch"]["message"])

    def test_l2b_a_no_at_an_approval_is_recorded_and_latches(self):
        for answers, code in ((["no"], "QUALIFY_NOT_APPROVED"), (["approve", "no"], "PROPOSAL_NOT_APPROVED")):
            with self.subTest(code=code):
                self.setUp()
                self.w.rules.insert(0, ["(type approve)", list(answers)])
                self.assertEqual(self.go(), g.EXIT_STOPPED)
                self.assertEqual(self.state()["latch"]["code"], code)
                self.assertTrue(any("NOT approved" in r["item"] for r in self.state()["records"]))
                self.assertEqual(self.go(), g.EXIT_LATCHED)

    def test_l2c_the_record_comes_from_the_append_only_log_and_survives_a_hand_edit_of_the_state(self):
        self.set_create(["422", "201", "409", "201"], ["REAL_REQUEST_INVALID", "-", "RW_WITHDRAWN", "-"])
        fired = {"n": 0}

        def interrupt():
            fired["n"] += 1
            if fired["n"] == 1:
                raise EOFError()
            return "1234.50"
        self.w.rules.insert(0, ["Type the holding value", interrupt])
        self.assertEqual(self.go(), g.EXIT_PAUSED)
        self.state_edit(lambda s: s.update({"creates": [], "records": [], "commands": []}))        # a hand edit
        self.assertEqual(self.go(), g.EXIT_DONE)
        record = (self.state_dir / "R8_RECORD.md").read_text()
        self.assertIn("create_a: status 422, code REAL_REQUEST_INVALID, RETRY", record)
        self.assertIn("P8", record)
        self.assertIn("-> 0", record)

    def test_l2c_a_redo_leaves_a_trace_and_the_log_is_append_only_and_private(self):
        self.set_create(["503", "201", "409", "201"], ["-", "-", "RW_WITHDRAWN", "-"])
        self.w.rules = [r for r in self.w.rules if r[0] != "Is that exactly"] + [["Is that exactly", ["redo", "yes", "yes", "yes"]]]
        flags = []
        real_open = os.open

        def spy(path, flags_, *a, **k):
            if str(path).endswith("events.log"):
                flags.append(flags_)
            return real_open(path, flags_, *a, **k)
        with mock.patch.object(g.os, "open", spy):
            self.assertEqual(self.go(), g.EXIT_DONE)
        self.assertTrue(flags)
        for f in flags:
            self.assertTrue(f & os.O_APPEND and f & os.O_WRONLY and not f & (os.O_TRUNC | os.O_RDWR), f)
        self.assertEqual(stat.S_IMODE((self.state_dir / "events.log").stat().st_mode), 0o600)
        self.assertEqual([e["kind"] for e in self.events()].count("redo"), 1)
        self.assertIn("typed, then withdrawn with redo", (self.state_dir / "R8_RECORD.md").read_text())

    def test_l2c_a_latch_the_state_and_the_log_disagree_about_is_refused(self):
        self.w.script["loader_window:load"] = [g.Result(2, b"REFUSED\n")]
        self.go()
        self.state_edit(lambda s: s.update({"latch": None}))              # erased by hand: the log wins
        self.assertEqual(self.go(), g.EXIT_LATCHED)
        self.assertIsNotNone(self.state()["latch"])
        self.setUp()
        self.w.rules.insert(0, ["Type the holding value", lambda: (_ for _ in ()).throw(EOFError())])
        self.go()
        self.state_edit(lambda s: s.update({"latch": {"code": "X", "message": "m", "step": "s", "at": "t", "head": None}}))       # added by hand: the log does not know it
        self.assertEqual(self.go(), g.EXIT_LATCHED)
        self.assertIn("holds a stop that events.log does not", "\n".join(self.w.said))

    def test_l2c_a_missing_log_is_refused(self):
        self.w.rules.insert(0, ["Type the holding value", lambda: (_ for _ in ()).throw(EOFError())])
        self.go()
        (self.state_dir / "events.log").unlink()
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("EVENTS_LOG_MISSING", "\n".join(self.w.said))

    def test_l2d_vite_is_the_installed_binary_and_a_missing_one_refuses_before_the_launcher(self):
        self.w.vite_installed = False
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertIn("VITE_MISSING", "\n".join(self.w.said))
        self.assertFalse(any(c.argv[0] == VITE_BIN or "real_launcher" in " ".join(c.argv) for c in self.w.calls))
        self.assertIsNone(self.state()["latch"])
        self.w.vite_installed = True
        self.assertEqual(self.go(), g.EXIT_DONE)

    # ---- L-3: the mutants that survived ----
    def test_l3_the_tree_is_rechecked_before_a_retry(self):
        self.w.script["psql:passwords.sql"] = [MistypedPasswordTests.AUTH]
        self.w.rules.insert(0, ["Retry after a mistyped password", lambda: setattr(self.w, "clean", False) or "y"])
        self.assertEqual(self.go(), g.EXIT_STOPPED)
        self.assertEqual(self.w.count("psql:passwords.sql"), 1)
        self.assertIn("TREE_NOT_CLEAN", "\n".join(self.w.said))

    def test_l3_sudo_is_retryable_only_on_its_own_exit_status_and_text(self):
        f = g.Guide.mistyped_password
        text = b"Sorry, try again.\nsudo: 3 incorrect password attempts\n"
        self.assertIsNotNone(f(["/usr/bin/sudo", "x"], g.Result(1, text)))
        for code in (0, 2, 4, 126):
            self.assertIsNone(f(["/usr/bin/sudo", "x"], g.Result(code, text)), code)
        self.assertIsNone(f(["/usr/bin/sudo", "x"], g.Result(1, b"Sorry, try again.\n")))


class RealRunTests(unittest.TestCase):
    """The default `run` seam: stdin is the terminal (not a pipe) unless data is given, stdout and stderr are captured, nothing else."""

    def test_the_default_run_captures_output_and_leaves_stdin_to_the_terminal(self):
        calls = {}

        class FakePopen:
            def __init__(self, argv, **kw):
                calls.update(kw)
                self.stdout = mock.Mock(fileno=lambda: 99)
                self.stdin = mock.Mock()

            def wait(self):
                return 7
        reads = [b"prompt-free output\n", b""]
        with mock.patch.object(g.subprocess, "Popen", FakePopen), mock.patch.object(g.os, "read", lambda fd, n: reads.pop(0)), mock.patch.object(g.sys, "stdout") as out:
            result = g._real_run(["x"], env={"A": "b"})
        self.assertEqual((result.code, result.out), (7, b"prompt-free output\n"))
        self.assertIsNone(calls["stdin"])
        self.assertEqual(calls["stdout"], g.subprocess.PIPE)
        self.assertEqual(calls["stderr"], g.subprocess.STDOUT)
        self.assertEqual(calls["env"], {"A": "b"})
        out.write.assert_called_with("prompt-free output\n")
        self.assertNotIn("shell", calls)

    def test_a_real_child_is_captured_and_echoed(self):
        with mock.patch.object(g.sys, "stdout") as out:
            result = g._real_run([sys.executable, "-c", "import sys; print('hello'); print('err', file=sys.stderr); sys.exit(3)"], env=dict(os.environ))
        self.assertEqual(result.code, 3)
        self.assertEqual(sorted(result.text.split()), ["err", "hello"])
        self.assertTrue(out.write.called)

    def test_stdin_data_is_piped_only_when_given(self):
        result = g._real_run([sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read().upper())"], env=dict(os.environ), stdin_data=b"abc", echo=False)
        self.assertEqual(result.out, b"ABC")

    def test_a_missing_program_is_a_127_not_a_crash(self):
        self.assertEqual(g._real_run(["/nonexistent/x"], env={}, echo=False).code, 127)

    def test_the_runbook_scripts_do_not_carry_a_password(self):
        for text in (g.SCRIPT_PASSWORDS, g.SCRIPT_OPEN, g.SCRIPT_CLOSE, g.SCRIPT_OWNER_ID):
            self.assertNotRegex(text.lower(), r"password\s+'|password\s*=|encrypted password")
        for role in (g.ROLE_PUBLISHER, g.ROLE_EXECUTOR, g.ROLE_ACCOUNT, g.ROLE_LOADER):
            self.assertIn(role, g.SCRIPT_PASSWORDS + g.SCRIPT_OPEN)

    def test_the_roles_and_database_equal_the_installers(self):
        from persistence import real_preflight as pf
        self.assertEqual((g.ROLE_PUBLISHER, g.ROLE_EXECUTOR, g.ROLE_ACCOUNT, g.ROLE_LOADER), (pf.REAL_ROLES["publisher"], pf.REAL_ROLES["executor"], pf.REAL_ROLES["account"],
                                                                                              pf.REAL_ROLES["loader"]))
        self.assertEqual((g.DATABASE, g.SCHEMA), (pf.REAL_DATABASE, pf.REAL_SCHEMA))
        self.assertEqual(g.EXIT_DONE, 0)

    def test_the_markers_parse(self):
        self.assertEqual(g.parse_marker("  R8_MARK login_set_at=2026-11-15T02:00:00Z\n(1 row)", "login_set_at"), "2026-11-15T02:00:00Z")
        self.assertIsNone(g.parse_marker("nothing", "owner_id"))


if __name__ == "__main__":
    unittest.main()
