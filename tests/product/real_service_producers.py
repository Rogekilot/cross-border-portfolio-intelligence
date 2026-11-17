"""The REAL PRODUCERS of the bytes the R3 seal checks. Not a test module.

R3 fix round (technical review H-1). The seal must accept what the services actually issue, so the tests no longer hand-write the issued
document: they CALL the services and seal what comes back.

  * Fictional branch: `financial_service_integration.issue_local_service` (F2's existing integration, unchanged), selector CP5_DIVERSIFICATION.
    It returns the CP5 Result bytes, the question bytes and the binding bytes. The inputs are the integration's own inline unit fixture
    (`test_financial_service_integration.fixture`), with the request re-addressed to the ids of the disposable database's world and the ledger
    connection replaced by one whose pin is the database's pin. The service reads that stub connection and nothing else; nothing of it is stored.
  * Real branch: `performance_service.compute_for_portfolio`, reached through the same integration's PERFORMANCE_SYNTHETIC_REFUSAL selector,
    which calls the unchanged performance service on the synthetic world and returns the refusal with the service's own `ComputationResult`
    bytes. This is the only real-branch service output that can exist before R8: the service refuses invented data (design fact 12, 4.4), so
    the bytes state `synthetic = true`, no release and no confirmation policy. They are sealed to be REFUSED by O4a (and by the two bindings that
    need a release and a policy); the accepted side is R8's.

Everything is invented. Nothing here marks invented data `synthetic = false`.
"""
from __future__ import annotations

import dataclasses
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import financial_service_integration as service  # noqa: E402
import test_financial_service_integration as unit  # noqa: E402
from performance_service import service as performance_service  # noqa: E402
from persistence import ledger_replay_store as replay, ledger_store  # noqa: E402

AS_OF = unit.DAY.isoformat()                      # the date of the integration's inline world


class PinnedConnection(unit.SourceOnlyConnection):
    """The integration's unit connection, with the ledger version and the event sequence numbers moved so that the last event's sequence IS `pin`
    (the disposable database's pin for the root). The events themselves are the unit fixture's."""

    def __init__(self, events, pin):
        super().__init__(events)
        self.pin = pin

    def execute(self, sql, params=None):
        if sql == replay.LEDGER_VERSION_SQL:
            self.calls.append(sql)
            return unit.Rows([(self.pin,)])
        if sql == replay.LOAD_EVENTS_SQL:
            self.calls.append(sql)
            # the last `pin` events when the database's pin is smaller than the unit fixture's event count (sequence numbers start at 1)
            events = self.events[-min(len(self.events), self.pin):]
            first = self.pin - len(events) + 1
            return unit.Rows([(first + i, *ledger_store.event_to_row(event)) for i, event in enumerate(events) if first + i <= params[1]])
        return super().execute(sql, params)


def service_constants():
    """(release_id, f8b policy digest) the integration's inline world issues: what a snapshot must carry for the seal's two bindings to hold."""
    _conn, context, _request, _inputs = unit.fixture()
    return context.port.release_id(), performance_service.policy_reference(context.policy)[0][1]


def _addressed(selector, *, owner, root, revision, operation, pin, generation):
    """The integration's unit world, re-addressed: the capital policy is scoped to the root (the integration checks it), so the context's
    fingerprint and id are those of THIS root's inputs, computed by the integration's own functions."""
    import hashlib
    conn, _context, request, inputs = unit.fixture()
    inputs = dict(inputs, capital_policy=dataclasses.replace(inputs["capital_policy"], portfolio_id=str(root)))
    snapshot = service.fingerprint_context_inputs(**inputs)
    context_id = hashlib.sha256(snapshot).hexdigest()
    pinned = PinnedConnection(conn.events, pin)
    context = service.LocalFictionalContext(pinned, 321, "777", context_id, generation, snapshot, **inputs)
    request = dataclasses.replace(request, selector=selector, owner_id=owner, root_id=root, portfolio_id=root, revision_id=revision,
                                  operation_id=operation, ledger_pin=pin, context_id=context_id, generation=generation)
    return pinned, context, request


def issue_fictional(*, owner, root, revision, operation, pin, generation=1):
    """The integration's `IssuedLocalServiceResult` for the CP5 selector (its bytes, its question, its binding)."""
    conn, context, request = _addressed(service.LocalServiceKind.CP5_DIVERSIFICATION, owner=owner, root=root, revision=revision,
                                        operation=operation, pin=pin, generation=generation)
    return service.issue_local_service(conn, request=request, context=context)


def issue_real_refusal(*, owner, root, revision, operation, pin, generation=1):
    """The performance service's `ComputationResult` bytes (as the integration returns them with its refusal) for the synthetic world."""
    conn, context, request = _addressed(service.LocalServiceKind.PERFORMANCE_SYNTHETIC_REFUSAL, owner=owner, root=root, revision=revision,
                                        operation=operation, pin=pin, generation=generation)
    try:
        service.issue_local_service(conn, request=request, context=context)
    except service.LocalServiceRefusal as refusal:
        assert refusal.code == performance_service.SYNTHETIC_MARKET_DATA_REFUSED
        return refusal.issued_bytes
    raise AssertionError("the performance service did not refuse the synthetic world")
