"""New inline fictional service tests; execution requires the frozen F2 runner."""
import dataclasses
import datetime as dt
import hashlib
import json
import unittest
import uuid
from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace

import financial_service_integration as service
from corporate_actions_service.split_confirmation import ConfirmationPolicy
from diversification.contracts import CapitalUniverseChoice
from diversification_service.service import compute_diversification_for_portfolio
from domain.currency import CurrencyCode, Money
from domain.instrument import SecurityType
from domain.ledger import EventType, LedgerEvent
from marketdata.calendars import CalendarSet
from marketdata.contracts import (AdjustmentStatus, CalendarDays, CalendarKind,
    DataDelayStatus, Lineage, QuoteObservation, SourceReading, SourceTiming, UsageScope)
from marketdata.manifest import MarketDataRelease, SourceRecord
from marketdata.market11 import market11_conventions
from marketdata.resolver import InMemoryIdentityRegistry, InstrumentEntry
from marketdata.store import InMemoryMarketData
from performance.engine import performance_conventions
from performance.periods import WindowRule, WindowSpec
from persistence import ledger_replay_store as replay, ledger_store
from risk_service.service import PORTFOLIO_CURRENCY_SQL, RiskRefusal

DAY = dt.date(2026, 1, 5)
USD = CurrencyCode("USD")
OWNER, ROOT, ACCOUNT, REVISION, OP = (uuid.UUID(int=i) for i in range(1, 6))
SOURCE = "f2.inline.unit.quotes"
QUOTE_SHA = hashlib.sha256(b"NEW_INLINE_F2_PRICE_10_UNIT_ONLY").hexdigest()
CAL_SHA = hashlib.sha256(b"NEW_INLINE_F2_UNIT_CALENDAR").hexdigest()


class Rows:
    def __init__(self, values):
        self.values = values
    def fetchone(self):
        return self.values[0] if self.values else None
    def fetchall(self):
        return list(self.values)


class SourceOnlyConnection:
    """Unit SQL reader only; actual PG chain is the separately owned core target."""
    def __init__(self, events):
        self.events = events
        self.info = SimpleNamespace(transaction_status=2)
        self.calls = []
    def execute(self, sql, params=None):
        self.calls.append(sql)
        if sql == service._TX_STATE_SQL:
            return Rows([(321, "777")])
        if sql == PORTFOLIO_CURRENCY_SQL:
            return Rows([("USD",)])
        if sql == replay.PORTFOLIO_EXISTS_SQL:
            return Rows([(1,)])
        if sql == replay.LEDGER_VERSION_SQL:
            return Rows([(len(self.events),)])
        if sql == replay.LOAD_EVENTS_SQL:
            return Rows([(i + 1, *ledger_store.event_to_row(event)) for i, event in enumerate(self.events) if i + 1 <= params[1]])
        raise AssertionError("Unit fixture unexpectedly requested SQL: " + sql)


def fixture():
    """Not the integration World100 fixture; independent exact40 arithmetic."""
    ids = iter(uuid.UUID(int=i) for i in range(100, 110))
    resolver = InMemoryIdentityRegistry(lambda: next(ids))
    (registration,) = resolver.register_instruments((InstrumentEntry(
        "F2 newly invented issuer", SecurityType.COMMON_STOCK, "XNYS", "NYSE", "F2-SYN-UNIT", USD),))
    listing = registration.listing_id
    def lineage(digest):
        return Lineage("new F2 inline unit", AdjustmentStatus.RAW, source_id=SOURCE,
            file_sha256=digest, adapter_id="f2.inline.unit", adapter_version="1",
            source_record_ref="unit", retrieved_at=dt.datetime(2026, 1, 5, tzinfo=dt.timezone.utc),
            usage_scope=UsageScope.SYNTHETIC_TEST, upstream="new inline fictional unit", independence_group=SOURCE,
            market="US")
    calendar = CalendarDays("F2-UNIT-CAL", CalendarKind.EXCHANGE_SESSIONS, ("XNYS",), "America/New_York",
        DAY, DAY, (DAY,), DAY, "new inline invented session", "F2 test", DAY, "1", lineage(CAL_SHA),
        default_close=dt.time(16))
    market = market11_conventions(CalendarSet((calendar,)))
    observation = QuoteObservation(listing, DAY, Decimal("10"), USD,
        SourceTiming(delay_status=DataDelayStatus.END_OF_DAY), lineage(QUOTE_SHA), volume=Decimal("1"))
    port = InMemoryMarketData(MarketDataRelease("new F2 UNIT_ONLY", tuple(sorted((CAL_SHA, QUOTE_SHA))), (SOURCE,), created_for="F2 unit only"),
        (SourceReading(SOURCE, SOURCE, QUOTE_SHA, observation),), exchange_of=resolver.exchange_mic,
        contains_synthetic=True, source_records=(SourceRecord(SOURCE, "F2 unit", "fictional unit", SOURCE, synthetic=True),))
    policy = ConfirmationPolicy(frozenset(("f2.feed",)), frozenset(("f2.filing",)))
    candidate = CapitalUniverseChoice("FULL_NAV", "SYNTHETIC_CANDIDATE", "new inline unit denominator",
        decision_id="F2-UNIT-POLICY", scope_kind="PORTFOLIO", portfolio_id=str(ROOT))
    events = (LedgerEvent(uuid.UUID(int=20), ACCOUNT, EventType.OPENING_POSITION, DAY, USD,
        listing_id=listing, quantity=Decimal("2"), source_reference="F2 inline unit security"),
        LedgerEvent(uuid.UUID(int=21), ACCOUNT, EventType.OPENING_CASH, DAY, USD,
        amount=Money(Decimal("20"), USD), source_reference="F2 inline unit cash"))
    conn = SourceOnlyConnection(events)
    inputs = dict(port=port, resolver=resolver, market_conventions=market, conventions=performance_conventions(),
        policy=policy, as_of=DAY, capital_policy=candidate, request=WindowSpec(WindowRule.SINCE_INCEPTION))
    snapshot = service.fingerprint_context_inputs(**inputs)
    context_id = hashlib.sha256(snapshot).hexdigest()
    context = service.LocalFictionalContext(conn, 321, "777", context_id, 1, snapshot, **inputs)
    request = service.LocalServiceRequest(service.LocalServiceKind.CP5_DIVERSIFICATION, OWNER, ROOT, REVISION, OP,
        ROOT, 2, DAY, context_id, 1)
    return conn, context, request, inputs


class LocalFinancialServiceTests(unittest.TestCase):
    def test_actual_cp5_issued_metrics_keep_independent_exact_unit_arithmetic(self):
        conn, context, request, _ = fixture()
        issued = service.issue_local_service(conn, request=request, context=context)
        obj = json.loads(issued.issued_bytes)
        metrics = {(m["metric_id"], tuple(m["subject"])): m for m in obj["metrics"]}
        for name, expected in (("largest_position_weight", "1/2"), ("largest_security_weight", "1/2"),
                               ("top5_concentration", "1/1"), ("hhi_concentration", "1/2"), ("effective_positions", "2/1")):
            self.assertEqual(metrics[name, ()]["exact"], expected)
        self.assertTrue(obj["manifest"]["synthetic"])
        self.assertEqual(obj["manifest"]["valuation_manifest"]["split_detection"], "F8B_DRY_RUN")
        self.assertEqual(hashlib.sha256(issued.issued_bytes).hexdigest(), issued.issued_sha256)

    def test_default_existing_cp5_service_still_refuses_synthetic(self):
        conn, context, request, _ = fixture()
        refused = compute_diversification_for_portfolio(conn, ROOT, DAY, context.port, context.resolver,
            context.market_conventions, context.conventions, policy=context.policy, metadata=None,
            capital_policy=context.capital_policy, ledger_version=2)
        self.assertIsInstance(refused, RiskRefusal)
        self.assertEqual(refused.code, "SYNTHETIC_MARKET_DATA_REFUSED")

    def test_actual_performance_refusal_preserves_unmodified_issued_no_number_bytes(self):
        conn, context, request, _ = fixture()
        request = dataclasses.replace(request, selector=service.LocalServiceKind.PERFORMANCE_SYNTHETIC_REFUSAL)
        with self.assertRaises(service.LocalServiceRefusal) as caught:
            service.issue_local_service(conn, request=request, context=context)
        refusal = caught.exception
        self.assertEqual(refusal.code, "SYNTHETIC_MARKET_DATA_REFUSED")
        self.assertEqual(refusal.issued_bytes, refusal.issued_result.canonical_json().encode())
        self.assertEqual(json.loads(refusal.issued_bytes)["manifest"]["detection_policy"], [])
        self.assertIsNone(json.loads(refusal.issued_bytes)["manifest"]["release_id"])
        self.assertEqual(json.loads(refusal.issued_bytes)["manifest"]["data_set_refs"], [])
        self.assertTrue(all(m.result.value is None for m in refusal.issued_result.metrics))
        self.assertNotIn("persisted", json.loads(refusal.issued_bytes))

    def test_wrong_connection_or_transaction_is_refused_before_service(self):
        conn, context, request, _ = fixture()
        with self.assertRaises(service.LocalServiceError):
            service.issue_local_service(SourceOnlyConnection(conn.events), request=request, context=context)
        conn.info.transaction_status = 0
        with self.assertRaisesRegex(service.LocalServiceError, "TRANSACTION_REQUIRED"):
            service.issue_local_service(conn, request=request, context=context)

    def test_context_snapshot_change_detects_live_quote_index_not_just_original_export(self):
        conn, context, request, _ = fixture()
        context.port._quotes.clear()
        with self.assertRaisesRegex(service.LocalServiceError, "CONTEXT_BINDING_DIFFERS"):
            service.issue_local_service(conn, request=request, context=context)

    def test_unknown_or_false_synthetic_marker_refuses(self):
        _, context, _, inputs = fixture()
        context.port._synthetic = False
        with self.assertRaisesRegex(service.LocalServiceError, "NOT_FICTIONAL"):
            service.fingerprint_context_inputs(**inputs)

    def test_mismatched_head_scope_and_strict_request_types_refuse(self):
        conn, context, request, _ = fixture()
        for change in ({"generation": 2}, {"as_of": DAY + dt.timedelta(days=1)}, {"context_id": "0" * 64}):
            with self.assertRaises(service.LocalServiceError):
                service.issue_local_service(conn, request=dataclasses.replace(request, **change), context=context)
        for change in ({"ledger_pin": True}, {"generation": True}, {"selector": "CP5_DIVERSIFICATION"}, {"root_id": uuid.UUID(int=99)}):
            with self.assertRaises(service.LocalServiceError):
                dataclasses.replace(request, **change)

    def test_full_canonical_reproduction_and_invalid_saved_hash(self):
        conn, context, request, _ = fixture()
        issued = service.issue_local_service(conn, request=request, context=context)
        self.assertEqual(service.reproduce_local_service(conn, request=request, context=context,
            saved_issued_bytes=issued.issued_bytes, expected_issued_sha256=issued.issued_sha256).status, "REPRODUCED")
        self.assertEqual(service.reproduce_local_service(conn, request=request, context=context,
            saved_issued_bytes=issued.issued_bytes, expected_issued_sha256="0" * 64).status, "INPUT_MISMATCH")
        changed = issued.issued_bytes + b" "
        self.assertEqual(service.reproduce_local_service(conn, request=request, context=context,
            saved_issued_bytes=changed, expected_issued_sha256=hashlib.sha256(changed).hexdigest()).status, "RESULT_DIFFERS")

    def test_output_bound_refuses_entire_generated_bytes(self):
        with self.assertRaisesRegex(service.LocalServiceError, "OUTPUT_LIMIT"):
            service._bounded({"invented": "x" * 100}, 16)

    def test_mutating_resolver_and_calendar_state_changes_actual_fingerprint(self):
        _, context, _, inputs = fixture()
        before = context.snapshot_bytes
        context.resolver._listings.clear()
        with self.assertRaises(service.LocalServiceError):
            service.fingerprint_context_inputs(**inputs)
        _, context, _, inputs = fixture()
        context.market_conventions.freshness.calendars._by_key.clear()
        self.assertNotEqual(service.fingerprint_context_inputs(**inputs), before)

    def test_full_payload_hashes_are_distinct_definitions_and_bound_to_question(self):
        conn, context, request, _ = fixture()
        issued = service.issue_local_service(conn, request=request, context=context)
        binding = json.loads(issued.binding_bytes)
        self.assertEqual(binding["question_sha256"], hashlib.sha256(issued.question_bytes).hexdigest())
        self.assertEqual(binding["question"]["root_id"], str(ROOT))
        self.assertEqual(binding["question"]["ledger_pin"], "2")
        self.assertEqual(binding["context_snapshot_sha256"], context.context_id)
        self.assertNotEqual(issued.manifest_id, issued.result_digest)
        self.assertNotEqual(issued.result_digest, issued.issued_sha256)

    def test_no_arbitrary_selector_callback_or_unknown_serializable_class(self):
        class Arbitrary:
            def to_json(self):
                raise AssertionError("arbitrary serializer must never run")
        with self.assertRaisesRegex(service.LocalServiceError, "CONTEXT_TYPE"):
            service._semantic(Arbitrary())
        self.assertEqual(tuple(k.value for k in service.LocalServiceKind),
            ("CP5_DIVERSIFICATION", "PERFORMANCE_SYNTHETIC_REFUSAL"))
