"""F1 R1: the scope core of the real-data path (design 4.2, 1.1).

One parameterised module holds every scope, so that all of them share identical rules and cannot be mixed
(PD-0066 decision 8). A scope is a pair (branch, origin axis) [E7]:

    SYNTHETIC_TEST   fictional branch, synthetic axis   TEST installs only
    TEST_SWITCH      REAL branch,      synthetic axis   TEST installs only; reachable only through the switch
    REAL             REAL branch,      real axis        REAL installs only

Origin labels follow the AXIS, not the branch [E16]: a `TEST_SWITCH` snapshot runs the real branch and carries
synthetic labels throughout. `REAL_SOURCE` never appears in a test scope (I1, I3). Invented data is never marked
`synthetic = false`: the first `synthetic = false` record is reserved for the real run.

Three things live here and nowhere else:

  * the scope definitions and their labels (pure, no I/O);
  * the REVIEWED TEST SWITCH (`resolve_scope`, section "THE TEST SWITCH" below): the only way to reach `TEST_SWITCH`,
    an explicit keyword argument that yields a `ResolvedScope`. Every function that builds a snapshot takes a
    `ResolvedScope` and refuses a bare scope name or a bare `ScopeDef`, so `SCOPES["TEST_SWITCH"]` is a table entry
    (data) and not a way in. No environment variable, command-line flag or HTTP field reaches the switch, and this module
    reads none (static tests check that, and check where scopes are looked up and where a `ResolvedScope` is made);
  * the install-kind guard (`check_install_kind`) and the factory (`make_snapshot`), which reads the install kind of the
    connected database (written once by the installer, [E6]) and refuses a scope the install does not hold.

Nothing here reads a clock, a file or the environment. Importing it never requires a database driver.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


class ScopeError(ValueError):
    """A scope refusal. `code` is the stable `RW_*` code; the message carries no number."""

    def __init__(self, code, detail="Real-path scope refused"):
        self.code = code
        super().__init__(detail)


INSTALL_KINDS = ("TEST", "REAL")

#: Origin labels (design 1.1; prospective names fixed in R1). They are a function of the scope's origin axis.
MARKET_ORIGIN_SYNTHETIC = "SYNTHETIC_TEST"
MARKET_ORIGIN_REAL = "REAL_SOURCE"
LEDGER_ORIGIN_SYNTHETIC = "INVENTED_TEST_LEDGER"
LEDGER_ORIGIN_REAL = "PROJECT_CONSTRUCTED_NONPERSONAL_UAT"
#: The one string that no stored row or output of a test scope may contain (I1, I3).
REAL_ORIGIN_MARKER = "REAL_SOURCE"


@dataclass(frozen=True)
class ScopeDef:
    name: str
    branch: str            # "FICTIONAL" | "REAL"
    origin_axis: str       # "SYNTHETIC" | "REAL"
    install_kind: str      # the only install kind that may hold this scope
    market_origin: str
    ledger_origin: str
    synthetic: bool
    requires_switch: bool

    def origin_fields(self):
        """The immutable origin fields of every snapshot of this scope. `personal_holdings` is stated, never defaulted."""
        return {"market_origin": self.market_origin, "ledger_origin": self.ledger_origin,
                "personal_holdings": False, "synthetic": self.synthetic}


#: The scope table is DATA: read-only, and nothing builds a snapshot from an entry of it directly. A snapshot is built only from
#: a `ResolvedScope`, which only `resolve_scope` makes.
SCOPES = MappingProxyType({
    "SYNTHETIC_TEST": ScopeDef("SYNTHETIC_TEST", "FICTIONAL", "SYNTHETIC", "TEST", MARKET_ORIGIN_SYNTHETIC,
                               LEDGER_ORIGIN_SYNTHETIC, True, False),
    "TEST_SWITCH": ScopeDef("TEST_SWITCH", "REAL", "SYNTHETIC", "TEST", MARKET_ORIGIN_SYNTHETIC,
                            LEDGER_ORIGIN_SYNTHETIC, True, True),
    "REAL": ScopeDef("REAL", "REAL", "REAL", "REAL", MARKET_ORIGIN_REAL, LEDGER_ORIGIN_REAL, False, False),
})


# ===================================================================================================================
# THE TEST SWITCH. This section is a separate item of R1's independent review (design 4.2, PD-0066 decision 8).
#
# `TEST_SWITCH` is the real branch run on invented data, in a disposable TEST install only. It is reachable through
# exactly one door: `resolve_scope(name, test_switch=True)`. That function is the only one that returns a
# `ResolvedScope`, and `real_proposal.build_snapshot`, `write_proposal` and `make_snapshot` (here) accept nothing else, so a
# caller who holds `SCOPES["TEST_SWITCH"]`, a copy of it or the string "TEST_SWITCH" cannot build with it. (The verifier
# reads the scope field of BYTES, which is data; it never builds from a caller's scope. A `REAL` install refuses such bytes
# at publish and at admit.) The argument is a plain `bool` supplied by calling code. Nothing in this module reads the
# environment, the command line or a request; the real-mode launcher has no code path that passes it (R7 checks that on the
# launcher module). `test_switch=True` for any scope that does not require it is itself refused, so the argument cannot be
# used as a general relaxation. A `REAL` install refuses a `TEST_SWITCH` snapshot again at publish and at admit (the
# install-kind guard, below and in the gateway SQL).
# ===================================================================================================================
_MINT = object()


class ResolvedScope:
    """A scope that went through `resolve_scope`. Only `resolve_scope` makes one: the constructor refuses any other caller."""
    __slots__ = ("definition",)

    def __init__(self, definition, mint=None):
        if mint is not _MINT or type(definition) is not ScopeDef:
            raise ScopeError("RW_SCOPE_UNRESOLVED", "A scope is obtained from resolve_scope")
        object.__setattr__(self, "definition", definition)

    def __setattr__(self, name, value):
        raise AttributeError("a resolved scope is read-only")

    def __getattr__(self, name):
        if name == "definition":
            raise AttributeError(name)
        return getattr(self.definition, name)


def resolve_scope(name, *, test_switch=False):
    scope = SCOPES.get(name) if isinstance(name, str) else None
    if scope is None:
        raise ScopeError("RW_SCOPE_UNKNOWN", "Unknown scope")
    if test_switch is not True and test_switch is not False:
        raise ScopeError("RW_SHAPE", "The test switch is a bool")
    if scope.requires_switch and test_switch is not True:
        raise ScopeError("RW_SWITCH_REQUIRED", "This scope is reachable only through the reviewed test switch")
    if test_switch is True and not scope.requires_switch:
        raise ScopeError("RW_SWITCH_NOT_APPLICABLE", "The test switch applies to TEST_SWITCH only")
    return ResolvedScope(scope, _MINT)
# ===================================================================================================================
# End of the test switch.
# ===================================================================================================================


def require_resolved(scope):
    """The `ScopeDef` behind a `ResolvedScope`; anything else (a name, a bare `ScopeDef`, a copy) is refused."""
    if type(scope) is not ResolvedScope:
        raise ScopeError("RW_SCOPE_UNRESOLVED", "A scope is obtained from resolve_scope")
    return scope.definition


def check_install_kind(scope, kind):
    """The install-kind guard (design 4.2): a TEST install holds only test scopes, a REAL install only `REAL`."""
    if kind not in INSTALL_KINDS:
        raise ScopeError("RW_INSTALL_MISSING", "The database does not report an install kind")
    if scope.install_kind != kind:
        raise ScopeError("RW_INSTALL_KIND", "This scope cannot exist in a %s install" % kind)
    return scope


def scope_by_snapshot_field(value):
    """The scope named by a snapshot's `scope` field, for refusal paths. Never grants the switch."""
    scope = SCOPES.get(value) if isinstance(value, str) else None
    if scope is None:
        raise ScopeError("RW_SCOPE_UNKNOWN", "Unknown scope")
    return scope


def labels_match_scope(scope, origin):
    """True when an `origin` mapping carries exactly the labels of `scope` (I1, I3; the seal's row guard is R3)."""
    return isinstance(origin, dict) and origin == scope.origin_fields()


def read_install_kind(conn, schema):
    """(kind, w_seconds) of the connected database, from the gateway's definer function. The row itself is readable by no
    runtime role (design 2.1)."""
    from persistence.real_workspace_context import identifier, query_one
    row = query_one(conn, identifier(schema), "rw_install_info")
    if row is None:
        raise ScopeError("RW_INSTALL_MISSING", "The database does not report an install kind")
    return row[0], row[1]


def make_snapshot(conn, schema, scope_name, *, test_switch=False, **content):
    """The scope factory (design 4.2): the only way tests and tools obtain a snapshot of a test scope.

    Order of refusals: unknown scope or switch misuse first (no I/O), then the install kind of the connected database.
    `content` is the keyword set of `real_proposal.build_snapshot`; the origin labels come from the scope, not from the
    caller. `scope_name` is a name: a `ScopeDef`, a copy of one or a `ResolvedScope` is refused (`RW_SCOPE_UNKNOWN`), so the
    only path from here to a test-scope snapshot is `resolve_scope` with its switch and the install-kind read below.
    Returns a `real_proposal.Snapshot`.
    """
    scope = resolve_scope(scope_name, test_switch=test_switch)
    kind, _w = read_install_kind(conn, schema)
    check_install_kind(scope, kind)
    from persistence import real_proposal
    return real_proposal.build_snapshot(scope, **content)
