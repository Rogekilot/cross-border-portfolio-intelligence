"""F1 R8: the GUIDED RUNNER for the owner's R8 run (`reviews/R8_RUNBOOK.md` sections 2 to 12; `implementation/CP7_F1_R8_GUIDED_RUNNER.md`).

    uv run --no-sync --frozen --offline python -m real_tools.r8_guide          (from the repository root; run it again to resume)

THE RUNNER DOES THE MECHANICS AND DECIDES NOTHING. It walks the runbook in order, runs the REVIEWED tools with the runbook's command lines, copies the values
one step prints into the next step, runs the loader windows' psql sessions, and records every time and exit status. The owner still types every password,
approves the proposal, writes and commits the decision records, and clicks through the screen.

WHAT IT NEVER DOES. It never reads, holds, forwards or logs a password: it has no `getpass`, asks no password question, passes nothing on argv or in the
environment, and never uses `PGPASSWORD`, a passfile or a service file. Every password is typed at a reviewed prompt (the tools' `terminal_prompt`, psql's
`\\password` and connection prompt, `initdb --pwprompt`, `sudo`), which read from the controlling terminal (`/dev/tty`), so a child's stdout can be captured
and parsed without touching them. It opens no database connection (only psql and the tools do), never creates a `finweb_real*` database (Phase 1 does), and
writes nothing inside the repository: everything it writes is under `~/finweb-r8/` (directory 0700, files 0600). The tools are invoked, not changed.

STOP RULES ARE CODE. Runbook rule 0.3 (the create; PD-0083: only `422 REAL_REQUEST_INVALID` and `404` may be corrected and retried) and rule 0.4 (any
installer refusal and any exit status the runbook does not cover) write a LATCH into the state file. While it is there every run refuses; only
`--reset-stop PD-NNNN`, after a reviewed fix is committed and the owner's decision record for it is committed, lifts it. A loader window is never left
open after a definite answer; an unknown answer keeps it open as the runbook says.

Exit status of the runner: 0 finished, 1 paused (run it again), 2 stopped or refused (this run), 3 refused because a stop latch is set.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import socket
import stat as stat_module
import subprocess
import sys
import threading
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

STATE_SCHEMA = "finweb.r8_guide_state/1"
STATE_NAME = "state.json"
EVENTS_NAME = "events.log"      # append-only; R8_RECORD.md is built from it, and a latch in the state must agree with it
CLOSE_COMMAND = "PYTHONPATH=src uv run --no-sync --frozen --offline python -m real_tools.r8_guide --close-window"
WINDOW_STEPS = {"w1_check": 1, "w1_load": 1, "w2_check": 2, "w2_register": 2}      # steps that need the loader to be LOGIN
VITE_BIN = "node_modules/.bin/vite"                                                  # under web/; never npx (it may download)
PY_STATES = ("STOP", "UNEXPECTED")
EXIT_DONE, EXIT_PAUSED, EXIT_STOPPED, EXIT_LATCHED = 0, 1, 2, 3

# ---- the runbook's fixed values ---------------------------------------------------------------------------------------------------------------
DEFAULTS = {"cluster_user": "finwebpg", "base": "/Users/Shared/finweb-r8-pg", "port": 5433, "superuser": "finweb_su", "release_name": "hg4-aapl-2026-09-30"}
DATABASE, SCHEMA = "finweb_real", "finweb"
ROLE_PUBLISHER, ROLE_EXECUTOR, ROLE_ACCOUNT, ROLE_LOADER = "finweb_real_publisher", "finweb_real_executor", "finweb_real_account", "finweb_real_loader"
FW = ("uv", "run", "--no-sync", "--frozen", "--offline", "python", "-m")
FILE_SHAS = ("066c65e6e7ce61c06f1f413b3e313f1b797fc9fff632ce2a2f2ca4b8b1b9d1fb", "b2aaeb7b71166529ffcc597773eff7a918e999ad5107df3c83c0fb42889c3ccc",
             "4f21b26b5f8b4d88e665808f6488424c088b91733621869192784efb3d5f72ef")
SIDECARS = ("data/marketdata/sidecars/alphavantage.us/quote/2026-10-01/AAPL_compact.csv.sidecar.json",
            "data/marketdata/sidecars/openfigi/identity/2026-10-23/AAPL_UW.json.sidecar.json",
            "data/marketdata/sidecars/calendar.manual/calendar/2026-10-02/NYSE_2025_2026.json.sidecar.json")
VALID_UNTIL = "2027-08-31T16:00:00Z"          # = 2027-09-01 00:00 Asia/Shanghai (runbook 7.3; never 2027-09-01T00:00:00Z)
ACTOR = "designated human product owner"
LAUNCHER_PORT, VITE_PORT = 8004, 5175
SCREEN_URL = "http://127.0.0.1:%d/real.html" % VITE_PORT
EXPECTED_LISTING_ID = "8dc364a1-67c8-5d46-8654-cff17ebe25de"      # runbook 9 item 4 (a fixed uuid5, not vendor data)
FORM_FIXED = (("As-of date", "2026-09-30"), ("Quantity", "10"), ("Opening cash", "500 (USD, the reporting currency)"))
EVIDENCE_PDS = (("alphavantage", "PD-0066"), ("openfigi", "PD-0068"), ("calendar", "PD-0068"))
MAX_LOADER_TRIES = 6
MAX_PW_RETRIES = 3          # per step; the next mistyped password latches
#: Stops that come before a step has started anything, so that a later run may run the step again.
PRE_EFFECT_CODES = frozenset(("TREE_NOT_CLEAN", "GIT_HEAD", "HEAD_MOVED", "GIT_REF", "EVIDENCE_PD", "PD_REUSED", "PORT_IN_USE", "VITE_MISSING"))

#: THE QUANT'S EXPECTED VALUES for the NAV check: `methodology/CP7_F1_O7_CLAIM_LINEAGE_RULING_2026-11-10.md` section 9.1, "Key-figure values" (close c;
#: holding 10 x c; NAV 10 x c + 500 USD; PUBLIC COPY: the vendor values are redacted (PD-0083) and the constants below are INVENTED) and "Missed sessions and freshness" (0; state AVAILABLE). They are not computed here and
#: not read from the payload or the code under test. THE CLOSE IS NOT COMPARED (PD-0087 item 2): the screen states `10 x p` symbolically and shows no price
#: (ruling section 8 item 4; DR-R8-2), and the client never derives p (P1), so the check compares only the figures the screen states.
QUANT_NUMBERS = (("holding", Decimal("1234.50")), ("nav", Decimal("1734.50")), ("missed_sessions", Decimal("0")))
QUANT_STATE = "AVAILABLE"

# ---- macOS cluster (the owner's sheet, block B) -----------------------------------------------------------------------------------------------
SUDO, SYSADMINCTL, MKDIR, CHOWN, CHMOD, TEE, CAT, TEST, ID = ("/usr/bin/sudo", "/usr/sbin/sysadminctl", "/bin/mkdir", "/usr/sbin/chown", "/bin/chmod", "/usr/bin/tee",
                                                           "/bin/cat", "/bin/test", "/usr/bin/id")
HBA_CONTENT = "local   all   all   scram-sha-256\n"
CONF_MARK = "# R8 settings (later lines override earlier ones)\n"
DIR_MODES = (("base", 0o755), ("data", 0o700), ("sock", 0o755), ("log", 0o700))


def conf_block(port, sockdir):
    return (CONF_MARK + "listen_addresses = ''\nport = %d\nunix_socket_directories = '%s'\npassword_encryption = scram-sha-256\nmax_prepared_transactions = 0\n"
            "log_statement = 'none'\nlog_min_duration_statement = -1\n" % (port, sockdir))


# ---- the psql scripts (constants; no password, no secret) ---------------------------------------------------------------------------------------
SCRIPT_PASSWORDS = "\\password %s\n\\password %s\n\\password %s\n" % (ROLE_PUBLISHER, ROLE_EXECUTOR, ROLE_ACCOUNT)
_UTC_NOW = "to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"')"
SCRIPT_OPEN = ("ALTER ROLE %s LOGIN;\nSELECT 'R8_MARK login_set_at=' || %s;\n\\password %s\n" % (ROLE_LOADER, _UTC_NOW, ROLE_LOADER))
SCRIPT_CLOSE = ("ALTER ROLE %(r)s NOLOGIN;\n"
                "SELECT pid, backend_start FROM pg_stat_activity WHERE usename = '%(r)s';\n"
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = '%(r)s';\n"
                "SELECT pid, pg_terminate_backend(pid) FROM pg_stat_activity WHERE usename = '%(r)s' \\watch i=1 c=30 min_rows=1\n"
                "SELECT 'R8_MARK loader_sessions_left=' || count(*) || ' at=' || %(t)s FROM pg_stat_activity WHERE usename = '%(r)s';\n"
                % {"r": ROLE_LOADER, "t": _UTC_NOW})
SCRIPT_OWNER_ID = "SELECT 'R8_MARK owner_id=' || user_id::text FROM finweb.web_identity WHERE username = :'username';\n"

_HEX64, _HEX40 = re.compile(r"[0-9a-f]{64}\Z"), re.compile(r"[0-9a-f]{40}\Z")
_PD_PATH = re.compile(r"decisions/product/(PD-\d{4})-[A-Za-z0-9][A-Za-z0-9._-]*\.md\Z")
_USERNAME = re.compile(r"[A-Za-z0-9._@-]{1,64}\Z")


# ---- the seams --------------------------------------------------------------------------------------------------------------------------------
@dataclasses.dataclass
class Result:
    code: int
    out: bytes = b""

    @property
    def text(self):
        return self.out.decode("utf-8", "replace")


@dataclasses.dataclass
class Seams:
    """Everything that touches the world. `run(argv, env=, cwd=, stdin_data=, echo=)` runs a child to the end, its stdin the terminal (or `stdin_data`), its
    stdout and stderr captured AND shown as they arrive; `spawn(argv, env=, cwd=, stdin_null=)` starts one that keeps running."""
    run: object
    spawn: object
    ask: object
    say: object
    now: object
    sleep: object
    port_open: object
    environ: object
    which: object
    realpath: object
    stat: object
    can_write: object
    can_read: object
    exists: object


class _Spawned:
    def __init__(self, argv, env, cwd, stdin_null=False):
        # `stdin_null` is for Vite: its dev server reads single keystrokes from a terminal stdin (q quits it), which would race the runner's own prompts.
        # The launcher keeps the terminal: its two password prompts read /dev/tty through getpass, and it reads nothing else.
        self.proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL if stdin_null else None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=cwd, close_fds=True)
        self.chunks = []
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()

    def _pump(self):
        fd = self.proc.stdout.fileno()
        while True:
            data = os.read(fd, 4096)
            if not data:
                break
            self.chunks.append(data)
            sys.stdout.write(data.decode("utf-8", "replace"))
            sys.stdout.flush()

    def poll(self):
        return self.proc.poll()

    def terminate(self):
        if self.proc.poll() is None:
            self.proc.terminate()

    def output(self):
        return b"".join(self.chunks)


def _real_run(argv, *, env, cwd=None, stdin_data=None, echo=True):
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE if stdin_data is not None else None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                cwd=cwd, close_fds=True)
    except OSError as error:
        return Result(127, ("cannot start %s: %s\n" % (argv[0], error)).encode())
    if stdin_data is not None:
        proc.stdin.write(stdin_data)
        proc.stdin.close()
    chunks, fd = [], proc.stdout.fileno()
    while True:
        data = os.read(fd, 4096)
        if not data:
            break
        chunks.append(data)
        if echo:
            sys.stdout.write(data.decode("utf-8", "replace"))
            sys.stdout.flush()
    code = proc.wait()
    proc.stdout.close()
    return Result(code, b"".join(chunks))


def _real_stat(path):
    import pwd
    try:
        info = os.stat(path)
    except OSError:
        return None
    return (pwd.getpwuid(info.st_uid).pw_name, stat_module.S_IMODE(info.st_mode))


def _real_can_read(path):
    try:
        with open(path, "rb"):
            return True
    except OSError:
        return False


def _real_port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def real_seams():
    import shutil
    import time
    return Seams(run=_real_run, spawn=lambda argv, env, cwd, stdin_null=False: _Spawned(argv, env, cwd, stdin_null), ask=input, say=print, now=lambda: dt.datetime.now().astimezone(),
                 sleep=time.sleep, port_open=_real_port_open, environ=lambda: dict(os.environ), which=shutil.which, realpath=os.path.realpath, stat=_real_stat,
                 can_write=lambda path: os.access(path, os.W_OK), can_read=_real_can_read, exists=os.path.exists)


# ---- pure helpers (tested directly) -----------------------------------------------------------------------------------------------------------
def strip_pg(environ):
    """The child environment: every variable whose name starts with PG removed; PYTHONPATH=src; unbuffered output so a prompt and a result show at once; no
    psql history file. No password is ever added."""
    env = {k: v for k, v in environ.items() if not k.upper().startswith("PG")}
    env.update({"PYTHONPATH": "src", "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1", "PSQL_HISTORY": "/dev/null"})
    return env


def fw(module, *args):
    return list(FW) + [module] + [str(a) for a in args]


def inputs_args(release_name):
    """The runbook's INPUTS, in its order."""
    out = ["--store-root", "data/marketdata", "--release-name", release_name]
    for sha in FILE_SHAS:
        out += ["--file", sha]
    for sidecar in SIDECARS:
        out += ["--sidecar", sidecar]
    return out + ["--registered-check", FILE_SHAS[2]]


def parse_number(text):
    """A typed figure as a Decimal: optional sign, digits, optional comma grouping, optional fraction. Anything else is None (and is then 'not equal')."""
    t = text.strip().replace(" ", " ")
    if re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    if not re.fullmatch(r"[+-]?\d+(\.\d+)?", t):
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def numbers_equal(typed, expected):
    """Numeric equality (trailing zeros and comma grouping do not matter). `expected` is a Decimal."""
    value = parse_number(typed)
    return value is not None and value == expected


def compare_nav(holding, nav, missed, state):
    """The NAV check against the Quant's values (ruling 9.1), for the figures the screen states: holding, NAV, missed sessions, state. Returns {field: bool}."""
    typed = {"holding": holding, "nav": nav, "missed_sessions": missed}
    out = {name: numbers_equal(typed[name], expected) for name, expected in QUANT_NUMBERS}
    out["state"] = state.strip().upper() == QUANT_STATE
    return out


def classify_create(status, code):
    """Runbook rule 0.3 as clarified by PD-0083. SUCCESS: 201 (200 for a replay) with no error code. RETRY: only `422 REAL_REQUEST_INVALID` and `404`, which
    come before any lease or commit. STOP: every other refusal, any UNKNOWN, any 503, anything not understood."""
    s, c = status.strip().upper(), code.strip().upper()
    if s in ("200", "201") and c in ("", "-", "NONE", "OK"):
        return "SUCCESS"
    if s == "422" and c == "REAL_REQUEST_INVALID":
        return "RETRY"
    if s == "404":
        return "RETRY"
    return "STOP"


_PF = r"(PF_CONNECT_FAILED)"      # PF_REQUIRE_AUTH is a refusal of the cluster's configuration, not a typo: it latches (TR8G-M-3)
#: Each reviewed tool's own failure line, whole lines only (a code quoted inside other output does not match), with the exit status 2 that goes with it. Read
#: from the tools' source (2026-11-15). The connect comes before anything is sent and the line is printed in the handler of that connect, EXCEPT:
#: `real_install` (its handler wraps the whole command, so the line can also follow a failed read; harmless for phase 0, phase 2 and check, which write nothing;
#: phase 1 is never retried) and `identity_seed` (the line covers a connect or a statement failure; the seed is ONE transaction and idempotent (ON CONFLICT DO
#: NOTHING, an equal row is left alone), so a re-run after any outcome changes nothing or completes the same rows; the question says it failed and was rolled
#: back, not that nothing was sent). The launcher's LAUNCH_ACCOUNT_ROLE with the class name OperationalError is printed before anything is served, and the account
#: store's connect only reads pg_roles and sets session settings. (A require_auth refusal at that second prompt prints the same words and cannot be told apart.)
OWN_CONNECTION = {
    "real_tools.loader_window": [("", re.compile(r"^REFUSED (LOADER_CONNECT_FAILED) " + _PF + r"\. Nothing was sent\.$", re.M))],
    "real_tools.admission_probe": [("", re.compile(r"^REFUSED (PROBE_CONNECT_FAILED) " + _PF + r"\. Nothing was sent\.$", re.M))],
    "web_api.real_launcher": [("", re.compile(r"^REFUSED (LAUNCH_CONNECT_FAILED)\. Nothing was started and nothing was written\.\n" + _PF + r"$", re.M)),
                              ("", re.compile(r"^REFUSED (LAUNCH_ACCOUNT_ROLE)\. Nothing was started and nothing was written\.\n(OperationalError)$", re.M))],
    "persistence.real_workspace_store": [("", re.compile(r"^refused: (RW_CONNECT_FAILED)  \(" + _PF + r" [A-Za-z]+\)\nnothing was recorded$", re.M))],
    "persistence.real_install": [("", re.compile(r"^REFUSED " + _PF + r" \([A-Za-z]+\): the installer's own connection failed; nothing was changed by this step$", re.M))],
    "real_tools.identity_seed": [("SEED_ROLLED_BACK", re.compile(r"^REFUSED " + _PF + r" \(OperationalError\): the seed's connection or statement failed; "
                                                              r"the seed is one transaction, so nothing was written$", re.M))],
}
INSTALL_WRITES_NOTHING = ("phase0", "phase2", "check")


def own_connection_failure(argv, code, text):
    """The tool's own code ("CODE PF_..."), when `argv` is a reviewed tool, it exited 2, and its output holds that tool's own connect-failure line; else None."""
    if code != 2 or len(argv) < 9 or list(argv[:7]) != list(FW) or argv[7] not in OWN_CONNECTION:
        return None
    if argv[7] == "persistence.real_install" and argv[8] not in INSTALL_WRITES_NOTHING:
        return None
    if argv[7] == "web_api.real_launcher" and "real-mode app:" in text:
        return None
    for prefix, pattern in OWN_CONNECTION[argv[7]]:
        found = pattern.search(text)
        if found:
            return " ".join(x for x in (prefix,) + found.groups() if x)
    return None


def parse_marker(text, name):
    """The value of the last `R8_MARK <name>=<value>` line of a psql output, or None."""
    found = re.findall(r"R8_MARK %s=(\S*)" % re.escape(name), text)
    return found[-1] if found else None


# ---- stops and pauses ---------------------------------------------------------------------------------------------------------------------------
class Stop(Exception):
    def __init__(self, code, message, *, latch=False, close_window=False, step=None):
        super().__init__(message)
        self.code, self.message, self.latch, self.close_window, self.step = code, message, latch, close_window, step


class Quit(Exception):
    """The owner chose to stop for now (or the terminal ended); nothing is wrong."""


@dataclasses.dataclass
class StepDef:
    sid: str
    title: str
    what: str
    gated: bool = False      # waits for Enter first: it writes, asks for a password or uses sudo
    password: bool = False   # the clean tree is re-checked first (runbook rule 0.1)
    safe: bool = True        # an interrupted run may simply run it again
    services: str = ""       # the contexts file the screen must be serving


class Guide:
    #: Behaviour-neutral class attributes (the supplementary-run runner, `r8_supplement`, subclasses `Guide` and changes only these two and the step table).
    DIR_NAME = "finweb-r8"
    SCHEMA = STATE_SCHEMA

    def __init__(self, seams, home, repo_root, *, overrides=None):
        self.s = seams
        self.home = Path(home)
        self.dir = self.home / self.DIR_NAME
        self.repo = Path(repo_root)
        self.overrides = overrides or {}
        self.st = None
        self.svc = None
        self.steps = self._steps()

    # ---- small utilities ---------------------------------------------------------------------------------------------------------------------
    def say(self, text=""):
        self.s.say(text)

    def stamp(self):
        n = self.s.now()
        return "%s %s" % (n.isoformat(timespec="seconds"), n.tzname() or "")

    def log(self, text):
        fd = os.open(str(self.dir / "transcript.log"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, text.encode("utf-8", "replace"))
        finally:
            os.close(fd)

    def path(self, name):
        return str(self.dir / name)

    def enter(self, message):
        """Wait for Enter. Anything else typed is not stored, and `quit` stops for now. (Never type a password here.)"""
        while True:
            try:
                answer = self.s.ask("%s\n  [Enter to go on, 'quit' to stop for now; never type a password here] " % message)
            except (EOFError, KeyboardInterrupt):
                raise Quit() from None
            if answer.strip() == "":
                return
            if answer.strip().lower() == "quit":
                raise Quit()
            self.say("  (only Enter or quit)")

    def typed(self, prompt, check=None, tries=6):
        """A short typed value (never a password). `check(value)` returns an error text or None."""
        for _ in range(tries):
            try:
                answer = self.s.ask(prompt + " ").strip()
            except (EOFError, KeyboardInterrupt):
                raise Quit() from None
            if answer.lower() == "quit":
                raise Quit()
            problem = check(answer) if check else None
            if problem is None:
                return answer
            self.say("  " + problem)
        raise Stop("TOO_MANY_BAD_ANSWERS", "no usable answer after %d tries" % tries)

    def approve_or_stop(self, prompt, code, what):
        """An approval the owner may refuse. `no` is recorded and stops R8 with a latch (runbook rule 0.4 and section 6: stop, tell the main session)."""
        answer = self.typed("%s (type approve) (or no, to stop R8 here)" % prompt, check=lambda a: None if a in ("approve", "no") else "type approve or no, or quit")
        if answer == "approve":
            return
        self.record("%s: NOT approved" % what, "no")
        raise Stop(code, "%s was not approved (runbook: stop). Tell the main session; nothing continues until a reviewed fix and --reset-stop." % what, latch=True)

    def confirm_word(self, prompt, word):
        answer = self.typed("%s (type %s)" % (prompt, word), check=lambda a: None if a == word else "type exactly %s, or quit" % word)
        return answer

    # ---- state -------------------------------------------------------------------------------------------------------------------------------
    def save(self):
        path = self.dir / STATE_NAME
        tmp = self.dir / (STATE_NAME + ".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.fchmod(fd, 0o600)
            os.write(fd, (json.dumps(self.st, indent=2, sort_keys=True) + "\n").encode())
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(str(tmp), str(path))

    def ensure_dir(self):
        if not self.dir.exists():
            os.makedirs(str(self.dir), mode=0o700)
        info = self.dir.stat()
        if stat_module.S_IMODE(info.st_mode) != 0o700:
            os.chmod(str(self.dir), 0o700)
        (self.dir / "scripts").mkdir(mode=0o700, exist_ok=True)

    def load(self):
        path = self.dir / STATE_NAME
        if not path.exists():
            if (self.dir / EVENTS_NAME).exists():
                raise Stop("STATE_MISSING", "%s exists but the state file does not (lost or deleted). Nothing is started afresh over an existing log. Tell the main session." % (self.dir / EVENTS_NAME))
            return False
        self.st = json.loads(path.read_text("utf8"))
        if self.st.get("schema") != self.SCHEMA:
            raise Stop("STATE_SCHEMA", "the state file is not a %s document" % self.SCHEMA)
        if not (self.dir / EVENTS_NAME).exists():
            raise Stop("EVENTS_LOG_MISSING", "%s is missing although the state file exists; the record cannot be trusted. Tell the main session." % (self.dir / EVENTS_NAME))
        return True

    def event(self, kind, **data):
        """Append one JSON line to the append-only events log (the record's source). Opened for append only; never rewritten."""
        entry = dict(data, kind=kind, at=self.stamp())
        fd = os.open(str(self.dir / EVENTS_NAME), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (json.dumps(entry, sort_keys=True) + "\n").encode("utf-8"))
        finally:
            os.close(fd)

    def read_events(self):
        path = self.dir / EVENTS_NAME
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text("utf8").splitlines() if line.strip()]

    @staticmethod
    def latch_from_events(events):
        """What the log says: (latched, the last latch event). A create outcome that stops R8 counts until a lift."""
        latched, last = False, None
        for e in events:
            if e["kind"] == "latch":
                latched, last = True, e
            elif e["kind"] == "latch_lifted":
                latched, last = False, None
            elif e["kind"] == "create" and e.get("verdict") in PY_STATES:
                latched, last = True, {"code": "CREATE_%s_%s" % (e.get("status"), str(e.get("code")).upper()), "step": e.get("label"), "at": e["at"], "head": None,
                                       "message": "a create outcome that stops R8 (rule 0.3) is in the events log (%s)" % e["at"]}
        return latched, last

    def command(self, step, argv, code):
        self.event("command", step=step, argv=argv, code=code)
        self.st["commands"].append({"step": step, "argv": argv, "code": code, "at": self.stamp()})

    def record(self, item, value, **extra):
        entry = {"item": item, "value": value, "at": self.stamp()}
        entry.update(extra)
        self.event("record", **{k: v for k, v in entry.items() if k != "at"})
        self.st["records"].append(entry)
        self.save()

    # ---- frozen values -----------------------------------------------------------------------------------------------------------------------
    def frozen_values(self):
        values = dict(DEFAULTS)
        values.update({k: v for k, v in self.overrides.items() if v is not None})
        problems = []
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,31}", str(values["cluster_user"])):
            problems.append("cluster user")
        if not (isinstance(values["base"], str) and re.fullmatch(r"/[A-Za-z0-9._/-]+", values["base"]) and ".." not in values["base"]):
            problems.append("base directory (an absolute path of plain characters)")
        elif str(self.repo) in values["base"] or "/tmp" in values["base"] or "/var/folders" in values["base"] or "/private" in values["base"]:
            problems.append("base directory (outside the project and the temp directory)")
        if not (isinstance(values["port"], int) and 1024 <= values["port"] <= 65535):
            problems.append("port")
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", str(values["superuser"])):
            problems.append("superuser name")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,62}", str(values["release_name"])):
            problems.append("release name")
        if problems:
            raise Stop("FROZEN_INVALID", "not usable: " + ", ".join(problems))
        return values

    def check_frozen_unchanged(self):
        """The values are frozen on the first run; a different value later is refused (the release name enters the release id and the context for good)."""
        frozen = self.st["frozen"]
        for key, value in self.overrides.items():
            if value is not None and frozen.get(key) != value:
                raise Stop("FROZEN_CHANGED", "%s was frozen as %r on the first run; %r is refused. The values cannot change after the first run." % (key, frozen.get(key), value))

    @property
    def sockdir(self):
        return self.st["frozen"]["base"] + "/sock"

    @property
    def sock(self):
        return "%s/.s.PGSQL.%d" % (self.sockdir, self.st["frozen"]["port"])

    def d(self, which):
        return "%s/%s" % (self.st["frozen"]["base"], "" if which == "base" else which)

    @property
    def su(self):
        return self.st["frozen"]["superuser"]

    @property
    def name(self):
        return self.st["frozen"]["release_name"]

    # ---- git and the clean-tree rule ---------------------------------------------------------------------------------------------------------
    def child_env(self):
        return strip_pg(self.s.environ())

    def git(self, *args, record=False):
        argv = ["git"] + list(args)
        result = self.s.run(argv, env=self.child_env(), cwd=str(self.repo), stdin_data=None, echo=False)
        if record:
            self.command("git", argv, result.code)
        self.log("$ %s -> %d\n" % (shlex.join(argv), result.code))
        return result

    def require_clean_tree(self):
        """Runbook rule 0.1 and section 2: nothing may be modified, staged or untracked; HEAD may have moved only by commits that touch decisions/product/."""
        result = self.git("status", "--porcelain")
        if result.code != 0 or result.text.strip() != "":
            raise Stop("TREE_NOT_CLEAN", "the working tree is not clean (`git status --porcelain` must print nothing): %s. Passwords are typed only from a clean "
                       "tree. Commit or remove the change (an agent session may have edited the repository), then run again." % (result.text.strip()[:300] or "git failed"))
        self.check_head()

    def head(self):
        result = self.git("rev-parse", "HEAD")
        text = result.text.strip()
        if result.code != 0 or not _HEX40.fullmatch(text):
            raise Stop("GIT_HEAD", "cannot read HEAD")
        return text

    def check_head(self):
        p8 = self.st["p8"]["commit"]
        head = self.head()
        if head == p8:
            return head
        if self.git("merge-base", "--is-ancestor", p8, head).code != 0:
            raise Stop("HEAD_MOVED", "HEAD %s is not a descendant of the reviewed commit P8 %s" % (head, p8))
        names = self.git("diff", "--name-only", "--no-renames", p8, "HEAD")
        if names.code != 0:
            raise Stop("HEAD_MOVED", "cannot compare HEAD with P8")
        outside = [n for n in names.text.splitlines() if n and not n.startswith("decisions/product/")]
        if outside:
            raise Stop("HEAD_MOVED", "HEAD has moved from P8 %s by more than decision records; changed outside decisions/product/: %s. Passwords are typed only "
                       "from the reviewed commit." % (p8, ", ".join(outside[:8])))
        return head

    # ---- running commands ---------------------------------------------------------------------------------------------------------------------
    def exec(self, step, argv, *, cwd=None, stdin_data=None, echo=True, show=True, record=True):
        argv = [str(a) for a in argv]
        if show:
            self.say("$ " + shlex.join(argv))
        self.log("$ %s\n" % shlex.join(argv))
        result = self.s.run(argv, env=self.child_env(), cwd=cwd, stdin_data=stdin_data, echo=echo)
        self.log(result.text + ("\n" if not result.text.endswith("\n") else "") + "-> exit %d\n" % result.code)
        if record:
            self.command(step, argv, result.code)
            self.save()
        return result

    @staticmethod
    def mistyped_password(argv, result):
        """The ONE narrow case where a failed child may be tried again (PM, 2026-11-15; a typo must not cost a committed fix). Returns a label or None. Only
        programs where the output says clearly that nothing ran: sudo after its own three wrong passwords, and psql whose login (exit 2) or `\\password` pair
        (exit 3 under ON_ERROR_STOP) failed. The reviewed TOOLS are NOT in this list: none of them prints the server's text, so a refused password cannot be told
        from a server that is down (see the implementation note, section 4)."""
        text = result.text
        if os.path.basename(argv[0]) == "sudo" and result.code == 1 and "incorrect password attempt" in text:
            return "sudo password refused"
        if os.path.basename(argv[0]) == "psql":
            if result.code == 2 and "password authentication failed" in text:
                return "psql login refused (password authentication failed)"
            if result.code == 3 and "Passwords didn't match" in text:
                return "psql set-password command: the two entries did not match"
        return None

    def exec_pw(self, step, argv, **kw):
        """`exec`, plus: after a mistyped password the owner may choose to run the identical command again, at most MAX_PW_RETRIES times per step; the next
        failure latches. Each failed attempt is recorded with its time and a label, never with anything the owner typed (the runner never sees it)."""
        while True:
            result = self.exec(step, argv, **kw)
            label = self.mistyped_password(argv, result)
            tool_code = None if label else own_connection_failure(argv, result.code, result.text)
            if label is None and tool_code is None:
                return result
            self.retry_gate(step, label, tool_code)

    def retry_gate(self, step, label, tool_code):
        """One failed attempt that sent nothing: record it (time and label or code only), latch after MAX_PW_RETRIES retries, otherwise ask the owner. Returns to
        mean 'run it again'; raises Stop otherwise. The count is per step, kept in the state, and cleared by a reset."""
        counts = self.st.setdefault("pw_failures", {})
        counts[step] = failures = counts.get(step, 0) + 1
        self.record("failed attempt %d at %s" % (failures, step), label or tool_code, step=step)
        what = label or "the tool's own connection failed (%s)" % tool_code
        if failures > MAX_PW_RETRIES:
            raise Stop("PASSWORD_RETRIES_EXHAUSTED", "%s at step %s, %d attempts in all. Retries are exhausted (rule 0.4)." % (what, step, failures),
                       latch=True, step=step, close_window=bool(WINDOW_STEPS.get(step)))      # a definite answer: a loader window is not left open
        if tool_code and tool_code.startswith("SEED_ROLLED_BACK"):
            self.say("The identity seed failed and was rolled back (%s). It is one transaction and safe to run again. A mistyped password is the usual cause." % tool_code)
        elif tool_code:
            self.say("The tool could not connect (%s); nothing was sent. A mistyped password is the usual cause." % tool_code)
        else:
            self.say("%s. Nothing ran in that attempt." % label)
        self.say("(attempt %d of %d)" % (failures, MAX_PW_RETRIES + 1))
        answer = self.typed("Retry after a mistyped password? [y/N]", check=lambda a: None if a.lower() in ("", "y", "n", "yes", "no") else "y or n")
        if answer.lower() not in ("y", "yes"):
            raise Stop("PASSWORD_NOT_RETRIED", "%s; you chose not to retry. Run again when ready." % what)
        if self.st is not None and "p8" in self.st:
            self.require_clean_tree()

    def write_script(self, name, content):
        path = self.dir / "scripts" / name
        if path.exists():
            if path.read_text("utf8") != content:
                raise Stop("SCRIPT_CHANGED", "%s differs from what this runner writes; not used" % path)
            return str(path)
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, content.encode())
        finally:
            os.close(fd)
        return str(path)

    def psql_argv(self, script_path, *variables):
        """The runbook's `psql -h <SOCKDIR> -p <PORT> -U <SU> -d finweb_real`, plus -X, ON_ERROR_STOP, no history file, and the script. psql asks for the
        superuser password itself (on the terminal)."""
        argv = [self.st["frozen"]["psql"], "-X", "-v", "ON_ERROR_STOP=1", "-v", "HISTFILE=/dev/null"]
        for key, value in variables:
            argv += ["-v", "%s=%s" % (key, value)]
        return argv + ["-h", self.sockdir, "-p", str(self.st["frozen"]["port"]), "-U", self.su, "-d", DATABASE, "-f", script_path]

    # ---- the step table ---------------------------------------------------------------------------------------------------------------------
    def _steps(self):
        S = StepDef
        t = []

        def add(sid, fn, title, what, **kw):
            t.append((S(sid, title, what, **kw), fn))
        add("cluster_user", self.s_cluster_user, "macOS user for the cluster (runbook 3.1)",
            "Creates a Standard (non-administrator) macOS user for the cluster, or verifies that it exists and is not an administrator. sudo asks for YOUR macOS "
            "password, and the new user's password is asked by sysadminctl.", gated=True, password=True)
        add("cluster_dirs", self.s_cluster_dirs, "Cluster directories (runbook 3.1)",
            "Creates the base, data, sock and log directories with their owners and modes (or verifies them).", gated=True)
        add("cluster_initdb", self.s_cluster_initdb, "initdb (runbook 3.1)",
            "Runs initdb as the cluster user, scram-sha-256, `--pwprompt`: you type the superuser password twice at initdb's prompt (or it is verified to exist).", gated=True, password=True)
        add("cluster_hba", self.s_cluster_hba, "pg_hba.conf (runbook 3.1)", "Writes the one line `local all all scram-sha-256` and nothing else.", gated=True)
        add("cluster_conf", self.s_cluster_conf, "postgresql.conf (runbook 3.1)",
            "Appends the R8 settings: no TCP, the socket directory, scram, no prepared transactions, no statement logging.", gated=True)
        add("cluster_start", self.s_cluster_start, "Start the cluster (runbook 3.1)", "Starts it as the cluster user with pg_ctl and waits for the socket.", gated=True)
        add("cluster_verify", self.s_cluster_verify, "Record owners and modes (runbook 3.1 [record])",
            "Records the owners and modes of the four directories and that your account cannot write the data directory or read pg_hba.conf.")
        add("phase0", self.s_phase0, "Phase 0 (runbook 3.2)", "Read-only checks before anything exists. The superuser password is asked at the tool's prompt.",
            gated=True, password=True)
        add("phase1", self.s_phase1, "Phase 1 (runbook 3.3)",
            "Creates the real database, the five roles (no passwords), the schema and the gateway; writes install kind REAL. Not one transaction: a failure stops R8.",
            gated=True, password=True, safe=False)
        add("passwords", self.s_passwords, "Three passwords in one psql session (runbook 3.4)",
            "psql asks for the superuser password, then `\\password` asks for the publisher, executor and account passwords (each twice).", gated=True, password=True)
        add("phase2", self.s_phase2, "Phase 2 (runbook 3.5)", "Read-only checks including the catalog audit.", gated=True, password=True)
        add("qualify", self.s_qualify, "Offline qualification (runbook 4)",
            "Writes P.json and F.json in ~/finweb-r8 (never overwrites). No connection and no password.", gated=True, safe=False)
        add("qualify_approve", self.s_qualify_approve, "Review the qualification listing (runbook 4)",
            "Shows the points you must check in the listing and asks for your explicit approval.")
        add("seed", self.s_seed, "Identity seed (runbook 5.1)", "Writes the issuer, instrument and listing rows in one transaction. Superuser password at the tool's prompt.",
            gated=True, password=True, safe=False)
        add("w1_open", lambda: self.s_window_open(1), "Open loader window 1 (runbook 5.2)",
            "In one psql session: ALTER ROLE finweb_real_loader LOGIN, then `\\password` for it (a fresh password). Records the LOGIN time.", gated=True, password=True)
        add("w1_check", lambda: self.s_window_check(1), "real_install check, window 1 (runbook 5.3)", "A refusal stops the window before anything is loaded.",
            gated=True, password=True)
        add("w1_load", lambda: self.s_loader(1, "load"), "The load (runbook 5.4)",
            "Loads the release and registers the UNBOUND candidate; the loader password is asked at the tool's prompt. Exit codes are handled as the runbook says.",
            gated=True, password=True)
        add("w1_close", lambda: self.s_window_close(1), "Close loader window 1 (runbook 5.5)",
            "NOLOGIN, end the loader's sessions, repeat until none is left (in one psql session with a bounded wait). Records the time.", gated=True, password=True)
        add("proposal_review", self.s_proposal_review, "Review the proposal (runbook 6)", "Shows the key fields of P.json and asks for your explicit approval.")
        add("pub_pd", lambda: self.s_pd_record("publish"), "Publish decision record (runbook 7.1)",
            "You write and commit the decision record; the runner then computes GIT40 and DOC64 and runs the two git checks.")
        add("pub_evidence", lambda: self.s_evidence("E.json"), "Expiry-evidence file (runbook 7.2)",
            "Computes the PD-0066 and PD-0068 citations with git log / git show and writes E.json (never overwrites).", gated=True, safe=False)
        add("publish", self.s_publish, "Publish (runbook 7.3)", "The publisher password is asked at the tool's prompt. Gated by the preflight.", gated=True, password=True)
        add("w2_open", lambda: self.s_window_open(2), "Open loader window 2 (runbook 8.1)", "As window 1.", gated=True, password=True)
        add("w2_check", lambda: self.s_window_check(2), "real_install check, window 2 (runbook 8.1)", "As window 1.", gated=True, password=True)
        add("w2_register", lambda: self.s_loader(2, "register-bound"), "register-bound (runbook 8.2)", "Registers the BOUND candidate.", gated=True, password=True)
        add("w2_close", lambda: self.s_window_close(2), "Close loader window 2 (runbook 8.3)", "As window 1. This is the loader's last use in R8.", gated=True, password=True)
        add("contexts", lambda: self.s_contexts("C.json", "generation"), "Contexts file (runbook 9.1)", "Writes C.json with the generation the publish printed.", gated=True, safe=False)
        add("create", self.s_create, "Launcher, screen and the create (runbook 9.2 to 9.4)",
            "Starts the launcher (two password prompts) and Vite, shows the form values, and classifies the create's outcome by rule 0.3.", services="C.json")
        add("check_nav", self.s_check_nav, "Check 10.1: NAV against the Quant's figures", "You type what the screen shows; the runner compares numerically.", services="C.json")
        add("check_keyfigs", lambda: self.s_check_simple("check_keyfigs", "10.2 the filled key-figures list in the browser", ("result",)),
            "Check 10.2: key-figures list", "Look at the list in the browser.", services="C.json")
        add("check_nonav", lambda: self.s_check_simple("check_nonav", "10.3 the no-NAV notice's prominence (bold text only)", ("result",)),
            "Check 10.3: no-NAV notice", "Look at the notice in the browser.", services="C.json")
        add("check_claims", lambda: self.s_check_simple("check_claims", "10.4 the 7.4 claim-limit wording from the real lineage", ("English, all three depths", "Chinese, all three depths", "the real root's origin label")),
            "Check 10.4: claim-limit wording", "Look at the wording in English and Chinese at all three depths, and the origin label.", services="C.json")
        add("check_isolation", lambda: self.s_check_simple("check_isolation", "10.5 two-user isolation (sign up user B)", ("B sees none of A's roots", "B cannot open A's root by its id")),
            "Check 10.5: two-user isolation", "Sign up user B and try.", services="C.json")
        add("check_repro", lambda: self.s_check_simple("check_repro", "10.6 reproduce and list A's root", ("reproduce", "list")),
            "Check 10.6: reproduce and list", "As user A.", services="C.json")
        add("probe_ids", self.s_probe_ids, "Owner and root ids for the probe (runbook 11.1)",
            "Reads user A's id with a read-only psql query (never password_hash); you type the root id from A's list.", gated=True, password=True)
        add("probe_control", lambda: self.s_probe("probe_control", "generation", 0, "control, before the withdraw"), "Export probe, control (runbook 11.2)",
            "Direct gateway admission; it rolls back and writes nothing. Executor password at the tool's prompt.", gated=True, password=True)
        add("stop1", self.s_stop_services, "Stop the launcher (runbook 11.3)", "So that no screen request holds a lease.")
        add("wd_pd", lambda: self.s_pd_record("withdraw"), "Withdraw decision record (runbook 11.3)", "You write and commit it; then the git checks.")
        add("withdraw", self.s_withdraw, "Withdraw (runbook 11.3)", "Publisher password at the tool's prompt. Exit 3 means run the identical command again.", gated=True, password=True)
        add("c1_contexts", lambda: self.s_contexts("C1.json", "generation_withdrawn"), "Contexts file at N' (runbook 11.4)", "Writes C1.json.", gated=True, safe=False)
        add("c1_refusals", self.s_c1_refusals, "The four refusals (runbook 11.4)", "Launcher on C1.json; you confirm what the screen shows.", services="C1.json")
        add("probe_n1", lambda: self.s_probe("probe_n1", "generation_withdrawn", 1, "export refused after the withdraw (direct gateway admission)"),
            "Export probe at N' (runbook 11.4)", "Expected: refused with RW_WITHDRAWN.", gated=True, password=True)
        add("stop2", self.s_stop_services, "Stop the launcher again (runbook 11.4)", "Before the renew.")
        add("rn_pd", lambda: self.s_pd_record("renew"), "Renew decision record (runbook 11.5)", "You write and commit it; then the git checks.")
        add("rn_evidence", lambda: self.s_evidence("E2.json"), "Fresh evidence file (runbook 11.5)", "Writes E2.json with the same citations.", gated=True, safe=False)
        add("renew", self.s_renew, "Renew (runbook 11.5)", "Publisher password at the tool's prompt.", gated=True, password=True, safe=False)
        add("c2_contexts", lambda: self.s_contexts("C2.json", "generation_renewed"), "Contexts file at N'' (runbook 11.6)", "Writes C2.json.", gated=True, safe=False)
        add("c2_rights", self.s_c2_rights, "Rights restored (runbook 11.6)", "Launcher on C2.json; you confirm read, reproduce, list and a create (rule 0.3 applies).", services="C2.json")
        add("probe_n2", lambda: self.s_probe("probe_n2", "generation_renewed", 0, "export restored"), "Export probe at N'' (runbook 11.6)", "Expected: admitted.",
            gated=True, password=True)
        add("stop3", self.s_stop_services, "Stop the launcher and Vite (runbook 12)", "")
        add("close", self.s_close, "Close and write the record (runbook 12)",
            "You confirm the statement items; the runner writes ~/finweb-r8/R8_RECORD.md, the input for HG4.", gated=True)
        return t

    # ---- the driver -------------------------------------------------------------------------------------------------------------------------
    def progress(self):
        done = [d.sid for d, _ in self.steps if d.sid in self.st["done"]]
        nxt = next((d.sid for d, _ in self.steps if d.sid not in self.st["done"]), None)
        return done, nxt

    def run_steps(self):
        while True:
            pending = next(((d, f) for d, f in self.steps if d.sid not in self.st["done"]), None)
            if pending is None:
                return EXIT_DONE
            definition, fn = pending
            n = WINDOW_STEPS.get(definition.sid)
            window = self.st["window"]
            if n and not (window.get("open") and window.get("n") == n) and ("w%d_open" % n) in self.st["done"]:
                # The window was opened and has been closed since (a stop, a reset, --close-window): this step must never run against a NOLOGIN loader. Open it again
                # (a fresh LOGIN and a fresh password), then check again.
                self.say("Loader window %d is CLOSED. Opening it again (a fresh LOGIN and \\password) before %s." % (n, definition.sid))
                for sid in ("w%d_open" % n, "w%d_check" % n):
                    self.st["done"].pop(sid, None)
                    self.st["started"].pop(sid, None)
                self.event("window_reopen", window=n, before=definition.sid)
                self.save()
                continue
            self.run_one(definition, fn)

    def run_one(self, definition, fn):
        sid = definition.sid
        if self.st["started"].get(sid) and not definition.safe:
            raise Stop("STEP_INTERRUPTED", "step %s was started in an earlier run and its end was not recorded (interrupted?). It is not safe to run it again "
                       "blindly. Look at what it did (the transcript is %s), then run:  --resolve %s retry  (it did nothing) or  --resolve %s done  (it finished)."
                       % (sid, self.path("transcript.log"), sid, sid))
        self.say("\n== %s: %s ==" % (sid, definition.title))
        self.say(definition.what)
        try:
            if definition.gated:
                self.enter("Next: %s." % definition.title)
            if definition.password:
                self.require_clean_tree()
            if definition.services:
                self.ensure_services(definition.services)
            self.st["started"][sid] = self.stamp()
            self.save()
            data = fn()
        except Stop as stop:
            stop.step = sid
            if stop.code in PRE_EFFECT_CODES:           # the step refused before it started anything: it may simply be run again
                self.st["started"].pop(sid, None)
                self.save()
            raise
        self.event("done", step=sid)
        self.st["done"][sid] = {"at": self.stamp(), "data": data or {}}
        self.st["started"].pop(sid, None)
        self.save()

    # ---- stage 2: the cluster ------------------------------------------------------------------------------------------------------------------
    def sudo_as(self, step, *argv, stdin_data=None):
        return self.exec_pw(step, [SUDO, "-u", self.st["frozen"]["cluster_user"]] + list(argv), cwd="/", stdin_data=stdin_data)

    def need(self, result, step, what):
        if result.code != 0:
            raise Stop("CLUSTER_STEP_FAILED", "%s failed (exit %d). Nothing further is done; fix the cause and run again (this step verifies before it changes)." % (what, result.code))
        return result

    def s_cluster_user(self):
        user = self.st["frozen"]["cluster_user"]
        if self.exec("cluster_user", [ID, "-u", user], show=True).code == 0:
            groups = self.exec("cluster_user", [ID, "-Gn", user])
            if "admin" in groups.text.split():
                raise Stop("CLUSTER_USER_ADMIN", "the macOS user %s exists and is an administrator; the cluster user must be a Standard user" % user)
            self.say("The user %s exists and is not an administrator: verified, not recreated." % user)
            return {"created": False}
        self.need(self.exec_pw("cluster_user", [SUDO, SYSADMINCTL, "-addUser", user, "-fullName", "FinWeb R8 Postgres", "-password", "-"]), "cluster_user", "creating the macOS user")
        if self.exec("cluster_user", [ID, "-u", user]).code != 0:
            raise Stop("CLUSTER_STEP_FAILED", "the user %s is not there after sysadminctl" % user)
        return {"created": True}

    def dirs_state(self):
        owner = self.st["frozen"]["cluster_user"]
        out = {}
        for which, mode in DIR_MODES:
            info = self.s.stat(self.d(which).rstrip("/"))
            out[which] = {"path": self.d(which).rstrip("/"), "owner": info[0] if info else None, "mode": ("%04o" % info[1]) if info else None,
                          "ok": bool(info) and info[0] == owner and info[1] == mode}
        return out

    def s_cluster_dirs(self):
        owner = self.st["frozen"]["cluster_user"]
        state = self.dirs_state()
        base = state["base"]
        if base["owner"] is not None and base["owner"] not in (owner, "root"):
            raise Stop("CLUSTER_DIR_OWNER", "%s exists and belongs to %s; it is not recreated or chowned" % (base["path"], base["owner"]))
        if all(v["ok"] for v in state.values()):
            self.say("The directories exist with the right owners and modes: verified, not recreated.")
            return {"created": False, "dirs": state}
        b = self.d("base").rstrip("/")
        for argv in ([SUDO, MKDIR, "-p", b + "/data", b + "/sock", b + "/log"], [SUDO, CHOWN, "-R", owner + ":staff", b],
                     [SUDO, CHMOD, "755", b, b + "/sock"], [SUDO, CHMOD, "700", b + "/data", b + "/log"]):
            self.need(self.exec_pw("cluster_dirs", argv), "cluster_dirs", "`%s`" % shlex.join(argv[1:]))
        state = self.dirs_state()
        if not all(v["ok"] for v in state.values()):
            raise Stop("CLUSTER_DIR_STATE", "the directories do not have the expected owners and modes after creation: %s" % json.dumps(state, sort_keys=True))
        return {"created": True, "dirs": state}

    def s_cluster_initdb(self):
        data = self.d("data")
        if self.sudo_as("cluster_initdb", TEST, "-e", data + "/PG_VERSION").code == 0:
            self.say("The data directory already holds a cluster (PG_VERSION): verified, initdb is not run again.")
            return {"initdb": False}
        argv = [self.st["frozen"]["initdb"], "-D", data, "--auth-local=scram-sha-256", "--auth-host=scram-sha-256", "--pwprompt", "-U", self.su, "-E", "UTF8", "--locale=C"]
        self.need(self.sudo_as("cluster_initdb", *argv), "cluster_initdb", "initdb")
        return {"initdb": True}

    def s_cluster_hba(self):
        path = self.d("data") + "/pg_hba.conf"
        if self.sudo_as("cluster_hba", CAT, path).text == HBA_CONTENT:
            self.say("pg_hba.conf already holds exactly the one line: verified.")
            return {"written": False}
        self.need(self.sudo_as("cluster_hba", TEE, path, stdin_data=HBA_CONTENT.encode()), "cluster_hba", "writing pg_hba.conf")
        if self.sudo_as("cluster_hba", CAT, path).text != HBA_CONTENT:
            raise Stop("CLUSTER_STEP_FAILED", "pg_hba.conf does not hold exactly the expected content after writing")
        return {"written": True}

    def s_cluster_conf(self):
        path = self.d("data") + "/postgresql.conf"
        block = conf_block(self.st["frozen"]["port"], self.sockdir)
        current = self.sudo_as("cluster_conf", CAT, path)
        self.need(current, "cluster_conf", "reading postgresql.conf")
        if block in current.text:
            self.say("postgresql.conf already holds the R8 settings: verified.")
            return {"written": False}
        if CONF_MARK in current.text:
            raise Stop("CLUSTER_CONF_DIFFERS", "postgresql.conf holds an R8 block that differs from the frozen values; it is not edited. Fix it by hand and run again.")
        self.need(self.sudo_as("cluster_conf", TEE, "-a", path, stdin_data=block.encode()), "cluster_conf", "appending to postgresql.conf")
        return {"written": True}

    def s_cluster_start(self):
        pg_ctl, data = self.st["frozen"]["pg_ctl"], self.d("data")
        if self.sudo_as("cluster_start", pg_ctl, "-D", data, "status").code == 0:
            self.say("The cluster is already running: verified.")
            started = False
        else:
            result = self.sudo_as("cluster_start", pg_ctl, "-D", data, "-l", self.d("log") + "/server.log", "start")
            if result.code != 0:
                raise Stop("CLUSTER_START_FAILED", "pg_ctl start failed (exit %d). Read %s/server.log as the cluster user. If it says 'postmaster became multithreaded' "
                           "(seen on the development cluster, STATUS.md 2026-10-22), tell the main session: the start needs LANG and LC_ALL set to C, which this runner "
                           "does not add on its own." % (result.code, self.d("log")))
            started = True
        for _ in range(30):
            if self.s.exists(self.sock):
                return {"started": started}
            self.s.sleep(1)
        raise Stop("CLUSTER_SOCKET", "the socket %s did not appear" % self.sock)

    def s_cluster_verify(self):
        problems, state = [], self.dirs_state()
        for which, info in state.items():
            if not info["ok"]:
                problems.append("%s is %s/%s" % (info["path"], info["owner"], info["mode"]))
        data = self.d("data")
        writable = bool(self.s.can_write(data))
        hba_readable = bool(self.s.can_read(data + "/pg_hba.conf"))
        socket_there = bool(self.s.exists(self.sock))
        if writable:
            problems.append("your account CAN write the data directory")
        if hba_readable:
            problems.append("your account CAN read pg_hba.conf")
        if not socket_there:
            problems.append("the socket is missing")
        facts = {"dirs": state, "owner_account_can_write_data_dir": writable, "owner_account_can_read_pg_hba": hba_readable, "socket_exists": socket_there}
        self.record("cluster owners and modes", state)
        self.record("owner's account can write the data directory", writable)
        if problems:
            raise Stop("CLUSTER_VERIFY", "not as the runbook requires: " + "; ".join(problems) + ". Fix it (this is cluster setup, not an R8 stop) and run again.")
        return facts

    # ---- stage 3: the install ---------------------------------------------------------------------------------------------------------------
    def tool_stop(self, step, result, what, *, latch=True):
        text = result.text
        tail = "\n".join(text.strip().splitlines()[-12:])
        raise Stop("%s_EXIT_%d" % (step.upper(), result.code), "%s exited with status %d, which the runbook does not tell you how to handle (rule 0.4).\n%s" % (what, result.code, tail),
                   latch=latch, step=step)

    def s_phase0(self):
        result = self.exec_pw("phase0", fw("persistence.real_install", "phase0", "--socket", self.sock, "--user", self.su))
        if result.code != 0:
            # Runbook 3.2: "Resolve any refusal before going on". Phase 0 writes nothing, so a plain re-run re-checks.
            raise Stop("PHASE0_REFUSED", "Phase 0 exited with status %d and wrote nothing. Resolve the refusal it names (runbook 3.2; after editing a config file restart the "
                       "cluster as the cluster user), then run this again." % result.code)
        return {"exit": 0}

    def s_phase1(self):
        result = self.exec("phase1", fw("persistence.real_install", "phase1", "--socket", self.sock, "--user", self.su, "--loader-login", "nologin"))
        if result.code != 0:
            self.tool_stop("phase1", result, "Phase 1 (a refused or partial install stays unused until a reviewed fix)")
        self.record("Phase 1 done", "exit 0")
        return {"exit": 0}

    def s_passwords(self):
        script = self.write_script("passwords.sql", SCRIPT_PASSWORDS)
        result = self.exec_pw("passwords", self.psql_argv(script))
        if result.code != 0:
            raise Stop("PASSWORDS_NOT_SET", "psql exited with status %d, so the three passwords are not confirmed set. Run this step again (setting a password again is harmless)." % result.code)
        return {"roles": [ROLE_PUBLISHER, ROLE_EXECUTOR, ROLE_ACCOUNT]}

    def s_phase2(self):
        result = self.exec_pw("phase2", fw("persistence.real_install", "phase2", "--socket", self.sock, "--user", self.su))
        if result.code != 0:
            self.tool_stop("phase2", result, "Phase 2 (a refusal here: the install stays unused until a reviewed fix)")
        self.record("Phase 2 done", "exit 0")
        return {"exit": 0}

    # ---- stage 4: the qualification ---------------------------------------------------------------------------------------------------------
    def s_qualify(self):
        argv = fw("real_tools.qualify_run", *inputs_args(self.name), "--proposal-out", self.path("P.json"), "--seed-out", self.path("F.json"))
        result = self.exec("qualify", argv)
        if result.code != 0:
            self.tool_stop("qualify", result, "the offline qualification")
        lines = result.text.splitlines()
        return {"listing": lines[-400:]}

    def s_qualify_approve(self):
        listing = self.st["done"]["qualify"]["data"]["listing"]
        flagged = [l for l in listing if re.search(r"needs review|NOT_CONFIRMED|O5|refus", l, re.I)]
        self.say("Points to check in the listing above (the runner decides nothing about them):")
        self.say("  1. the three payload and manifest hashes against PD-0066's table;")
        self.say("  2. O5 passing for all three members;")
        self.say("  3. no 'needs review' line (the calendar is --registered-check'ed, so no NOT_CONFIRMED).")
        self.say("Lines of the listing that mention review, NOT_CONFIRMED, O5 or a refusal (%d):" % len(flagged))
        for line in flagged:
            self.say("    " + line)
        self.approve_or_stop("Do you approve the qualification?", "QUALIFY_NOT_APPROVED", "the qualification")
        self.record("qualification approved", "approve")
        return {"approved": True}

    # ---- stage 5: identity seed and a loader window ---------------------------------------------------------------------------------------------
    def s_seed(self):
        argv = fw("real_tools.identity_seed", "--socket", self.sock, "--user", self.su, "--seed-file", self.path("F.json"), "--proposal", self.path("P.json"))
        result = self.exec_pw("seed", argv)
        if result.code != 0:
            self.tool_stop("seed", result, "the identity seed")
        return {"exit": 0}

    def s_window_open(self, n):
        self.st["window"] = {"n": n, "open": True, "open_started_at": self.stamp()}      # before the psql: LOGIN may be set even if the rest fails
        self.save()
        script = self.write_script("window_open.sql", SCRIPT_OPEN)
        result = self.exec_pw("w%d_open" % n, self.psql_argv(script))
        if result.code != 0:
            raise Stop("WINDOW_OPEN_FAILED", "psql exited with status %d. The loader MAY be LOGIN now (window %d is marked open). Run this step again, or close the window with "
                       "--close-window." % (result.code, n))
        login_at = parse_marker(result.text, "login_set_at")
        self.record("window %d LOGIN set" % n, login_at or "not printed", window=n)
        return {"login_set_at": login_at}

    def s_window_check(self, n):
        result = self.exec_pw("w%d_check" % n, fw("persistence.real_install", "check", "--socket", self.sock, "--user", self.su))
        if result.code != 0:
            # A refusal stops the window before anything is loaded; the answer is definite, so the window is closed (below) and R8 stops (rule 0.4).
            raise Stop("W%d_CHECK_EXIT_%d" % (n, result.code), "real_install check exited with status %d (a refusal stops the window; rule 0.4).\n%s" % (
                result.code, "\n".join(result.text.strip().splitlines()[-12:])), latch=True, close_window=True, step="w%d_check" % n)
        return {"exit": 0}

    def loader_argv(self, command, candidate=None):
        argv = fw("real_tools.loader_window", command, "--socket", self.sock, "--database", DATABASE, "--user", ROLE_LOADER, "--schema", SCHEMA) + inputs_args(self.name)
        argv += ["--proposal", self.path("P.json")]
        if command == "reconcile":
            argv += ["--candidate", candidate]
        return argv

    def s_loader(self, n, command):
        candidate = "unbound" if command == "load" else "bound"
        step = "w%d_%s" % (n, "load" if command == "load" else "register")
        mode, history = "main", []
        for attempt in range(1, MAX_LOADER_TRIES + 1):
            self.require_clean_tree()
            result = self.exec_pw(step, self.loader_argv(command) if mode == "main" else self.loader_argv("reconcile", candidate))
            history.append({"mode": mode, "exit": result.code})
            code = result.code
            if code == 0:
                return {"exit_path": history}
            if code == 5:
                self.say("Exit 5 (lock timeout): running the identical command again, as the runbook says.")
                continue
            if code == 4:
                asked = re.search(r"reconcile --candidate (unbound|bound)", result.text)
                if mode == "main" and asked:
                    if asked.group(1) != candidate:
                        raise Stop("LOADER_UNEXPECTED_RECONCILE", "the tool printed `reconcile --candidate %s` after a %s" % (asked.group(1), command), latch=True, close_window=False, step=step)
                    self.say("Exit 4 (unknown). THE WINDOW STAYS OPEN. Running the reconcile the tool printed, with the same arguments.")
                    mode = "reconcile"
                else:
                    self.say("Exit 4 (unknown). THE WINDOW STAYS OPEN. Reconcile found nothing or the outcome of the %s is unknown: running the identical %s again (it is idempotent)." % (command, command))
                    mode = "main"
                continue
            raise Stop("%s_EXIT_%d" % (step.upper(), code), "%s exited with status %d (runbook: 2 stop; anything else not covered, rule 0.4).\n%s" % (
                "loader_window " + (command if mode == "main" else "reconcile"), code, "\n".join(result.text.strip().splitlines()[-12:])),
                latch=True, close_window=True, step=step)
        raise Stop("LOADER_UNRESOLVED", "the answer is still not definite after %d tries. THE LOADER WINDOW IS STILL OPEN (as the runbook requires for an unknown answer). "
                   "Tell the main session; run again to try once more." % MAX_LOADER_TRIES)

    def close_window_now(self, n):
        """Section 5.5: NOLOGIN, end the sessions, repeat until none is left. Several tries; each needs the superuser password at psql's prompt."""
        script = self.write_script("window_close.sql", SCRIPT_CLOSE)
        for attempt in range(1, 6):
            self.require_clean_tree()
            result = self.exec_pw("w%d_close" % n, self.psql_argv(script))
            left, at = None, None
            found = re.findall(r"R8_MARK loader_sessions_left=(\d+) at=(\S+)", result.text)
            if found:
                left, at = int(found[-1][0]), found[-1][1]
            if result.code == 0 and left == 0:
                self.st["window"] = {"n": n, "open": False, "closed_at": self.stamp()}
                self.save()
                self.record("window %d last loader session ended (server UTC)" % n, at, window=n)
                self.record("window %d closed, zero loader sessions" % n, "NOLOGIN; 0 rows", window=n)
                return {"last_session_ended_utc": at}
            self.say("The window is NOT confirmed closed (psql exit %d, sessions left: %s)." % (result.code, left if left is not None else "unknown"))
            answer = self.typed("Run the close again? Enter = yes; type 'stop' to stop with the window OPEN:", check=lambda a: None if a in ("", "stop") else "Enter or stop")
            if answer == "stop":
                break
        raise Stop("WINDOW_NOT_CLOSED", "LOADER WINDOW %d IS NOT CONFIRMED CLOSED. Close it before anything else (run with --close-window), and tell the main session." % n)

    def s_window_close(self, n):
        return self.close_window_now(n)

    # ---- stage 6: the proposal --------------------------------------------------------------------------------------------------------------
    def load_json(self, name):
        return json.loads(Path(self.path(name)).read_bytes().decode("utf-8"))

    def form_values(self):
        p = self.load_json("P.json")
        f = self.load_json("F.json")
        return {"context_id": p["context_id"], "release_id": p["snapshot"]["release"]["release_id"], "listing_id": f["listings"][0][0]}

    def s_proposal_review(self):
        p = self.load_json("P.json")
        snap = p["snapshot"]
        self.say("P.json (the reviewed proposal), key fields:")
        self.say("  context_id         %s" % p["context_id"])
        self.say("  scope              %s" % snap["scope"])
        self.say("  release_id         %s" % snap["release"]["release_id"])
        self.say("  release_digest     %s" % snap["release"]["release_digest"])
        self.say("  projection_digest  %s" % snap["projection_digest"])
        self.say("  identity_digest    %s" % snap["identity_digest"])
        payloads = []
        for m in snap["members"]:
            payloads.append(m["payload_sha256"])
            self.say("  member %-18s payload %s manifest %s" % (m["source_id"], m["payload_sha256"], m["manifest_sha256"]))
        same = sorted(payloads) == sorted(FILE_SHAS)
        self.say("  the member payload hashes %s the three hashes of the runbook" % ("EQUAL" if same else "DIFFER FROM"))
        if not same:
            self.say("  (that is a reason to say no)")
        self.approve_or_stop("Do you approve this proposal for publishing?", "PROPOSAL_NOT_APPROVED", "the proposal")
        self.record("proposal approved", "approve")
        return {"approved": True, "context_id": p["context_id"], "payloads_match_runbook": same}

    # ---- stage 7: decision records, evidence, publish ---------------------------------------------------------------------------------------
    def git_ref(self, path):
        """GIT40 and DOC64 as runbook 7.1 and 7.2 say: the last commit that touched the file, and the SHA-256 of the file at that commit."""
        log = self.git("log", "-1", "--format=%H", "--", path, record=True)
        commit = log.text.strip()
        if log.code != 0 or not _HEX40.fullmatch(commit):
            raise Stop("GIT_REF", "no commit holds %s" % path)
        shown = self.git("show", "%s:%s" % (commit, path), record=True)
        if shown.code != 0:
            raise Stop("GIT_REF", "cannot read %s at %s" % (path, commit))
        return commit, hashlib.sha256(shown.out).hexdigest()

    def added_after(self, path, base):
        """True when `path` was ADDED by a commit in `base..HEAD` (git log --diff-filter=A): a file that is new since `base`, not one that was already there."""
        listed = self.git("log", "--diff-filter=A", "--format=%H", "%s..HEAD" % base, "--", path)
        lines = listed.text.split()
        return listed.code == 0 and bool(lines) and all(_HEX40.fullmatch(x) for x in lines)

    def s_pd_record(self, kind):
        texts = {"publish": "your decision to publish this release, valid_until 2027-09-01 00:00 Asia/Shanghai, and the disclosed upper-bound limit (PD-0068 answer 4: "
                            "term_end_not_after is an upper bound), as decisions/product/PD-NNNN-r8-publish.md",
                 "withdraw": "your decision to withdraw the context, as decisions/product/PD-NNNN-r8-withdraw.md",
                 "renew": "your decision to renew the context, valid_until 2027-09-01 00:00 Asia/Shanghai, as decisions/product/PD-NNNN-r8-renew.md"}
        self.say("Write and COMMIT %s." % texts[kind])
        self.say("(You may ask the main session to record your words verbatim. The commit may touch decisions/product/ only.)")
        used = {v["data"]["path"] for k, v in self.st["done"].items() if "path" in v["data"]}
        used |= {e["record"] for e in self.read_events() if e["kind"] == "latch_lifted" and e.get("record")}       # a reset's record is not a stage record
        while True:
            self.enter("When it is committed:")
            path = self.typed("Path of the committed file (decisions/product/PD-NNNN-....md):",
                              check=lambda a: None if _PD_PATH.fullmatch(a) else "not a path of the form decisions/product/PD-NNNN-name.md")
            try:
                if path in used:
                    raise Stop("PD_REUSED", "%s was already used for an earlier stage; each stage has its own record" % path)
                self.require_clean_tree()
                commit, sha = self.git_ref(path)
                first = (self.st["p8_history"][0] if self.st["p8_history"] else self.st["p8"])["commit"]
                if not self.added_after(path, first):
                    raise Stop("PD_NOT_NEW", "%s was not added in a commit after P8 (%s): a new decision record is needed for this act, not one that existed before R8" % (path, first))
            except Stop as stop:
                self.say("  not accepted: " + stop.message)
                continue
            stat = self.git("diff", "--stat", self.st["p8"]["commit"], "HEAD")
            self.say("git diff --stat P8 HEAD (only decisions/product/ files may appear):")
            self.say(stat.text.rstrip())
            pd_id = _PD_PATH.fullmatch(path).group(1)
            self.say("  GIT40 %s\n  DOC64 %s\n  %s\n  tree clean: yes" % (commit, sha, pd_id))
            self.record("%s decision record" % kind, {"path": path, "pd": pd_id, "commit": commit, "sha256": sha})
            return {"path": path, "pd": pd_id, "commit": commit, "sha256": sha}

    def pd_of(self, sid):
        return self.st["done"][sid]["data"]

    def evidence_refs(self):
        refs = {}
        for prefix, pd in EVIDENCE_PDS:
            listed = self.git("ls-files", "--", "decisions/product/%s-*.md" % pd, record=True)
            files = [l for l in listed.text.splitlines() if l]
            if len(files) != 1:
                raise Stop("EVIDENCE_PD", "expected exactly one committed file for %s, found %d" % (pd, len(files)))
            commit, sha = self.git_ref(files[0])
            refs[prefix] = (pd, commit, sha, files[0])
        return refs

    def s_evidence(self, out):
        self.require_clean_tree()
        refs = self.evidence_refs()
        argv = fw("real_tools.r8_files", "evidence")
        for prefix, _pd in EVIDENCE_PDS:
            pd, commit, sha, _file = refs[prefix]
            argv += ["--%s-pd" % prefix, pd, "--%s-commit" % prefix, commit, "--%s-sha" % prefix, sha]
        argv += ["--out", self.path(out)]
        result = self.exec("evidence", argv)
        if result.code != 0:
            self.tool_stop("evidence", result, "the evidence file writer")
        self.record("evidence citations (%s)" % out, {p: {"pd": r[0], "file": r[3], "commit": r[1], "sha256": r[2]} for p, r in refs.items()})
        return {"file": out}

    def status_generation(self, context):
        result = self.exec_pw("status", fw("persistence.real_workspace_store", "--socket", self.sock, "--database", DATABASE, "--user", ROLE_PUBLISHER, "--schema", SCHEMA,
                                        "status", "--context", context))
        found = re.search(r"context %s generation (\d+) kind" % re.escape(context), result.text)
        if result.code != 0 or not found:
            raise Stop("STATUS_UNREADABLE", "the status command did not give the generation (exit %d)" % result.code)
        return int(found.group(1))

    def publisher_argv(self, command, *args):
        return fw("persistence.real_workspace_store", "--socket", self.sock, "--database", DATABASE, "--user", ROLE_PUBLISHER, "--schema", SCHEMA, command, *args)

    def s_publish(self):
        pd = self.pd_of("pub_pd")
        argv = self.publisher_argv("publish", "--proposal", self.path("P.json"))
        for sidecar in SIDECARS:
            argv += ["--sidecar", sidecar]
        argv += ["--valid-until", VALID_UNTIL, "--evidence-file", self.path("E.json"), "--actor", ACTOR, "--pd", pd["pd"], "--commit", pd["commit"], "--sha", pd["sha256"]]
        result = self.exec_pw("publish", argv)
        if result.code != 0:
            self.tool_stop("publish", result, "publish")
        p_context = self.load_json("P.json")["context_id"]
        found = re.search(r"published context ([0-9a-f]{64}) at generation (\d+)", result.text) or re.search(r"already published: context ([0-9a-f]{64}), the original at generation (\d+)", result.text)
        if found is None:
            generation, context, created = self.status_generation(p_context), p_context, None
        else:
            context, generation, created = found.group(1), int(found.group(2)), "already published" not in found.group(0)
        if context != p_context:
            raise Stop("PUBLISH_CONTEXT_DIFFERS", "the publish printed context %s, but context_id in P.json is %s. Nothing further is done." % (context, p_context), latch=True, step="publish")
        self.record("publish", {"context": context, "generation": generation, "created": created})
        return {"context": context, "generation": generation, "created": created}

    # ---- the generation chain ---------------------------------------------------------------------------------------------------------------
    def generation_of(self, key):
        """The generation a later step needs: N from the publish, N' from the withdraw, N'' from the renew."""
        sid = {"generation": "publish", "generation_withdrawn": "withdraw", "generation_renewed": "renew"}[key]
        return self.st["done"][sid]["data"]["generation"]

    @property
    def context(self):
        return self.st["done"]["publish"]["data"]["context"]

    def s_contexts(self, out, key):
        argv = fw("real_tools.r8_files", "contexts", *inputs_args(self.name), "--proposal", self.path("P.json"), "--generation", self.generation_of(key), "--out", self.path(out))
        result = self.exec("contexts", argv)
        if result.code != 0:
            self.tool_stop("contexts", result, "the contexts file writer")
        return {"file": out, "generation": self.generation_of(key)}

    # ---- the screen -------------------------------------------------------------------------------------------------------------------------
    def ensure_services(self, cfile):
        svc = self.svc
        if svc and svc["cfile"] == cfile and svc["launcher"].poll() is None and svc["vite"].poll() is None:
            return
        self.stop_services(strict=True)
        vite_bin = str(self.repo / "web" / VITE_BIN)
        if not self.s.exists(vite_bin):         # the installed Vite only: npx with no terminal would DOWNLOAD a missing one
            raise Stop("VITE_MISSING", "%s is missing. Install the web dependencies (a provisioning step), then run again. The runner never uses npx." % vite_bin)
        for port in (LAUNCHER_PORT, VITE_PORT):
            if self.s.port_open(port):
                raise Stop("PORT_IN_USE", "port %d is already in use; stop what is using it, then run again" % port)
        self.enter("Next: start the launcher and the screen (two password prompts follow, then Vite).")
        self.require_clean_tree()
        self.say("Starting the launcher on %s. It asks for TWO passwords at its own prompts: the executor's, then the account role's." % cfile)
        argv = fw("web_api.real_launcher", "--socket", self.sock, "--database", DATABASE, "--user", ROLE_EXECUTOR, "--schema", SCHEMA, "--account-user", ROLE_ACCOUNT,
                  "--contexts-file", self.path(cfile), "--port", LAUNCHER_PORT)
        while True:
            self.say("$ " + shlex.join(argv))
            launcher = self.s.spawn(argv, env=self.child_env(), cwd=None)
            self.command("launcher", argv, None)
            self.save()
            outcome = None
            for _ in range(900):
                if launcher.poll() is not None:
                    text = launcher.output().decode("utf-8", "replace")
                    self.log("$ launcher -> exit %s\n%s\n" % (launcher.poll(), text))
                    tool_code = own_connection_failure(argv, launcher.poll(), text)
                    if tool_code is None:
                        raise Stop("LAUNCHER_EXIT_%s" % launcher.poll(), "the launcher stopped before it was ready (exit %s). A refusal of the gated launcher is not covered by the "
                                   "runbook (rule 0.4).\n%s" % (launcher.poll(), "\n".join(text.strip().splitlines()[-12:])), latch=True, step="create")
                    outcome = tool_code          # its own connection failed and nothing was started: the owner may try the identical command again
                    break
                if self.s.port_open(LAUNCHER_PORT):
                    outcome = ""
                    break
                self.s.sleep(1)
            if outcome is None:
                launcher.terminate()
                raise Stop("LAUNCHER_NOT_READY", "the launcher was not listening after 15 minutes")
            if outcome == "":
                break
            self.retry_gate("launcher", None, outcome)
        vite_argv = [vite_bin, "--config", "vite.real.config.ts"]
        self.say("$ (cd web && %s)" % shlex.join(vite_argv))
        vite = self.s.spawn(vite_argv, env=self.child_env(), cwd=str(self.repo / "web"), stdin_null=True)
        self.command("vite", vite_argv, None)
        self.save()
        self.svc = {"cfile": cfile, "launcher": launcher, "vite": vite}
        for _ in range(90):
            if vite.poll() is not None:
                self.stop_services(strict=False)
                raise Stop("VITE_EXIT", "Vite stopped before it was ready (exit %s); this is not an R8 tool. Run again." % vite.poll())
            if self.s.port_open(VITE_PORT):
                self.say("Both are ready. The screen: %s" % SCREEN_URL)
                return
            self.s.sleep(1)
        self.stop_services(strict=False)
        raise Stop("VITE_NOT_READY", "Vite was not listening on %d after 90 s" % VITE_PORT)

    def stop_services(self, strict=True):
        svc, self.svc = self.svc, None
        if svc is None:
            return
        for key in ("vite", "launcher"):
            svc[key].terminate()
        ports = {"vite": VITE_PORT, "launcher": LAUNCHER_PORT}
        for _ in range(20):
            if all(svc[k].poll() is not None and not self.s.port_open(ports[k]) for k in ports):
                self.say("The launcher and Vite are stopped.")
                return
            self.s.sleep(1)
        still = [k for k in ports if self.s.port_open(ports[k])]
        message = "the %s still listens on port(s) %s. Stop it by hand (Ctrl-C in its terminal, or kill it) before going on." % (" and ".join(still) or "process", ", ".join(str(ports[k]) for k in still))
        if strict:
            raise Stop("SERVICES_NOT_STOPPED", message)
        self.say("WARNING: " + message)

    def s_stop_services(self):
        self.stop_services(strict=True)
        for port in (LAUNCHER_PORT, VITE_PORT):
            if self.s.port_open(port):
                raise Stop("SERVICES_NOT_STOPPED", "port %d still listens; stop what holds it, then run again" % port)
        return {"stopped_at": self.stamp()}

    # ---- the create (rule 0.3) --------------------------------------------------------------------------------------------------------------
    def ask_response(self):
        status = self.typed("Status of the create's response (a number such as 201, 422, 404, 503, or UNKNOWN):",
                            check=lambda a: None if re.fullmatch(r"[0-9]{3}|UNKNOWN", a.upper()) else "a three-digit status or UNKNOWN")
        code = self.typed("Code of the response (for example REAL_REQUEST_INVALID; '-' if there is none):", check=lambda a: None if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", a) else "letters, digits, _ . - only")
        return status.upper(), code

    def s_create(self):
        v = self.form_values()
        self.say("Open %s, sign up a first account (user A), and fill the 'Create a root' form:" % SCREEN_URL)
        self.say("  Context ID  %s   (context_id in P.json, equal to the publish's hash)" % v["context_id"])
        self.say("  Release ID  %s   (snapshot.release.release_id in P.json)" % v["release_id"])
        self.say("  Listing ID  %s   (listings[0][0] in F.json; expected %s)" % (v["listing_id"], EXPECTED_LISTING_ID))
        self.say("  Name        free text, for example: R8 AAPL")
        for label, value in FORM_FIXED:
            self.say("  %-11s %s" % (label, value))
        self.say("Tick the acknowledgement, check the three ids above against the form BEFORE you click Create, then click Create.")
        if v["listing_id"] != EXPECTED_LISTING_ID:
            raise Stop("LISTING_ID_DIFFERS", "listings[0][0] of F.json is %s, not the expected %s" % (v["listing_id"], EXPECTED_LISTING_ID), latch=True, step="create")
        if v["context_id"] != self.context:
            raise Stop("CONTEXT_ID_DIFFERS", "context_id of P.json differs from the published context", latch=True, step="create")
        return self.classify_create_loop("create_a", "create")

    def classify_create_loop(self, label, step):
        """Ask for the response, classify it by rule 0.3, record every attempt. Returns on SUCCESS; raises a LATCHED stop on STOP."""
        attempts = []
        skip_enter = False
        if self.st.get("create_pending"):
            self.say("WARNING: an earlier run offered a create (%s) and no outcome of it was recorded. It may have been made." % self.st["create_pending"])
            skip_enter = self.typed("Did you click Create in that earlier run? (yes / no; if yes, type its outcome next):",
                                    check=lambda a: None if a in ("yes", "no") else "yes or no") == "yes"
        self.st["create_pending"] = label        # until an outcome is recorded: a quit or an interrupt cannot lose a create that may have happened
        self.save()
        while True:
            if not skip_enter:
                self.enter("When you have clicked Create and seen the response:")
            skip_enter = False
            status, code = self.ask_response()
            verdict = classify_create(status, code)
            self.say("  classified: %s" % {"SUCCESS": "success", "RETRY": "refused before any lease or commit (422 REAL_REQUEST_INVALID or 404): correct the input and retry",
                                           "STOP": "R8 STOPS (rule 0.3; PD-0081 as clarified by PD-0083)"}[verdict])
            if self.typed("Is that exactly what the screen showed? (yes / redo):", check=lambda a: None if a in ("yes", "redo") else "yes or redo") == "redo":
                self.event("redo", label=label, status=status, code=code, verdict=verdict)       # a typed-and-withdrawn answer leaves a trace
                continue
            note = ""
            if verdict == "RETRY":
                note = self.typed("What did you correct? (free text, no passwords):")
            entry = {"label": label, "status": status, "code": code, "verdict": verdict, "at": self.stamp(), "note": note}
            self.event("create", **{k: v for k, v in entry.items() if k != "at"})
            self.st["creates"].append(entry)
            attempts.append(entry)
            if verdict != "RETRY":
                self.st["create_pending"] = None
            self.save()
            if verdict == "SUCCESS":
                self.record("create outcome (%s)" % label, {"status": status, "code": code})
                return {"attempts": attempts}
            if verdict == "STOP":
                raise Stop("CREATE_%s_%s" % (status, code.upper()), "The real create (%s) came back %s %s. By rule 0.3 R8 STOPS here: nothing is re-run, by hand or by a tool, until the cause "
                           "is found and a reviewed fix is committed. The outcome, its code and what you observed go in the HG4 package as a first-run observation." % (label, status, code),
                           latch=True, step=step)
            self.say("Recorded the refusal and its code. Correct the input (the three ids against P.json and F.json) and click Create again.")

    # ---- checks -----------------------------------------------------------------------------------------------------------------------------
    def s_check_nav(self):
        self.say("Compare with what the screen shows (the figures show without trailing zeros or grouping; the runner compares numerically). The close is not asked: the "
                 "screen shows `10 x p` and no price by design (ruling section 8 item 4; DR-R8-2), and the client never derives it.")
        attempts = []
        for _ in range(3):
            typed = {name: self.typed("Type the %s the screen shows:" % label, check=lambda a: None if a else "type a value") for name, label in
                     (("holding", "holding value"), ("nav", "NAV (USD)"), ("missed_sessions", "missed sessions"), ("state", "state (AVAILABLE, LIMITED or INSUFFICIENT_DATA)"))}
            result = compare_nav(typed["holding"], typed["nav"], typed["missed_sessions"], typed["state"])
            attempts.append({"typed": typed, "equal": result, "at": self.stamp()})
            ok = all(result.values())
            self.say("  against the Quant's values (ruling 9.1): %s" % ", ".join("%s %s" % (k, "equal" if v else "NOT equal") for k, v in result.items()))
            if ok or self.typed("Retype? (yes / no):", check=lambda a: None if a in ("yes", "no") else "yes or no") == "no":
                break
        final = all(attempts[-1]["equal"].values())
        self.record("check 10.1 NAV against the Quant's figure", {"result": "PASS" if final else "FAIL", "attempts": attempts})
        return {"result": "PASS" if final else "FAIL"}

    def ask_verdict(self, label):
        verdict = self.typed("%s: pass or fail? (pass / fail):" % label, check=lambda a: None if a.lower() in ("pass", "fail") else "pass or fail").upper()
        note = self.typed("A note for the record (free text, no passwords; Enter for none):")
        return {"result": verdict, "note": note}

    def s_check_simple(self, sid, title, parts):
        out = {}
        for part in parts:
            out[part] = self.ask_verdict(title if part == "result" else "%s, %s" % (title, part))
        self.record("check " + title, out)
        return {"results": out}

    # ---- stage 11 ---------------------------------------------------------------------------------------------------------------------------
    def s_probe_ids(self):
        username = self.typed("User A's username on the screen:", check=lambda a: None if _USERNAME.fullmatch(a) else "letters, digits and . _ @ - only")
        script = self.write_script("owner_id.sql", SCRIPT_OWNER_ID)
        result = self.exec_pw("probe_ids", self.psql_argv(script, ("username", username)))
        owner = parse_marker(result.text, "owner_id")
        if result.code != 0 or owner is None:
            raise Stop("OWNER_ID_NOT_READ", "the owner id was not read (psql exit %d); check the username and run this step again" % result.code)
        try:
            owner = str(uuid.UUID(owner))
        except ValueError:
            raise Stop("OWNER_ID_NOT_READ", "psql returned something that is not a UUID") from None
        root = self.typed("The root id of A's root (from the list on the screen):", check=lambda a: None if _valid_uuid(a) else "a UUID in lowercase hyphenated form")
        self.record("probe ids", {"owner_id": owner, "root_id": root, "username": username})
        return {"owner_id": owner, "root_id": root}

    def s_probe(self, step, key, expect, label):
        ids = self.st["done"]["probe_ids"]["data"]
        generation = self.generation_of(key)
        argv = fw("real_tools.admission_probe", "--socket", self.sock, "--database", DATABASE, "--user", ROLE_EXECUTOR, "--schema", SCHEMA, "--purpose", "ARCHIVE_EXPORT",
                  "--owner-id", ids["owner_id"], "--root-id", ids["root_id"], "--context", self.context, "--generation", generation)
        result = self.exec_pw(step, argv)
        refused = re.search(r"REFUSED (RW_[A-Z0-9_]+) purpose=", result.text)
        if result.code != expect:
            raise Stop("%s_EXIT_%d" % (step.upper(), result.code), "the probe (%s) exited %d; %d was expected. It is not a gateway answer the runbook covers (rule 0.4).\n%s" % (
                label, result.code, expect, "\n".join(result.text.strip().splitlines()[-8:])), latch=True, step=step)
        code = refused.group(1) if refused else None
        showing = None if expect == 0 else (code == "RW_WITHDRAWN")
        self.record("probe: %s" % label, {"exit": result.code, "generation": generation, "gateway_code": code, "shows_the_withdrawal": showing})
        return {"exit": result.code, "code": code, "shows_the_withdrawal": showing}

    def s_withdraw(self):
        pd = self.pd_of("wd_pd")
        argv = self.publisher_argv("withdraw", "--context", self.context, "--generation", self.generation_of("generation"), "--actor", ACTOR, "--pd", pd["pd"], "--commit", pd["commit"], "--sha", pd["sha256"])
        while True:
            self.require_clean_tree()
            result = self.exec_pw("withdraw", argv)
            if result.code == 0:
                found = re.search(r"done(?: \(already effective\))?: generation (\d+) names drain mark (\d+)", result.text)
                if found is None:
                    raise Stop("WITHDRAW_UNPARSED", "the withdraw exited 0 but its generation was not found in the output; read it with the `status` command", latch=False)
                generation = int(found.group(1))
                self.record("withdraw", {"generation": generation, "mark": int(found.group(2))})
                return {"generation": generation, "mark": int(found.group(2))}
            if result.code == 3:
                self.enter("Exit 3 (not yet effective: a lease was in flight). The runbook says to run the identical withdraw again once the in-flight work ends.")
                continue
            self.tool_stop("withdraw", result, "withdraw")

    def s_c1_refusals(self):
        self.say("With the launcher on C1.json (the withdrawn generation), check all four rights are refused, each showing the WITHDRAWAL, not 'the context changed':")
        out = {}
        self.enter("1. create: try a create of the same form. Expect 'The context has been withdrawn' (RW_WITHDRAWN). Then:")
        status, code = self.ask_response()
        # Under the withdrawal only a REFUSAL (a 4xx status) with the code RW_WITHDRAWN passes; a 2xx means the rights were not revoked, and it stops R8.
        expected = code.upper() == "RW_WITHDRAWN" and status.startswith("4")
        entry = {"label": "create_withdrawn", "status": status, "code": code, "verdict": "EXPECTED_REFUSAL" if expected else "UNEXPECTED", "at": self.stamp(), "note": ""}
        self.event("create", **{k: v for k, v in entry.items() if k != "at"})
        self.st["creates"].append(entry)
        self.save()
        out["create"] = entry
        if entry["verdict"] != "EXPECTED_REFUSAL":
            raise Stop("C1_CREATE_%s_%s" % (status, code.upper()), "The create under the withdrawn context came back %s %s, not a refusal with RW_WITHDRAWN (a 2xx means the rights were not revoked). R8 stops here (rule 0.3 applies to every real create)." % (status, code), latch=True, step="c1_refusals")
        for part in ("2. read and reproduce A's root at the screen", "3. the list, with its per-root status"):
            out[part] = self.ask_verdict("%s: refused and showing the withdrawal" % part)
        self.say("4. export: the next step runs the probe at N' (direct gateway admission).")
        self.record("withdrawn: four rights (create, read/reproduce, list)", out)
        return {"results": out}

    def s_renew(self):
        pd = self.pd_of("rn_pd")
        argv = self.publisher_argv("renew", "--context", self.context, "--generation", self.generation_of("generation_withdrawn"), "--valid-until", VALID_UNTIL,
                                   "--evidence-file", self.path("E2.json"), "--actor", ACTOR, "--pd", pd["pd"], "--commit", pd["commit"], "--sha", pd["sha256"])
        result = self.exec_pw("renew", argv)
        if result.code != 0:
            self.tool_stop("renew", result, "renew")
        found = re.search(r"renewed context ([0-9a-f]{64}): generation (\d+) recorded", result.text)
        if found is None or found.group(1) != self.context:
            raise Stop("RENEW_UNPARSED", "the renew exited 0 but its generation was not found for this context; read it with the `status` command and use --resolve renew done", latch=False)
        generation = int(found.group(2))
        self.record("renew", {"generation": generation})
        return {"generation": generation}

    def s_c2_rights(self):
        self.say("With the launcher on C2.json (the renewed generation), check user A can read, reproduce, list and create again.")
        out = {}
        for part in ("read", "reproduce", "list"):
            out[part] = self.ask_verdict("A can %s again" % part)
        self.say("Now a create (a real commit: rule 0.3 applies exactly as in the first create). Fill the same form values as before and click Create.")
        out["create"] = self.classify_create_loop("create_c2", "c2_rights")
        self.record("renewed: rights restored (read, reproduce, list)", {k: v for k, v in out.items() if k != "create"})
        return {"results": out}

    # ---- stage 12 ---------------------------------------------------------------------------------------------------------------------------
    STATEMENTS = ("I held the executor's and the loader's credentials myself; no agent session held any (PD-0077).",
                  "I typed every password only at a prompt of a reviewed tool, psql, initdb or sudo, never on a command line, in a file or in a message.")

    def s_close(self):
        self.stop_services(strict=False)
        confirmed = []
        for text in self.STATEMENTS:
            self.say("Statement: " + text)
            confirmed.append({"statement": text, "answer": self.typed("Is it true? (yes / no):", check=lambda a: None if a in ("yes", "no") else "yes or no")})
        surprised = self.typed("Anything that surprised you? (free text, no passwords; Enter for none):")
        self.st["statements"] = confirmed
        self.st["surprises"] = surprised
        self.record("statements", confirmed)
        self.record("surprises", surprised)
        path = self.dir / "R8_RECORD.md"
        if path.exists():
            raise Stop("RECORD_EXISTS", "%s already exists and is never overwritten" % path)
        body = self.record_text()
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, body.encode())
        finally:
            os.close(fd)
        self.say("Wrote %s (mode 0600). Give it to the main session as the HG4 input (it holds no password)." % path)
        self.say("The cluster is still running. To stop it, as the cluster user: sudo -u %s %s -D %s stop" % (self.st["frozen"]["cluster_user"], self.st["frozen"]["pg_ctl"], self.d("data")))
        return {"record": str(path)}

    def record_text(self):
        """Built from the append-only events log, not from state.json: a hand edit of the state cannot erase a stop or a create from the record."""
        events = self.read_events()
        lines = ["# R8 record (written by the guided runner)", "", "Written %s. This is the owner's input to HG4: every [record] item of the runbook, the tool exit statuses, "
                 "codes, hashes and generations, the check results and the create outcomes. Built from %s. It holds no password." % (self.stamp(), EVENTS_NAME), ""]
        records = [e for e in events if e["kind"] == "record"]
        lines += ["## Run", ""]
        for e in records:
            if e["item"].startswith("P8"):
                lines.append("- reviewed commit P8: `%s` (recorded %s)" % (e["value"], e["at"]))
        for e in records:
            if e["item"] == "frozen values":
                lines.append("- frozen values: `%s`" % json.dumps(e["value"], sort_keys=True))
        lines += ["", "## Stops", ""]
        for e in events:
            if e["kind"] == "latch":
                lines.append("- STOP latched (%s): %s at step %s: %s" % (e["at"], e.get("code"), e.get("step"), (e.get("message") or "").splitlines()[0] if e.get("message") else ""))
            elif e["kind"] == "latch_lifted":
                lines.append("- stop lifted (%s) under %s (%s); new P8 `%s`" % (e["at"], e.get("by"), e.get("record"), e.get("new_p8")))
            elif e["kind"] == "window_reopen":
                lines.append("- loader window %s reopened before %s (%s)" % (e.get("window"), e.get("before"), e["at"]))
        lines += ["", "## Records", ""]
        for e in records:
            lines.append("- %s: `%s` (%s)" % (e["item"], json.dumps(e["value"], sort_keys=True), e["at"]))
        lines += ["", "## Create outcomes", ""]
        for e in events:
            if e["kind"] == "create":
                lines.append("- %s: status %s, code %s, %s (%s)%s" % (e["label"], e["status"], e["code"], e["verdict"], e["at"], (" note: " + e["note"]) if e.get("note") else ""))
            elif e["kind"] == "redo":
                lines.append("- (typed, then withdrawn with redo) %s: status %s, code %s, would have been %s (%s)" % (e["label"], e["status"], e["code"], e["verdict"], e["at"]))
        lines += ["", "## Steps done", ""]
        for e in events:
            if e["kind"] == "done":
                lines.append("- %s at %s" % (e["step"], e["at"]))
        lines += ["", "## Commands and exit statuses (no output, no secrets)", ""]
        for e in events:
            if e["kind"] == "command":
                lines.append("- [%s] %s -> %s (%s)" % (e["step"], shlex.join(e["argv"]), "running" if e["code"] is None else e["code"], e["at"]))
        surprises = [e["value"] for e in records if e["item"] == "surprises"]
        lines += ["", "## Surprises", "", surprises[-1] if surprises and surprises[-1] else "(none stated)", ""]
        return "\n".join(lines)

    # ---- entry points -----------------------------------------------------------------------------------------------------------------------
    def preconditions(self):
        """Runbook section 2. Refuses, rather than repairs."""
        if not (self.repo / "pyproject.toml").exists() or not (self.repo / "src" / "real_tools" / "r8_guide.py").exists():
            raise Stop("NOT_REPO_ROOT", "run this from the repository root")
        top = self.git("rev-parse", "--show-toplevel")
        if top.code != 0 or self.s.realpath(top.text.strip()) != self.s.realpath(str(self.repo)):
            raise Stop("NOT_REPO_ROOT", "the current directory is not the root of the git repository")
        pg = sorted(k for k in self.s.environ() if k.upper().startswith("PG"))
        if pg:
            raise Stop("ENV_HAS_LIBPQ_VARIABLES", "these PG* variables are set (names only): %s. Unset them (`unset $(env | grep -o '^PG[A-Z_]*')`) and run again; the runner does not "
                       "do it for you, and it never uses them." % ", ".join(pg))
        for name in (".pgpass", ".pg_service.conf"):
            if self.s.exists(str(self.home / name)):
                raise Stop("STORED_CREDENTIAL_FILE_PRESENT", "%s exists; R8 refuses to run with a passfile or a service file present" % (self.home / name))
        status = self.git("status", "--porcelain")
        if status.code != 0 or status.text.strip():
            raise Stop("TREE_NOT_CLEAN", "the working tree is not clean (`git status --porcelain` must print nothing): %s" % (status.text.strip()[:300] or "git failed"))

    def resolve_binaries(self):
        psql = self.s.which("psql")
        if not psql:
            raise Stop("NO_PSQL", "psql is not on PATH")
        real = self.s.realpath(psql)
        bindir = os.path.dirname(real)
        out = {"psql": real, "initdb": bindir + "/initdb", "pg_ctl": bindir + "/pg_ctl"}
        version = self.exec("preconditions", [real, "--version"], record=False)
        found = re.search(r"(\d+)\.", version.text)
        if version.code != 0 or not found or int(found.group(1)) < 17:
            raise Stop("PSQL_VERSION", "psql 17 or later is needed (the window close uses \\watch min_rows): %s" % version.text.strip())
        out["psql_version"] = version.text.strip()
        return out

    def first_run(self):
        values = self.frozen_values()
        head = self.git("rev-parse", "HEAD")
        subject = self.git("log", "-1", "--format=%s")
        self.say("First run. These values are FROZEN from now on (the release name enters the release id and the context for good):")
        for k, v in values.items():
            self.say("  %-13s %s" % (k, v))
        self.say("This commit becomes P8, the reviewed commit you run from: %s  %s" % (head.text.strip(), subject.text.strip()))
        self.confirm_word("Freeze these values and record this commit as P8?", "freeze")
        binaries = self.resolve_binaries()
        self.st = {"schema": self.SCHEMA, "frozen": dict(values, **binaries), "p8": {"commit": self.head(), "at": self.stamp(), "subject": subject.text.strip()},
                   "done": {}, "started": {}, "records": [], "commands": [], "creates": [], "create_pending": None, "window": {"n": 0, "open": False}, "latch": None, "latch_history": [], "p8_history": []}
        self.record("P8 (the reviewed commit)", self.st["p8"]["commit"])      # the first event, written before the state file exists
        self.record("frozen values", self.st["frozen"])

    def latch_message(self):
        latch = self.st["latch"]
        return ("R8 IS STOPPED (since %s): %s at step %s.\n%s\nNothing is re-run, by hand or by a tool, until the cause is found and a reviewed fix is committed. "
                "A plain re-run does not continue. After the fix and your decision record are committed: --reset-stop PD-NNNN%s" % (
                    latch["at"], latch["code"], latch["step"], latch["message"], self.window_notice()))

    def window_notice(self):
        """Prominent, whenever a loader window is marked open (TR8G-M-1)."""
        window = (self.st or {}).get("window") or {}
        if not window.get("open"):
            return ""
        return ("\n!!! LOADER WINDOW %s IS MARKED OPEN: the loader role may still be LOGIN. Close it (it asks for the superuser password at psql's prompt):\n"
                "!!!   %s" % (window.get("n"), CLOSE_COMMAND))

    def handle_stop(self, stop):
        self.say("\nSTOP [%s]: %s" % (stop.code, stop.message))
        if stop.latch and self.st is not None:
            # FIRST, before anything that can be interrupted (the window close asks for a password): a latch that is not saved is a stop that did not happen.
            latch = {"code": stop.code, "message": stop.message, "step": stop.step, "at": self.stamp(), "head": None}
            self.event("latch", **{k: v for k, v in latch.items() if k != "at"})
            self.st["latch"] = latch
            self.save()
            latch["head"] = self.safe_head()
            self.save()
        if stop.close_window and self.st and self.st["window"].get("open"):
            self.say("A definite answer: the loader window is closed now.")
            try:
                self.close_window_now(self.st["window"]["n"])
            except (Exception, KeyboardInterrupt) as other:         # the latch is already saved; the window may be open and the notice says so
                self.say("The window could not be closed here: %s" % (other.message if isinstance(other, Stop) else "stopped or interrupted"))
        if self.window_notice():
            self.say(self.window_notice())
        if stop.latch and self.st is not None:
            self.say("\nTell the main session: R8 stopped at step %s with %s. Quote the lines above. Do not re-run anything. The runner now refuses every later run until a "
                     "reviewed fix is committed and --reset-stop is used." % (stop.step, stop.code))
            return EXIT_STOPPED
        self.say("(No latch: fix the cause and run again.)")
        return EXIT_STOPPED

    def safe_head(self):
        try:
            return self.head()
        except Stop:
            return None

    def main_run(self):
        try:
            self.ensure_dir()
            had = self.load()
            if had:
                self.check_frozen_unchanged()
                log_latched, log_latch = self.latch_from_events(self.read_events())
                if log_latched and not self.st["latch"]:
                    # The log says R8 is stopped and the state does not (an interrupt between the two writes, or a hand edit): the log decides.
                    self.say("The state file and %s disagree about a stop; the log wins and the latch is restored." % EVENTS_NAME)
                    self.st["latch"] = dict(log_latch, head=log_latch.get("head"))
                    self.save()
                elif self.st["latch"] and not log_latched:
                    self.say("The state file holds a stop that %s does not. Nothing continues until the main session has looked at it." % EVENTS_NAME)
                    self.say(self.latch_message())
                    return EXIT_LATCHED
                if self.st["latch"]:
                    self.say(self.latch_message())
                    return EXIT_LATCHED
                self.preconditions()
                self.check_head()
            else:
                self.preconditions()
                self.first_run()
            if self.st["window"].get("open"):
                self.say("NOTE: loader window %s is marked OPEN. It is closed by its own step (or run with --close-window)." % self.st["window"]["n"])
            return self.run_steps()
        except Quit:
            self.say("\nStopped for now. Run the same command again to continue.")
            return EXIT_PAUSED
        except Stop as stop:
            return self.handle_stop(stop)
        except KeyboardInterrupt:
            self.say("\nInterrupted. Run the same command again to continue.")
            return EXIT_PAUSED
        finally:
            self.stop_services(strict=False)

    def close_window_mode(self):
        """`--close-window`: closes an open loader window even when a stop latch is set (closing only reduces what is open)."""
        try:
            self.ensure_dir()
            if not self.load():
                self.say("No state file: nothing is open.")
                return EXIT_DONE
            self.preconditions()
            n = self.st["window"].get("n", 0)
            if not self.st["window"].get("open"):
                self.say("No loader window is marked open.")
                return EXIT_DONE
            self.enter("Close loader window %d (NOLOGIN, end its sessions):" % n)
            self.close_window_now(n)
            return EXIT_DONE
        except Quit:
            return EXIT_PAUSED
        except Stop as stop:
            self.say("STOP [%s]: %s" % (stop.code, stop.message))
            return EXIT_STOPPED

    def reset_stop(self, pd_id):
        """Lifts the latch after a reviewed fix: the owner's decision record is committed, HEAD is newer than the stopped one and clean, and the owner types the phrase."""
        try:
            self.ensure_dir()
            if not self.load():
                self.say("No state file.")
                return EXIT_STOPPED
            log_latched, log_latch = self.latch_from_events(self.read_events())
            if log_latched and not self.st["latch"]:
                self.st["latch"] = dict(log_latch)
                self.save()
            elif self.st["latch"] and not log_latched:
                raise Stop("STATE_LOG_DISAGREE", "the state file holds a stop that %s does not; tell the main session" % EVENTS_NAME)
            if not self.st["latch"]:
                self.say("No stop latch is set.")
                return EXIT_DONE
            if not re.fullmatch(r"PD-\d{4}", pd_id):
                raise Stop("RESET_PD", "give the owner's decision record as PD-NNNN")
            self.preconditions()
            files = [l for l in self.git("ls-files", "--", "decisions/product/%s-*.md" % pd_id).text.splitlines() if l]
            if len(files) != 1:
                raise Stop("RESET_PD", "%s is not committed under decisions/product/ (found %d files)" % (pd_id, len(files)))
            latch = self.st["latch"]
            head = self.head()
            since = latch.get("head") or self.st["p8"]["commit"]
            if head == since or self.git("merge-base", "--is-ancestor", since, head).code != 0:
                raise Stop("RESET_NO_FIX", "HEAD %s is not a newer commit than the one the stop happened at (%s): a reviewed fix must be committed first" % (head, since))
            if not self.added_after(files[0], since):
                raise Stop("RESET_PD", "%s was not added in a commit after the stop (%s): the decision record for a reset must be a new file, not an earlier one" % (files[0], since))
            self.say(self.latch_message())
            self.say("Lifting it records: the stop, %s (your record), and the new HEAD %s as the new reviewed commit P8." % (pd_id, head))
            self.confirm_word("Have the fix and its review been committed, and do you lift the stop?", "RESET R8 STOP")
            self.event("latch_lifted", by=pd_id, record=files[0], new_p8=head, latch=latch)
            self.st["latch_history"].append(dict(latch, lifted_at=self.stamp(), lifted_by=pd_id, new_p8=head))
            self.st["p8_history"].append(dict(self.st["p8"]))
            self.st["p8"] = {"commit": head, "at": self.stamp(), "subject": "after stop reset under " + pd_id}
            if latch.get("step") and latch["step"] in self.st["started"]:
                self.st["started"].pop(latch["step"])
            self.st["latch"] = None
            self.st["pw_failures"] = {}
            self.save()
            self.say("The stop is lifted. Run the runner again; it continues at the step that stopped.")
            return EXIT_DONE
        except Quit:
            return EXIT_PAUSED
        except Stop as stop:
            self.say("STOP [%s]: %s" % (stop.code, stop.message))
            return EXIT_STOPPED

    def resolve(self, sid, action):
        """`--resolve STEP retry|done`: the owner's statement about a step whose end was not recorded."""
        try:
            self.ensure_dir()
            if not self.load():
                self.say("No state file.")
                return EXIT_STOPPED
            if self.st["latch"]:
                self.say(self.latch_message())
                return EXIT_LATCHED
            names = [d.sid for d, _ in self.steps]
            if sid not in names or sid not in self.st["started"] or sid in self.st["done"]:
                self.say("Step %s is not an interrupted step." % sid)
                return EXIT_STOPPED
            if action == "retry":
                self.confirm_word("Nothing of %s happened (or you have undone it)?" % sid, "retry")
                self.st["started"].pop(sid)
            else:
                self.confirm_word("%s finished?" % sid, "done")
                data = {}
                if sid == "renew":
                    self.preconditions()
                    data = {"generation": self.status_generation(self.context)}
                self.st["done"][sid] = {"at": self.stamp(), "data": dict(data, resolved_by_owner=True)}
                self.st["started"].pop(sid)
            self.record("owner resolved an interrupted step", {"step": sid, "action": action})
            return EXIT_DONE
        except Quit:
            return EXIT_PAUSED
        except Stop as stop:
            self.say("STOP [%s]: %s" % (stop.code, stop.message))
            return EXIT_STOPPED

    def status_mode(self):
        self.ensure_dir()
        try:
            if not self.load():
                self.say("No R8 run started yet.")
                return EXIT_DONE
        except Stop as stop:
            self.say("STATUS cannot be shown [%s]: %s" % (stop.code, stop.message))
            return EXIT_STOPPED
        done, nxt = self.progress()
        self.say("P8 %s; frozen %s" % (self.st["p8"]["commit"], json.dumps({k: v for k, v in self.st["frozen"].items() if k in DEFAULTS}, sort_keys=True)))
        self.say("done: %s" % (", ".join(done) or "nothing"))
        self.say("next: %s" % (nxt or "(all done)"))
        if self.st["latch"]:
            self.say(self.latch_message())
        elif self.window_notice():
            self.say(self.window_notice())
        log_latched, _ = self.latch_from_events(self.read_events())
        if log_latched != bool(self.st["latch"]):
            self.say("WARNING: the state file and %s disagree about a stop. The next run refuses until the main session has looked." % EVENTS_NAME)
        return EXIT_DONE


def _valid_uuid(text):
    try:
        return str(uuid.UUID(text)) == text
    except ValueError:
        return False


def _build_parser():
    parser = argparse.ArgumentParser(prog="r8_guide", description="Guided runner for the R8 runbook. Run it from the repository root; run it again to resume.")
    parser.add_argument("--cluster-user", help="first run only (default finwebpg)")
    parser.add_argument("--base", help="first run only (default /Users/Shared/finweb-r8-pg)")
    parser.add_argument("--port", type=int, help="first run only (default 5433)")
    parser.add_argument("--superuser", help="first run only (default finweb_su)")
    parser.add_argument("--release-name", help="first run only (default hg4-aapl-2026-09-30); permanent")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true", help="show progress; does nothing else")
    mode.add_argument("--close-window", action="store_true", help="close an open loader window (also when a stop is latched)")
    mode.add_argument("--reset-stop", metavar="PD-NNNN", help="lift a stop after a reviewed fix and the owner's decision record are committed")
    mode.add_argument("--resolve", nargs=2, metavar=("STEP", "ACTION"), help="tell the runner what happened to an interrupted step: retry or done")
    return parser


def main(argv=None, *, seams=None, home=None, repo_root=None):
    args = _build_parser().parse_args(argv)
    seams = seams or real_seams()
    guide = Guide(seams, home or Path.home(), repo_root or Path.cwd(),
                  overrides={"cluster_user": args.cluster_user, "base": args.base, "port": args.port, "superuser": args.superuser, "release_name": args.release_name})
    if args.status:
        return guide.status_mode()
    if args.close_window:
        return guide.close_window_mode()
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
