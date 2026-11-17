"""Connection-string building and the lazy driver import.

No password is ever handled here: libpq reads `PGPASSWORD` / `~/.pgpass`
itself, so no secret passes through repository code or test output.
"""

from __future__ import annotations

import os
import re
from typing import Any, List, Mapping, Optional, Tuple

OPT_IN_VAR = "FINWEB_PG_INTEGRATION"
SOCKET_VAR = "FINWEB_PG_SOCKET"
HOST_VAR = "FINWEB_PG_HOST"
PORT_VAR = "FINWEB_PG_PORT"
DATABASE_VAR = "FINWEB_PG_DATABASE"
USER_VAR = "FINWEB_PG_USER"

#: The reserved real-install namespace (design 1.2 rules 5.2 and 6): a database whose name starts with it is a REAL target. It lives here, the
#: lowest module, so that the tools, the preflight, the TEST provisioner and the environment-driven tests all read the one constant.
RESERVED_REAL_PREFIX = "finweb_real"

_SOCKET_NAME = re.compile(r"^\.s\.PGSQL\.(\d+)$")


def is_reserved_real_name(name: object) -> bool:
    """True for a name in the reserved real-install namespace (a pure prefix test; no connection)."""
    return isinstance(name, str) and name.startswith(RESERVED_REAL_PREFIX)


def _quote(value: str) -> str:
    """libpq keyword/value quoting: single quotes, backslash-escaped."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def build_conninfo(
    *,
    dbname: str,
    user: str,
    socket: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[str] = None,
) -> str:
    """A libpq connection string. Either `socket` (the Unix-socket *file*
    path, e.g. `/tmp/.s.PGSQL.5432`) or `host`+`port` must be given. The
    socket form is translated to libpq's directory-plus-port form."""
    if socket:
        directory, base = os.path.split(socket)
        match = _SOCKET_NAME.match(base)
        if not directory or match is None:
            raise ValueError(
                f"socket path must look like <dir>/.s.PGSQL.<port>, got {socket!r}"
            )
        host, port = directory, match.group(1)
    if not host or not port:
        raise ValueError("either socket, or both host and port, must be given")
    parts: List[Tuple[str, str]] = [
        ("host", host), ("port", str(port)), ("dbname", dbname), ("user", user),
    ]
    return " ".join(f"{k}={_quote(v)}" for k, v in parts)


def conninfo_with(base: str, **params: str) -> str:
    """`base` (a `build_conninfo` string) plus further libpq keyword/value pairs, quoted. Generic: it does not know what a value is."""
    return base + "".join(f" {k}={_quote(str(v))}" for k, v in params.items())


def missing_env_vars(environ: Mapping[str, str]) -> List[str]:
    """Names the integration tests still need, in the order to set them.
    Empty list means the opt-in is complete."""
    missing: List[str] = []
    if environ.get(OPT_IN_VAR) != "1":
        missing.append(OPT_IN_VAR + "=1")
    if not environ.get(SOCKET_VAR) and not (
        environ.get(HOST_VAR) and environ.get(PORT_VAR)
    ):
        missing.append(f"{SOCKET_VAR} (or {HOST_VAR} and {PORT_VAR})")
    if not environ.get(DATABASE_VAR):
        missing.append(DATABASE_VAR)
    elif is_reserved_real_name(environ.get(DATABASE_VAR)):
        # F1 R6 (design 1.2 rule 6): the environment-driven tests never run against the reserved real-install namespace. The refusal is by
        # name only and builds no connection; what stops a database with another name on the real cluster is the credential rule.
        missing.append(f"{DATABASE_VAR} (refused: a name starting with {RESERVED_REAL_PREFIX!r} is the reserved real-install namespace, "
                       "which the test tooling never uses)")
    if not environ.get(USER_VAR):
        missing.append(USER_VAR)
    return missing


def conninfo_from_env(environ: Mapping[str, str]) -> str:
    return build_conninfo(
        dbname=environ[DATABASE_VAR],
        user=environ[USER_VAR],
        socket=environ.get(SOCKET_VAR) or None,
        host=environ.get(HOST_VAR) or None,
        port=environ.get(PORT_VAR) or None,
    )


def connect(conninfo: str, *, autocommit: bool = False) -> Any:
    """Open a psycopg 3 connection. The driver is imported here, lazily: it is
    a declared dependency (`pyproject.toml`) that may not be installed yet."""
    import psycopg  # noqa: PLC0415 — deliberate lazy import

    return psycopg.connect(conninfo, autocommit=autocommit)
