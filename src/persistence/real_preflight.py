"""F1 R6: the PREFLIGHT of the install rule for the real cluster (design 1.2 rule 5, 5.1 to 5.4, rule 6 and rule 7).

WHAT IT GUARDS. A REAL install and nothing else: a database whose install kind row is `REAL` and whose name starts with the reserved prefix
(`connection.RESERVED_REAL_PREFIX`, "finweb_real"). There is NO flag, environment variable or configuration key that selects, skips or relaxes
it: the decision comes from two facts read from the database (`decide_target`, the table of 5.2), and the gate is keyed to the COMMAND
(`command_plan`, 5.1): `publish` and `renew` are gated, `withdraw` never is. The launcher and the admission probe are R7's; they call the same
entry point.

THREE LAYERS, so that the decision logic is testable on facts and the gathering on a server:

  * `decide(facts, ...)`            pure. A fact set in, a `Decision` out. Every refusal has its own named code (`PF_*`). No connection, no clock,
                                    no file, no environment. This is what R6's case list exercises.
  * `gather_facts(conn, ...)`       reads the facts from a connection (a runtime tool's non-superuser vantage, or the installer's superuser
                                    vantage), plus Pass S (static scan of stored credentials, no connection) and Pass A / Pass B (connection
                                    attempts in a child process). Anything it cannot read is recorded as NOT INSPECTED, which refuses.
  * `run_runtime_gate` / the installer's phases   glue.

WHAT IT NEVER DOES. It sends no statement on a probe connection (the child opens a connection with libpq and closes it at once). It prints no
password: Pass S reads the first four fields of a passfile line and the keys of a service section, and the password is neither kept nor shown.
It takes no credential from the environment, a file or an argument: the only route is the terminal prompt (`terminal_prompt`), in the tests
too (the tests hand a fake prompt to the same seam, which a static test confirms is the only one).

THE ONE ENVIRONMENT READ. `process_environment()` returns a copy of the caller's environment so that Pass S can look for `PGPASSWORD` and the
file names libpq would use, and so that Pass B's child inherits the caller's own default credential sources. It is READ to REFUSE; no value of it
reaches a connection string. A static test confines every `os.environ` access of this module to that function.

WHAT IT CANNOT SEE (5.4, stated again): from a runtime tool's vantage the hba rows and the verifiers; from either vantage the owner's password
stores outside the files libpq itself would read; grants are not re-read at a gated start (the installer's catalog audit does that, at Phase 2
and in each `--check`). A passing preflight is a tripwire from the vantage of the process that ran it, now.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile

from persistence.connection import RESERVED_REAL_PREFIX, build_conninfo, conninfo_with, is_reserved_real_name

# ---- the real install's names (one place; the installer, the seed and the gate read these) ---------------------------------------------------
#: Chosen by the engineer (design 1.2 rule 5.3 (d) names `finweb_real` and `finweb_real_publisher` as examples). The database name starts with the
#: reserved prefix, so a tool that sees it takes the database for a REAL target before it reads the kind row.
REAL_DATABASE = RESERVED_REAL_PREFIX
REAL_SCHEMA = "finweb"
REAL_ROLES = {"owner": "finweb_real_owner", "executor": "finweb_real_executor", "loader": "finweb_real_loader", "publisher": "finweb_real_publisher",
              "account": "finweb_real_account"}      # PD-0078: the fifth role, which holds the web accounts (identity and session tables) and nothing else
#: `W` of the lease (design E4: the engineer's proposal for the real install is 10 minutes; it only shortens deadlines; the owner may change it).
REAL_W_SECONDS = 600
MIN_SERVER_VERSION_NUM = 170000

#: What `withdraw` demands of the server's authentication (design 5.1; PM list (v); PD-0076 choice E, the owner's answer "Refuse plaintext
#: (!password)"). "!password": libpq refuses only a server that asks for a CLEARTEXT password, so the publisher's password is never sent in the
#: clear to whatever answers on the socket, and a scram server (which never asks for one) never stops a withdrawal. The alternatives were None (no
#: demand) and "scram-sha-256" (the gated commands' demand, one more thing that can stop a withdrawal). `withdraw` is still never gated by the
#: preflight: only its own connection carries this. A reviewed change to this constant is the only way to change it: no option, variable or key reaches it.
WITHDRAW_REQUIRE_AUTH = "!password"
GATED_REQUIRE_AUTH = "scram-sha-256"

# ---- refusal codes ------------------------------------------------------------------------------------------------------------------------
PF_SERVER_VERSION = "PF_SERVER_VERSION_BELOW_17"
PF_PREPARED = "PF_PREPARED_TRANSACTIONS"
PF_LISTEN = "PF_LISTEN_ADDRESSES"
PF_SESSION_REPLICATION = "PF_SESSION_REPLICATION_ROLE"
PF_KIND_DISAGREE = "PF_KIND_NAME_DISAGREE"
PF_NO_KIND = "PF_NO_KIND_ROW"
PF_CONNECTED = "PF_CONNECTED"
PF_OTHER = "PF_OTHER_OUTCOME"
PF_LOGIN_POWER = "PF_LOGIN_POWER_ROLE"
PF_MEMBERSHIP = "PF_ESCALATION_PATH"
PF_ROLE_CONFIG = "PF_ROLE_SETTING"
PF_DB_ROLE_SETTING = "PF_DB_ROLE_SETTING_ROW"
PF_PARAMETER = "PF_PARAMETER_PRIVILEGE"
PF_CONNECT_ELSEWHERE = "PF_CONNECT_OUTSIDE_REAL_DATABASE"
PF_STORED = "PF_STORED_CREDENTIAL"
PF_NOT_INSPECTED = "PF_NOT_INSPECTED"
PF_COVERAGE = "PF_PROBE_NOT_RUN"
PF_HBA_METHOD = "PF_HBA_METHOD"
PF_HBA_TYPE = "PF_HBA_NOT_LOCAL"
PF_HBA_ERROR = "PF_HBA_ROW_ERROR"
PF_HBA_LOADED = "PF_HBA_FILE_LOADED_DIFFER"
PF_VERIFIER = "PF_VERIFIER_NOT_SCRAM"
PF_PASSWORD_ENCRYPTION = "PF_PASSWORD_ENCRYPTION"
PF_LOG = "PF_LOG_STATEMENT"
PF_PATH = "PF_PATH_UNDER_FORBIDDEN_ROOT"
PF_AUDIT = "PF_CATALOG_AUDIT"
PF_ROLE_MISSING = "PF_REAL_ROLE_MISSING"
PF_REQUIRE_AUTH = "PF_REQUIRE_AUTH"
PF_CONNECT_FAILED = "PF_CONNECT_FAILED"
PF_REAL_EXISTS = "PF_REAL_ALREADY_EXISTS"

CONNECTED, CHALLENGED, REJECTED, OTHER = "CONNECTED", "CHALLENGED", "REJECTED", "OTHER"
POWER_ATTRIBUTES = ("superuser", "createrole", "createdb", "replication", "bypassrls")


@dataclass(frozen=True)
class Refusal:
    code: str
    subject: str = ""
    detail: str = ""

    def short(self):
        return "%s %s%s" % (self.code, self.subject, (" (" + self.detail + ")") if self.detail else "")


@dataclass(frozen=True)
class Decision:
    ok: bool
    refusals: tuple
    lines: tuple

    def codes(self):
        return tuple(sorted({r.code for r in self.refusals}))

    @property
    def text(self):
        return "\n".join(self.lines)


# ===================================================================================================================================
# 5.2: what is a REAL target; 5.1: which command is gated
# ===================================================================================================================================
@dataclass(frozen=True)
class Target:
    decision: str            # "REAL", "TEST" or "REFUSE"
    code: str = ""
    detail: str = ""


def decide_target(database, kind_rows):
    """The table of 5.2. Two facts, both READ: the database's name and its install-kind rows (`kind_rows`: the kinds read from the database, or
    None when they cannot be read). No argument, variable or key enters. REAL: kind `REAL` and a name with the reserved prefix. TEST: kind `TEST`
    and a name without it. Any other pairing, and a missing, unreadable or duplicated row, refuses."""
    if kind_rows is None:
        return Target("REFUSE", PF_NO_KIND, "the install-kind row cannot be read: not an install of the real gateway")
    rows = tuple(kind_rows)
    if len(rows) != 1 or rows[0] not in ("REAL", "TEST"):
        return Target("REFUSE", PF_NO_KIND, "%d install-kind row(s), expected exactly one of kind REAL or TEST" % len(rows))
    real_name = is_reserved_real_name(database)
    if rows[0] == "REAL" and real_name:
        return Target("REAL")
    if rows[0] == "TEST" and not real_name:
        return Target("TEST")
    return Target("REFUSE", PF_KIND_DISAGREE, "install kind %s but the database name %s the reserved prefix %r" % (
        rows[0], "starts with" if real_name else "does not start with", RESERVED_REAL_PREFIX))


@dataclass(frozen=True)
class Plan:
    """What the command may do, from the target alone (5.1). `preflight_before`: run the gate first and proceed only if it passes.
    `preflight_after`: run the gate after the command and print its result beside the command's own, never changing the command's status."""
    proceed: bool
    preflight_before: bool = False
    preflight_after: bool = False
    code: str = ""
    detail: str = ""


#: Gated by COMMAND (5.1): `publish` and `renew` (the publisher tool), `serve` (the real-mode launcher's start) and `admit` (the admission probe's
#: start; R7). A tool's command name is a constant of the tool; no argument, variable or key moves a command to another row.
GATED_COMMANDS = ("publish", "renew", "serve", "admit")
NEVER_GATED_COMMANDS = ("withdraw",)


def command_plan(command, target):
    """The by-command rule of 5.1. KEYED TO THE COMMAND: nothing else (no argument, variable, key or content) moves a command to another row."""
    if command in GATED_COMMANDS:
        if target.decision == "REFUSE":
            return Plan(False, code=target.code, detail=target.detail)
        return Plan(True, preflight_before=target.decision == "REAL")
    if command in NEVER_GATED_COMMANDS:
        if target.decision == "REFUSE" and target.code == PF_NO_KIND:
            # no (or more than one) kind row: there is no real gateway to withdraw from; the tool says so and writes nothing
            return Plan(False, code=target.code, detail=target.detail)
        # a name and kind that disagree, or a TEST kind, never stop a withdrawal (it only narrows): they decide only whether the result prints
        return Plan(True, preflight_after=target.decision == "REAL")
    return Plan(True)                           # status and any other read-only command


# ===================================================================================================================================
# facts
# ===================================================================================================================================
@dataclass(frozen=True)
class RoleFact:
    name: str
    login: bool = False
    superuser: bool = False
    createrole: bool = False
    createdb: bool = False
    replication: bool = False
    bypassrls: bool = False
    valid_until: object = None
    config: tuple = ()

    def has_power(self):
        return any(getattr(self, a) for a in POWER_ATTRIBUTES)


@dataclass(frozen=True)
class Attempt:
    role: str
    database: str
    probe_pass: str                 # "A" or "B"
    replication: bool
    outcome: str
    message: str = ""

    @property
    def key(self):
        return (self.role, self.database, self.probe_pass, self.replication)


@dataclass(frozen=True)
class HbaRow:
    line: int
    type: str
    databases: tuple
    users: tuple
    method: str
    error: object = None


@dataclass(frozen=True)
class ScanFinding:
    store: str
    file: str
    where: str
    fields: str
    reason: str

    def short(self):
        return "%s %s %s: %s (%s)" % (self.store, self.file, self.where, self.fields, self.reason)


@dataclass(frozen=True)
class Facts:
    """Everything `decide` judges. A field that is None was NOT INSPECTED (not readable, not run) and refuses where it is required."""
    database: str = ""
    version_num: object = None
    max_prepared_transactions: object = None
    listen_addresses: object = None
    session_replication_role: object = None
    roles: object = None                    # tuple of RoleFact
    escalation: object = None               # {(login_role, other_role): (member, usage, set)}
    databases: object = None                # tuple of (name, datallowconn)
    connect: object = None                  # {(real_role, database): bool}
    db_role_settings: object = None         # tuple of (role name or "", database name or "")
    parameter_privileges: object = None     # {(role or "public", "SET"|"ALTER SYSTEM"): bool}
    never_role: str = ""
    attempts: tuple = ()
    stored: tuple = ()                      # ScanFinding
    not_inspected: tuple = ()               # texts: Pass S files that exist but cannot be read, catalogs that cannot be read
    notes: tuple = ()                       # texts printed as "not inspected / limits" (they do not refuse)
    # the installer's (superuser) vantage only; None for a runtime tool
    hba_rows: object = None
    verifiers: object = None                # {login role: True if the verifier starts SCRAM-SHA-256$}
    settings: object = None                 # {name: value}
    forbidden_roots: tuple = ()
    audit_findings: object = None           # tuple of Finding-like with .short(), or None when the audit did not run


# ===================================================================================================================================
# the outcome classifier (5.3 (f))
# ===================================================================================================================================
_REJECT = re.compile(r"pg_hba\.conf rejects (?:replication )?connection|no pg_hba\.conf entry for (?:replication connection from )?host", re.I)
_CHALLENGE = re.compile(r"password authentication failed for user|no password supplied|SASL authentication failed", re.I)


def classify_attempt(connected, message):
    """One connection attempt's outcome. CONNECTED: the connection opened. CHALLENGED: a POSITIVELY recognised authentication refusal (a password
    was demanded, or the password failed). REJECTED: a POSITIVELY recognised refusal by the access rules (a `reject` record matched, or no record
    matched). OTHER: everything else (an error after authentication, a timeout, a missing socket, an unrecognised message). CHALLENGED and
    REJECTED pass the preflight; CONNECTED and OTHER refuse. The texts are libpq's and the server's (`auth.c`); they are not quoted in the
    manual pages the design cites, so they are CALIBRATED against a real scram-only server by the opt-in test (`test_preflight_calibration`),
    and a mis-calibration fails closed: an unrecognised message is OTHER."""
    if connected:
        return CONNECTED
    text = message or ""
    if _REJECT.search(text):
        return REJECTED
    if _CHALLENGE.search(text):
        return CHALLENGED
    return OTHER


def classify_own_connection_error(message):
    """The tool's OWN connection (made with `require_auth`) failed: a refusal code for the print. A server that skips authentication fails on the
    client side, with no catalog read (5.2)."""
    if "authentication method requirement" in (message or "") or "require_auth" in (message or ""):
        return PF_REQUIRE_AUTH
    return PF_CONNECT_FAILED


# ===================================================================================================================================
# pg_hba prediction (5.3 (e)): what the file's rows say about one attempt on the Unix socket
# ===================================================================================================================================
def predict_hba(rows, role, database, replication):
    """The method of the first row that matches a LOCAL connection of `role` to `database` (`replication`: a physical replication attempt), or
    "no-match". Only `local` rows can match a Unix-socket connection. `all` does not match a replication connection (`auth-pg-hba-conf`).
    A token this function cannot evaluate (a file include, a group) returns "unpredictable", which refuses."""
    for row in rows:
        if row.type != "local":
            continue
        if replication:
            db_match = "replication" in row.databases
        else:
            db_match = any(d == "all" or d == database or (d == "sameuser" and database == role) for d in row.databases)
        # tokens this function does not evaluate: a file include (@), a group (+), a regular expression (/..., PostgreSQL 16+), and the group keywords
        # samerole / samegroup (TR6B-L-3). Any of them in a local row makes the prediction impossible, which refuses (5.3 (e))
        if (any(d.startswith(("@", "/")) or d in ("samerole", "samegroup") for d in row.databases)
                or any(u.startswith(("@", "+", "/")) for u in row.users)):
            return "unpredictable"
        if db_match and any(u == "all" or u == role for u in row.users):
            return row.method
    return "no-match"


# ===================================================================================================================================
# which attempts the probe must make (5.3 (d))
# ===================================================================================================================================
def required_attempts(roles, databases, never_role):
    """The attempts of 5.3 (d): for every LOGIN role and one never-created role name, every `datallowconn` database, in each of Pass A and Pass B;
    and a `replication` attempt for every LOGIN role with `rolsuper` or `rolreplication`, in each pass. Keys are (role, database, pass, replication)."""
    names = [r.name for r in roles if r.login] + [never_role]
    allowed = [name for name, allow in databases if allow]
    out = []
    for probe_pass in ("A", "B"):
        for name in names:
            out += [(name, d, probe_pass, False) for d in allowed]
        out += [(r.name, "replication", probe_pass, True) for r in roles if r.login and (r.superuser or r.replication)]
    return out


# ===================================================================================================================================
# Pass S: the static scan of stored credentials (5.3 (d)); no connection
# ===================================================================================================================================
def process_environment():
    """A copy of the caller's environment. THE ONLY environment read of this module (a static test confines `os.environ` to this function)."""
    return dict(os.environ)


def process_home():
    return str(Path("~").expanduser())


def _pgpass_fields(line):
    """The first four fields (host, port, database, user) of a passfile line, honouring `\\:` and `\\\\`; the password is NEVER taken. None if the
    line has fewer than four separators (it cannot carry a password for any entry)."""
    fields, current, i = [], [], 0
    while i < len(line) and len(fields) < 4:
        ch = line[i]
        if ch == "\\" and i + 1 < len(line):
            current.append(line[i + 1])
            i += 2
            continue
        if ch == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    return tuple(fields) if len(fields) == 4 else None


def _read(path):
    """(text, None) / (None, reason). A file that does not exist is `(None, 'absent')`; one that exists and cannot be read is `(None, 'unreadable')`."""
    p = Path(path)
    try:
        if not p.exists():
            return None, "absent"
    except OSError:
        return None, "unreadable"
    try:
        return p.read_text("utf8", errors="replace"), None
    except OSError:
        return None, "unreadable"


def _same_directory(host, socket_dir):
    """True when `host` (an absolute directory as a passfile or service file spells it) is the socket directory, by REAL path (TR6B-L-4): a
    trailing slash, `//`, `.` or a symlink in the spelling still matches. A path that cannot be resolved counts as a match (fail closed)."""
    if not host.startswith("/"):
        return False
    try:
        return os.path.realpath(host) == os.path.realpath(socket_dir)
    except (OSError, ValueError):
        return True


def _address_matches(host, port, socket_dir, real_port):
    host_ok = host in ("localhost", "*") or _same_directory(host, socket_dir)
    port_ok = port in (str(real_port), "*")
    return host_ok and port_ok


#: Where the libpq the product's tools actually use (psycopg-binary's bundled libpq 18) looks for the system `pg_service.conf` when `PGSYSCONFDIR`
#: is not set: its compiled-in default (TR6B-M-1; the strings of `libpq.5.dylib` show `/etc/postgresql-common`). This is not `pg_config`'s
#: directory, which is the SYSTEM client's. Both are scanned, and `PGSYSCONFDIR`, whichever libpq is in use.
LIBPQ_COMPILED_SYSCONFDIRS = ("/etc/postgresql-common",)


def scan_stored_credentials(environ, home, *, socket_dir, port, login_roles, sysconfdir=None, compiled_sysconfdirs=LIBPQ_COMPILED_SYSCONFDIRS):
    """Pass S (5.3 (d)): reads the caller's environment, the files it names AND the default locations, without connecting. Returns
    `(findings, not_inspected, notes)`. It refuses (as findings) on:

      1. `PGPASSWORD` set in the environment, to anything;
      2. any passfile line (either location) whose host field is the real cluster's socket directory, `localhost` or `*` and whose port field is
         the real port or `*`, WHATEVER THE FILE'S MODE; and any line whose user field names a LOGIN role of the real cluster, whatever its host and port;
      3. any service-file section with a `password` whose host is absent or the socket directory or `localhost` and whose port is absent or the real
         port, or whose `user` names a LOGIN role of the real cluster, whatever its host and port; every section is read whether or not a service is
         named; a section's `passfile` sends the scan to that file too;
      4. a file named above that exists and cannot be read ("not inspected" is a failure).

    The password is never read into a result or printed. The system `pg_service.conf` is looked for in EVERY directory libpq could use
    (TR6B-M-1): `PGSYSCONFDIR`, `sysconfdir` (`pg_config --sysconfdir`) and `compiled_sysconfdirs` (the bundled libpq's compiled default). If
    `sysconfdir` is None (`pg_config` is missing or fails) the scan cannot say it covered the installation's directory: that is NOT INSPECTED, which
    refuses. A file that exists and cannot be read is likewise NOT INSPECTED."""
    findings, not_inspected, notes = [], [], []
    roles = set(login_roles)
    real_port = str(port)
    home = str(home)
    if "PGPASSWORD" in environ:
        findings.append(ScanFinding("environment", "PGPASSWORD", "set", "(value not shown)", "PGPASSWORD is set; unset it"))

    passfiles = []                                  # (path, store label)
    if environ.get("PGPASSFILE"):
        passfiles.append((environ["PGPASSFILE"], "passfile (PGPASSFILE)"))
    passfiles.append((str(Path(home) / ".pgpass"), "passfile (default)"))
    service_files = []
    if environ.get("PGSERVICEFILE"):
        service_files.append((environ["PGSERVICEFILE"], "service file (PGSERVICEFILE)"))
    service_files.append((str(Path(home) / ".pg_service.conf"), "service file (default)"))
    if environ.get("PGSYSCONFDIR"):
        service_files.append((str(Path(environ["PGSYSCONFDIR"]) / "pg_service.conf"), "service file (PGSYSCONFDIR)"))
    if sysconfdir:
        service_files.append((str(Path(sysconfdir) / "pg_service.conf"), "service file (pg_config --sysconfdir)"))
    else:
        not_inspected.append("pg_config --sysconfdir could not be determined (pg_config is missing or failed): the installation's pg_service.conf "
                             "was not inspected")
    for compiled in compiled_sysconfdirs:
        service_files.append((str(Path(compiled) / "pg_service.conf"), "service file (libpq compiled default)"))

    seen_pass = set()

    def scan_passfile(path, store):
        if path in seen_pass:
            return
        seen_pass.add(path)
        text, problem = _read(path)
        if problem == "unreadable":
            not_inspected.append("%s %s exists and cannot be read" % (store, path))
            return
        if text is None:
            return
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            fields = _pgpass_fields(line)
            if fields is None:
                continue
            host, fport, database, user = fields
            shown = "host=%s port=%s db=%s user=%s" % (host, fport, database, user)
            if user in roles:
                findings.append(ScanFinding(store, path, "line %d" % number, shown, "the user field names a LOGIN role of the real cluster"))
            elif _address_matches(host, fport, socket_dir, real_port):
                findings.append(ScanFinding(store, path, "line %d" % number, shown, "could address the real cluster, whatever the file's mode"))

    for path, store in passfiles:
        scan_passfile(path, store)

    for path, store in service_files:
        text, problem = _read(path)
        if problem == "unreadable":
            not_inspected.append("%s %s exists and cannot be read" % (store, path))
            continue
        if text is None:
            continue
        sections, current = {}, None
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("[") and stripped.endswith("]"):
                current = stripped[1:-1]
                sections.setdefault(current, {})
            elif current is not None and "=" in stripped:
                key, _sep, value = stripped.partition("=")
                sections[current][key.strip()] = value.strip()
        for name, params in sections.items():
            if "passfile" in params:
                scan_passfile(params["passfile"], "passfile (service %s)" % name)
            if "password" not in params:
                continue
            host, fport, user = params.get("host"), params.get("port"), params.get("user")
            shown = "host=%s port=%s user=%s" % (host if host is not None else "(absent)", fport if fport is not None else "(absent)",
                                                user if user is not None else "(absent)")
            if user in roles:
                findings.append(ScanFinding(store, path, "section [%s]" % name, shown, "the user names a LOGIN role of the real cluster"))
            elif (host is None or host == "localhost" or _same_directory(host, socket_dir)) and (fport is None or fport == real_port):
                findings.append(ScanFinding(store, path, "section [%s]" % name, shown, "a password that could address the real cluster, named or not"))
    return tuple(findings), tuple(not_inspected), tuple(notes)


def installation_sysconfdir():
    """`pg_config --sysconfdir`, or None when pg_config is not found or fails. Runs a local program and sends nothing anywhere."""
    try:
        done = subprocess.run(["pg_config", "--sysconfdir"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    out = done.stdout.strip()
    return out if done.returncode == 0 and out else None


# ===================================================================================================================================
# Pass A and Pass B: connection attempts in a child process (5.3 (d))
# ===================================================================================================================================
#: The child: open a libpq connection with the given keyword/value string and close it at once. NO statement is sent, no password is passed.
_CHILD = (
    "import json,sys\n"
    "try:\n"
    "    import psycopg\n"
    "    c=psycopg.pq.PGconn.connect(sys.argv[1].encode())\n"
    "    ok=c.status==psycopg.pq.ConnStatus.OK\n"
    "    m=(c.error_message or b'').decode('utf8','replace')\n"
    "    c.finish()\n"
    "    print(json.dumps({'connected':bool(ok),'message':m}))\n"
    "except BaseException as e:\n"
    "    print(json.dumps({'connected':False,'message':'child error: '+type(e).__name__}))\n"
)


def _spawn_child(conninfo, env, timeout):
    """Run one attempt in a child process. Returns (connected, message)."""
    try:
        done = subprocess.run([sys.executable, "-I", "-c", _CHILD, conninfo], env=env, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except OSError as error:
        return False, "child error: " + type(error).__name__
    try:
        data = json.loads(done.stdout.strip().splitlines()[-1])
        return bool(data["connected"]), str(data["message"])
    except (ValueError, IndexError, KeyError, TypeError):
        return False, "child error: unreadable result"


class Prober:
    """Pass A (a scrubbed environment: a minimal one, `HOME` an empty temporary directory, `passfile=/dev/null`, no service) and Pass B (the caller's
    own environment and `HOME`, so that libpq reads `PGPASSWORD`, `PGPASSFILE`/`~/.pgpass` and `PGSERVICE`/`~/.pg_service.conf`). Serial, with a
    short `connect_timeout`. `spawn` is a seam for the tests of the logic (a fake child); production uses `_spawn_child`."""

    def __init__(self, socket_dir, port, *, environ, connect_timeout=3, spawn=None):
        self.socket_dir, self.port, self.environ = socket_dir, str(port), dict(environ)
        self.connect_timeout, self.spawn = connect_timeout, spawn or _spawn_child
        self._empty_home = tempfile.TemporaryDirectory(prefix="finweb-pf-home-")

    def close(self):
        self._empty_home.cleanup()

    def attempt(self, role, database, probe_pass, replication):
        base = build_conninfo(socket=self.socket_dir.rstrip("/") + "/.s.PGSQL." + self.port, dbname=database, user=role)
        params = {"connect_timeout": str(self.connect_timeout), "sslmode": "disable", "gssencmode": "disable", "application_name": "finweb_preflight"}
        if replication:
            params["replication"] = "true"
        if probe_pass == "A":
            params["passfile"] = "/dev/null"
            env = {"PATH": "/usr/bin:/bin", "HOME": self._empty_home.name}
        else:
            env = dict(self.environ)
        connected, message = self.spawn(conninfo_with(base, **params), env, self.connect_timeout + 5)
        first = (message or "").strip().splitlines()[0] if (message or "").strip() else ""
        return Attempt(role, database, probe_pass, replication, classify_attempt(connected, message), first)

    def run(self, required):
        return tuple(self.attempt(*key) for key in required)


# ===================================================================================================================================
# decide: the pure logic
# ===================================================================================================================================
def _under(path, roots):
    try:
        real = os.path.realpath(path)
    except (OSError, ValueError):
        return False
    return any(real == r or real.startswith(r.rstrip(os.sep) + os.sep) for r in roots)


def decide(facts, *, vantage="runtime", phase=None, real_roles=REAL_ROLES, real_database=REAL_DATABASE):
    """Judge a fact set. `vantage`: "runtime" (a non-superuser tool) or "installer" (the superuser). `phase` (installer only): "0" (before anything
    is created: the four roles and the gateway are not there yet), "2" (after the owner set the passwords) or "check" (the same as "2", re-run).
    Returns a `Decision`; `ok` only when there is no refusal. The output never holds a password: no fact carries one."""
    refusals = []
    lines = []
    real_names = tuple(real_roles.values())

    def refuse(code, subject="", detail=""):
        refusals.append(Refusal(code, subject, detail))

    # ---- the server itself: first, and alone when it fails (the later catalog reads may not exist on an older server) ------------------
    if facts.version_num is None:
        refuse(PF_NOT_INSPECTED, "server_version_num", "the server version cannot be read")
    elif facts.version_num < MIN_SERVER_VERSION_NUM:
        refuse(PF_SERVER_VERSION, "server_version_num", "%s: the install rule needs PostgreSQL 17 or later" % facts.version_num)
    if refusals:
        return _finish(refusals, lines, facts)
    if facts.max_prepared_transactions is None or str(facts.max_prepared_transactions) != "0":
        refuse(PF_PREPARED, "max_prepared_transactions", "is %r, must be 0: a prepared transaction would let an executor commit after complete_by" %
               (facts.max_prepared_transactions,))
    if facts.listen_addresses is None:
        refuse(PF_NOT_INSPECTED, "listen_addresses", "cannot be read")
    elif str(facts.listen_addresses).strip() != "":
        refuse(PF_LISTEN, "listen_addresses", "is %r, must be empty (Unix-domain sockets only)" % (facts.listen_addresses,))
    if facts.session_replication_role is None:
        refuse(PF_NOT_INSPECTED, "session_replication_role", "cannot be read")
    elif facts.session_replication_role != "origin":
        refuse(PF_SESSION_REPLICATION, "session_replication_role", "is %r, must be 'origin'" % (facts.session_replication_role,))

    # ---- roles (5.3 (a)) -----------------------------------------------------------------------------------------------------------------
    if facts.roles is None:
        refuse(PF_NOT_INSPECTED, "pg_roles", "cannot be read")
        roles = ()
    else:
        roles = tuple(facts.roles)
    login = [r for r in roles if r.login]
    powered = [r for r in login if r.has_power()]
    superusers = [r for r in login if r.superuser]
    for r in powered:
        if not r.superuser:
            refuse(PF_LOGIN_POWER, r.name, "a LOGIN role with a power attribute that is not the LOGIN superuser")
    if len(superusers) > 1:
        for r in superusers:
            refuse(PF_LOGIN_POWER, r.name, "more than one LOGIN superuser")
    non_super_login = [r for r in login if not r.superuser]
    present_real = {r.name for r in roles if r.name in real_names}

    # ---- escalation paths (5.3 (b)): no allowed-pairs list, no exemption ---------------------------------------------------------------
    if facts.escalation is None:
        refuse(PF_NOT_INSPECTED, "pg_has_role", "the membership of the LOGIN roles cannot be read")
    else:
        for u in non_super_login:
            for x in roles:
                if x.name == u.name:
                    continue                     # a role counts as a member of itself: not a finding
                flags = facts.escalation.get((u.name, x.name))
                if flags is None:
                    refuse(PF_NOT_INSPECTED, "%s in %s" % (u.name, x.name), "pg_has_role was not asked")
                elif any(flags):
                    kinds = [k for k, f in zip(("MEMBER", "USAGE", "SET"), flags) if f]
                    refuse(PF_MEMBERSHIP, u.name, "%s of %s" % ("/".join(kinds), x.name))

    # ---- settings (5.3 (a)) -------------------------------------------------------------------------------------------------------------
    for r in roles:
        if r.name in real_names and r.config:
            refuse(PF_ROLE_CONFIG, r.name, "rolconfig is not empty: %s" % ", ".join(r.config))
    if facts.db_role_settings is None:
        refuse(PF_NOT_INSPECTED, "pg_db_role_setting", "cannot be read")
    else:
        for role_name, db_name in facts.db_role_settings:
            if role_name in real_names or db_name == real_database:
                refuse(PF_DB_ROLE_SETTING, role_name or "(all roles)", "a pg_db_role_setting row names %s" % (
                    "role " + role_name if role_name in real_names else "database " + db_name))
    if facts.parameter_privileges is None:
        refuse(PF_NOT_INSPECTED, "has_parameter_privilege", "cannot be read")
    else:
        for who in [r.name for r in non_super_login] + ["public"]:
            for privilege in ("SET", "ALTER SYSTEM"):
                held = facts.parameter_privileges.get((who, privilege))
                if held is None:
                    refuse(PF_NOT_INSPECTED, who, "has_parameter_privilege(session_replication_role, %s) was not asked" % privilege)
                elif held:
                    refuse(PF_PARAMETER, who, "holds %s on session_replication_role" % privilege)

    # ---- databases (5.3 (c)) ------------------------------------------------------------------------------------------------------------
    if facts.databases is None or facts.connect is None:
        refuse(PF_NOT_INSPECTED, "pg_database", "databases or CONNECT privileges cannot be read")
        databases = ()
    else:
        databases = tuple(facts.databases)
        for role_name in sorted(present_real):
            for name, allow in databases:
                if not allow or name == real_database:
                    continue
                held = facts.connect.get((role_name, name))
                if held is None:
                    refuse(PF_NOT_INSPECTED, role_name, "has_database_privilege on %s was not asked" % name)
                elif held:
                    refuse(PF_CONNECT_ELSEWHERE, role_name, "holds CONNECT on %s (the installer revokes PUBLIC's CONNECT there)" % name)

    # ---- the probe (5.3 (d), (f)) --------------------------------------------------------------------------------------------------------
    if roles or databases:
        have = {a.key: a for a in facts.attempts}
        for key in required_attempts(roles, databases, facts.never_role):
            if key not in have:
                refuse(PF_COVERAGE, key[0], "no attempt in Pass %s on %s%s" % (key[2], key[1], " (replication)" if key[3] else ""))
    for a in facts.attempts:
        where = "%s on %s Pass %s%s" % (a.role, a.database, a.probe_pass, " (replication)" if a.replication else "")
        lines.append("attempt: %s -> %s%s" % (where, a.outcome, (" [" + a.message + "]") if a.message and a.outcome != CHALLENGED else ""))
        if a.outcome == CONNECTED:
            refuse(PF_CONNECTED, a.role, "connected without a credential: %s" % where)
        elif a.outcome == OTHER:
            refuse(PF_OTHER, a.role, "%s: %s" % (where, a.message or "no message"))
    for f in facts.stored:
        refuse(PF_STORED, f.store, f.short())
    for text in facts.not_inspected:
        refuse(PF_NOT_INSPECTED, "", text)

    # ---- the installer's vantage (5.3 (e)) -----------------------------------------------------------------------------------------------
    if vantage == "installer":
        _installer_checks(facts, phase, refuse, roles, login, present_real, real_names, real_database, lines)

    # ---- the login state of the four real roles (E29): a print, never a refusal --------------------------------------------------------
    by_name = {r.name: r for r in roles}
    for kind, name in real_roles.items():
        r = by_name.get(name)
        lines.append("real role %s (%s): %s" % (kind, name, "absent" if r is None else "can log in: %s" % ("true" if r.login else "false")))
    return _finish(refusals, lines, facts)


def _installer_checks(facts, phase, refuse, roles, login, present_real, real_names, real_database, lines):
    if phase not in ("0", "2", "check"):
        refuse(PF_NOT_INSPECTED, "phase", "the installer's phase is 0, 2 or check")
    settings = facts.settings
    if settings is None:
        refuse(PF_NOT_INSPECTED, "pg_settings", "the superuser's SHOW settings cannot be read")
        settings = {}
    if settings.get("password_encryption") != "scram-sha-256":
        refuse(PF_PASSWORD_ENCRYPTION, "password_encryption", "is %r, must be 'scram-sha-256'" % (settings.get("password_encryption"),))
    if settings.get("log_statement") != "none":
        refuse(PF_LOG, "log_statement", "is %r, must be 'none' while passwords are set" % (settings.get("log_statement"),))
    for name in ("log_min_duration_statement", "log_min_error_statement"):
        lines.append("setting %s = %s" % (name, settings.get(name)))
    for name in ("data_directory", "hba_file", "ident_file", "unix_socket_directories"):
        value = settings.get(name)
        lines.append("setting %s = %s" % (name, value))
        if value is None:
            refuse(PF_NOT_INSPECTED, name, "cannot be read")
        elif any(_under(p.strip(), facts.forbidden_roots) for p in str(value).split(",") if p.strip()):
            refuse(PF_PATH, name, "%s lies under the repository root or the system temporary directory" % value)
    # hba rows: only `local` rows with scram-sha-256 or reject; the file, not only what shadows what
    if facts.hba_rows is None:
        refuse(PF_NOT_INSPECTED, "pg_hba_file_rules", "cannot be read")
        rows = ()
    else:
        rows = tuple(facts.hba_rows)
        for row in rows:
            if row.error:
                refuse(PF_HBA_ERROR, "line %d" % row.line, str(row.error))
            if row.type != "local":
                refuse(PF_HBA_TYPE, "line %d" % row.line, "%s row: only local rows may appear (no TCP)" % row.type)
            elif row.method not in ("scram-sha-256", "reject"):
                refuse(PF_HBA_METHOD, "line %d" % row.line, "method %s: only scram-sha-256 and reject may appear" % row.method)
    # a CHALLENGED or REJECTED outcome must be what the rows predict; a difference is "edited but not reloaded"
    if rows or facts.hba_rows is not None:
        for a in facts.attempts:
            if a.outcome not in (CHALLENGED, REJECTED):
                continue
            predicted = predict_hba(rows, a.role, a.database, a.replication)
            want_rejected = predicted in ("reject", "no-match")
            if predicted == "unpredictable" or (a.outcome == REJECTED) != want_rejected or (a.outcome == CHALLENGED and predicted != "scram-sha-256"):
                refuse(PF_HBA_LOADED, a.role, "attempt on %s (Pass %s%s) was %s but the file predicts %s: edited but not reloaded?" % (
                    a.database, a.probe_pass, ", replication" if a.replication else "", a.outcome, predicted))
    if phase in ("2", "check"):
        for name in real_names:
            if name not in present_real:
                refuse(PF_ROLE_MISSING, name, "the real role does not exist")
        verifiers = facts.verifiers
        if verifiers is None:
            refuse(PF_NOT_INSPECTED, "pg_authid", "the password verifiers cannot be read")
        else:
            for r in login:
                if verifiers.get(r.name) is not True:
                    refuse(PF_VERIFIER, r.name, "no stored verifier that begins SCRAM-SHA-256$ (md5, or no password set)")
        if facts.audit_findings is None:
            refuse(PF_NOT_INSPECTED, "catalog audit", "did not run")
        else:
            lines.append("catalog audit (as REAL): %d finding(s)" % len(facts.audit_findings))
            for finding in facts.audit_findings:
                refuse(PF_AUDIT, getattr(finding, "subject", ""), finding.short())
    if phase == "0":
        if real_database in [n for n, _a in (facts.databases or ())]:
            refuse(PF_REAL_EXISTS, real_database, "the real database already exists: Phase 1 is not claimed to re-run over an existing install")
        for name in sorted(present_real):
            refuse(PF_REAL_EXISTS, name, "a real role already exists")


def _finish(refusals, lines, facts):
    out = list(lines)
    out.append("not inspected / limits: grants are not re-read at a gated start; a passing preflight is a tripwire from this process's vantage, now")
    out += ["not inspected note: " + n for n in facts.notes]
    for r in refusals:
        out.append("REFUSED " + r.short())
    out.append("preflight: " + ("PASSED" if not refusals else "REFUSED (%d)" % len(refusals)))
    return Decision(not refusals, tuple(refusals), tuple(out))


# ===================================================================================================================================
# gathering
# ===================================================================================================================================
def forbidden_roots():
    """The repository root and the system temporary directory, resolved (5.3 (e))."""
    project = Path(__file__).resolve().parents[2]
    roots = {os.path.realpath(str(project)), os.path.realpath(tempfile.gettempdir()), os.path.realpath("/tmp"), os.path.realpath("/private/tmp")}
    return tuple(sorted(roots))


def _try(not_inspected, what, fn):
    try:
        return fn()
    except Exception as error:      # noqa: BLE001 - any failure to read is "not inspected", which refuses
        not_inspected.append("%s: %s" % (what, type(error).__name__))
        return None


def gather_facts(conn, *, vantage, database, socket, phase=None, environ=None, home=None, prober=None, sysconfdir=None, real_roles=REAL_ROLES,
                 real_database=REAL_DATABASE, audit=None, run_probe=True):
    """Read the facts from `conn` (IDLE; each group is read in a transaction of its own), run Pass S and the probe, and return a `Facts`.
    Anything that cannot be read is None (or listed in `not_inspected`). `audit` (the installer's Phase 2 and `--check`): a callable returning
    the catalog audit's findings, called on its own connection by the installer. A server below version 17 stops the reads after the version."""
    not_inspected = []
    environ = process_environment() if environ is None else environ
    home = process_home() if home is None else home

    def one(sql, params=()):
        with conn.transaction():
            return conn.execute(sql, params).fetchone()

    def many(sql, params=()):
        with conn.transaction():
            return conn.execute(sql, params).fetchall()

    version = _try(not_inspected, "server_version_num", lambda: int(one("SELECT current_setting('server_version_num')")[0]))
    if version is None or version < MIN_SERVER_VERSION_NUM:
        return Facts(database=database, version_num=version, not_inspected=tuple(not_inspected), forbidden_roots=forbidden_roots())
    show = lambda name: _try(not_inspected, name, lambda: one("SELECT current_setting(%s)", (name,))[0])      # noqa: E731
    prepared, listen, replica = show("max_prepared_transactions"), show("listen_addresses"), show("session_replication_role")
    role_rows = _try(not_inspected, "pg_roles", lambda: many(
        "SELECT rolname::text,rolcanlogin,rolsuper,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls,rolvaliduntil,rolconfig FROM pg_roles ORDER BY 1"))
    roles = None if role_rows is None else tuple(RoleFact(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], tuple(r[8] or ())) for r in role_rows)
    escalation = None
    if roles is not None:
        rows = _try(not_inspected, "pg_has_role", lambda: many(
            "SELECT u.rolname::text,x.rolname::text,pg_has_role(u.oid,x.oid,'MEMBER'),pg_has_role(u.oid,x.oid,'USAGE'),pg_has_role(u.oid,x.oid,'SET') "
            "FROM pg_roles u JOIN pg_roles x ON x.oid<>u.oid WHERE u.rolcanlogin AND NOT u.rolsuper"))
        escalation = None if rows is None else {(r[0], r[1]): (bool(r[2]), bool(r[3]), bool(r[4])) for r in rows}
    db_rows = _try(not_inspected, "pg_database", lambda: many("SELECT datname::text,datallowconn FROM pg_database ORDER BY 1"))
    databases = None if db_rows is None else tuple((r[0], bool(r[1])) for r in db_rows)
    connect = None
    if databases is not None and roles is not None:
        connect = {}
        present = [r.name for r in roles if r.name in real_roles.values()]
        for role_name in present:
            for name, allow in databases:
                if allow and name != real_database:
                    connect[(role_name, name)] = _try(not_inspected, "has_database_privilege %s on %s" % (role_name, name), lambda r=role_name, d=name: bool(
                        one("SELECT has_database_privilege(%s::text,%s::text,'CONNECT')", (r, d))[0]))
    settings_rows = _try(not_inspected, "pg_db_role_setting", lambda: many(
        "SELECT coalesce(r.rolname::text,''),coalesce(d.datname::text,'') FROM pg_db_role_setting s LEFT JOIN pg_roles r ON r.oid=s.setrole "
        "LEFT JOIN pg_database d ON d.oid=s.setdatabase"))
    db_role_settings = None if settings_rows is None else tuple((r[0], r[1]) for r in settings_rows)
    parameter_privileges = None
    if roles is not None:
        parameter_privileges = {}
        for who in [r.name for r in roles if r.login and not r.superuser] + ["public"]:
            for privilege in ("SET", "ALTER SYSTEM"):
                value = _try(not_inspected, "has_parameter_privilege %s %s" % (who, privilege), lambda w=who, p=privilege: bool(
                    one("SELECT has_parameter_privilege(%s::text,'session_replication_role',%s)", (w, p))[0]))
                if value is not None:
                    parameter_privileges[(who, privilege)] = value

    socket_dir, port = _split_socket(socket)
    login_names = {r.name for r in roles if r.login} | set(real_roles.values()) if roles is not None else set(real_roles.values())
    stored, scan_missing, notes = scan_stored_credentials(environ, home, socket_dir=socket_dir, port=port, login_roles=login_names,
                                                          sysconfdir=sysconfdir)
    not_inspected += list(scan_missing)
    never_role = "finweb_pf_" + secrets.token_hex(6)
    attempts = ()
    if run_probe and roles is not None and databases is not None:
        own = prober or Prober(socket_dir, port, environ=environ)
        try:
            attempts = own.run(required_attempts(roles, databases, never_role))
        finally:
            if prober is None:
                own.close()

    hba_rows = verifiers = settings = None
    if vantage == "installer":
        raw = _try(not_inspected, "pg_hba_file_rules", lambda: many(
            "SELECT line_number,type::text,database,user_name,auth_method::text,error::text FROM pg_hba_file_rules ORDER BY line_number"))
        if raw is not None:
            hba_rows = tuple(HbaRow(r[0], r[1], tuple(r[2] or ()), tuple(r[3] or ()), r[4], r[5]) for r in raw)
        auth = _try(not_inspected, "pg_authid", lambda: many(
            "SELECT rolname::text,coalesce(left(rolpassword,14)='SCRAM-SHA-256$',false) FROM pg_authid WHERE rolcanlogin"))
        if auth is not None:
            verifiers = {r[0]: bool(r[1]) for r in auth}
        settings = {}
        for name in ("password_encryption", "log_statement", "log_min_duration_statement", "log_min_error_statement", "data_directory", "hba_file",
                     "ident_file", "unix_socket_directories"):
            settings[name] = show(name)
    findings = None
    if vantage == "installer" and phase in ("2", "check") and audit is not None:
        findings = _try(not_inspected, "catalog audit", lambda: tuple(audit()))
    return Facts(database=database, version_num=version, max_prepared_transactions=prepared, listen_addresses=listen, session_replication_role=replica,
                 roles=roles, escalation=escalation, databases=databases, connect=connect, db_role_settings=db_role_settings,
                 parameter_privileges=parameter_privileges, never_role=never_role, attempts=attempts, stored=stored,
                 not_inspected=tuple(not_inspected), notes=notes, hba_rows=hba_rows, verifiers=verifiers, settings=settings,
                 forbidden_roots=forbidden_roots(), audit_findings=findings)


def _split_socket(socket):
    """`/dir/.s.PGSQL.<port>` -> (dir, port)."""
    directory, base = os.path.split(socket)
    match = re.fullmatch(r"\.s\.PGSQL\.(\d+)", base)
    if not directory or match is None:
        raise ValueError("socket path must look like <dir>/.s.PGSQL.<port>")
    return directory, match.group(1)


def run_runtime_gate(conn, *, database, socket, environ=None, home=None, prober=None, sysconfdir=None):
    """The gate of 5.1 for a runtime tool (a non-superuser): gather and decide. The connection is the tool's own, IDLE. An exception while
    gathering is a refusal, never a pass."""
    try:
        facts = gather_facts(conn, vantage="runtime", database=database, socket=socket, environ=environ, home=home, prober=prober,
                             sysconfdir=sysconfdir if sysconfdir is not None else installation_sysconfdir())
    except Exception as error:      # noqa: BLE001
        refusal = Refusal(PF_NOT_INSPECTED, "", "the preflight could not gather its facts: %s" % type(error).__name__)
        return Decision(False, (refusal,), ("REFUSED " + refusal.short(), "preflight: REFUSED (1)"))
    return decide(facts, vantage="runtime")


# ===================================================================================================================================
# the terminal prompt: the ONLY credential route (rule 2, rule 4, 5.1)
# ===================================================================================================================================
def terminal_prompt(role):
    """Read a password for `role` from the controlling terminal (no echo). Nothing else supplies one: not an environment variable, a file, a
    passfile, a service entry or an argument."""
    import getpass
    return getpass.getpass("Password for role %s: " % role)


def connect_with_prompt(socket, database, user, *, require_auth, prompt, autocommit=False):
    """Open the tool's own connection over the Unix socket. The password comes from `prompt(user)` and goes into the connection string only;
    `passfile=/dev/null` so that no stored credential is used; `require_auth` (None for none) makes libpq refuse a server that does not use
    that method. Raises `psycopg.Error`."""
    import psycopg
    password = prompt(user)
    params = {"password": password, "passfile": "/dev/null", "sslmode": "disable", "gssencmode": "disable", "connect_timeout": "10",
              "application_name": "finweb_real_tool"}
    if require_auth:
        params["require_auth"] = require_auth
    return psycopg.connect(conninfo_with(build_conninfo(socket=socket, dbname=database, user=user), **params), autocommit=autocommit)
