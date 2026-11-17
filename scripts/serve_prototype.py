#!/usr/bin/env python3
"""The harness's own review server: loopback-only, confined to one directory under `designs/`.

Used by `.claude/hooks/guard_browser.py`, which permits exactly the one origin this server
registers. (History: archived ADR-0026 and ADR-0027 under `_archive/harness-3.2.0/`.)

## Why this exists

The `browser` capability was wired by ADR-0026 and the tool identifiers were then
observed resolving. What was NOT observed is the capability the grant is actually FOR.
A `file://` navigation to `designs/hg1-prototype-v2/index.html` is surfaced to the
reading tool as a `data:` snapshot of the HTML. A `data:` document has no base URL, so
every relative `<script src="js/shell.js">` in that file resolves against nothing and
never executes: `<main>` stays empty, no route renders, and a UX reviewer reading that
page observes the shell markup and calls it the product.

That is not a browser that "works". It is a browser that can open a file and cannot run
an application, and the difference is the whole of an HG1 UX review.

Serving the same directory over a real origin fixes it for one reason: an `http://`
document has a base URL, so relative subresources resolve and the scripts run.

## Why the harness owns the launch

Permitting `http://127.0.0.1:<port>/` in the navigation guard would be a URL filter, and
a URL filter proves nothing about what is on that port. Any process on this workstation
can bind a loopback port and serve anything, including the rest of the filesystem. So
the permission cannot be attached to the *origin*; it has to be attached to a *server
this harness started and can still identify*.

This script is that server, and `runtime/review-server.json` is the statement it makes
about itself:

    pid                     a process to check is not a corpse
    mtime (heartbeat)       touched every HEARTBEAT_SECONDS, so freshness proves THIS
                            process is still the one holding the port
    host / port             the exact origin the guard may permit, and nothing wider
    root                    the realpath being served, which the guard re-checks is
                            inside `designs/` rather than taking the lockfile's word
    token                   returned at `/__harness__`, so a server that ANSWERS with
                            the wrong identity is caught

`PreToolUse:guard_browser.py` reads that file on every navigation. If it is absent, the
heartbeat has gone stale, the process is gone, the port differs by one, or the root is
not under `designs/`, the navigation is denied. The origin is permitted because the
SERVER is known, not because the string looked local.

## Why freshness rather than `ps`, and why not a loopback probe alone

Both were tried and both are unavailable where this has to work: the Bash sandbox denies
`ps` outright and denies a loopback connect (observed 2026-09-08, this surface). A check
that cannot run is a denial, so a boundary built on either would have failed closed and
bricked the capability it exists to enable.

What is always available is a `stat` and a signal-0. The argument they support is sound:
the bind is exclusive (no `SO_REUSEPORT`), so while this process lives, that port is this
process — and a heartbeat that stops when the process stops is what makes "still lives" a
fact rather than a file's opinion. The `/__harness__` probe stays as supplementary
confirmation for contexts that can reach it; a WRONG answer is a hard denial, an
unreachable one is not, because the freshness argument does not depend on it.

## What this does NOT establish

The window is bounded, not zero: a server killed without cleanup leaves an acceptable
registration for up to STALE_AFTER_SECONDS. And none of this survives a **determined
local user** — anything running as this user can read the lockfile, and CLAUDE.md is
explicit that hooks defend against agent error and drift, not against a human with a
shell. The control is honest at that rung: it confines where a browser tool may navigate,
not what a local user can do.

## Usage

    python3 scripts/serve_prototype.py --start [--root designs/hg1-prototype-v2] [--port 8899]
    python3 scripts/serve_prototype.py --status
    python3 scripts/serve_prototype.py --stop

`--start` runs in the foreground; the orchestrator launches it as a background Bash
command. Exit 0 = served and stopped cleanly, 2 = refused.
"""
from __future__ import annotations

import argparse
import atexit
import errno
import json
import os
import signal
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pathguard import ConfinementError, confine  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

#: The one subtree a review server may serve, mirroring `guard_browser.ALLOWED_ROOT`.
#: `tests/test_review_server.py` asserts the two agree; a server confined to a wider
#: root than the guard permits would be a hole the guard could not see.
ALLOWED_ROOT = "designs"

#: Live runtime state, not a versioned artifact. `.gitignore`d.
LOCKFILE_REL = "runtime/review-server.json"

DEFAULT_ROOT = "designs/hg1-prototype-v2"
DEFAULT_PORT = 8899

#: Loopback literals only. `localhost` is a NAME, and a name is resolved by something
#: this harness does not control; the guard compares against whatever is recorded here,
#: so recording an address keeps that comparison an address comparison.
LOOPBACK_HOSTS = ("127.0.0.1", "::1")

IDENTITY_PATH = "/__harness__"

#: The lockfile's mtime is a HEARTBEAT, touched by the running server. It is the one
#: freshness signal every context this code runs in can actually obtain: the Bash sandbox
#: denies `ps` and denies a loopback connect (both observed 2026-09-08), so a check built
#: on either would be a check that cannot run — and a check that cannot run is a denial.
#: A file's mtime needs no subprocess and no socket.
HEARTBEAT_SECONDS = 2
STALE_AFTER_SECONDS = 10


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def refuse(msg):
    print(f"REFUSED: {msg}", file=sys.stderr)
    raise SystemExit(2)


def lockfile(root: Path = ROOT) -> Path:
    return root / LOCKFILE_REL


def origin_url(host: str, port: int, path: str = "") -> str:
    literal = f"[{host}]" if ":" in host else host
    return f"http://{literal}:{port}{path}"


def ask_listener(host: str, port: int, timeout: float = 2.0):
    """What the process actually on `host:port` says it is, or None.

    SUPPLEMENTARY, not decisive — see `verify_lock`, which explains why. Asking the
    listener is the most direct answer to "what is on this port", and it is the only
    check that catches a server which ANSWERS with the wrong identity. It cannot be the
    boundary's foundation because it cannot always run: the Bash sandbox denies a
    loopback connect outright (observed 2026-09-08). So a wrong answer denies, an
    unreachable listener does not, and the freshness argument carries the claim.

    Proxy handlers are stripped explicitly. `urllib` honours `http_proxy` from the
    environment, and a check that can be redirected by an environment variable is not a
    check — it would let the caller choose which server answers for the origin.
    """
    import urllib.error
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(origin_url(host, port, IDENTITY_PATH), timeout=timeout) as r:
            if r.status != 200:
                return None
            return json.loads(r.read(64 * 1024).decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM  # exists, owned by someone else
    return True


def read_lock(root: Path = ROOT):
    try:
        d = json.loads(lockfile(root).read_text(encoding="utf-8"))
    except Exception:
        return None
    return d if isinstance(d, dict) else None


def write_lock(data, root: Path = ROOT):
    p = lockfile(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def clear_lock(root: Path = ROOT):
    try:
        lockfile(root).unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


# ---------------------------------------------------------------------------
# The one function the guard and this script must agree on.
# ---------------------------------------------------------------------------

def verify_lock(lock, root: Path = ROOT):
    """(ok, why_not) for a lockfile: is a server this harness started still running?

    Imported by `.claude/hooks/guard_browser.py`, deliberately, so that the navigation
    boundary and the server share ONE definition of "the approved origin". Two copies of
    this predicate would drift, and the drift would be silent in the permissive
    direction.

    Every failure is a denial. There is no "cannot tell, so allow".
    """
    if not isinstance(lock, dict):
        return False, ("no review server is registered — runtime/review-server.json is "
                       "absent or unreadable. Start one with "
                       "`python3 scripts/serve_prototype.py --start`")

    pid = lock.get("pid")
    # `isinstance(True, int)` is True in Python, and JSON `true` would then reach
    # `os.kill(1, 0)` -- which returns EPERM for launchd and reads as "alive".
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 1:
        return False, "the review-server lockfile records no usable pid"
    if not alive(pid):
        return False, (f"the review server recorded at pid {pid} is not running. Its "
                       f"lockfile is stale; the port it names is now served by nothing, "
                       f"or by something else")

    host = lock.get("host")
    if host not in LOOPBACK_HOSTS:
        return False, (f"the review server records host {host!r}, which is not a "
                       f"loopback literal ({', '.join(LOOPBACK_HOSTS)}). A review server "
                       f"reachable off this workstation is not a review server")

    port = lock.get("port")
    if not isinstance(port, int) or not (1 <= port <= 65535):
        return False, "the review-server lockfile records no usable port"

    served = lock.get("root")
    if not isinstance(served, str) or not served:
        return False, "the review-server lockfile records no served directory"
    # Re-derive containment rather than trusting the lockfile's own claim. The lockfile
    # is the server's statement about itself; this is the guard's check of it.
    allowed = os.path.realpath(str(root / ALLOWED_ROOT))
    real = os.path.realpath(served)
    if real != allowed and not real.startswith(allowed + os.sep):
        return False, (f"the review server is serving `{real}`, which is outside "
                       f"`{ALLOWED_ROOT}/`. Whatever is on that port, it is not the "
                       f"design artifacts this capability is granted for")

    token = lock.get("token")
    if not isinstance(token, str) or len(token) < 32:
        return False, "the review-server lockfile records no usable identity token"

    # THE decisive check, and the argument it rests on.
    #
    # A running server touches its own lockfile every HEARTBEAT_SECONDS. A fresh mtime
    # therefore means THIS process is still alive; `alive(pid)` above means the pid is
    # not a corpse; and the bind was exclusive (no `SO_REUSEPORT`), so while that process
    # lives nothing else can be listening on the host:port it recorded. Freshness +
    # liveness + exclusive bind is what ties the ORIGIN to the SERVER — which is the
    # entire claim the navigation permission rests on, and it is established with a
    # `stat` and a signal-0, both of which work everywhere this code runs.
    #
    # The window this leaves is bounded and named: if the server dies without running its
    # cleanup, the registration stays acceptable for at most STALE_AFTER_SECONDS before
    # it goes stale.
    try:
        age = time.time() - lockfile(root).stat().st_mtime
    except OSError as exc:
        return False, f"the review-server lockfile could not be stat'd ({exc})"
    if age > STALE_AFTER_SECONDS:
        return False, (f"the review server's registration is {int(age)}s stale (heartbeat "
                       f"every {HEARTBEAT_SECONDS}s, stale after {STALE_AFTER_SECONDS}s). "
                       f"The process that bound {origin_url(host, port)} is no longer "
                       f"maintaining it, so nothing establishes what is on that port now")

    # Supplementary confirmation, when the environment permits a loopback connect at all.
    # A server that ANSWERS with the wrong identity is a hard denial — that is the case
    # this catches and the heartbeat cannot. A listener that cannot be reached is NOT
    # treated as a denial: the Bash sandbox refuses the connect outright, and the
    # freshness argument above already establishes the claim without it.
    said = ask_listener(host, port)
    if said is not None and (said.get("token") != token
                             or said.get("pid") != pid
                             or said.get("root") != lock.get("root")):
        return False, (f"the server answering on {origin_url(host, port)} is not the one "
                       f"registered here — it returned a different identity. Something "
                       f"else holds that port; permitting it because the address is "
                       f"loopback is exactly the mistake this check exists to prevent")
    return True, None


def approved_origin(root: Path = ROOT):
    """(host, port, why_not). The single origin a browser may open, or None."""
    lock = read_lock(root)
    ok, why = verify_lock(lock, root)
    if not ok:
        return None, None, why
    return lock["host"], lock["port"], None


# ---------------------------------------------------------------------------
# The server
# ---------------------------------------------------------------------------

class ReviewHandler(SimpleHTTPRequestHandler):
    """Static GET/HEAD under one directory. No listing, no upward escape, no cache."""

    server_version = "HEAReviewServer/1.0"
    identity = {}

    def log_message(self, fmt, *args):  # quieter, and to stderr like the rest
        sys.stderr.write("[review-server] %s - %s\n" % (self.address_string(), fmt % args))

    def end_headers(self):
        # A reviewer must never be shown a cached earlier build of the prototype.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        # A marker, deliberately NOT the identity token: this header is visible to the
        # page and to anything that can reach the port, and the token is what proves the
        # listener is ours. Identity is proved at `/__harness__`, not broadcast.
        self.send_header("X-Harness-Review-Server", "1")
        super().end_headers()

    def translate_path(self, path):
        """SimpleHTTPRequestHandler strips `..`; it does NOT stop a symlink out of root.

        `designs/` is agent-writable, so a symlink planted inside it is a reachable way
        to serve the rest of the repository through an origin the guard has approved.
        Both forms are resolved and both must land inside the root.
        """
        served = super().translate_path(path)
        base = os.path.realpath(self.directory)
        real = os.path.realpath(served)
        if real != base and not real.startswith(base + os.sep):
            return os.path.join(base, "\0")  # unopenable → 404
        return served

    def list_directory(self, path):
        self.send_error(HTTPStatus.NOT_FOUND, "No directory listing")
        return None

    def do_GET(self):
        if self._identity():
            return
        super().do_GET()

    def do_HEAD(self):
        if self._identity():
            return
        super().do_HEAD()

    def _identity(self):
        """`/__harness__` — what this server is, for an operator confirming out of band."""
        if urlsplit(self.path).path != IDENTITY_PATH:
            return False
        body = json.dumps(self.identity, indent=2).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        return True


def cmd_start(a, root: Path = ROOT):
    try:
        served = confine(a.root, ALLOWED_ROOT, project_root=root)
    except ConfinementError as exc:
        refuse(f"{exc}\n  A review server exists to show the design artifacts under "
               f"`{ALLOWED_ROOT}/`. Serving anything else would hand an approved origin "
               f"to the rest of the filesystem.")
    if not served.is_dir():
        refuse(f"{served} is not a directory, so there is nothing to serve.")

    existing = read_lock(root)
    ok, _ = verify_lock(existing, root)
    if ok:
        refuse(f"a review server is already running (pid {existing['pid']}) on "
               f"http://{existing['host']}:{existing['port']}/ serving "
               f"{existing['root']}. Stop it with --stop before starting another; two "
               f"servers would mean the approved origin is ambiguous.")

    handler = partial(ReviewHandler, directory=str(served))
    try:
        httpd = ThreadingHTTPServer((a.host, a.port), handler)
    except OSError as exc:
        if exc.errno in (errno.EPERM, errno.EACCES):
            refuse(f"binding {a.host}:{a.port} was not permitted ({exc}).\n"
                   f"  This is the Bash SANDBOX refusing a listening socket, not a busy "
                   f"port — observed 2026-09-08. The review server must be launched from "
                   f"a Bash call with the sandbox disabled for that command; it is a "
                   f"read-only static file server on loopback, and the boundary that "
                   f"matters (what may be OPENED) is PreToolUse:guard_browser.py, which "
                   f"is unaffected.")
        refuse(f"could not bind {a.host}:{a.port} ({exc}). A busy port is not a port to "
               f"work around: something else is already listening there, and that is "
               f"precisely the provenance hazard this server exists to remove. Choose a "
               f"free port with --port, or stop whatever holds this one.")

    host, port = httpd.server_address[0], httpd.server_address[1]
    token = os.urandom(16).hex()
    identity = {
        "schema_version": "1.0",
        "token": token,
        "pid": os.getpid(),
        "host": host,
        "port": port,
        "root": str(served),
        "root_rel": str(served.relative_to(root)),
        "allowed_root": ALLOWED_ROOT,
        "started_at": now(),
        "server_script": str(Path(__file__).resolve()),
    }
    # What `/__harness__` answers with. Only the three fields the guard compares, so the
    # endpoint is an identity proof and not a disclosure of who is running what.
    ReviewHandler.identity = {k: identity[k] for k in ("token", "pid", "root")}
    write_lock(identity, root)
    atexit.register(clear_lock, root)

    def _shutdown(signum, frame):
        clear_lock(root)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    def _heartbeat():
        """Touch the lockfile so its mtime proves this process is still here.

        A daemon thread, so it cannot keep the process alive past its server: the whole
        point of the heartbeat is that it STOPS when the server does.
        """
        while True:
            time.sleep(HEARTBEAT_SECONDS)
            try:
                os.utime(lockfile(root), None)
            except OSError:
                return

    threading.Thread(target=_heartbeat, daemon=True).start()

    print(f"review server listening on http://{host}:{port}/")
    print(f"  serving   {served}")
    print(f"  lockfile  {lockfile(root)}")
    print(f"  identity  http://{host}:{port}{IDENTITY_PATH}")
    print("This is the ONLY origin PreToolUse:guard_browser.py will permit. Any other "
          "port, host or scheme stays denied.")
    try:
        httpd.serve_forever()
    finally:
        clear_lock(root)
        httpd.server_close()
    return 0


def cmd_status(root: Path = ROOT):
    lock = read_lock(root)
    ok, why = verify_lock(lock, root)
    if not ok:
        print(f"no approved review-server origin: {why}")
        return 1
    print(f"review server RUNNING  pid={lock['pid']}  "
          f"http://{lock['host']}:{lock['port']}/")
    print(f"  serving   {lock['root']}")
    print(f"  started   {lock['started_at']}")
    print(f"  approved origin for guard_browser: http://{lock['host']}:{lock['port']}/")
    return 0


def cmd_selftest(root: Path = ROOT):
    """Exercise the running server over HTTP and report what it actually does.

    Separate from `--verify` on purpose. `--verify` answers the guard's question ("is
    there an approved origin"), which must work in every context and therefore rests on
    file evidence. This answers the REVIEWER's question ("will the prototype actually
    run"), which can only be answered by fetching, and fetching needs a loopback connect
    the Bash sandbox denies — so run it with the sandbox off, the same way the server is
    launched.
    """
    import urllib.error
    import urllib.request
    lock = read_lock(root)
    ok, why = verify_lock(lock, root)
    if not ok:
        print(f"FAIL  no approved origin: {why}")
        return 1
    host, port = lock["host"], lock["port"]
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def fetch(path):
        try:
            with opener.open(origin_url(host, port, path), timeout=5) as r:
                return r.status, r.read(200000)
        except urllib.error.HTTPError as exc:
            return exc.code, b""
        except (urllib.error.URLError, OSError) as exc:
            return None, str(exc).encode()

    failures = []

    def check(label, condition, detail=""):
        print(f"  {'PASS' if condition else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
        if not condition:
            failures.append(label)

    print(f"review-server self-test against {origin_url(host, port)}")
    st, body = fetch("/index.html")
    check("index.html is served", st == 200, f"status={st}")
    check("index.html carries the prototype's script tags",
          b"js/shell.js" in body, f"{len(body)} bytes")
    st, body = fetch("/js/shell.js")
    check("a relative script subresource is served", st == 200 and len(body) > 0,
          f"status={st} bytes={len(body)}")
    st, body = fetch("/styles/app.css")
    check("a relative stylesheet is served", st == 200 and len(body) > 0, f"status={st}")
    st, _ = fetch("/")
    check("the directory root serves index.html rather than a listing", st == 200)
    # Targets that EXIST outside the default served root (designs/hg1-prototype-v2), so a
    # 404 here means confinement worked, not that the file was missing.
    st, _ = fetch("/../FEATURE_DESIGN.md")
    check("upward traversal out of the served root is refused", st in (400, 403, 404),
          f"status={st}")
    st, _ = fetch("/../../CLAUDE.md")
    check("deeper traversal is refused", st in (400, 403, 404), f"status={st}")
    st, body = fetch(IDENTITY_PATH)
    check("the identity endpoint answers", st == 200 and lock["token"].encode() in body)

    print("SELFTEST " + ("PASS" if not failures else f"FAIL ({len(failures)} check(s))"))
    return 0 if not failures else 1


def cmd_stop(root: Path = ROOT):
    lock = read_lock(root)
    if not isinstance(lock, dict):
        print("no review-server lockfile; nothing to stop")
        return 0
    ok, why = verify_lock(lock, root)
    if not ok:
        # A stale lockfile is removed; a lockfile naming a process that is NOT ours is
        # not something this script may kill.
        clear_lock(root)
        print(f"removed a lockfile that does not describe a running review server: {why}")
        # Deliberately NOT killed. A registration this script cannot verify may name a
        # pid the OS has since reused, and signalling an unrelated process is worse than
        # leaving a port held. Name it instead, so an operator can decide.
        if isinstance(lock.get("pid"), int):
            print(f"  the registration named pid {lock['pid']} on "
                  f"{origin_url(lock.get('host', '?'), lock.get('port', 0))}; if that "
                  f"process is still holding the port, stop it yourself — this script "
                  f"will not signal a process it cannot identify")
        return 0
    try:
        os.kill(lock["pid"], signal.SIGTERM)
    except OSError as exc:
        if exc.errno in (errno.EPERM, errno.EACCES):
            refuse(f"signalling pid {lock['pid']} was not permitted ({exc}).\n"
                   f"  The server is launched with the Bash sandbox disabled, so it runs "
                   f"outside it — and a sandboxed call cannot signal it. Run --stop the "
                   f"same way you ran --start. The lockfile is deliberately left in "
                   f"place: removing it would withdraw the approved origin while the "
                   f"server kept serving, which is the confusing half of both states.")
        refuse(f"could not signal pid {lock['pid']}: {exc}")
    clear_lock(root)
    print(f"stopped review server pid={lock['pid']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--start", action="store_true",
                      help="serve in the foreground (launch as a background command)")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--stop", action="store_true")
    mode.add_argument("--verify", action="store_true",
                      help="run the exact check PreToolUse:guard_browser.py runs, and "
                           "print the origin it would permit (exit 0) or the reason it "
                           "would deny (exit 1)")
    mode.add_argument("--selftest", action="store_true",
                      help="fetch from the running server and report whether the "
                           "prototype's subresources are actually served (needs a "
                           "loopback connect; run with the Bash sandbox disabled)")
    ap.add_argument("--root", default=DEFAULT_ROOT,
                    help=f"directory to serve; confined to {ALLOWED_ROOT}/ "
                         f"(default: {DEFAULT_ROOT})")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default="127.0.0.1", choices=list(LOOPBACK_HOSTS),
                    help="loopback literal to bind (default: 127.0.0.1)")
    a = ap.parse_args(argv)

    if a.status:
        return cmd_status()
    if a.stop:
        return cmd_stop()
    if a.selftest:
        return cmd_selftest()
    if a.verify:
        host, port, why = approved_origin()
        if host is None:
            print(f"DENY  no origin approved: {why}")
            return 1
        print(f"ALLOW {origin_url(host, port)}  (and only this origin)")
        return 0
    return cmd_start(a)


if __name__ == "__main__":
    sys.exit(main())
