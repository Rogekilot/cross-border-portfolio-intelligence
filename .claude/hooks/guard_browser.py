#!/usr/bin/env python3
"""PreToolUse: browser tools may open the local prototype and nothing else.

Registered in `.claude/settings.json` for both browser namespaces: the in-app browser
(`mcp__Claude_Browser__*`) and Claude in Chrome (`mcp__claude-in-chrome__*`). Applies to
every caller, main session and subagents alike.

## Why

The Bash sandbox's network filter governs Bash, not a tool that fetches a URL in its own
process, so without this hook nothing confines where a browser tool goes. It also closes a
read route around the `Read(./.env)`-style deny rules: `file:///…/.env` would reach the
same bytes through a tool those rules never name.

`file://` alone is not enough to review the prototype. The page arrives as a `data:`
snapshot with no base URL, so the prototype's relative `<script src>` tags never run and
`<main>` stays empty. The review server fixes that. But permitting `http://127.0.0.1:*`
would be a URL filter, and a URL filter proves nothing about what is on a port. So the
permission is attached to a server this project started and can still identify:
`scripts/serve_prototype.py` binds one loopback port, serves one directory under
`designs/`, and records pid, host, port, root, a token and a heartbeat in
`runtime/review-server.json`. This guard re-verifies that on every call using the
server's own `verify_lock`, so the two cannot drift apart.

## What it enforces

ALLOW  a `file://` URL whose symlink-resolved path is inside `<project>/designs/`
ALLOW  `http://<host>:<port>/…` for the ONE origin a live, verified review server holds.
       The path after the origin is confined by the server itself, which refuses
       traversal and symlink escapes (`serve_prototype.py --selftest`).
ALLOW  a bare path under a path-typed key (`path`, `file_path`) inside `designs/`
ALLOW  `about:blank`
ALLOW  a call that carries no destination at all (reading or acting on the current page)
DENY   everything else: `https:`, other loopback ports, `localhost` by name, `data:`,
       `javascript:`, `file://` elsewhere, a schemeless value under a URL-typed key, and
       anything unparseable

## Known gaps

- A call that names a `tabId` (click, read_page, screenshot) acts on that tab with no check
  of which tab it is. In Claude in Chrome that is the owner's real browser. Agents are told
  to act only on tabs they opened; this hook does not enforce it (see `STATUS.md`).
- A click on an approved page can still navigate somewhere else. Only the initial
  navigation is checked.
- A browser tool exposed under a name outside the two matchers is not guarded.
- A determined local user can defeat the review-server check. This guards against agent
  error, not against a person with a shell.

Exit 0 = allow. Exit 2 = deny, reason on stderr.
"""
import importlib.util
import json
import os
import sys
from urllib.parse import unquote, urlparse

PROJECT = os.environ.get("CLAUDE_PROJECT_DIR", ".")

#: The one subtree a governed worker may open. The prototype under review lives here, and
#: so does every design artifact a Designer or a reviewer has a reason to look at.
ALLOWED_ROOT = "designs"

#: Input keys a browser tool might carry a destination under. Checked in order; the first
#: present, non-empty string wins. A key not listed here that carries a URL would slip
#: past, so extend this list if a browser tool gains a new destination key.
URL_KEYS = ("url", "uri", "href", "address", "location", "path", "file_path")

#: Keys whose value a browser interprets as a URL. A schemeless value under one of these
#: (`designs/x.html`) is NOT a local path to a browser: Chrome turns it into
#: `https://designs/x.html`, a remote host. So a scheme is required here; only the
#: path-typed keys (`path`, `file_path`) may carry a bare filesystem path.
URL_TYPED_KEYS = ("url", "uri", "href", "address", "location")

SCHEMELESS_OK = ("about:blank",)

#: The only scheme a review server is reachable on. `https:` is deliberately absent: the
#: harness's server speaks plain HTTP on loopback, so an `https://127.0.0.1:<port>/` that
#: answered would be a DIFFERENT server, and the point is that the permission names a
#: server rather than an address.
SERVER_SCHEMES = ("http",)


def deny(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def project_root():
    return os.path.realpath(PROJECT)


def allowed_root():
    return os.path.join(project_root(), ALLOWED_ROOT)


def _serve_module():
    """Load the review server's own module from THIS project, or None.

    Loaded by path from `CLAUDE_PROJECT_DIR` rather than imported by name, so that a test
    pointing at a temporary project exercises that project's server definition, not the
    live one's.
    """
    path = os.path.join(project_root(), "scripts", "serve_prototype.py")
    if not os.path.exists(path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("_guard_serve_prototype", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def approved_origin():
    """(host, port, why_not) for the single permitted review-server origin."""
    mod = _serve_module()
    if mod is None:
        return None, None, ("scripts/serve_prototype.py is absent or unloadable, so no "
                            "review server can be verified and no origin is approved")
    try:
        from pathlib import Path
        return mod.approved_origin(Path(project_root()))
    except Exception as exc:
        return None, None, (f"the review-server registration could not be checked "
                            f"({exc}). A boundary denies when it cannot perform its check")


def is_review_server(parsed):
    """(ok, why_not) for an `http://…` destination. Fails closed on every branch."""
    if parsed.username or parsed.password:
        return False, ("the URL carries userinfo before the host. A destination whose "
                       "authority section needs interpreting is not one this guard will "
                       "interpret")
    host, port, why = approved_origin()
    if host is None:
        return False, (f"no approved review-server origin exists — {why}.\n"
                       f"  A loopback port is permitted because the SERVER on it is "
                       f"known, never because the address looked local")
    try:
        got_host, got_port = parsed.hostname, parsed.port
    except ValueError as exc:
        return False, f"the destination's host/port could not be read ({exc})"
    if got_host != host or got_port != port:
        return False, (f"`{got_host}:{got_port}` is not the approved review-server "
                       f"origin, which is `{host}:{port}`. Loopback is not a permission: "
                       f"the harness permits the one origin it started and can still "
                       f"identify, and every other port on this machine — including "
                       f"another server of your own — stays denied")
    return True, None


def is_local_prototype(url: str):
    """(ok, why_not). Exact parsing — no substring matching, no prefix trust."""
    raw = (url or "").strip()
    if not raw:
        return False, "the destination is empty"
    if raw.lower() in SCHEMELESS_OK:
        return True, None

    try:
        parsed = urlparse(raw)
    except Exception as exc:
        return False, f"the destination could not be parsed as a URL ({exc})"

    scheme = (parsed.scheme or "").lower()
    if scheme in SERVER_SCHEMES:
        return is_review_server(parsed)
    if scheme and scheme != "file":
        return False, (f"scheme `{scheme}:` reaches outside this workstation. Only "
                       f"`file:` under `{ALLOWED_ROOT}/`, and the harness's own loopback "
                       f"review server, are permitted")
    if scheme == "file" and parsed.netloc and parsed.netloc.lower() not in ("", "localhost"):
        return False, (f"a `file://` URL with host `{parsed.netloc}` names a remote "
                       f"filesystem, not this one")

    # A bare path with no scheme is treated as a local path, which is what a tool that
    # accepts `path` rather than `url` would carry.
    target = unquote(parsed.path if scheme == "file" else raw)
    if not target:
        return False, "the destination names no path"
    if not os.path.isabs(target):
        target = os.path.join(project_root(), target)

    # Resolve BOTH forms. A containment check that compares an unnormalized path is not a
    # containment check — the lesson `scripts/_pathguard.py` already carries.
    real = os.path.realpath(target)
    lexical = os.path.normpath(target)
    root = allowed_root()
    for candidate in (real, lexical):
        if candidate != root and not candidate.startswith(root + os.sep):
            return False, (f"`{candidate}` is outside `{ALLOWED_ROOT}/`. Navigation is "
                           f"confined to the design artifacts under that directory; the "
                           f"rest of the filesystem — including credential files the "
                           f"`Read` deny list already protects — is not reachable "
                           f"through a browser either")
    return True, None


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
    except Exception as exc:
        deny(f"BLOCKED: the browser guard could not parse its hook payload ({exc}). A "
             f"boundary hook denies when it cannot determine whether an operation is safe.")

    tool = payload.get("tool_name") or "this browser tool"
    tool_input = payload.get("tool_input")
    if tool_input is None:
        return  # nothing to navigate to
    if not isinstance(tool_input, dict):
        deny(f"BLOCKED: `{tool}` was invoked with an unreadable tool_input, so its "
             f"destination cannot be checked against the navigation policy.")

    key = next((k for k in URL_KEYS
                if isinstance(tool_input.get(k), str) and tool_input[k].strip()), None)
    if key is None:
        # Not navigation. Reading the page already open carries no destination, and
        # denying it would break the capability without closing anything: the page it
        # would read is one this guard already vetted, or one the human opened.
        return
    url = tool_input[key]

    if key in URL_TYPED_KEYS and url.strip().lower() not in SCHEMELESS_OK \
            and not urlparse(url.strip()).scheme:
        deny(f"BLOCKED: `{tool}` was given `{url[:200]}` with no scheme. A browser reads "
             f"that as a web address (`https://{url.strip()[:80]}`), not a local file. Use "
             f"`file://<absolute path inside {ALLOWED_ROOT}/>` or the review server's "
             f"`http://` origin.")

    ok, why = is_local_prototype(url)
    if ok:
        return

    deny(f"BLOCKED: `{tool}` may not open `{url[:200]}` — {why}.\n"
         f"  Browser tools in this project exist to observe the local prototype under "
         f"`{ALLOWED_ROOT}/`. Two destinations are permitted: a `file://` path inside "
         f"`{ALLOWED_ROOT}/` (static shell only — scripts do not run), and the review "
         f"server started with `python3 scripts/serve_prototype.py --start`, re-verified "
         f"here on every call.\n"
         f"  If the artifact you need is genuinely outside `{ALLOWED_ROOT}/`, say so in "
         f"your findings and stop. Do not ask another worker to fetch it for you.")


if __name__ == "__main__":
    main()
