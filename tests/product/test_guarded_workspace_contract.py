"""Local boundary contracts; substantive database behavior has separate PG cases."""
import dataclasses
import hashlib
import json
import unittest
import uuid
from types import SimpleNamespace

from psycopg.pq import TransactionStatus
from persistence.guarded_workspace_context import GuardedWorkspaceError, identifier, require_idle, validate_domain_constraints
from persistence.guarded_workspace_store import (CommittedWorkspaceResult, UnknownWorkspaceResult,
    RefusedWorkspaceResult, GuardedWorkspaceStore, root_id_for)
from financial_service_integration import LocalServiceKind


class GuardedWorkspaceContractTests(unittest.TestCase):
    def test_identifier_refuses_substitution_and_nontext(self):
        self.assertEqual(identifier("f2_schema"), "f2_schema")
        for value in (None, 1, "public;select", "../old", "A", "a" * 64):
            with self.subTest(value=value), self.assertRaises(GuardedWorkspaceError):
                identifier(value)

    def test_public_edge_requires_actual_idle_status(self):
        for state in TransactionStatus:
            conn = SimpleNamespace(info=SimpleNamespace(transaction_status=state), autocommit=True)
            if state == TransactionStatus.IDLE:
                require_idle(conn)
            else:
                with self.subTest(state=state), self.assertRaises(GuardedWorkspaceError):
                    require_idle(conn)

    def test_scope_seam_rejects_caller_boolean_before_sql(self):
        for scope in (None, True, {"admitted": True}, object()):
            with self.subTest(scope=type(scope).__name__), self.assertRaises(GuardedWorkspaceError):
                validate_domain_constraints(None, scope)

    def test_root_namespace_is_deterministic_owner_scoped(self):
        owner, other, op = uuid.UUID(int=1), uuid.UUID(int=2), uuid.UUID(int=3)
        self.assertEqual(root_id_for(owner, op), root_id_for(owner, op))
        self.assertNotEqual(root_id_for(owner, op), root_id_for(other, op))
        with self.assertRaises(GuardedWorkspaceError):
            root_id_for(str(owner), op)
        core = object.__new__(GuardedWorkspaceStore)
        body = {"name": "identity encoding only"}
        expected = {"schema": "finweb.f2.fictional-command/1", "owner_id": "00000000-0000-0000-0000-000000000001",
            "root_id": "00000000-0000-0000-0000-000000000002", "operation_id": "00000000-0000-0000-0000-000000000003",
            "kind": "CREATE", "selector": "CP5_DIVERSIFICATION", "body": body}
        exact = json.dumps(expected, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        self.assertEqual(core._command(owner, other, op, "CREATE", body, LocalServiceKind.CP5_DIVERSIFICATION, None), hashlib.sha256(exact).hexdigest())
        with self.assertRaises(GuardedWorkspaceError):
            core._command(str(owner), other, op, "CREATE", body, LocalServiceKind.CP5_DIVERSIFICATION, None)

    def test_unknown_has_no_staged_numeric_or_zero_write_assertion(self):
        value = UnknownWorkspaceResult(uuid.UUID(int=3))
        self.assertEqual({f.name for f in dataclasses.fields(value)}, {"operation_id", "disposition"})
        self.assertEqual(value.disposition, "UNKNOWN")

    def test_result_dispositions_are_immutable_and_explicit(self):
        refused = RefusedWorkspaceResult("ACTUAL_REFUSAL", b"{}")
        self.assertFalse(refused.persisted)
        self.assertEqual(refused.economic_writes, 0)
        result = CommittedWorkspaceResult(uuid.UUID(int=1), uuid.UUID(int=2), b"{}", "a" * 64, b"{}", "a" * 64)
        self.assertTrue(result.synthetic)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            result.persisted = False
