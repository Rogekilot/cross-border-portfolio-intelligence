"""Fixed local-fictional financial services; no connection/transaction ownership.

The core owns the current DB lease and immutable snapshot. Public Python objects
are trusted operator inputs, not cryptographic authority or hostile-code isolation.
Archive READ and exact committed-operation retry do not call this module's issuer.
"""
from __future__ import annotations

import datetime as dt
import dataclasses
import hashlib
import json
import re
import uuid
from types import FunctionType
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from fractions import Fraction

from corporate_actions_service.split_confirmation import ConfirmationPolicy
from domain.currency import CurrencyCode
from diversification.contracts import CapitalUniverseChoice, MetadataSnapshot, Result
from diversification.engine import ENGINE_ID as CP5_ENGINE_ID
from diversification_service import service as cp5_service
from marketdata.calendars import CalendarSet
from marketdata.canonical import canonical_json
from marketdata.contracts import Lineage, QuoteObservation, UsageScope
from marketdata.conventions import ConventionSet
from marketdata.manifest import source_registry_digest
from marketdata.market11 import Market11Freshness, Market11FX, Market11PriceOfDate
from marketdata.reconciliation import Market11Reconciler
from marketdata.resolver import InMemoryIdentityRegistry
from marketdata.store import InMemoryMarketData
from performance.conventions import PerformanceConventionSet
from performance.manifest import ComputationResult
from performance.periods import WindowRule, WindowSpec
from performance.series import Frequency
from performance_service import service as performance_service

MAX_ISSUED_BYTES = 2_000_000
MAX_BINDING_BYTES = 32_768
MAX_SNAPSHOT_BYTES = 262_144
MAX_ITEMS = 4096
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_XID = re.compile(r"[1-9][0-9]{0,19}\Z")
_TX_STATE_SQL = "SELECT pg_backend_pid(),pg_current_xact_id_if_assigned()::text"
_DATACLASS_MODULES = frozenset((
    "domain.currency", "domain.instrument", "marketdata.contracts",
    "marketdata.manifest", "marketdata.store", "marketdata.resolver", "performance.conventions",
    "performance.rounding", "performance.states", "performance.periods",
    "diversification.contracts", "corporate_actions_service.split_confirmation",
))


class LocalServiceKind(Enum):
    CP5_DIVERSIFICATION = "CP5_DIVERSIFICATION"
    PERFORMANCE_SYNTHETIC_REFUSAL = "PERFORMANCE_SYNTHETIC_REFUSAL"


class LocalServiceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class LocalServiceRefusal(LocalServiceError):
    """Provisional actual service diagnosis; only core can prove whole rollback."""
    def __init__(self, code, issued_result=None, issued_bytes=None):
        self.issued_result = issued_result
        self.issued_bytes = issued_bytes
        self.issued_sha256 = None if issued_bytes is None else _sha(issued_bytes)
        super().__init__(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _fail(code="LOCAL_SERVICE_BINDING_DIFFERS"):
    raise LocalServiceError(code)


def _bounded(value, limit):
    raw = canonical_json(value).encode("utf-8")
    if len(raw) > limit:
        _fail("LOCAL_SERVICE_OUTPUT_LIMIT")
    return raw


def _semantic(value, depth=0):
    """Closed typed state encoding; never invokes arbitrary serialization hooks."""
    if depth > 16:
        _fail("LOCAL_CONTEXT_BOUND")
    typ = type(value)
    if value is None or typ in (bool, int, str):
        if typ is str and (len(value.encode("utf-8")) > 8192 or any(ord(c) < 32 for c in value)):
            _fail("LOCAL_CONTEXT_BOUND")
        return value
    if typ is uuid.UUID:
        return {"uuid": str(value)}
    if typ in (Decimal, Fraction, dt.date, dt.datetime, dt.time):
        return {typ.__name__: canonical_json(value)}
    if isinstance(value, Enum) and typ.__module__.startswith(("domain.", "marketdata.", "performance.", "diversification.")):
        return {"enum": typ.__module__ + "." + typ.__name__, "value": value.value}
    if typ in (tuple, list, frozenset):
        if len(value) > MAX_ITEMS:
            _fail("LOCAL_CONTEXT_BOUND")
        rows = [_semantic(v, depth + 1) for v in value]
        return sorted(rows, key=canonical_json) if typ is frozenset else rows
    if typ is dict:
        if len(value) > MAX_ITEMS:
            _fail("LOCAL_CONTEXT_TYPE")
        rows = [[_semantic(k, depth + 1), _semantic(v, depth + 1)] for k, v in value.items()]
        return {"mapping": sorted(rows, key=lambda row: canonical_json(row[0]))}
    if typ is CalendarSet:
        return {"type": "marketdata.calendars.CalendarSet", "state": _semantic(vars(value), depth + 1)}
    rules = {
        Market11Freshness: {"_calendars"}, Market11FX: {"_calendars", "_parity"},
        Market11PriceOfDate: set(), Market11Reconciler: {"_order"},
    }
    if typ in rules:
        if set(vars(value)) != rules[typ] or (typ is Market11FX and value._parity is not None):
            _fail("LOCAL_CONTEXT_TYPE")
        return {"type": typ.__module__ + "." + typ.__name__, "state": _semantic(vars(value), depth + 1)}
    if (dataclasses.is_dataclass(value) and not isinstance(value, type)
            and (typ is ConventionSet or typ.__module__ in _DATACLASS_MODULES)):
        fields = dataclasses.fields(value)
        if hasattr(value, "__dict__") and set(vars(value)) != {f.name for f in fields}:
            _fail("LOCAL_CONTEXT_TYPE")
        return {"type": typ.__module__ + "." + typ.__name__,
                "fields": {f.name: _semantic(getattr(value, f.name), depth + 1) for f in fields}}
    _fail("LOCAL_CONTEXT_TYPE")


def _lineage(lineage):
    if type(lineage) is not Lineage or lineage.usage_scope is not UsageScope.SYNTHETIC_TEST or lineage.is_synthetic is not True:
        _fail("LOCAL_CONTEXT_NOT_FICTIONAL")


def fingerprint_context_inputs(*, port, resolver, market_conventions, conventions,
                               policy, as_of, reporting_currency="USD", metadata=None,
                               coverage=(), capital_policy=None, request=None,
                               frequency=Frequency.WEEKLY):
    """Actual source/scope canonical bytes; context_id is their self-free SHA256."""
    if (type(port) is not InMemoryMarketData or type(resolver) is not InMemoryIdentityRegistry
            or type(market_conventions) is not ConventionSet or type(conventions) is not PerformanceConventionSet
            or type(policy) is not ConfirmationPolicy or type(as_of) is not dt.date
            or reporting_currency != "USD" or type(reporting_currency) is not str
            or type(frequency) is not Frequency or type(coverage) is not tuple):
        _fail("LOCAL_CONTEXT_TYPE")
    if port.contains_synthetic is not True or (metadata is not None and (type(metadata) is not MetadataSnapshot or metadata.synthetic is not True)):
        _fail("LOCAL_CONTEXT_NOT_FICTIONAL")
    contents = port.export()
    exchange = vars(port).get("_exchange_of")
    if (getattr(exchange, "__self__", None) is not resolver
            or getattr(exchange, "__func__", None) is not InMemoryIdentityRegistry.exchange_mic):
        _fail("LOCAL_CONTEXT_BINDING_DIFFERS")
    rank = vars(port).get("_rank")
    if (type(rank) is not FunctionType or rank.__module__ != "marketdata.store"
            or rank.__qualname__ != "InMemoryMarketData.__init__.<locals>.<lambda>"
            or rank.__dict__ or rank.__defaults__ is not None or rank.__kwdefaults__ is not None):
        _fail("LOCAL_CONTEXT_TYPE")
    rank_state = {"code": rank.__code__.co_code.hex(), "constants": _semantic(rank.__code__.co_consts),
                  "closure": _semantic(tuple(c.cell_contents for c in rank.__closure__ or ()))}
    if (not contents.readings or len(contents.readings) > 128 or contents.benchmarks
            or contents.adjusted or contents.fx_windows or contents.exclusions or contents.risk_free or coverage):
        _fail("LOCAL_CONTEXT_SCOPE_REFUSED")
    for reading in contents.readings:
        if type(reading.observation) is not QuoteObservation or reading.observation.currency.code != "USD":
            _fail("LOCAL_CONTEXT_SCOPE_REFUSED")
        _lineage(reading.observation.lineage)
    records = port.source_registry_records()
    if not records or len(records) > 16 or any(r.synthetic is not True for r in records):
        _fail("LOCAL_CONTEXT_NOT_FICTIONAL")
    calendars = getattr(market_conventions.freshness, "calendars", None)
    if type(calendars) is not CalendarSet or not calendars or len(calendars.calendars()) > 8:
        _fail("LOCAL_CONTEXT_TYPE")
    for cal in calendars.calendars():
        _lineage(cal.lineage)
    if type(capital_policy) is not CapitalUniverseChoice or capital_policy.choice != "FULL_NAV":
        _fail("LOCAL_CONTEXT_POLICY_REFUSED")
    resolved_request = WindowSpec(WindowRule.TRAILING_MONTHS, 36) if request is None else request
    if type(resolved_request) is not WindowSpec or resolved_request.rule not in (WindowRule.SINCE_INCEPTION, WindowRule.TRAILING_MONTHS):
        _fail("LOCAL_CONTEXT_SCOPE_REFUSED")
    if resolved_request.rule is WindowRule.TRAILING_MONTHS and (type(resolved_request.months) is not int or not 1 <= resolved_request.months <= 36):
        _fail("LOCAL_CONTEXT_SCOPE_REFUSED")
    identities = resolver.snapshot()
    if not identities[2] or len(identities[2]) > 16:
        _fail("LOCAL_CONTEXT_BOUND")
    lookup = []
    for listing in identities[2]:
        lid = listing.listing_id
        lookup.append((lid, resolver.trading_currency(lid), resolver.exchange_mic(lid), resolver.security_type(lid)))
    obj = {"schema": "finweb.local_fictional.service_context/1", "scope": "LOCAL_FICTIONAL_ONLY",
           "as_of": as_of, "reporting_currency": reporting_currency,
           "port": _semantic(contents),
           "port_live_state": _semantic({k: v for k, v in vars(port).items() if k not in ("_exchange_of", "_rank")}),
           "port_rank_state": rank_state,
           "source_records": _semantic(records),
           "release": _semantic(port.release), "resolver": _semantic(identities),
           "identifier_rows": _semantic(resolver.identifier_rows()), "lookup_answers": _semantic(tuple(lookup)),
           "calendars": _semantic(calendars), "market_conventions": _semantic(market_conventions),
           "conventions": _semantic(conventions), "policy": _semantic(policy),
           "metadata": _semantic(metadata), "coverage": _semantic(coverage),
           "capital_policy": _semantic(capital_policy), "request": _semantic(resolved_request),
           "frequency": frequency.value}
    return _bounded(obj, MAX_SNAPSHOT_BYTES)


@dataclass(frozen=True)
class LocalServiceRequest:
    selector: LocalServiceKind
    owner_id: uuid.UUID
    root_id: uuid.UUID
    revision_id: uuid.UUID
    operation_id: uuid.UUID
    portfolio_id: uuid.UUID
    ledger_pin: int
    as_of: dt.date
    context_id: str
    generation: int
    account_scope: None = None
    reporting_currency: str = "USD"

    def __post_init__(self):
        if type(self.selector) is not LocalServiceKind or any(type(v) is not uuid.UUID for v in (
                self.owner_id, self.root_id, self.revision_id, self.operation_id, self.portfolio_id)):
            _fail("LOCAL_SERVICE_REQUEST_INVALID")
        if (self.root_id != self.portfolio_id or type(self.as_of) is not dt.date or self.account_scope is not None
                or type(self.reporting_currency) is not str or self.reporting_currency != "USD"
                or type(self.context_id) is not str or _SHA.fullmatch(self.context_id) is None
                or any(type(v) is not int or not 1 <= v <= 2**63 - 1 for v in (self.ledger_pin, self.generation))):
            _fail("LOCAL_SERVICE_REQUEST_INVALID")


@dataclass(frozen=True)
class LocalFictionalContext:
    connection: object
    backend_pid: int
    transaction_id: str
    context_id: str
    generation: int
    snapshot_bytes: bytes
    port: object
    resolver: object
    market_conventions: object
    conventions: object
    policy: object
    as_of: dt.date
    reporting_currency: str = "USD"
    metadata: object = None
    coverage: tuple = ()
    capital_policy: object = None
    request: object = None
    frequency: Frequency = Frequency.WEEKLY

    def __post_init__(self):
        if (type(self.backend_pid) is not int or self.backend_pid <= 0
                or type(self.transaction_id) is not str or _XID.fullmatch(self.transaction_id) is None
                or int(self.transaction_id) > 2**64 - 1
                or type(self.generation) is not int or not 1 <= self.generation <= 2**63 - 1
                or type(self.snapshot_bytes) is not bytes or len(self.snapshot_bytes) > MAX_SNAPSHOT_BYTES
                or type(self.context_id) is not str or _SHA.fullmatch(self.context_id) is None
                or _sha(self.snapshot_bytes) != self.context_id):
            _fail("LOCAL_CONTEXT_BINDING_DIFFERS")

    def actual_snapshot(self):
        return fingerprint_context_inputs(port=self.port, resolver=self.resolver,
            market_conventions=self.market_conventions, conventions=self.conventions,
            policy=self.policy, as_of=self.as_of, reporting_currency=self.reporting_currency,
            metadata=self.metadata, coverage=self.coverage, capital_policy=self.capital_policy,
            request=self.request, frequency=self.frequency)


@dataclass(frozen=True)
class IssuedLocalServiceResult:
    family: str
    engine_id: str
    issued_bytes: bytes
    issued_sha256: str
    manifest_id: str
    result_digest: str
    question_bytes: bytes
    question_sha256: str
    binding_bytes: bytes
    binding_sha256: str
    synthetic: bool = True


@dataclass(frozen=True)
class LocalServiceReproduction:
    status: str
    detail: str = ""
    issued_sha256: str | None = None


def _verify_context(conn, request, context):
    if type(request) is not LocalServiceRequest or type(context) is not LocalFictionalContext:
        _fail("LOCAL_CONTEXT_TYPE")
    if (context.connection is not conn or request.context_id != context.context_id
            or request.generation != context.generation or request.as_of != context.as_of
            or request.reporting_currency != context.reporting_currency):
        _fail()
    if int(conn.info.transaction_status) != 2:
        _fail("LOCAL_SERVICE_TRANSACTION_REQUIRED")
    row = conn.execute(_TX_STATE_SQL).fetchone()
    if row is None or (row[0], row[1]) != (context.backend_pid, context.transaction_id):
        _fail("LOCAL_SERVICE_TRANSACTION_DIFFERS")
    if context.actual_snapshot() != context.snapshot_bytes:
        _fail("LOCAL_CONTEXT_BINDING_DIFFERS")


def _question(request):
    return {"schema": "finweb.local_fictional.service_question/1", "selector": request.selector.value,
        **{name: str(getattr(request, name)) for name in ("owner_id", "root_id", "revision_id", "operation_id", "portfolio_id")},
        "ledger_pin": str(request.ledger_pin), "as_of": request.as_of.isoformat(),
        "context_id": request.context_id, "generation": request.generation,
        "account_scope": None, "reporting_currency": request.reporting_currency}


def _validate_valuation(manifest, request, context, *, synthetic_refusal=False):
    # The unchanged performance refusal happens before confirmation-policy
    # evaluation and truthfully records an empty policy, unlike CP5 valuation.
    expected_policy = [] if synthetic_refusal else [list(p) for p in performance_service.policy_reference(context.policy)]
    expected_release = None if synthetic_refusal else context.port.release_id()
    if (manifest["portfolio_id"] != str(request.portfolio_id) or manifest["ledger_version"] != request.ledger_pin
            or manifest["as_of"] != request.as_of.isoformat() or manifest["reporting_currency"] != request.reporting_currency
            or manifest["scope"] != "PORTFOLIO" or manifest["state_kind"] != "ACTUAL"
            or manifest["synthetic"] is not True or manifest["split_detection"] != "F8B_DRY_RUN"
            or manifest["release_id"] != expected_release
            or manifest["source_registry_digest"] != source_registry_digest(context.port.source_registry_records())
            or manifest["detection_policy"] != expected_policy):
        _fail()
    if synthetic_refusal and manifest["data_set_refs"] != []:
        _fail()
    digest_fields = ("identity_digest", "ledger_digest") if synthetic_refusal else ("identity_digest", "ledger_digest", "release_id")
    for key in digest_fields:
        if type(manifest[key]) is not str or _SHA.fullmatch(manifest[key]) is None:
            _fail()


def issue_local_service(conn, *, request, context):
    """Core must hold its DB lease; return bytes only to its provisional stage."""
    _verify_context(conn, request, context)
    if request.selector is LocalServiceKind.PERFORMANCE_SYNTHETIC_REFUSAL:
        issued = performance_service.compute_for_portfolio(conn, request.portfolio_id, request.as_of,
            CurrencyCode("USD"),
            context.port, context.resolver, context.market_conventions, context.conventions,
            policy=context.policy, ledger_version=request.ledger_pin)
        if type(issued) is not ComputationResult:
            _fail("LOCAL_SERVICE_RESULT_INVALID")
        raw = issued.canonical_json().encode("utf-8")
        if len(raw) > MAX_ISSUED_BYTES:
            _fail("LOCAL_SERVICE_OUTPUT_LIMIT")
        _verify_context(conn, request, context)
        if (issued.manifest.synthetic is not True or not issued.metrics
                or any(m.result.value is not None for m in issued.metrics)
                or not all(performance_service.SYNTHETIC_MARKET_DATA_REFUSED in m.details for m in issued.metrics)):
            _fail("LOCAL_SERVICE_RESULT_INVALID")
        _validate_valuation(json.loads(raw)["manifest"], request, context, synthetic_refusal=True)
        raise LocalServiceRefusal(performance_service.SYNTHETIC_MARKET_DATA_REFUSED, issued, raw)
    issued = cp5_service.compute_diversification_for_portfolio(conn, request.portfolio_id,
        request.as_of, context.port, context.resolver, context.market_conventions, context.conventions,
        policy=context.policy, metadata=context.metadata, coverage=context.coverage,
        capital_policy=context.capital_policy, request=context.request, frequency=context.frequency,
        ledger_version=request.ledger_pin, account_scope=None, allow_synthetic=True)
    if type(issued) is not Result:
        raise LocalServiceRefusal(getattr(issued, "code", "LOCAL_SERVICE_RESULT_REFUSED"), issued)
    raw = issued.canonical_json().encode("utf-8")
    if len(raw) > MAX_ISSUED_BYTES:
        _fail("LOCAL_SERVICE_OUTPUT_LIMIT")
    _verify_context(conn, request, context)
    manifest = json.loads(issued.manifest_json)
    if (manifest["schema"] != "finweb.diversification_manifest/1" or manifest["engine_id"] != CP5_ENGINE_ID
            or manifest["synthetic"] is not True or manifest["state_kind"] != "ACTUAL"
            or manifest["portfolio_id"] != str(request.portfolio_id) or manifest["account_scope"] is not None
            or manifest["as_of"] != request.as_of.isoformat() or manifest["reporting_currency"] != "USD"
            or manifest["capital_policy"] != json.loads(canonical_json(context.capital_policy.to_obj()))
            or manifest["capital_policy_confirmed"] is not True):
        _fail("LOCAL_SERVICE_RESULT_INVALID")
    _validate_valuation(manifest["valuation_manifest"], request, context)
    facts = manifest["identity_facts"]
    if type(facts) is not list or len(facts) > 48 or len({tuple(f[:2]) for f in facts}) != len(facts):
        _fail("LOCAL_SERVICE_RESULT_INVALID")
    for method, listing, expected in facts:
        if method not in ("trading_currency", "exchange_mic", "security_type"):
            _fail("LOCAL_SERVICE_RESULT_INVALID")
        answer = getattr(context.resolver, method)(uuid.UUID(listing))
        answer = "-" if answer is None else answer.code if method == "trading_currency" else str(answer)
        if answer != expected:
            _fail("LOCAL_SERVICE_RESULT_INVALID")
    if _sha(canonical_json(facts).encode()) != manifest["identity_digest"]:
        _fail("LOCAL_SERVICE_RESULT_INVALID")
    question = _bounded(_question(request), MAX_BINDING_BYTES)
    binding = _bounded({"schema": "finweb.local_fictional.service_binding/1", "question": json.loads(question),
        "question_sha256": _sha(question), "context_snapshot_sha256": context.context_id,
        "generation": context.generation, "family": "CP5_DIVERSIFICATION", "engine_id": CP5_ENGINE_ID,
        "manifest_id": issued.manifest_id, "result_digest": issued.result_digest,
        "issued_sha256": _sha(raw), "synthetic": True,
        "release_id": context.port.release_id(), "source_registry_digest": manifest["valuation_manifest"]["source_registry_digest"],
        "consumed_identity_digest": manifest["identity_digest"], "f8b_policy": manifest["valuation_manifest"]["detection_policy"]}, MAX_BINDING_BYTES)
    return IssuedLocalServiceResult("CP5_DIVERSIFICATION", CP5_ENGINE_ID, raw, _sha(raw),
        issued.manifest_id, issued.result_digest, question, _sha(question), binding, _sha(binding))


def reproduce_local_service(conn, *, request, context, saved_issued_bytes, expected_issued_sha256):
    """Explicit reproduce only; archive read/exact retry must not call issuance."""
    if (type(saved_issued_bytes) is not bytes or len(saved_issued_bytes) > MAX_ISSUED_BYTES
            or type(expected_issued_sha256) is not str or _SHA.fullmatch(expected_issued_sha256) is None
            or _sha(saved_issued_bytes) != expected_issued_sha256):
        return LocalServiceReproduction("INPUT_MISMATCH", "stored issued bytes/hash differ")
    try:
        rerun = issue_local_service(conn, request=request, context=context)
    except LocalServiceRefusal as error:
        return LocalServiceReproduction("SOURCE_REFUSED", error.code)
    if rerun.issued_bytes != saved_issued_bytes:
        return LocalServiceReproduction("RESULT_DIFFERS", "complete canonical issued answer differs", rerun.issued_sha256)
    return LocalServiceReproduction("REPRODUCED", "", rerun.issued_sha256)
