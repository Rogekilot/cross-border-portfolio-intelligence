"""F1 R5, PostgreSQL: the REAL branch's create code on INVENTED data (`TEST_SWITCH`), up to the service's refusal; and T-m, `read_release` through the
lease-checked functions (design 4.4, 2.6 item 6, PD-0069; FF1-C05, FF1-C08).

WHAT RUNS. The chain is the one R8 will run on real files, on an invented release: qualify, the loader projects the release, the candidate is
registered, the proposal is published, the bound candidate is registered (`test_postgres_real_qualification.QualifiedChainCase`). The PRODUCT create
then runs the real branch: admit, the guarded load of the link, the world built from the locked snapshot through the lease-checked `md_*` functions,
the staged root and ledger, and the ACTUAL performance service, which REFUSES invented data (`SYNTHETIC_MARKET_DATA_REFUSED`, design fact 12). The
refusal is never turned into a result or bypassed; the transaction rolls back whole and nothing is addressable (FF1-C08). The real branch cannot reach
a seal, a by-name firing or a COMMIT on invented data, so none of those is claimed here: they are "first run at R8" for the real branch, and "product
path, shared tail on SYNTHETIC_TEST" in `test_postgres_real_r5_tails`.

Labels: "product path, real branch to the service's refusal" is what these tests are. Nothing here is stored as `synthetic = false`.
"""
from __future__ import annotations

import sys
import time
import unittest.mock as mock
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402

import marketdata_exit_kit as x  # noqa: E402
from domain.currency import CurrencyCode  # noqa: E402
from domain.instrument import SecurityType  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from marketdata.resolver import InstrumentEntry  # noqa: E402
from performance.engine import performance_conventions  # noqa: E402
from persistence import market_data_store as mds, real_tails  # noqa: E402
from real_service import worlds as real_worlds  # noqa: E402
from real_service.service import ProvenanceLink, RealWorkspaceService  # noqa: E402
from real_gateway_kit import setUpModule, tearDownModule  # noqa: E402,F401
from real_r5_case import RecordingConnection, md_table_reads, rw_md_calls  # noqa: E402
from real_tools import candidates as cand  # noqa: E402
from test_postgres_real_qualification import QualifiedChainCase, TEST_SWITCH  # noqa: E402
from test_real_qualification import POLICY  # noqa: E402
from web_api import real_scoped_contract as contract  # noqa: E402

REAL_BRANCH = "product path, real branch to the service's refusal (invented data)"


class RealBranchCase(QualifiedChainCase):
    INSTALL = "r5real"
    W = 3

    def setUp(self):
        super().setUp()
        if self.count("md_release") == 0:                                  # the first test of the install runs the chain once
            self.load()
            self.register()
            published = self.publish_proposal()
            self.assertEqual((published.status, published.outcome), (0, "PUBLISHED"), published.text)
            self.register(financial_context=self.result.context_id)
        bound = cand.build_candidate(TEST_SWITCH, self.store, self.result, financial_context=self.result.context_id)
        self.link = ProvenanceLink(bound.context_sha256, bound.members, bound.witnesses)
        self.inputs = real_worlds.WorldInputs(self.ident, market11_conventions(self.world.built.calendars), performance_conventions(), POLICY)
        self.executor = self.conn("executor")
        self.service = RealWorkspaceService(self.s, executor_role=self.inst.roles["executor"], connect=lambda: self.inst.connect("executor"),
                                            world_inputs=self.inputs)
        self.user = uuid.uuid4()
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (self.user,))
        self.listing = self.ident.snapshot()[2][0].listing_id

    def intent(self, op=None, *, as_of="2026-01-05"):
        return {"schema_version": contract.CREATE_SCHEMA, "operation_id": str(op or uuid.uuid4()), "source_context_id": self.result.context_id,
                "expected_release_id": self.release_id, "name": "constructed probe", "reporting_currency": "USD", "as_of": as_of,
                "constructed_ledger_acknowledged": True,
                "opening_positions": [{"listing_id": str(self.listing), "quantity": "10", "cost_basis": None, "acquired_on": None}],
                "opening_cash": {"currency": "USD", "amount": "500"}}

    def root_of(self, body):
        from real_service.service import root_id_for
        return root_id_for(self.user, uuid.UUID(body["operation_id"]))

    def assertNothingAddressable(self, root):
        for table, where in (("portfolio", "portfolio_id=%s"), ("rw_root", "portfolio_id=%s"), ("rw_revision", "portfolio_id=%s"), ("account", "portfolio_id=%s"),
                             ("rw_root_link", "root_id=%s"), ("rw_lease", "root_id=%s"), ("rw_artifact", "root_id=%s"), ("rw_operation", "root_id=%s"),
                             ("rw_journal", "root_id=%s")):
            self.assertEqual(self.count(table, where, (root,)), 0, table)


class ServiceRefusalTests(RealBranchCase):
    INSTALL = "r5real1"

    def test_FF1_C08_the_actual_service_refuses_invented_data_and_everything_rolls_back(self):
        """product path, real branch to the service's refusal (invented data): the real branch up to the service's refusal. The ACTUAL performance service ran on the staged ledger and refused with
        SYNTHETIC_MARKET_DATA_REFUSED (every metric has no value); the create returns the definite refusal and the service's own bytes;
        nothing is addressable; the real branch reached no seal, no by-name firing and no COMMIT."""
        import json
        body = self.intent()
        recorder = RecordingConnection(self.executor)
        result = self.service.create(recorder, owner=self.user, body=body, generation=1, link=self.link)
        self.assertEqual((type(result).__name__, result.code), ("Refused", "SYNTHETIC_MARKET_DATA_REFUSED"), result)
        self.assertFalse(result.persisted)
        issued = json.loads(result.issued_bytes)                                       # the service's own refusal, not a number
        self.assertTrue(issued["manifest"]["synthetic"])
        self.assertTrue(issued["metrics"] and all(m["details"] and "SYNTHETIC_MARKET_DATA_REFUSED" in json.dumps(m["details"]) for m in issued["metrics"]))
        self.assertNothingAddressable(self.root_of(body))
        # the path really staged the economic rows before the service ran (so "nothing addressable" is a rollback, not an early exit) ...
        inserts = [s for s in recorder.statements if s.startswith("INSERT")]
        self.assertTrue(any("portfolio" in s for s in inserts) and any("rw_root" in s for s in inserts))
        self.assertGreaterEqual(len(recorder.matching("ledger_event")), 1)
        # ... and never reached the seal or the tail's firing
        self.assertEqual(recorder.matching("rw_seal"), [])
        self.assertEqual(recorder.set_constraints(), [])
        self.assertEqual(self.executor.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)

    def test_O7_an_unbuildable_claim_record_refuses_before_the_seal_and_rolls_back_whole(self):
        """product path, real branch to the service's refusal PATCHED OUT to reach the next gate (invented data; nothing is stored as `synthetic = false`, and a result that
        the service refused is never sealed). O-7, PD-0082 Q3: once the service has run, the create builds the claim block from exactly what the seal would store. The invented
        release's record builds (it is the `TEST_SWITCH` snapshot, which carries the synthetic origin), but the block it renders is refused at precondition P-7 (the stored origin is not a
        real source; TR-O7-L-1 corrected this: the cause is the block refusal, not a missing profile), so the create is refused with `RW_CLAIM_RECORD_REFUSED` inside its transaction:
        the economic rows were staged and rolled back, nothing is addressable, and the real branch reached no seal, no by-name firing and no COMMIT. The file rows
        the record copies are read through the lease-checked function (`rw_md_file`), never from a table, and equal the owner's own read of the release."""
        body = self.intent()
        recorder = RecordingConnection(self.executor)
        captured = {}
        original = real_worlds.read_claim_files

        def capture(conn, content):
            captured["files"] = original(conn, content)
            return captured["files"]
        with mock.patch.object(real_worlds, "service_refused", return_value=False), mock.patch.object(real_worlds, "read_claim_files", capture):
            result = self.service.create(recorder, owner=self.user, body=body, generation=1, link=self.link)
        self.assertEqual((type(result).__name__, result.code), ("Refused", "RW_CLAIM_RECORD_REFUSED"), result)
        self.assertTrue(result.detail.startswith("CLAIM_"), result.detail)                    # the render code, never public
        self.assertIn("CLAIM_PRECONDITION", result.detail)                                    # P-7: the TEST_SWITCH snapshot's origin is synthetic
        self.assertFalse(result.persisted)
        self.assertNothingAddressable(self.root_of(body))
        inserts = [s for s in recorder.statements if s.startswith("INSERT")]
        self.assertTrue(any("portfolio" in s for s in inserts) and any("rw_root" in s for s in inserts))
        self.assertGreaterEqual(len(recorder.matching("ledger_event")), 1)
        self.assertEqual(recorder.matching("rw_seal"), [])
        self.assertEqual(recorder.set_constraints(), [])
        self.assertEqual(self.executor.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)
        # the lease-checked file read: called by `read_release` and again for the record; no md_* table is read by the executor; parity with the owner's read
        self.assertGreaterEqual(len([s for s in rw_md_calls(recorder.statements) if "rw_md_file" in s]), 2)
        self.assertEqual(md_table_reads(recorder.statements), [])
        direct = mds.read_release_files(self.conn("owner"), self.release_id)
        self.assertTrue(direct)
        self.assertEqual(captured["files"], direct)
        self.assertTrue(all(row[2] in ("QUOTE", "FX", "CALENDAR", "IDENTITY", "CORPORATE_ACTION", "BENCHMARK", "RISK_FREE", "RESOLUTION_RECORD") for row in direct))

    def test_O7_a_held_claim_record_build_error_yields_to_the_services_own_refusal(self):
        """product path, real branch to the service's refusal (invented data): TR-O7-L-1. The claim record's build fails (the file read raises a render refusal) AND the actual
        service refuses the invented data. The create answers the SERVICE's refusal, SYNTHETIC_MARKET_DATA_REFUSED, with the service's own bytes, and not
        `RW_CLAIM_RECORD_REFUSED`: the build error is held until the service has run. Whole rollback, nothing addressable, no seal."""
        from marketdata.claim_render import ClaimRenderError
        body = self.intent()
        recorder = RecordingConnection(self.executor)
        with mock.patch.object(real_worlds, "read_claim_files", side_effect=ClaimRenderError("CLAIM_RECORD_MISSING", "held")):
            result = self.service.create(recorder, owner=self.user, body=body, generation=1, link=self.link)
        self.assertEqual((type(result).__name__, result.code), ("Refused", "SYNTHETIC_MARKET_DATA_REFUSED"), result)
        self.assertTrue(result.issued_bytes)
        self.assertFalse(result.persisted)
        self.assertNothingAddressable(self.root_of(body))
        self.assertEqual(recorder.matching("rw_seal"), [])
        self.assertEqual(self.executor.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)

    def test_O7_the_file_read_is_refused_outside_a_lease_and_the_executor_has_no_table_privilege(self):
        """product path, real branch to the service's refusal (invented data): the claim record's file read has the same two barriers as the release read: outside an open create or reproduce lease the
        function refuses (`RW_MD_READ_REFUSED`), and the executor's default-keyword read of the tables is refused by the database (42501)."""
        executor = self.conn("executor")
        executor.execute(f'SET search_path TO "{self.s}", pg_temp')
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            mds.read_release_files(executor, self.release_id, lease_checked=True)
        self.assertIn("RW_MD_READ_REFUSED", str(caught.exception))
        executor.rollback()
        executor.execute(f'SET search_path TO "{self.s}", pg_temp')
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            mds.read_release_files(executor, self.release_id)

    def test_FF1_C08_the_refusal_is_the_same_every_time_and_is_never_a_result(self):
        """product path, real branch to the service's refusal (invented data): a second, different operation is refused the same way; the service is not parameterised by the create."""
        first, second = self.intent(), self.intent()
        a = self.service.create(self.executor, owner=self.user, body=first, generation=1, link=self.link)
        b = self.service.create(self.executor, owner=self.user, body=second, generation=1, link=self.link)
        self.assertEqual((a.code, b.code), ("SYNTHETIC_MARKET_DATA_REFUSED", "SYNTHETIC_MARKET_DATA_REFUSED"))
        self.assertNothingAddressable(self.root_of(first))
        self.assertNothingAddressable(self.root_of(second))

    def test_FF1_C05_inputs_that_differ_from_the_snapshot_fail_before_any_economic_write(self):
        """product path, real branch to the service's refusal (invented data): the world's policy, then its identity registry, differ from the locked snapshot's. Each create is refused with
        RW_WORLD_DIFFERS naming the digest, with no INSERT sent and nothing left."""
        other_policy = real_worlds.WorldInputs(self.ident, self.inputs.market_conventions, self.inputs.perf_conventions,
                                               type(POLICY)(frozenset(("x.feed",)), frozenset(("x.filing",))))
        extra = x.identity()
        extra.register_instruments([InstrumentEntry("Extra Inc.", SecurityType.COMMON_STOCK, "XNYS", "NYSE", "EXTRA", CurrencyCode("USD"))])
        other_identity = real_worlds.WorldInputs(extra, self.inputs.market_conventions, self.inputs.perf_conventions, POLICY)
        for label, inputs, field in (("policy", other_policy, "f8b_policy_digest"), ("identity", other_identity, "identity_digest")):
            with self.subTest(label):
                service = RealWorkspaceService(self.s, executor_role=self.inst.roles["executor"], connect=lambda: self.inst.connect("executor"),
                                               world_inputs=inputs)
                body = self.intent()
                recorder = RecordingConnection(self.executor)
                result = service.create(recorder, owner=self.user, body=body, generation=1, link=self.link)
                self.assertEqual((type(result).__name__, result.code, result.detail), ("Refused", "RW_WORLD_DIFFERS", field), result)
                self.assertEqual([s for s in recorder.statements if s.startswith("INSERT")], [])
                self.assertNothingAddressable(self.root_of(body))

    def test_reads_on_a_real_branch_context_find_no_operation_first_run_at_R8(self):
        """product path, real branch to the service's refusal (invented data): no real-branch root can exist before R8, so a read and a reproduce find nothing and the list is empty. The real
        branch's own reads of a committed root are first run at R8."""
        body = self.intent()
        self.service.create(self.executor, owner=self.user, body=body, generation=1, link=self.link)
        root = self.root_of(body)
        read = self.service.archive_read(self.conn("executor"), owner=self.user, root=root, operation_id=uuid.UUID(body["operation_id"]),
                                         context_id=self.result.context_id, generation=1)
        self.assertEqual((type(read).__name__, read.code), ("Refused", "RW_NOT_FOUND"))
        again = self.service.reproduce(self.conn("executor"), owner=self.user, root=root, operation_id=uuid.UUID(body["operation_id"]),
                                       context_id=self.result.context_id, generation=1)
        self.assertEqual((type(again).__name__, again.code), ("Refused", "RW_NOT_FOUND"))
        self.assertEqual(self.service.list_roots(self.conn("executor"), owner=self.user).value, [])


class ReadReleaseThroughTheFunctionsTests(RealBranchCase):
    INSTALL = "r5real2"

    def test_T_m_parity_with_a_direct_read_refusal_after_complete_by_and_a_non_vacuous_recorder(self):
        """product path, real branch to the service's refusal (invented data) (T-m, PD-0069): through the product's own create path on an invented release of a TEST install, `read_release` is called
        with `lease_checked=True` on the executor's connection under an admitted EXECUTE_CREATE lease of the real branch. The port it returns has
        the projection digest and the contents of a direct read of the same release by the owner role (parity). The recorder sees `rw_md_*` calls
        and no statement that reads an `md_*` table. It is NOT vacuous: it sees at least one `rw_md_*` call; a control reads the same release as
        the owner with the default keyword on the same kind of recorder and MUST see the `md_*` reads (so a matcher that cannot read a
        schema-qualified quoted name fails); and the executor's own default-keyword read is refused by the database (42501)."""
        captured = {}
        original = real_worlds.build_real_world

        def capture(*args, **kw):
            captured["world"] = original(*args, **kw)
            return captured["world"]
        recorder = RecordingConnection(self.executor)
        with mock.patch.object(real_worlds, "build_real_world", capture):
            result = self.service.create(recorder, owner=self.user, body=self.intent(), generation=1, link=self.link)
        self.assertEqual(result.code, "SYNTHETIC_MARKET_DATA_REFUSED")                    # the create read the release and the service refused
        calls = rw_md_calls(recorder.statements)
        self.assertGreaterEqual(len(calls), 1, "the recorder saw no rw_md_* call: it would pass vacuously")
        self.assertEqual(md_table_reads(recorder.statements), [])
        # control: the owner role with the default keyword reads the tables, and the matcher sees them
        owner_conn = self.conn("owner")
        owner_recorder = RecordingConnection(owner_conn)
        direct = mds.read_release(owner_recorder, self.release_id, self.ident.exchange_mic, registry=self.store.load_registry())
        self.assertGreaterEqual(len(md_table_reads(owner_recorder.statements)), 1, "the control saw no md_* read: the matcher cannot read a qualified name")
        self.assertEqual(rw_md_calls(owner_recorder.statements), [])
        # parity
        port = captured["world"].port
        self.assertEqual(port.projection_digest(), direct.projection_digest())
        self.assertEqual(port.projection_digest(), self.snapshot["projection_digest"])
        self.assertEqual(port.export(), direct.export())
        self.assertEqual(port.release, direct.release)
        # the database's barrier: the executor has no privilege on the tables, so the default keyword is refused as the executor
        bare = self.conn("executor")
        bare.execute(f'SET search_path TO "{self.s}", pg_temp')
        with self.assertRaises(psycopg.errors.InsufficientPrivilege):
            mds.read_release(bare, self.release_id, self.ident.exchange_mic, registry=self.store.load_registry())

    def test_T_m_the_same_call_after_complete_by_is_refused_with_the_functions_code_and_whole_rollback(self):
        """product path, real branch to the service's refusal (invented data) (T-m): the lease-checked read after `complete_by` (the session's timeouts are 0) is refused with RW_MD_READ_REFUSED and
        is classified a typed refusal with whole rollback, not a write-rule error and not UNKNOWN."""
        original = real_worlds.build_real_world

        def late(*args, **kw):
            time.sleep(self.W + 1.0)
            return original(*args, **kw)
        body = self.intent()
        executor = self.conn("executor", options=self.stall_options())
        with mock.patch.object(real_worlds, "build_real_world", late):
            result = self.service.create(executor, owner=self.user, body=body, generation=1, link=self.link)
        self.assertEqual((type(result).__name__, result.code, result.detail), ("Refused", "RW_MD_READ_REFUSED", "DEADLINE"), result)
        self.assertNothingAddressable(self.root_of(body))
        self.assertEqual(executor.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)

    def test_T_m_control_the_same_path_without_the_delay_reads_the_release(self):
        """product path, real branch to the service's refusal (invented data) (T-m control): without the delay the read succeeds (the refusal above is the deadline's, nothing else)."""
        executor = self.conn("executor", options=self.stall_options())
        result = self.service.create(executor, owner=self.user, body=self.intent(), generation=1, link=self.link)
        self.assertEqual(result.code, "SYNTHETIC_MARKET_DATA_REFUSED")


class ProjectionRecomputeStillRunsTests(RealBranchCase):
    INSTALL = "r5real3"

    def test_a_changed_stored_row_fails_the_projection_recompute_on_the_executors_path(self):
        """E11 crafted probe, not product evidence (FR-L1 (a)): the owner role, with the table triggers disabled for this crafted edit in its own
        disposable database, changes one stored price. The executor's lease-checked read still recomputes the projection digest from the rows it
        read and refuses (a typed refusal with whole rollback); the control above (T-m) reads the unedited release."""
        with self.owner.transaction():
            self.owner.execute(f"ALTER TABLE {self.s}.md_quote DISABLE TRIGGER USER")
            try:
                self.owner.execute(f"UPDATE {self.s}.md_quote SET price=price+1 WHERE release_id=%s", (self.release_id,))
            finally:
                self.owner.execute(f"ALTER TABLE {self.s}.md_quote ENABLE TRIGGER USER")
        body = self.intent()
        result = self.service.create(self.executor, owner=self.user, body=body, generation=1, link=self.link)
        self.assertEqual((type(result).__name__, result.code, result.detail), ("Refused", "RW_RELEASE_REFUSED", "ProjectionDigestMismatchError"), result)
        self.assertNothingAddressable(self.root_of(body))


class FileListCheckStillRunsTests(RealBranchCase):
    INSTALL = "r5real4"

    def test_a_release_whose_file_rows_are_not_its_file_list_is_refused_on_the_executors_path(self):
        """E11 crafted probe, not product evidence (FR-L1 (a)): the owner role moves one file row of the release to another position (triggers
        disabled for this crafted edit; a deleted row is blocked by the quote rows' foreign key). The executor's lease-checked read still compares
        the release content's file list with the file rows and refuses."""
        with self.owner.transaction():
            self.owner.execute(f"ALTER TABLE {self.s}.md_release_file DISABLE TRIGGER USER")
            try:
                self.owner.execute(f"UPDATE {self.s}.md_release_file SET ordinal=99 WHERE ctid IN "
                                   f"(SELECT ctid FROM {self.s}.md_release_file WHERE release_id=%s ORDER BY ordinal LIMIT 1)", (self.release_id,))
            finally:
                self.owner.execute(f"ALTER TABLE {self.s}.md_release_file ENABLE TRIGGER USER")
        body = self.intent()
        result = self.service.create(self.executor, owner=self.user, body=body, generation=1, link=self.link)
        self.assertEqual((type(result).__name__, result.code), ("Refused", "RW_RELEASE_REFUSED"), result)
        self.assertEqual(result.detail, "ReleaseKeyMismatchError")
        self.assertNothingAddressable(self.root_of(body))


if __name__ == "__main__":
    import unittest
    unittest.main()
