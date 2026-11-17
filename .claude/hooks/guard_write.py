#!/usr/bin/env python3
"""PreToolUse (Write|Edit|NotebookEdit): keep specialist subagents inside their own paths.

Rules, in order:
  1. Secret files (.env, .env.*, *.pem, *.key, id_rsa*; any letter case) are never
     written, by anyone.
  2. A SUBAGENT (the payload carries an agent identity) may write only the paths listed
     for its agent name in .claude/role-write-paths.json. An agent with no entry there
     (general-purpose, Explore, Plan, ...) writes nothing: it reads, and reports back to
     the main session, which persists what matters.
  3. The main session (no agent identity) is not path-restricted.

Failure direction: if this script itself errors, a SUBAGENT's write is denied and the
main session's write is allowed. So a broken guard or config can never lock the main
session out of repairing it.

Self-contained on purpose: no registry, no task state, no other harness file. Changing
who may write where is an edit to .claude/role-write-paths.json, not to this script.

Known limit: subagent writes into a git worktree outside this project directory are
denied (they are outside every grant). Run writers in the main checkout.

Exit 0 = allow. Exit 2 = deny; stderr is shown to the agent.
"""
import json
import os
import sys

PROJECT_LEX = os.path.normpath(os.path.abspath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()))
PROJECT_REAL = os.path.realpath(PROJECT_LEX)
CONFIG = os.path.join(PROJECT_REAL, ".claude", "role-write-paths.json")
PATH_KEYS = ("file_path", "notebook_path", "path")
AGENT_KEYS = ("agent_type", "agent_name", "subagent_type", "agent_id")
NAME_KEYS = ("agent_type", "agent_name", "subagent_type")


def deny(msg):
    print("BLOCKED: " + msg, file=sys.stderr)
    sys.exit(2)


def _secret_name(base):
    base = base.lower()
    return (base == ".env" or base.startswith(".env.") or base.startswith("id_rsa")
            or base.endswith((".pem", ".key")))


def is_secret(path):
    """By the given name, or by the name a symlink at that path resolves to."""
    absolute = path if os.path.isabs(path) else os.path.join(PROJECT_LEX, path)
    return (_secret_name(os.path.basename(path))
            or _secret_name(os.path.basename(os.path.realpath(absolute))))


def _inside(path, root):
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    return None if rel == ".." or rel.startswith("../") else rel


def rel_forms(path):
    """Project-relative forms of `path` (symlink-resolved and lexical), or None if either
    lands outside the project. The lexical form may be relative to the project path as
    given or as resolved, so a symlinked project directory does not deny every write."""
    absolute = path if os.path.isabs(path) else os.path.join(PROJECT_LEX, path)
    real = _inside(os.path.realpath(absolute), PROJECT_REAL)
    lexical_abs = os.path.normpath(absolute)
    lexical = _inside(lexical_abs, PROJECT_LEX) or _inside(lexical_abs, PROJECT_REAL)
    if real is None or lexical is None:
        return None
    return [real, lexical]


def covered(rel, grants):
    for g in grants:
        g = str(g).lstrip("/")
        if g.endswith("/"):
            base = g.rstrip("/")
            if rel == base or rel.startswith(base + "/"):
                return True
        elif rel == g:
            return True
    return False


def check_subagent(payload, paths):
    name = next((str(payload[k]).strip() for k in NAME_KEYS
                 if payload.get(k) not in (None, "") and str(payload[k]).strip()), None)
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            config = json.load(fh)
        if not isinstance(config, dict):
            raise ValueError("not a JSON object")
    except Exception as exc:
        deny(f"{CONFIG} is unreadable ({exc}), so subagent write paths cannot be "
             f"checked. The main session can fix that file.")

    grants = config.get(name) if name else None
    if not isinstance(grants, list):
        deny(f"subagent `{name or '?'}` has no write paths in "
             f".claude/role-write-paths.json, so it may not write. Report findings to "
             f"the main session, which persists them.")
    if not paths:
        deny(f"`{payload.get('tool_name', 'this tool')}` carried no target path, so it "
             f"cannot be checked against `{name}`'s write paths.")

    for path in paths:  # every path-like key the call carries must be covered
        forms = rel_forms(path)
        if forms is None or not all(covered(r, grants) for r in forms):
            deny(f"subagent `{name}` may not write `{path}`. Its write paths are: "
                 f"{', '.join(map(str, grants)) or '(none)'}. Hand this change to the "
                 f"role that owns the path, or ask the main session to change "
                 f".claude/role-write-paths.json.")


def main():
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
    except Exception as exc:
        deny(f"the write guard could not parse its hook payload ({exc}).")

    # Any agent field with a value (whitespace or a non-string included) means the caller
    # is a subagent; the main session's payload carries none of these keys. An exactly
    # empty string is treated as absent, so a defaulted "" can never lock the main session
    # out. Decided first, so the failure direction below is known before anything else can
    # go wrong.
    is_subagent = any(payload.get(k) not in (None, "") for k in AGENT_KEYS)
    try:
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict):
            tool_input = {}
        paths = [tool_input[k] for k in PATH_KEYS
                 if isinstance(tool_input.get(k), str) and tool_input[k].strip()]
        if is_subagent and any(k in tool_input and not isinstance(tool_input[k], str)
                               for k in PATH_KEYS):
            deny("a path argument is not a string, so it cannot be checked.")

        for path in paths:
            if is_secret(path):
                deny(f"`{path}` looks like a credential file; agents never write secrets.")
        if is_subagent:
            check_subagent(payload, paths)
    except SystemExit:
        raise
    except Exception as exc:
        if is_subagent:
            deny(f"the write guard hit an internal error ({type(exc).__name__}: {exc}), "
                 f"so this subagent write is refused. The main session can inspect "
                 f".claude/hooks/guard_write.py and .claude/role-write-paths.json.")
        print(f"guard_write: internal error ignored for the main session "
              f"({type(exc).__name__}: {exc})", file=sys.stderr)


if __name__ == "__main__":
    main()
