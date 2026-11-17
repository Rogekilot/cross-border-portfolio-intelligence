"""E0 — PostgreSQL connectivity preflight (Tech Plan §13.F; CP1 authority §2.3).

Bounded first `implement` increment. Sole purpose: determine whether the actual
governed Engineer runtime can reach the human-provisioned PostgreSQL endpoint, over
two independent transports (Unix-domain socket, loopback TCP). This test sends no
credentials, no PostgreSQL startup packet, and no application query/payload of any
kind — it opens a socket, observes whether the connect() succeeds, and closes it.

**E0 PASS = TRANSPORT REACHABILITY ONLY.** It does not establish PostgreSQL protocol
success, authentication, server identity/version, role permissions, schema access,
transaction behaviour, migrations, or `Decimal`/`NUMERIC` correctness. That is E0b
(Tech Plan §13.G), a separate, later, opt-in-gated increment.

Standard library only: `socket`, `os`, `errno`, `unittest`. No driver, no ORM, no
third-party import of any kind.

## Opt-in gate — load-bearing (Tech Plan §13.F [J])

Under ordinary test discovery, with no extra environment set, both test methods in
this file MUST be collected and skipped WITHOUT opening any socket. This file will be
picked up by `python3 -m unittest discover -s tests/product -t .` on every machine
that runs `implement`'s revalidation suite — including machines with no PostgreSQL
endpoint at all. Skip is unconditional unless every one of the following is true:

  - `FINWEB_PG_PREFLIGHT=1` is set (the explicit opt-in), AND
  - the transport variable(s) the specific route needs are set:
      - Route U needs `FINWEB_PG_SOCKET`
      - Route T needs `FINWEB_PG_HOST` and `FINWEB_PG_PORT`

No default socket path, host, or port is ever assumed. If the opt-in is present but a
route's own transport variable(s) are missing, that route (only) skips with a message
naming exactly what is missing; it does not fail and does not open a socket.

Run via:
    python3 -m unittest discover -s tests/product -t .                     (skipped)
    FINWEB_PG_PREFLIGHT=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 \\
    FINWEB_PG_HOST=127.0.0.1 FINWEB_PG_PORT=5432 \\
        python3 -m unittest discover -s tests/product -t . \\
            -p 'test_postgres_connectivity_preflight.py' -v                (opt-in probe)
"""

import errno
import os
import socket
import unittest

_OPT_IN_VAR = "FINWEB_PG_PREFLIGHT"
_SOCKET_VAR = "FINWEB_PG_SOCKET"
_HOST_VAR = "FINWEB_PG_HOST"
_PORT_VAR = "FINWEB_PG_PORT"

_TCP_TIMEOUT_SECONDS = 5

# Classification taxonomy (Tech Plan §13.F / CP1 authority §2.3) — exact strings.
_TRANSPORT_REACHABLE = "TRANSPORT_REACHABLE"
_PERMITTED_NO_LISTENER = "PERMITTED_NO_LISTENER"
_SOCKET_MISSING = "SOCKET_MISSING"
_POLICY_DENIED = "POLICY_DENIED"
_RUNTIME_ERROR = "RUNTIME_ERROR"
_OTHER = "OTHER"


def _opted_in() -> bool:
    return os.environ.get(_OPT_IN_VAR) == "1"


def _classify_connect_exception(exc: BaseException, *, allow_socket_missing: bool) -> str:
    """Map a raised exception from connect() onto the required taxonomy.

    Returns the classification string. Does not print or assert — callers do that,
    since only the caller knows which route (U/T) and which raw evidence to attach.
    """
    if isinstance(exc, socket.timeout):
        return _OTHER
    if allow_socket_missing and isinstance(exc, FileNotFoundError):
        return _SOCKET_MISSING
    if isinstance(exc, ConnectionRefusedError):
        return _PERMITTED_NO_LISTENER
    if isinstance(exc, PermissionError):
        return _POLICY_DENIED
    if isinstance(exc, OSError):
        err = exc.errno
        if allow_socket_missing and err == errno.ENOENT:
            return _SOCKET_MISSING
        if err == errno.ECONNREFUSED:
            return _PERMITTED_NO_LISTENER
        if err in (errno.EPERM, errno.EACCES):
            return _POLICY_DENIED
        return _RUNTIME_ERROR
    return _OTHER


def _report(route: str, classification: str, evidence: str) -> None:
    print(f"E0 {route}: classification={classification} evidence={evidence}")


class PostgresConnectivityPreflightTests(unittest.TestCase):
    """E0 — transport reachability only. No credentials, no PostgreSQL protocol."""

    def test_route_u_unix_domain_socket(self) -> None:
        if not _opted_in():
            self.skipTest(
                f"E0 opt-in probe disabled by default. To run Route U (Unix-domain "
                f"socket), set {_OPT_IN_VAR}=1 and {_SOCKET_VAR}=<path to the "
                f"PostgreSQL Unix-domain socket>."
            )
        socket_path = os.environ.get(_SOCKET_VAR)
        if not socket_path:
            self.skipTest(
                f"{_OPT_IN_VAR}=1 is set but {_SOCKET_VAR} is not. Set "
                f"{_SOCKET_VAR}=<path to the PostgreSQL Unix-domain socket> to run "
                f"Route U."
            )

        sock = None
        classification = None
        evidence = ""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(_TCP_TIMEOUT_SECONDS)
            sock.connect(socket_path)
            classification = _TRANSPORT_REACHABLE
            evidence = f"connect({socket_path!r}) returned with no exception"
        except Exception as exc:  # noqa: BLE001 - deliberately broad; classified below
            classification = _classify_connect_exception(exc, allow_socket_missing=True)
            errno_val = getattr(exc, "errno", None)
            errno_name = errno.errorcode.get(errno_val, "n/a") if errno_val else "n/a"
            evidence = (
                f"{type(exc).__name__}: {exc} (errno={errno_val} [{errno_name}])"
            )
        finally:
            if sock is not None:
                sock.close()

        _report("Route U (Unix-domain socket)", classification, evidence)

        if classification == _TRANSPORT_REACHABLE:
            return
        # Report but do not fail a non-reachable route: PERMITTED_NO_LISTENER,
        # SOCKET_MISSING, POLICY_DENIED, RUNTIME_ERROR and OTHER are all lawful,
        # informative preflight outcomes about a human-provisioned endpoint this
        # test does not control. The taxonomy string above and the raw evidence
        # printed to stdout are the record of what was observed; nothing here is
        # silently swallowed.
        self.assertIn(
            classification,
            {
                _PERMITTED_NO_LISTENER,
                _SOCKET_MISSING,
                _POLICY_DENIED,
                _RUNTIME_ERROR,
                _OTHER,
            },
        )

    def test_route_t_loopback_tcp(self) -> None:
        if not _opted_in():
            self.skipTest(
                f"E0 opt-in probe disabled by default. To run Route T (loopback "
                f"TCP), set {_OPT_IN_VAR}=1, {_HOST_VAR}=<loopback host>, and "
                f"{_PORT_VAR}=<port>."
            )
        host = os.environ.get(_HOST_VAR)
        port_raw = os.environ.get(_PORT_VAR)
        if not host or not port_raw:
            self.skipTest(
                f"{_OPT_IN_VAR}=1 is set but {_HOST_VAR} and/or {_PORT_VAR} is not. "
                f"Set {_HOST_VAR}=<loopback host> and {_PORT_VAR}=<port> to run "
                f"Route T."
            )
        try:
            port = int(port_raw)
        except ValueError:
            self.fail(f"{_PORT_VAR}={port_raw!r} is not an integer port number.")

        sock = None
        classification = None
        evidence = ""
        try:
            sock = socket.create_connection((host, port), timeout=_TCP_TIMEOUT_SECONDS)
            classification = _TRANSPORT_REACHABLE
            evidence = f"create_connection(({host!r}, {port})) returned with no exception"
        except Exception as exc:  # noqa: BLE001 - deliberately broad; classified below
            classification = _classify_connect_exception(exc, allow_socket_missing=False)
            errno_val = getattr(exc, "errno", None)
            errno_name = errno.errorcode.get(errno_val, "n/a") if errno_val else "n/a"
            evidence = (
                f"{type(exc).__name__}: {exc} (errno={errno_val} [{errno_name}])"
            )
        finally:
            if sock is not None:
                sock.close()

        _report("Route T (loopback TCP)", classification, evidence)

        if classification == _TRANSPORT_REACHABLE:
            return
        self.assertIn(
            classification,
            {
                _PERMITTED_NO_LISTENER,
                _SOCKET_MISSING,
                _POLICY_DENIED,
                _RUNTIME_ERROR,
                _OTHER,
            },
        )


if __name__ == "__main__":
    unittest.main()
