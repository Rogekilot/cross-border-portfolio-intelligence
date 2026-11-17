"""F1 R5: the WORLD BUILDERS of the real-path create (design 7.1 R5 row: "the world builder from the locked snapshot (N2b)"; 4.4).

PLACEMENT. This package sits ABOVE `persistence`: it calls the performance engine and its service, and `persistence` is below the engine by a
standing rule (`tests/product/test_performance_boundaries.py`). It was first written in `persistence` and moved here for that reason.

A "world" is what a financial service needs to value a ledger: a market-data port, an identity resolver, the conventions and the F8B confirmation
policy. The create builds its world FROM THE LOCKED SNAPSHOT of the lease it was admitted under, and checks that the world is the snapshot's: it
recomputes every digest the snapshot holds with R4b's own functions (`persistence.real_digests`, moved there from `real_tools.qualification` in R5
so that product code does not import the tools package; nothing is re-implemented here) and refuses the create on any difference
(`RW_WORLD_DIFFERS`, the field named in the detail). A snapshot is a content hash of those digests, so a world that differs from it in any field
is not the world the owner published.

Two builders, one verifier:

  * `build_real_world`  (the REAL branch: `REAL` and `TEST_SWITCH`). Reads the release through `read_release(..., lease_checked=True)`: the
    thirteen lease-checked read functions of R3, the only reads the executor has (PD-0069), under the open `EXECUTE_CREATE` or
    `EXECUTE_REPRODUCE` lease. The source registry it passes is built from the SNAPSHOT's own source records (`real_registry_map`), not from a
    file on disk. The identity resolver, the conventions and the policy are INPUTS (the executor has no identity grant: the resolver is built by
    the caller from the owner-seeded rows, and its `identity_digest` is checked against the snapshot's).
  * `build_fictional_world` (the test-scope create, the fictional branch). The invented world of the EXISTING fictional integration
    (`financial_service_integration`, unchanged): one invented listing, one invented quote, one invented calendar day. It is data in this module,
    deterministic, built in memory; it is never stored as market data. Its snapshot fields (`FictionalWorld.snapshot_fields`) are what a
    test-scope snapshot must carry for the world to pass the same verifier.

Pure of connections except `build_real_world`'s one read; no clock, no environment, no file.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
import hashlib
import types
import uuid
from decimal import Decimal

from corporate_actions_service.split_confirmation import ConfirmationPolicy
from diversification.contracts import CapitalUniverseChoice
from domain.currency import CurrencyCode
from domain.instrument import SecurityType
from marketdata.calendars import CalendarSet
from marketdata.contracts import (AdjustmentStatus, CalendarDays, CalendarKind, DataDelayStatus, Lineage, QuoteObservation,
                                  SourceReading, SourceTiming, UsageScope)
from marketdata.manifest import MarketDataRelease, SourceRecord, SourceRegistry, source_registry_digest
from marketdata.market11 import market11_conventions
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry
from marketdata.store import InMemoryMarketData
from performance.engine import performance_conventions
from performance.periods import WindowRule, WindowSpec
from performance_service import service as _service
from performance_service.service import policy_reference
from persistence import market_data_store as mds, real_registry_map
from persistence import real_digests as q
from persistence.real_workspace_context import RealWorkspaceError

USD = CurrencyCode("USD")
#: The financial service's own refusal code for market data it knows to be invented (design fact 12), and the one test of it. The real branch's
#: create, reproduce and any later reader ask `service_refused(result)`; none of them spells the code.
REFUSAL_CODE = _service.SYNTHETIC_MARKET_DATA_REFUSED
FICTIONAL_DAY = dt.date(2026, 1, 5)
FICTIONAL_SOURCE = "r5.inline.invented.quotes"
_QUOTE_SHA = hashlib.sha256(b"R5_INVENTED_QUOTE_10_UNIT_ONLY").hexdigest()
_CAL_SHA = hashlib.sha256(b"R5_INVENTED_UNIT_CALENDAR").hexdigest()
FICTIONAL_PRICE = Decimal("10")


def service_refused(result):
    """True when the performance service's result carries its refusal of invented market data in any metric."""
    return any(REFUSAL_CODE in metric.details for metric in result.metrics)


class WorldError(RealWorkspaceError):
    """The world is not the snapshot's. `detail` names the first field that differs."""

    def __init__(self, field_name):
        super().__init__("RW_WORLD_DIFFERS", field_name)


@dataclass(frozen=True)
class WorldInputs:
    """The inputs the REAL branch's world takes from its caller (the executor has no identity grant, and the conventions are code)."""
    resolver: object
    market_conventions: object
    perf_conventions: object
    policy: object


@dataclass(frozen=True)
class World:
    port: object
    resolver: object
    market_conventions: object
    perf_conventions: object
    policy: object
    calendars: object
    release: object
    registry: object


@dataclass(frozen=True)
class FictionalWorld:
    world: World
    listing_id: uuid.UUID
    capital_policy: object
    request: object
    as_of: dt.date
    release_id: str
    f8b_policy_digest: str

    def snapshot_fields(self, members, scope):
        """The keyword set of `real_proposal.build_snapshot` that makes a test-scope snapshot whose digests are this world's (`members`
        are the provenance candidate's). `scope` is a `ResolvedScope`."""
        w = self.world
        contents = w.port.export()
        records = [_record_of(r) for r in w.port.source_registry_records()]
        from persistence.real_proposal import SourceRecord as ProposalRecord
        return dict(members=list(members), source_records=[ProposalRecord(**r) for r in records], release_id=w.release.release_id,
                    release_digest=q.release_digest(w.release), projection_digest=q.projection_digest(w.release, contents, w.calendars),
                    identity_digest=q.identity_digest(w.resolver), calendar_digest=q.calendar_digest(w.release, contents, w.calendars),
                    convention_digest=q.convention_digest(w.market_conventions, w.perf_conventions, w.release),
                    profile_digest=q.profile_digest(m.source_id for m in members), f8b_policy_digest=self.f8b_policy_digest)


def _record_of(record):
    return {"source_id": record.source_id, "name": record.name, "upstream_provider": record.upstream_provider,
            "independence_group": record.independence_group, "terms_url": record.terms_url, "terms_check": None}


def _lineage(digest):
    return Lineage("R5 inline invented world", AdjustmentStatus.RAW, source_id=FICTIONAL_SOURCE, file_sha256=digest,
                   adapter_id="r5.inline.invented", adapter_version="1", source_record_ref="unit",
                   retrieved_at=dt.datetime(2026, 1, 5, tzinfo=dt.timezone.utc), usage_scope=UsageScope.SYNTHETIC_TEST,
                   upstream="R5 inline invented unit", independence_group=FICTIONAL_SOURCE, market="US")


def build_fictional_world(root_id):
    """The invented world of the fictional branch for one root (the capital-policy choice is scoped to the root, as the fictional integration
    requires). Deterministic: the identity ids are fixed (the owner seeds them as rows once; E11 in tests, R6's plan for a real database)."""
    ids = iter(uuid.UUID(int=i) for i in range(200, 210))
    resolver = InMemoryIdentityRegistry(lambda: next(ids))
    (registration,) = resolver.register_instruments((InstrumentEntry(
        "R5 invented issuer", SecurityType.COMMON_STOCK, "XNYS", "NYSE", "R5-SYN-UNIT", USD),))
    listing = registration.listing_id
    calendar = CalendarDays("R5-UNIT-CAL", CalendarKind.EXCHANGE_SESSIONS, ("XNYS",), "America/New_York", FICTIONAL_DAY, FICTIONAL_DAY,
                            (FICTIONAL_DAY,), FICTIONAL_DAY, "R5 inline invented session", "R5 invented", FICTIONAL_DAY, "1", _lineage(_CAL_SHA),
                            default_close=dt.time(16))
    calendars = CalendarSet((calendar,))
    market = market11_conventions(calendars)
    observation = QuoteObservation(listing, FICTIONAL_DAY, FICTIONAL_PRICE, USD, SourceTiming(delay_status=DataDelayStatus.END_OF_DAY),
                                   _lineage(_QUOTE_SHA), volume=Decimal("1"))
    release = MarketDataRelease("R5 invented UNIT_ONLY", tuple(sorted((_CAL_SHA, _QUOTE_SHA))), (FICTIONAL_SOURCE,), created_for="R5 unit only")
    record = SourceRecord(FICTIONAL_SOURCE, "F2 unit", "fictional unit", FICTIONAL_SOURCE, synthetic=True)
    port = InMemoryMarketData(release, (SourceReading(FICTIONAL_SOURCE, FICTIONAL_SOURCE, _QUOTE_SHA, observation),),
                              exchange_of=resolver.exchange_mic, contains_synthetic=True, source_records=(record,))
    policy = ConfirmationPolicy(frozenset(("r5.feed",)), frozenset(("r5.filing",)))
    capital = CapitalUniverseChoice("FULL_NAV", "SYNTHETIC_CANDIDATE", "R5 inline invented denominator", decision_id="R5-UNIT-POLICY",
                                    scope_kind="PORTFOLIO", portfolio_id=str(root_id))
    world = World(port, resolver, market, performance_conventions(), policy, calendars, release, SourceRegistry((record,)))
    return FictionalWorld(world, listing, capital, WindowSpec(WindowRule.SINCE_INCEPTION), FICTIONAL_DAY, release.release_id,
                          dict(policy_reference(policy))["digest"])


def fictional_snapshot_fields(members, scope):
    """The snapshot fields of the invented world, independent of a root (the root only scopes the capital-policy choice)."""
    return build_fictional_world(uuid.UUID(int=0)).snapshot_fields(members, scope)


def verify_world(content, scope, world, *, projection_digest):
    """Recompute every digest of the snapshot `content` from `world` with R4b's functions and refuse the create on the first difference.
    `projection_digest` is the digest of the projection as the caller read it (the real branch: the port's own, which `read_release` already
    compared with the stored release row; the fictional branch: the invented projection after `stored_contents`)."""
    port, release, calendars = world.port, world.release, world.calendars
    contents = port.export()
    member_sources = sorted({m["source_id"] for m in content["members"]})
    full, used = real_registry_map.registry_digests(content["source_records"], member_sources, synthetic=scope.synthetic)
    observed = (
        ("release_id", release.release_id, content["release"]["release_id"]),
        ("release_digest", q.release_digest(release), content["release"]["release_digest"]),
        ("projection_digest", projection_digest, content["projection_digest"]),
        ("identity_digest", q.identity_digest(world.resolver), content["identity_digest"]),
        ("calendar_digest", q.calendar_digest(release, contents, calendars), content["calendar_digest"]),
        ("convention_digest", q.convention_digest(world.market_conventions, world.perf_conventions, release), content["convention_digest"]),
        ("profile_digest", q.profile_digest(member_sources), content["profile_digest"]),
        ("f8b_policy_digest", dict(policy_reference(world.policy))["digest"], content["f8b_policy_digest"]),
        ("registry.full_registry_digest", full, content["registry"]["full_registry_digest"]),
        ("registry.used_source_digest", used, content["registry"]["used_source_digest"]),
        ("registry.port", source_registry_digest(port.source_registry_records()), content["registry"]["used_source_digest"]),
        ("contains_synthetic", bool(port.contains_synthetic), bool(scope.synthetic)),      # I2: synthetic and real origins never mix
    )
    for name, actual, expected in observed:
        if actual != expected:
            raise WorldError(name)
    return world


def market_conventions_for(inputs, calendars):
    """The market conventions of a world. `WorldInputs.market_conventions` is either the convention set itself (the tests, which hold the calendars when
    they build it) or a FUNCTION of the release's calendars (the real launcher, which cannot know them before the release is read): the same
    `market11_conventions(calendars)` every caller builds, called here on the calendars the world's own port holds."""
    conventions = inputs.market_conventions
    return conventions(calendars) if isinstance(conventions, types.FunctionType) else conventions


def build_real_world(conn, content, scope, inputs):
    """The REAL branch's world from the locked snapshot `content` (a parsed snapshot), inside an open EXECUTE_CREATE or EXECUTE_REPRODUCE lease on
    `conn` (the executor). The release is read through the lease-checked read functions; a read outside the lease, or at or after
    `complete_by`, is refused by the function and surfaces as the tail's definite refusal."""
    if type(inputs) is not WorldInputs:
        raise RealWorkspaceError("RW_SHAPE", "world inputs are required")
    records = [real_registry_map.engine_source_record(r, synthetic=scope.synthetic) for r in content["source_records"]]
    registry = SourceRegistry(records)
    try:
        port = mds.read_release(conn, content["release"]["release_id"], inputs.resolver.exchange_mic, registry=registry, lease_checked=True)
    except (mds.MarketDataStoreError, LookupError, PermissionError, ValueError) as error:
        # read_release's own integrity checks (the release's file list against its content, the projection digest recomputed from the rows read,
        # the registry against the stored rows, the profile gate) still run on the executor's path (FR-L1 (a)). Their failure is a typed
        # refusal with whole rollback. A database error, including the lease-checked function's own refusal, is not caught here.
        raise RealWorkspaceError("RW_RELEASE_REFUSED", type(error).__name__) from error
    world = World(port, inputs.resolver, market_conventions_for(inputs, port.calendars()), inputs.perf_conventions, inputs.policy, port.calendars(), port.release,
                  registry)
    return verify_world(content, scope, world, projection_digest=port.projection_digest())


def read_claim_files(conn, content):
    """The files of the snapshot's release for the claim record (O-7), through the lease-checked read functions, under the same open `EXECUTE_CREATE` or
    `EXECUTE_REPRODUCE` lease as `build_real_world`: `(file_sha256, source_id, data_kind, manifest)` per file. A read outside the lease is refused by the
    function and surfaces as the tail's definite refusal."""
    return mds.read_release_files(conn, content["release"]["release_id"], lease_checked=True)


def check_fictional_world(content, scope, fictional):
    """The fictional branch's counterpart: the same verifier over the invented world."""
    world = fictional.world
    return verify_world(content, scope, world, projection_digest=q.projection_digest(world.release, world.port.export(), world.calendars))
