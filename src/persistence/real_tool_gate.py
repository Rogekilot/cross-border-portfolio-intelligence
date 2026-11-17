"""F1 R7: the START GATE of the two runtime tools that are not the publisher: the real-mode launcher (`serve`) and the admission probe (`admit`).

Design 1.2 rules 5.1 and 5.2. Both tools run as the executor role (a non-superuser). Each decides what it is from two facts that it READS, the
database's NAME and the install-kind rows (`rw_install_info()`, which the executor may execute), and never from an argument, a variable or a key:

    install kind REAL + a name in the reserved namespace  ->  REAL: run the preflight (`real_preflight.run_runtime_gate`), refuse on any failure
    install kind TEST + any other name                    ->  TEST: no preflight
    any other pairing, and a missing, unreadable or duplicated row  ->  refuse

The rule is KEYED TO THE COMMAND: the command is a constant of the calling tool (`serve` or `admit`), and `real_preflight.command_plan` is the one
function that maps it to a row of the table. This module has no switch, no option and no environment read; it holds no credential and opens no
connection (the caller passes its own, IDLE). It writes nothing: the only statement it sends is the read of the install-kind rows.

The preflight itself is `_run_gate`, a module-level seam so that a test of the command rule can put a failing decision in its place with fake facts
(as `real_workspace_store._run_gate` is the publisher's); it is not reachable from any command line.
"""
from __future__ import annotations

from dataclasses import dataclass

from persistence import real_preflight as pf
from persistence.real_workspace_context import RealWorkspaceError, identifier, query_all

START_COMMANDS = ("serve", "admit")


@dataclass(frozen=True)
class StartDecision:
    """`proceed`: the tool may go on. `target`: "REAL" or "TEST" when it may, "" when it may not. `code`: the refusal code. `lines`: what to print."""
    proceed: bool
    target: str = ""
    code: str = ""
    lines: tuple = ()


def read_install_kinds(conn, schema):
    """The install-kind rows the database holds (`rw_install_info()`) as a tuple of kinds, or None when they cannot be read. A read on a
    transaction of its own, so the connection is IDLE again afterwards."""
    import psycopg
    try:
        with conn.transaction():
            return tuple(r[0] for r in query_all(conn, identifier(schema), "rw_install_info", ()))
    except (psycopg.Error, RealWorkspaceError):
        return None


def _run_gate(conn, database, socket):
    """The preflight of design 1.2 for this tool's own connection (a non-superuser). Returns a `Decision`. Not reachable from a command line."""
    return pf.run_runtime_gate(conn, database=database, socket=socket)


def start_gate(conn, command, *, database, schema, socket):
    """Decide whether the tool whose command is `command` may start. Reads the install-kind rows, decides the target from them and the NAME,
    applies the by-command rule, and runs the preflight first for a REAL target. Returns a `StartDecision`; a refusal means: do nothing."""
    if command not in START_COMMANDS:
        raise ValueError("the start gate serves the launcher and the admission probe only")
    target = pf.decide_target(database, read_install_kinds(conn, schema))
    plan = pf.command_plan(command, target)
    if not plan.proceed:
        return StartDecision(False, "", plan.code, ("REFUSED %s: %s" % (plan.code, plan.detail),))
    if plan.preflight_before:
        decision = _run_gate(conn, database, socket)
        if not decision.ok:
            return StartDecision(False, "", "PF_PREFLIGHT_REFUSED", tuple(decision.lines) + ("REFUSED PF_PREFLIGHT_REFUSED: " + ", ".join(decision.codes()),))
        return StartDecision(True, "REAL", "", tuple(decision.lines))
    return StartDecision(True, "TEST", "", ())
