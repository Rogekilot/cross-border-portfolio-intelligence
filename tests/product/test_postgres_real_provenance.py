"""F1 R2, PostgreSQL: the real gateway's candidate registry (N2a generalised), the guarded load, and publish's consultation of the origin
validators (design 3.2, 3.3, 4.2). Opt-in like every database test here; without a provisioning superuser the tests SKIP with the reason.

What is product code and what is crafted (E11):
  * product: the installer (kind TEST), the scope factory, the publisher tool, admit, the loader's store (`register`, `load_context`,
    `reconcile`), the executor's `load_guarded`, the registry and gateway SQL;
  * E11 crafted, never product evidence, all in DISPOSABLE databases: a root row, the kit's `kind="REAL"` install, the owner role replacing
    a function to show wiring, and the owner role's ALTER ROLE LOGIN/NOLOGIN (the owner's procedure of PD-0070 decision 1).
Everything stored is invented. Candidates of the test scopes carry synthetic sources and no attestation. The REAL-scope bytes are the
relabelled bytes of a test snapshot, which a REAL install never stores (the predicates refuse them).
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

import real_gateway_fixtures as fx  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from persistence import real_provenance as rp, real_provenance_store as provstore, real_scope, real_workspace_store as store  # noqa: E402
from persistence.real_provenance import O1, O2, O3, ProvenanceError, origin_report  # noqa: E402

OM = "RW_ORIGIN_MISMATCH"          # R3: the origin-label code; the relabelled real-scope bytes below carry synthetic labels
from real_gateway_kit import KIT, PURPOSES, begin, commit, rollback, setUpModule, tearDownModule  # noqa: E402,F401
from real_provenance_case import ProvCase, scope_of  # noqa: E402
from real_provenance_fixtures import PAYLOAD, SOURCE_ID, candidate, encode, h, source_record, with_context, with_manifest_fields, with_members  # noqa: E402

TEST_SCOPES = ("SYNTHETIC_TEST", "TEST_SWITCH")
PERMITTING = {"checked_by": "invented-checker", "checked_on": "2001-02-03", "permits_internal_development_use": True, "notes": "invented"}


# =====================================================================================================================
# N2a regression, both test scopes
# =====================================================================================================================
class N2aRegression:
    """N2a's PostgreSQL groups p01 to p06 re-run on the real registry. The mixin is run once per test scope."""
    SCOPE = "SYNTHETIC_TEST"

    def cand(self, payload=PAYLOAD, acquisitions=(1,), **kw):
        return candidate(payload, acquisitions, scope=self.SCOPE, salt=self.tag("n2a"), **kw)

    def test_p01_durable_original_and_empty_fresh_load(self):
        native = self.rows(native=True)
        for payload in (PAYLOAD, b""):
            cand = self.cand(payload)
            _, saved = self.save(cand)
            self.assertIsInstance(saved, provstore.CommittedRegistration)
            loaded = self.load(cand)
            self.assertEqual(loaded.bundle, cand.bundle)
            self.assertEqual((loaded.scope, loaded.state, loaded.promotable, loaded.source_admitted), (self.SCOPE, "INTEGRITY_BOUND_NOT_ADMITTED", False, False))
        self.assertEqual(self.rows(native=True), native)               # registering writes nothing to the gateway or the market-data tables

    def test_p02_two_acquisitions_preserved_and_exact_replay_counts(self):
        native = self.rows(native=True)
        old, both = self.cand(acquisitions=(1,)), self.cand(acquisitions=(1, 2))
        self.save(old)
        op, saved = self.save(both)
        self.assertIsInstance(saved, provstore.CommittedRegistration)
        before = self.rows()
        _, replay = self.save(both, op)
        self.assertEqual(replay, saved)
        self.assertEqual(self.rows(), before)                          # an exact replay adds no row
        self.assertEqual(self.load(old).bundle, old.bundle)
        self.assertEqual(self.load(both).bundle, both.bundle)
        counts = json.loads(saved.response_bytes)
        self.assertEqual((counts["payload_count"], counts["manifest_count"], counts["envelope_count"], counts["member_count"]), (1, 2, 2, 2))
        self.assertEqual(self.rows(native=True), native)

    def test_p03_conflict_missing_and_bad_selectors_have_no_partial_rows(self):
        first, other = self.cand(), self.cand(acquisitions=(2,))
        op, result = self.save(first)
        self.assertIsInstance(result, provstore.CommittedRegistration)
        before, native = self.rows(), self.rows(native=True)
        # JSON null is SQL NULL under ->>: direct SQL must reject a null schema too, before any partial bundle row.
        bad = json.loads(first.bundle.context_bytes)
        bad["schema"] = None
        bad_cand = replace(first, bundle=replace(first.bundle, context_bytes=encode(bad)))
        self.database_code(lambda: self.put_sql(self.loader, bad_cand), "RW_PROV_UNSUPPORTED")
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.error_of(lambda: self.save(other, op)).code, "RW_PROV_OPERATION_CONFLICT")
        self.assertEqual(self.error_of(lambda: self.registry.load_context(scope_of(self.SCOPE), h(b"absent context"), expected_members=first.members,
                                                                         witnesses=first.witnesses)).code, "RW_PROV_INPUT_MISSING")
        for args in ((None, None), (first.context_sha256, op), ("invalid", None)):
            self.database_code(lambda a=args: self.get_sql(self.loader, *a), "RW_PROV_SHAPE")
        self.assertEqual(self.rows(), before)
        self.assertEqual(self.rows(native=True), native)

    def test_p04_a_precommit_fault_rolls_back_and_a_postcommit_ack_loss_is_unknown(self):
        """E4 (design 3.1): before the commit point a fault on a usable IDLE connection is a definite rollback; at or after it every fault
        that is not a gateway code on an IDLE connection is UNKNOWN. The identical command (the operation id) reconciles. Nothing retries."""
        cand = self.cand(acquisitions=(3,))
        before, native = self.rows(), self.rows(native=True)
        roles = dict(loader_role=self.inst.roles["loader"])

        class PreCommitFault(provstore.RealProvenanceStore):
            def _before_commit(self):
                raise psycopg.OperationalError("labelled precommit fault")

        failed = uuid.uuid4()
        refused = self.error_of(lambda: self.save(cand, failed, registry=PreCommitFault(self.loader, self.s, **roles)))
        self.assertEqual(refused.code, "RW_STATEMENT_FAILED")          # rolled back: the connection is IDLE and usable, so this is definite
        self.assertEqual(self.rows(), before)
        self.assertIsInstance(self.recover(failed, cand), provstore.UnknownRegistration)

        class PostCommitFault(provstore.RealProvenanceStore):
            def _after_commit(self):
                raise psycopg.OperationalError("labelled postcommit fault")

        committed = uuid.uuid4()
        _, unknown = self.save(cand, committed, registry=PostCommitFault(self.loader, self.s, **roles))
        self.assertIsInstance(unknown, provstore.UnknownRegistration)
        original = self.recover(committed, cand)
        self.assertIsInstance(original, provstore.CommittedRegistration)
        self.assertEqual(original.response_bytes, self.recover(committed, cand).response_bytes)
        self.assertEqual(self.rows(native=True), native)

    def test_p04b_after_the_commit_point_only_a_gateway_code_on_an_idle_connection_is_a_refusal(self):
        cand = self.cand(acquisitions=(4,))
        roles = dict(loader_role=self.inst.roles["loader"])
        cases = {"a non-gateway database error": psycopg.errors.UniqueViolation("labelled"),
                 "a lock timeout": psycopg.errors.LockNotAvailable("labelled"),
                 "a deadlock": psycopg.errors.DeadlockDetected("labelled"),
                 "a driver error": psycopg.OperationalError("labelled")}
        for label, fault in cases.items():
            class AtCommit(provstore.RealProvenanceStore):
                def _after_commit(self, fault=fault):
                    raise fault
            _, result = self.save(cand, uuid.uuid4(), registry=AtCommit(self.loader, self.s, **roles))
            self.assertIsInstance(result, provstore.UnknownRegistration, label)

        class GatewayCodeAtCommit(provstore.RealProvenanceStore):
            def _after_commit(self):
                # A real gateway refusal (RW_PROV_SHAPE) on the IDLE connection after the COMMIT.
                self.conn.execute(f"SELECT * FROM {self.schema}.rwp_get_context(NULL,NULL)")
        op = uuid.uuid4()
        refusal = self.error_of(lambda: self.save(cand, op, registry=GatewayCodeAtCommit(self.loader, self.s, **roles)))
        self.assertEqual(refusal.code, "RW_PROV_SHAPE")                # the rule is by classification, not by what was stored:
        self.assertIsInstance(self.recover(op, cand), provstore.CommittedRegistration)         # the registration is in fact stored

    def test_p04c_a_killed_connection_before_the_commit_is_unknown_and_nothing_remains(self):
        cand = self.cand(acquisitions=(5,))
        before = self.rows()
        admin = self.admin
        roles = dict(loader_role=self.inst.roles["loader"])

        class Killed(provstore.RealProvenanceStore):
            def _before_commit(self):
                pid = self.conn.execute("SELECT pg_backend_pid()").fetchone()[0]
                admin.execute("SELECT pg_terminate_backend(%s)", (pid,))
                time.sleep(0.3)
        op = uuid.uuid4()
        _, result = self.save(cand, op, registry=Killed(self.loader, self.s, **roles))
        self.assertIsInstance(result, provstore.UnknownRegistration)
        self.assertEqual(self.rows(), before)
        fresh = provstore.RealProvenanceStore(self.conn("loader"), self.s, **roles)
        self.assertIsInstance(self.recover(op, cand, registry=fresh), provstore.UnknownRegistration)
        _, rerun = self.save(cand, op, registry=fresh)
        self.assertIsInstance(rerun, provstore.CommittedRegistration)

    def test_p04d_a_lock_wait_past_the_timeout_records_nothing(self):
        cand = self.cand(acquisitions=(6,))
        before = self.rows()
        holder = self.conn("admin")
        begin(holder)
        try:
            holder.execute("SELECT pg_advisory_xact_lock(hashtextextended('rw.prov.register:'||%s,0) & 4611686018427387903)", (self.s,))
            short = provstore.RealProvenanceStore(self.loader, self.s, loader_role=self.inst.roles["loader"], lock_timeout_ms=300)
            started = time.monotonic()
            error = self.error_of(lambda: self.save(cand, registry=short))
            self.assertEqual(error.code, "RW_PROV_LOCK_TIMEOUT")
            self.assertLess(time.monotonic() - started, 10)
        finally:
            rollback(holder)
        self.assertEqual(self.rows(), before)
        self.assertIsInstance(self.save(cand)[1], provstore.CommittedRegistration)      # and the identical command then succeeds

    def test_p05_the_loader_and_the_executor_are_exactly_themselves_and_touch_no_registry_table(self):
        for who in ("loader", "executor"):
            conn = self.conn(who)
            role = self.inst.roles[who]
            self.assertEqual(conn.execute("SELECT current_user::text,session_user::text,current_setting('role')").fetchone(), (role, role, "none"))
            statements = (f"SELECT * FROM {self.s}.rwp_payload", f"UPDATE {self.s}.rwp_payload SET size_bytes=size_bytes",
                          f"DELETE FROM {self.s}.rwp_manifest", f"INSERT INTO {self.s}.rwp_context SELECT * FROM {self.s}.rwp_context",
                          f"CREATE TABLE {self.s}.rwp_illegal(value integer)", f"SET ROLE {self.inst.roles['owner']}")
            for statement in statements:
                self.assertDenied(lambda c=conn, s=statement: c.execute(s))

    def test_p06_concurrent_exact_and_conflicting_operations(self):
        cand = self.cand(acquisitions=(4,))
        native = self.rows(native=True)
        roles = dict(loader_role=self.inst.roles["loader"])
        stores = [provstore.RealProvenanceStore(self.conn("loader"), self.s, **roles) for _ in range(2)]
        op = uuid.uuid4()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.save, cand, op, registry=s) for s in stores]
            results = [f.result(timeout=30)[1] for f in futures]
        self.assertTrue(all(isinstance(x, provstore.CommittedRegistration) for x in results))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.load(cand).bundle, cand.bundle)
        other = self.cand(acquisitions=(5,))
        op = uuid.uuid4()

        def offer(registry, candidate_):
            try:
                return self.save(candidate_, op, registry=registry)[1]
            except ProvenanceError as error:
                return error.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(offer, s, c) for s, c in zip(stores, (cand, other))]
            outcome = [f.result(timeout=30) for f in futures]
        self.assertEqual(sum(isinstance(x, provstore.CommittedRegistration) for x in outcome), 1, outcome)
        self.assertEqual(sum(x == "RW_PROV_OPERATION_CONFLICT" for x in outcome), 1, outcome)
        self.assertEqual(self.rows(native=True), native)


class N2aOnSyntheticTest(N2aRegression, ProvCase):
    SCOPE = "SYNTHETIC_TEST"


class N2aOnTestSwitch(N2aRegression, ProvCase):
    SCOPE = "TEST_SWITCH"


# =====================================================================================================================
# Binding (design 3.3 item 1): exit statement R2 (a)
# =====================================================================================================================
class BindingTests(ProvCase):
    def test_a_bound_registration_is_refused_before_the_publish_and_accepted_after_it(self):
        """EXIT STATEMENT (a): the real registry binds as N2a does. A context-bound registration needs the published context: before the
        publish it is refused (RW_PROV_INPUT_MISSING) and nothing is stored; after it the same bytes are accepted. So the loader registers
        the context-bound bundle AFTER the publish, and its last use in the sequence is step (4a)."""
        for scope_name in TEST_SCOPES:
            with self.subTest(scope=scope_name):
                salt = self.tag(scope_name)
                payload = PAYLOAD + salt.encode()
                unbound = candidate(payload, scope=scope_name, salt=salt)
                snap = self.snapshot_for(unbound, scope_name)                        # built, NOT published
                bound = candidate(payload, scope=scope_name, salt=salt, financial_context=snap.context_id)
                before = self.rows()
                self.assertEqual(self.error_of(lambda: self.save(bound)).code, "RW_PROV_INPUT_MISSING")
                self.assertEqual(self.rows(), before)
                # The key itself, with the function out of the picture (E11 crafted insert as the owner; refused, nothing remains).
                with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                    self.owner.execute(f"INSERT INTO {self.s}.rwp_context(context_sha256,context,financial_context_sha256) VALUES(%s,%s,%s)",
                                       (bound.context_sha256, bound.bundle.context_bytes, snap.context_id))
                self.assertEqual(self.rows(), before)
                self.publish(snap, valid_in=120.0, evidence=fx.hg4_shape(self.bound(), sources=(SOURCE_ID,)))
                _, saved = self.save(bound)
                self.assertIsInstance(saved, provstore.CommittedRegistration)
                self.assertEqual(self.load(bound).financial_context_sha256, snap.context_id)

    def test_an_unbound_registration_is_accepted_before_the_publish_and_is_not_what_a_lease_loads(self):
        for scope_name in TEST_SCOPES:
            with self.subTest(scope=scope_name):
                salt = self.tag(scope_name)
                payload = PAYLOAD + salt.encode()
                unbound = candidate(payload, scope=scope_name, salt=salt)
                _, saved = self.save(unbound)                                         # the qualification run's registration
                self.assertIsInstance(saved, provstore.CommittedRegistration)
                self.assertIsNone(self.load(unbound).financial_context_sha256)

    def test_a_bound_registration_must_hold_exactly_the_snapshots_members_and_scope(self):
        salt = self.tag("members")
        payload = PAYLOAD + salt.encode()
        base = candidate(payload, scope="TEST_SWITCH", salt=salt)
        snap = self.snapshot_for(base, "TEST_SWITCH")
        self.publish(snap, valid_in=120.0, evidence=fx.hg4_shape(self.bound(), sources=(SOURCE_ID,)))
        before = self.rows()
        other_payload = candidate(PAYLOAD + b"other" + salt.encode(), scope="TEST_SWITCH", salt=salt, financial_context=snap.context_id)
        self.assertEqual(self.error_of(lambda: self.save(other_payload)).code, "RW_PROV_BINDING_DIFFERS")
        two = candidate(payload, (1, 2), scope="TEST_SWITCH", salt=salt, financial_context=snap.context_id)
        self.assertEqual(self.error_of(lambda: self.save(two)).code, "RW_PROV_BINDING_DIFFERS")
        other_scope = candidate(payload, scope="SYNTHETIC_TEST", salt=salt, financial_context=snap.context_id)
        self.assertEqual(self.error_of(lambda: self.save(other_scope)).code, "RW_PROV_BINDING_DIFFERS")
        self.assertEqual(self.rows(), before)
        same = candidate(payload, scope="TEST_SWITCH", salt=salt, financial_context=snap.context_id)       # the control
        self.assertIsInstance(self.save(same)[1], provstore.CommittedRegistration)

    def test_the_bound_check_holds_for_the_function_called_directly_too(self):
        salt = self.tag("direct")
        payload = PAYLOAD + salt.encode()
        base = candidate(payload, scope="TEST_SWITCH", salt=salt)
        snap = self.snapshot_for(base, "TEST_SWITCH")
        bound = candidate(payload, scope="TEST_SWITCH", salt=salt, financial_context=snap.context_id)
        before = self.rows()
        self.database_code(lambda: self.put_sql(self.loader, bound), "RW_PROV_INPUT_MISSING")
        self.assertEqual(self.rows(), before)

    def test_a_context_is_bound_to_at_most_the_published_value_and_never_changes(self):
        """The registry's candidate rows are append-only: the binding column cannot be rewritten (design 3.3 item 1)."""
        live = self.live("TEST_SWITCH")
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            self.owner.execute(f"UPDATE {self.s}.rwp_context SET financial_context_sha256=NULL WHERE context_sha256=%s", (live.cand.context_sha256,))
        self.assertEqual(caught.exception.diag.message_primary, "RW_PROV_STORAGE_CONFLICT")


# =====================================================================================================================
# The guarded load (design 3.2): bound to R1's mode, head, lease and root
# =====================================================================================================================
class GuardedLoadMixin:
    SCOPE = "TEST_SWITCH"

    def test_a_create_lease_loads_the_bound_candidate_and_commits(self):
        live = self.live(self.SCOPE)
        before = self.rows()
        executor = self.conn("executor")
        with self.bundle_guard_off():            # E11 crafted for the commit (R3: an unsealed create lease does not commit); see below
            begin(executor)
            try:
                lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
                context = self.guarded(executor, lease, live)
                self.assertEqual(context.bundle, live.cand.bundle)
                self.assertEqual(context.bundle.payloads[0][1], live.cand.bundle.payloads[0][1])          # the payload bytes arrive
                self.assertEqual((context.scope, context.promotable, context.source_admitted, context.financial_context_sha256),
                                 (self.SCOPE, False, False, live.ctx))
                commit(executor)
            finally:
                rollback(executor)
        self.assertEqual(self.rows(), before)                                           # the load writes no candidate row
        self.assertEqual(self.count("rw_lease", "context_id=%s", (live.ctx,)), 1)

    def test_a_reproduce_lease_loads_too(self):
        live = self.live(self.SCOPE)
        executor = self.conn("executor")
        begin(executor)
        try:
            lease = self.admit(executor, live.ctx, 1, "EXECUTE_REPRODUCE", live.owner_id, live.root_id)
            self.assertEqual(self.guarded(executor, lease, live).bundle, live.cand.bundle)
        finally:
            rollback(executor)

    def test_a_v1_candidate_loads_with_null_provenance(self):
        live = self.live(self.SCOPE, v1=True)
        executor = self.conn("executor")
        begin(executor)
        try:
            lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            context = self.guarded(executor, lease, live)
            self.assertIsNone(context.members[0].envelope_sha256)
        finally:
            rollback(executor)

    def test_read_and_export_leases_are_not_a_way_to_the_candidates(self):
        live = self.live(self.SCOPE)
        executor = self.conn("executor")
        for purpose in ("ARCHIVE_READ", "ARCHIVE_EXPORT"):
            begin(executor)
            try:
                lease = self.admit(executor, live.ctx, 1, purpose, live.owner_id, live.root_id)
                self.assertEqual(self.error_of(lambda: self.guarded(executor, lease, live)).code, "RW_PROV_LEASE_REQUIRED")    # refused before any statement
            finally:
                rollback(executor)
            begin(executor)
            try:
                self.admit(executor, live.ctx, 1, purpose, live.owner_id, live.root_id)
                self.database_code(lambda: executor.execute(f"SELECT * FROM {self.s}.rwp_load_context(%s,%s)", (live.cand.context_sha256, purpose)), "RW_PROV_PURPOSE_REFUSED")
            finally:
                rollback(executor)

    def test_without_a_lease_there_is_no_load(self):
        live = self.live(self.SCOPE)
        executor = self.conn("executor")
        self.database_code(lambda: executor.execute(f"SELECT * FROM {self.s}.rwp_load_context(%s,'EXECUTE_CREATE')", (live.cand.context_sha256,)), "RW_PROV_LEASE_REQUIRED")
        begin(executor)
        try:
            self.database_code(lambda: executor.execute(f"SELECT * FROM {self.s}.rwp_load_context(%s,'EXECUTE_CREATE')", (live.cand.context_sha256,)), "RW_PROV_LEASE_REQUIRED")
        finally:
            rollback(executor)
        # And the Python wrapper refuses a value that is not an admitted lease, and a connection with no open transaction.
        begin(executor)
        try:
            lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            for bad in (None, object(), replace(lease, purpose="ARCHIVE_READ")):
                self.assertEqual(self.error_of(lambda: self.guarded(executor, bad, live)).code, "RW_PROV_LEASE_REQUIRED")
        finally:
            rollback(executor)
        self.assertEqual(self.error_of(lambda: self.guarded(executor, lease, live)).code, "RW_PROV_LEASE_REQUIRED")      # no transaction now

    def test_the_lease_purpose_and_the_requested_purpose_must_agree(self):
        live = self.live(self.SCOPE)
        executor = self.conn("executor")
        begin(executor)
        try:
            self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            self.database_code(lambda: executor.execute(f"SELECT * FROM {self.s}.rwp_load_context(%s,'EXECUTE_REPRODUCE')", (live.cand.context_sha256,)), "RW_SCOPE_DIFFERS")
        finally:
            rollback(executor)

    def test_only_a_registration_bound_to_the_leases_own_context_is_returned(self):
        live, other = self.live(self.SCOPE, label="a"), self.live(self.SCOPE, label="b")
        executor = self.conn("executor")
        begin(executor)
        try:
            lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            # The candidate bound to the OTHER context, requested under this lease.
            self.assertEqual(self.error_of(lambda: provstore.load_guarded(
                executor, self.s, self.inst.roles["executor"], lease, other.cand.context_sha256, expected_members=other.cand.members,
                witnesses=other.cand.witnesses)).code, "RW_PROV_CONTEXT_DIFFERS")
        finally:
            rollback(executor)

    def test_the_database_alone_refuses_another_contexts_or_an_unbound_candidate(self):
        """The same two refusals as above, called on the DATABASE function directly: the guard does not depend on the Python wrapper's
        own comparison (which is defence in depth)."""
        live, other = self.live(self.SCOPE, label="a"), self.live(self.SCOPE, label="b")
        unbound = candidate(PAYLOAD + b"raw-unbound", scope=self.SCOPE, salt=self.tag("raw-unbound"))
        self.save(unbound)
        executor = self.conn("executor")
        for label, sha in (("another context's", other.cand.context_sha256), ("an unbound", unbound.context_sha256)):
            begin(executor)
            try:
                self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
                self.database_code(lambda s=sha: executor.execute(f"SELECT * FROM {self.s}.rwp_load_context(%s,'EXECUTE_CREATE')", (s,)), "RW_PROV_CONTEXT_DIFFERS")
            finally:
                rollback(executor)
        begin(executor)
        try:                                                              # the control: the lease's own bound candidate is returned
            self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            row = executor.execute(f"SELECT * FROM {self.s}.rwp_load_context(%s,'EXECUTE_CREATE')", (live.cand.context_sha256,)).fetchone()
            self.assertEqual(bytes(row[0]), live.cand.bundle.context_bytes)
            self.assertEqual([bytes(p) for p in row[1]], [live.cand.bundle.payloads[0][1]])
            self.assertIsNone(row[5])
        finally:
            rollback(executor)

    def test_an_unbound_registration_is_never_returned(self):
        live = self.live(self.SCOPE)
        unbound = candidate(PAYLOAD + b"unbound", scope=self.SCOPE, salt=self.tag("unbound"))
        self.save(unbound)
        executor = self.conn("executor")
        begin(executor)
        try:
            lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            self.assertEqual(self.error_of(lambda: provstore.load_guarded(
                executor, self.s, self.inst.roles["executor"], lease, unbound.context_sha256, expected_members=unbound.members,
                witnesses=unbound.witnesses)).code, "RW_PROV_CONTEXT_DIFFERS")
        finally:
            rollback(executor)

    def test_an_unknown_candidate_is_input_missing(self):
        live = self.live(self.SCOPE)
        executor = self.conn("executor")
        begin(executor)
        try:
            lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            self.assertEqual(self.error_of(lambda: provstore.load_guarded(
                executor, self.s, self.inst.roles["executor"], lease, h(b"never registered"), expected_members=live.cand.members,
                witnesses=live.cand.witnesses)).code, "RW_PROV_INPUT_MISSING")
        finally:
            rollback(executor)

    def test_another_role_or_a_set_role_cannot_use_the_executors_function(self):
        live = self.live(self.SCOPE)
        for who in ("loader", "publisher"):
            conn = self.conn(who)
            self.assertDenied(lambda c=conn: c.execute(f"SELECT * FROM {self.s}.rwp_load_context(%s,'EXECUTE_CREATE')", (live.cand.context_sha256,)))
        executor = self.conn("executor")
        for statement in (f"SELECT * FROM {self.s}.rwp_put_context(NULL,NULL,NULL,NULL,NULL,NULL,NULL)", f"SELECT * FROM {self.s}.rwp_get_context(NULL,NULL)",
                          f"SELECT {self.s}.rwp_guard('EXECUTE_CREATE')", f"SELECT * FROM {self.s}.rwp_collect_context(NULL,NULL)",
                          f"SELECT {self.s}.rwp_origin_failures('{{}}'::bytea)"):
            self.assertDenied(lambda s=statement: executor.execute(s))
        # The Python wrapper also checks the session: a publisher session is not the executor.
        publisher = self.conn("publisher")
        begin(publisher)
        try:
            shaped = store.AdmittedLease(live.snap.data, live.owner_id, live.root_id, live.ctx, 1, uuid.uuid4(), "EXECUTE_CREATE", self.db_now())
            self.assertEqual(self.error_of(lambda: self.guarded(publisher, shaped, live)).code, "RW_PROV_ROLE_REFUSED")
        finally:
            rollback(publisher)

    def test_a_candidate_whose_manifest_names_another_source_is_not_a_member_of_the_snapshot(self):
        """The snapshot's member list is the source of the binding: a bound registration of a candidate whose manifest is for another source
        is refused at registration, so the guarded load cannot return one (defence in depth: the Python wrapper compares the members again)."""
        salt = self.tag("source")
        payload = PAYLOAD + salt.encode()
        base = candidate(payload, scope=self.SCOPE, salt=salt)
        snap = self.snapshot_for(base, self.SCOPE)
        self.publish(snap, valid_in=120.0, evidence=fx.hg4_shape(self.bound(), sources=(SOURCE_ID,)))
        renamed = candidate(payload, scope=self.SCOPE, salt=salt, source_id="fictional.other", financial_context=snap.context_id)
        self.assertEqual(self.error_of(lambda: self.save(renamed)).code, "RW_PROV_BINDING_DIFFERS")

    def test_loading_changes_no_candidate_and_publishing_does_not_either(self):
        live = self.live(self.SCOPE)
        before = self.rows()
        executor = self.conn("executor")
        with self.bundle_guard_off():            # E11 crafted for the commit (R3: an unsealed create lease does not commit)
            for purpose in ("EXECUTE_CREATE", "EXECUTE_REPRODUCE"):
                begin(executor)
                try:
                    lease = self.admit(executor, live.ctx, 1, purpose, live.owner_id, live.root_id)
                    self.guarded(executor, lease, live)
                    commit(executor)
                finally:
                    rollback(executor)
        self.assertEqual(self.rows(), before)


class GuardedLoadOnTestSwitch(GuardedLoadMixin, ProvCase):
    """The `TEST_SWITCH` guarded load with a real-branch lease (design 7.1, R2): the snapshot is of the real branch run on invented data."""
    SCOPE = "TEST_SWITCH"


class GuardedLoadOnSyntheticTest(GuardedLoadMixin, ProvCase):
    SCOPE = "SYNTHETIC_TEST"


# =====================================================================================================================
# The deadline of the guarded load (design 3.2; technical re-review L-1): at or past complete_by, with every session timeout at 0
# =====================================================================================================================
class GuardedLoadDeadlineTests(ProvCase):
    INSTALL = "provdeadline"
    W = 3

    def test_the_load_is_refused_at_or_past_complete_by_whichever_of_w_and_valid_until_is_earlier(self):
        """T07 R2: the PAUSE BEFORE THE GUARDED LOAD. The lease is admitted, the session stalls (every timeout is 0, so no session timeout
        is the bound), and the load is refused AT the call: `RW_DEADLINE`, not at the later COMMIT. The cap decides when valid_until is
        nearer than W; W decides otherwise."""
        for label, valid_in in (("the cap decides", 2.0), ("W decides", 120.0)):
            live = self.live("TEST_SWITCH", valid_in=valid_in, label=label)
            executor = self.conn("executor", options=self.stall_options())
            for setting in ("statement_timeout", "idle_in_transaction_session_timeout", "lock_timeout", "transaction_timeout"):
                self.assertEqual(executor.execute(f"SHOW {setting}").fetchone()[0], "0", setting)
            begin(executor)
            try:
                lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
                if valid_in < self.inst.w_seconds:
                    self.assertEqual(lease.complete_by, live.valid, label)
                else:
                    self.assertLess(lease.complete_by, live.valid, label)
                self.wait_for_db_time(lease.complete_by)
                refusal = self.error_of(lambda: self.guarded(executor, lease, live))
                self.assertEqual(refusal.code, "RW_DEADLINE", label)
            finally:
                rollback(executor)
            self.assertEqual(self.count("rw_lease", "context_id=%s", (live.ctx,)), 0, label)         # the whole transaction rolled back

    def test_the_positive_control_a_load_before_the_deadline_succeeds_and_commits(self):
        live = self.live("TEST_SWITCH")
        executor = self.conn("executor", options=self.stall_options())
        # E11 crafted for the commit only: with R3 a create lease commits only with a sealed bundle, and a load alone seals nothing. The
        # guard is switched off BEFORE the admission (a deferred trigger event is queued when the row is inserted).
        with self.bundle_guard_off():
            begin(executor)
            try:
                lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
                self.assertLess(self.db_now(), lease.complete_by)
                self.assertEqual(self.guarded(executor, lease, live).bundle, live.cand.bundle)
                commit(executor)
            finally:
                rollback(executor)
        self.assertEqual(self.count("rw_lease", "context_id=%s", (live.ctx,)), 1)

    def test_the_deadline_is_checked_before_the_candidate_is_read(self):
        """A stalled holder gets no bytes: the refusal comes with no row in the answer (the call raises before it returns one)."""
        live = self.live("TEST_SWITCH", valid_in=120.0, label="no-bytes")
        executor = self.conn("executor", options=self.stall_options())
        begin(executor)
        try:
            lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            self.wait_for_db_time(lease.complete_by)
            error = self.database_code(lambda: executor.execute(f"SELECT * FROM {self.s}.rwp_load_context(%s,'EXECUTE_CREATE')", (live.cand.context_sha256,)), "RW_DEADLINE")
            self.assertIsNotNone(error)
        finally:
            rollback(executor)


class GuardedLoadCraftedStateTests(ProvCase):
    """The guard re-checks, under the locks the lease holds, the facts admission checked. In normal operation the lease's head lock keeps
    them true, so no PRODUCT path reaches a state where one fails. These tests craft such a state (E11: the owner role inserts a lease row
    for an executor transaction that has not admitted, which does NOT take the head lock, so a renewal can intervene) to see each re-check fire.
    The control is the same crafted lease in a state that is true. Never product evidence."""
    INSTALL = "provcrafted"

    def craft_lease(self, executor, live, *, generation=1, purpose="EXECUTE_CREATE", phase="OPEN"):
        pid, xid = executor.execute("SELECT pg_backend_pid(),pg_current_xact_id()::text").fetchone()
        valid_until = self.owner.execute(f"SELECT valid_until FROM {self.s}.rw_history WHERE context_id=%s AND generation=%s", (live.ctx, generation)).fetchone()[0]
        now = self.db_now()
        with self.bundle_guard_off():            # R3: the bundle guard would refuse to commit this unsealed create lease row (E11 crafted)
            self.owner.execute(
                f"INSERT INTO {self.s}.rw_lease(backend_pid,xid,owner_id,root_id,context_id,generation,operation_id,command_sha256,purpose,phase,admitted_at,valid_until,complete_by)"
                " VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (pid, xid, live.owner_id, live.root_id, live.ctx, generation, uuid.uuid4(), "1" * 64, purpose, phase, now, valid_until, now + fx.seconds(60)))

    def load(self, executor, live, purpose="EXECUTE_CREATE"):
        return executor.execute(f"SELECT * FROM {self.s}.rwp_load_context(%s,%s)", (live.cand.context_sha256, purpose)).fetchone()

    def test_the_control_a_crafted_lease_in_a_true_state_loads(self):
        live = self.live("TEST_SWITCH")
        executor = self.conn("executor")
        begin(executor)
        try:
            self.craft_lease(executor, live)
            self.assertEqual(bytes(self.load(executor, live)[0]), live.cand.bundle.context_bytes)
        finally:
            rollback(executor)

    def test_a_head_that_moved_on_refuses_the_lease_of_the_old_generation(self):
        live = self.live("TEST_SWITCH", valid_in=300.0)
        renewed = self.renew(live.ctx, 1, valid_until=self.db_now() + fx.seconds(400), evidence=fx.hg4_shape(self.bound(), sources=(SOURCE_ID,)))
        self.assertEqual(renewed.status, 0, renewed.text)
        executor = self.conn("executor")
        begin(executor)
        try:
            self.craft_lease(executor, live, generation=1)
            self.database_code(lambda: self.load(executor, live), "RW_GENERATION_DIFFERS")
        finally:
            rollback(executor)

    def test_a_right_that_was_withdrawn_refuses_the_lease(self):
        live = self.live("TEST_SWITCH", valid_in=300.0)
        rights = {**fx.ALL_RIGHTS, "EXECUTE_CREATE": False}
        renewed = self.renew(live.ctx, 1, valid_until=self.db_now() + fx.seconds(400), rights=rights, evidence=fx.hg4_shape(self.bound(), sources=(SOURCE_ID,)))
        self.assertEqual(renewed.status, 0, renewed.text)
        executor = self.conn("executor")
        begin(executor)
        try:
            self.craft_lease(executor, live, generation=2)
            self.database_code(lambda: self.load(executor, live), "RW_RIGHT_REFUSED")
        finally:
            rollback(executor)
        begin(executor)
        try:                                                              # the control: the right still held loads
            self.craft_lease(executor, live, generation=2, purpose="EXECUTE_REPRODUCE", phase="READONLY")
            self.assertEqual(bytes(self.load(executor, live, "EXECUTE_REPRODUCE")[0]), live.cand.bundle.context_bytes)
        finally:
            rollback(executor)

    def test_a_phase_that_does_not_fit_the_purpose_is_refused(self):
        live = self.live("TEST_SWITCH")
        executor = self.conn("executor")
        for purpose, phase in (("EXECUTE_CREATE", "READONLY"), ("EXECUTE_REPRODUCE", "OPEN")):
            begin(executor)
            try:
                self.craft_lease(executor, live, purpose=purpose, phase=phase)
                self.database_code(lambda p=purpose: self.load(executor, live, p), "RW_SCOPE_DIFFERS")
            finally:
                rollback(executor)


class GuardedLoadBeforeAnyPublishTests(ProvCase):
    INSTALL = "provfresh"

    def test_a_database_with_nothing_published_holds_the_guard_shut(self):
        executor = self.conn("executor")
        self.assertEqual(self.owner.execute(f"SELECT mode FROM {self.s}.rw_mode").fetchone()[0], "CLOSED")
        self.database_code(lambda: executor.execute(f"SELECT * FROM {self.s}.rwp_load_context(%s,'EXECUTE_CREATE')", (h(b"x"),)), "RW_MODE_HOLD")


class GuardedLoadPredicateWiringTests(ProvCase):
    """Like R1's wiring class: the guarded load CALLS `rw_reached(clock, complete_by)`. In an install of its own the owner role (E11 crafted,
    restored after every test) replaces the predicate with one that is true 30 s early; a guard written inline as `>` or `>=` could not
    change its answer. The control is the same load before the replacement."""
    INSTALL = "provwiring"

    def setUp(self):
        super().setUp()
        self.original = self.owner.execute("SELECT pg_get_functiondef(to_regprocedure(%s))", (f"{self.s}.rw_reached(timestamptz,timestamptz)",)).fetchone()[0]
        self.addCleanup(self.restore)

    def restore(self):
        self.owner.execute("SET lock_timeout = '5s'")
        self.owner.execute(self.original)

    def replace_predicate(self, early_seconds):
        self.owner.execute("SET lock_timeout = '5s'")
        self.owner.execute(f"CREATE OR REPLACE FUNCTION {self.s}.rw_reached(p_now timestamptz,p_limit timestamptz) RETURNS boolean "
                           f"LANGUAGE sql IMMUTABLE SET search_path=pg_catalog,{self.s},pg_temp AS $$ "
                           f"SELECT COALESCE(p_now>=p_limit-make_interval(secs=>{int(early_seconds)}),false) $$")

    def test_the_guarded_load_calls_the_one_predicate_with_the_clock_first_and_complete_by_second(self):
        live = self.live("TEST_SWITCH")
        executor = self.conn("executor")
        begin(executor)
        try:
            lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            self.assertEqual(self.guarded(executor, lease, live).bundle, live.cand.bundle)                    # the control
        finally:
            rollback(executor)
        self.replace_predicate(30)
        executor = self.conn("executor")                         # a new backend: no plan under the old definition
        begin(executor)
        try:
            lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            self.assertEqual(self.error_of(lambda: self.guarded(executor, lease, live)).code, "RW_DEADLINE")
        finally:
            rollback(executor)


# =====================================================================================================================
# Publish consults the origin validators (design 4.2)
# =====================================================================================================================
def relabelled_real_bytes(case, label=""):
    """The bytes of a TEST snapshot with the scope field changed to REAL: synthetic origin labels, no REAL_SOURCE string anywhere, invented
    digests, no registered candidate. A REAL install never stores them (the predicates refuse them)."""
    core = KIT.install("prov", w_seconds=4, kind="TEST")
    executor = core.connect("executor")
    case.addCleanup(executor.close)
    snap = real_scope.make_snapshot(executor, core.schema, "SYNTHETIC_TEST", **fx.content(case.tag("real-bytes" + label)))
    data = canonical_json({**json.loads(snap.data), "scope": "REAL"}).encode()
    case.assertNotIn(b"REAL_SOURCE", data)
    return data


class PublishReportsEveryFailedPredicateTests(ProvCase):
    """Publish evaluates the same predicates plus the install-kind check and reports them together (design 4.2). A TEST install: the
    install-kind guard is listed too. The predicates do not read the install kind, so it cannot mask them."""

    def publish_call(self, data):
        publisher = self.conn("publisher")
        return self.database_code(lambda: publisher.execute(f"SELECT * FROM {self.s}.rw_publish(%s,%s,NULL,%s,'a','PD-9001',%s,%s)",
                                                            (data, Jsonb(fx.ALL_RIGHTS), Jsonb([]), "a" * 40, "b" * 64)), "RW_PUBLISH_REFUSED")

    def test_every_failed_predicate_is_listed_at_once_in_the_order_kind_o1_o2_o3_candidate(self):
        data = relabelled_real_bytes(self)
        listed = self.detail_codes(self.publish_call(data))
        self.assertEqual(listed, ["RW_INSTALL_KIND", OM, O1, O2, O3, "RW_PROV_CANDIDATE_MISSING"])       # R3: the origin-label code is second
        self.assertEqual(self.count("rw_snapshot", "context_id=%s", (store.digest(data),)), 0)

    def test_o1_is_listed_for_a_synthetic_source(self):
        self.assertIn(O1, self.detail_codes(self.publish_call(relabelled_real_bytes(self, "o1"))))

    def test_o2_is_listed_for_a_missing_terms_check(self):
        self.assertIn(O2, self.detail_codes(self.publish_call(relabelled_real_bytes(self, "o2"))))

    def test_o3_is_listed_for_members_that_are_not_human_internal_development_acquisitions(self):
        self.assertIn(O3, self.detail_codes(self.publish_call(relabelled_real_bytes(self, "o3"))))

    def test_a_missing_candidate_is_its_own_code(self):
        self.assertIn("RW_PROV_CANDIDATE_MISSING", self.detail_codes(self.publish_call(relabelled_real_bytes(self, "missing"))))

    def test_a_test_scope_publish_does_not_run_the_validators(self):
        """The REAL branch only: a test scope snapshot publishes with nothing registered (the R1 tests rely on it)."""
        snap, _valid, result = self.publish()
        self.assertEqual(result.status, 0, result.text)

    def test_the_origin_function_with_registered_candidates_lists_the_predicates_and_not_a_missing_candidate(self):
        """E11 crafted call: the owner role runs `rwp_origin_failures` on the bytes of a TEST_SWITCH snapshot whose candidates are registered.
        The control for the missing-candidate code is the registration; the other three still fail because invented data is synthetic."""
        for scope_name in TEST_SCOPES:
            with self.subTest(scope=scope_name):
                salt = self.tag(scope_name)
                payload = PAYLOAD + salt.encode()
                cand = candidate(payload, scope=scope_name, salt=salt)
                snap = self.snapshot_for(cand, scope_name)
                call = lambda: self.owner.execute(f"SELECT {self.s}.rwp_origin_failures(%s)", (snap.data,)).fetchone()[0]  # noqa: E731
                self.assertEqual(call(), [O1, O2, O3, "RW_PROV_CANDIDATE_MISSING"])
                self.save(cand)
                self.assertEqual(call(), [O1, O2, O3])
                for v1 in (True, False):
                    cand = candidate(payload + bytes([v1]), scope=scope_name, salt=salt, v1=v1)
                    other = self.snapshot_for(cand, scope_name, "v1" if v1 else "v2")
                    self.save(cand)
                    self.assertEqual(self.owner.execute(f"SELECT {self.s}.rwp_origin_failures(%s)", (other.data,)).fetchone()[0], [O1, O2, O3], v1)


PERMITTING = {"checked_by": "invented-checker", "checked_on": "2001-02-03", "permits_internal_development_use": True, "notes": "invented"}


class PublishOriginPassingSideTests(ProvCase):
    """R2 review L-1: the PASSING side of O2 at publish. Publish feeds O2 from each source record's own `terms_check` in the snapshot, so
    a snapshot whose member sources all carry a permitting check drops O2 from the failed list while the predicates the bytes still fail
    (O1: the origin is synthetic; O3: no registered human acquisition) stay listed. The permitting check is an invented attestation that
    is passed BY VALUE to a validator and to a publish that is refused; nothing is stored, and the snapshot is never marked
    `synthetic=false` (design 4.2)."""

    def with_checks(self, label, checks):
        """The relabelled REAL bytes with `checks[i]` as the terms_check of the i-th source record (the rest unchanged)."""
        document = json.loads(relabelled_real_bytes(self, label))
        records = document["source_records"]
        self.assertGreaterEqual(len(records), 2)                       # "all member sources" is not a vacuous claim
        self.assertEqual({r["source_id"] for r in records}, {m["source_id"] for m in document["members"]})
        for record, check in zip(records, checks):
            record["terms_check"] = check
        self.assertTrue(document["origin"]["synthetic"])
        return canonical_json(document).encode(), len(records)

    def origin(self, data):
        return self.owner.execute(f"SELECT {self.s}.rwp_origin_failures(%s)", (data,)).fetchone()[0]

    def publish_codes(self, data):
        publisher = self.conn("publisher")
        return self.detail_codes(self.database_code(lambda: publisher.execute(
            f"SELECT * FROM {self.s}.rw_publish(%s,%s,NULL,%s,'a','PD-9001',%s,%s)", (data, Jsonb(fx.ALL_RIGHTS), Jsonb([]), "a" * 40, "b" * 64),
        ), "RW_PUBLISH_REFUSED"))

    def test_o2_drops_out_when_every_member_source_carries_a_permitting_check_and_the_other_predicates_stay_listed(self):
        count = self.with_checks("o2none", [None, None])[1]
        none_data = self.with_checks("o2none", [None] * count)[0]
        all_data = self.with_checks("o2all", [PERMITTING] * count)[0]
        self.assertEqual(self.origin(none_data), [OM, O1, O2, O3, "RW_PROV_CANDIDATE_MISSING"])      # the control: O2 fails with none
        self.assertEqual(self.origin(all_data), [OM, O1, O3, "RW_PROV_CANDIDATE_MISSING"])           # O2 dropped, the label code, O1 and O3 stay
        self.assertEqual(self.publish_codes(none_data), ["RW_INSTALL_KIND", OM, O1, O2, O3, "RW_PROV_CANDIDATE_MISSING"])
        self.assertEqual(self.publish_codes(all_data), ["RW_INSTALL_KIND", OM, O1, O3, "RW_PROV_CANDIDATE_MISSING"])
        self.assertEqual(self.count("rw_snapshot", "context_id IN (%s,%s)", (store.digest(none_data), store.digest(all_data))), 0)

    def test_every_source_needs_its_own_check_one_missing_or_negative_keeps_o2_listed(self):
        count = self.with_checks("o2partial", [None, None])[1]
        negative = dict(PERMITTING, permits_internal_development_use=False)
        for label, checks in {"first only": [PERMITTING] + [None] * (count - 1), "last only": [None] * (count - 1) + [PERMITTING],
                              "one negative": [PERMITTING] * (count - 1) + [negative]}.items():
            with self.subTest(label):
                data, _ = self.with_checks("o2partial-" + label.replace(" ", ""), checks)
                self.assertEqual(self.origin(data), [OM, O1, O2, O3, "RW_PROV_CANDIDATE_MISSING"])
                self.assertEqual(self.publish_codes(data), ["RW_INSTALL_KIND", OM, O1, O2, O3, "RW_PROV_CANDIDATE_MISSING"])

    def test_the_synthetic_flag_is_no_exemption_so_the_check_in_the_snapshot_is_what_o2_reads(self):
        """The bytes are synthetic-labelled throughout. If publish ignored the snapshot's check (always passing null) O2 would fail here too."""
        count = self.with_checks("o2flag", [None, None])[1]
        data, _ = self.with_checks("o2flag", [PERMITTING] * count)
        self.assertNotIn(O2, self.origin(data))
        self.assertIn(O1, self.origin(data))


class PublishInARealInstallTests(ProvCase):
    """The same, in an install whose kind row is REAL (E11 crafted: the kit's owner role writes it in a DISPOSABLE database). The install-kind
    code is absent, so every listed code is a validator's. The REAL branch is enabled and sits behind the validators."""
    INSTALL = "provreal"
    KIND = "REAL"

    def publish_call(self, data, conn=None):
        publisher = conn or self.conn("publisher")
        return self.database_code(lambda: publisher.execute(f"SELECT * FROM {self.s}.rw_publish(%s,%s,NULL,%s,'a','PD-9001',%s,%s)",
                                                            (data, Jsonb(fx.ALL_RIGHTS), Jsonb([]), "a" * 40, "b" * 64)), "RW_PUBLISH_REFUSED")

    def test_the_real_scope_lists_exactly_the_validators_codes(self):
        data = relabelled_real_bytes(self)
        self.assertEqual(self.detail_codes(self.publish_call(data)), [OM, O1, O2, O3, "RW_PROV_CANDIDATE_MISSING"])
        self.assertEqual(self.count("rw_snapshot", "context_id=%s", (store.digest(data),)), 0)
        self.assertEqual(self.count("rw_history"), 0)

    def test_the_tool_still_refuses_a_relabelled_proposal_before_the_database(self):
        data = relabelled_real_bytes(self, "tool")
        document = {"context_id": store.digest(data), "schema": "finweb.real_proposal/1", "snapshot": json.loads(data)}
        result = self.tool().publish(canonical_json(document).encode(), rights=fx.ALL_RIGHTS, valid_until=None, evidence=[], actor=fx.ACTOR, ref=fx.REF)
        # The tool's own check refuses a proposal whose scope field disagrees with its origin labels, so a REAL proposal reaches the
        # database only with REAL labels, which first exist at R8; the database's validators (above) do not rely on that check.
        self.assertEqual((result.status, result.data["code"]), (2, "RW_ORIGIN_MISMATCH"))

    def test_test_scopes_are_refused_for_the_install_kind_alone(self):
        core = KIT.install("prov", w_seconds=4, kind="TEST")
        executor = core.connect("executor")
        self.addCleanup(executor.close)
        for name in TEST_SCOPES:
            snap = real_scope.make_snapshot(executor, core.schema, name, test_switch=(name == "TEST_SWITCH"), **fx.content(self.tag(name)))
            self.assertEqual(self.detail_codes(self.publish_call(snap.data)), ["RW_INSTALL_KIND"], name)

    def test_the_real_branch_is_enabled_and_sits_behind_the_validators(self):
        """E11 crafted WIRING in a install of its own: the owner role replaces `rwp_origin_failures` (restored after the test). The codes the
        function returns are exactly the codes publish lists, and with none the REAL-scope bytes are published. This shows that nothing
        else blocks the REAL branch and that the validators' result is what does. (The bytes are invented and synthetic-labelled; the
        database is disposable.)"""
        stub_install = KIT.install("provstub", w_seconds=4, kind="REAL")
        owner = stub_install.connect("owner")
        self.addCleanup(owner.close)
        original = owner.execute("SELECT pg_get_functiondef(to_regprocedure(%s))", (f"{stub_install.schema}.rwp_origin_failures(bytea)",)).fetchone()[0]

        def restore():
            owner.execute("SET lock_timeout = '5s'")
            owner.execute(original)
        self.addCleanup(restore)
        publisher = stub_install.connect("publisher")
        self.addCleanup(publisher.close)
        data = relabelled_real_bytes(self, "stub")
        s = stub_install.schema

        def stub(returns):
            owner.execute("SET lock_timeout = '5s'")
            owner.execute(f"CREATE OR REPLACE FUNCTION {s}.rwp_origin_failures(p_snapshot bytea) RETURNS text[] LANGUAGE sql STABLE SECURITY DEFINER "
                          f"SET search_path=pg_catalog,{s},pg_temp AS $$ SELECT {returns} $$")

        basis = Jsonb([e.as_json() for e in fx.none_shape()])        # NO_EXPIRY_READING for each member source: a supported shape

        def publish():
            return publisher.execute(f"SELECT * FROM {s}.rw_publish(%s,%s,NULL,%s,'a','PD-9001',%s,%s)", (data, Jsonb(fx.ALL_RIGHTS), basis, "a" * 40, "b" * 64))
        stub("ARRAY['RW_O2_TERMS_CHECK']::text[]")
        error = self.database_code(publish, "RW_PUBLISH_REFUSED")
        self.assertEqual(self.detail_codes(error), ["RW_O2_TERMS_CHECK"])                       # exactly the validators' answer
        stub("ARRAY[]::text[]")
        row = publish().fetchone()
        self.assertEqual((row[0], row[1], row[2]), (store.digest(data), 1, True))                # no code: the REAL branch publishes
        stored = json.loads(bytes(owner.execute(f"SELECT snapshot FROM {s}.rw_snapshot WHERE context_id=%s", (store.digest(data),)).fetchone()[0]))
        self.assertEqual((stored["scope"], stored["origin"]["synthetic"]), ("REAL", True))        # invented bytes: never marked synthetic=false


# =====================================================================================================================
# The origin predicates in SQL, by value: each predicate its own tests, controls, and parity with the Python predicates
# =====================================================================================================================
class OriginPredicateSqlTests(ProvCase):
    """The SQL predicates (`rwp_origin`) on invented inputs passed BY VALUE: the owner role calls an ungranted IMMUTABLE function with literal
    arguments. Nothing is stored (a test reads the tables before and after and runs the call in a READ ONLY transaction)."""

    def sql(self, sources, members):
        return tuple(self.owner.execute(f"SELECT {self.s}.rwp_origin(%s,%s)", (Jsonb(sources), Jsonb(members))).fetchone()[0])

    SOURCE = {"source_id": "fictional.source", "synthetic": True, "terms_check": None}
    MEMBER = {"manifest_sha256": "a" * 64, "schema": "v1", "retrieved_by": "synthetic", "usage_scope": "SYNTHETIC_TEST"}
    HUMAN = {"manifest_sha256": "a" * 64, "schema": "v1", "retrieved_by": "human", "usage_scope": "INTERNAL_DEVELOPMENT_ONLY"}

    def test_o1_failing_case_and_control(self):
        self.assertIn(O1, self.sql([self.SOURCE], [self.MEMBER]))
        self.assertNotIn(O1, self.sql([{**self.SOURCE, "synthetic": False}], [self.MEMBER]))
        for flag in (None, "false", 0, ""):
            self.assertIn(O1, self.sql([{**self.SOURCE, "synthetic": flag}], [self.MEMBER]), repr(flag))
        self.assertIn(O1, self.sql([{k: v for k, v in self.SOURCE.items() if k != "synthetic"}], [self.MEMBER]))

    def test_o2_failing_cases_and_control(self):
        self.assertIn(O2, self.sql([self.SOURCE], [self.MEMBER]))                                   # no terms check
        negative = {**PERMITTING, "permits_internal_development_use": False}
        for label, check in {"negative": negative, "string": {**PERMITTING, "permits_internal_development_use": "true"},
                             "blank checker": {**PERMITTING, "checked_by": " "}, "bad date": {**PERMITTING, "checked_on": "2001-13-45"},
                             "text date": {**PERMITTING, "checked_on": "soon"}, "list": [PERMITTING], "text": "permits"}.items():
            self.assertIn(O2, self.sql([{**self.SOURCE, "terms_check": check}], [self.MEMBER]), label)
        control = self.sql([{**self.SOURCE, "terms_check": PERMITTING}], [self.MEMBER])
        self.assertNotIn(O2, control)
        self.assertIn(O1, control)                                                                  # synthetic: still O1 (O2 does not exempt it)

    def test_o3_failing_cases_and_control(self):
        self.assertIn(O3, self.sql([self.SOURCE], [self.MEMBER]))
        for label, change in {"agent": dict(retrieved_by="agent"), "v2": dict(schema="v2"), "usage": dict(usage_scope="LICENSED_DISPLAY"),
                              "synthetic usage": dict(usage_scope="SYNTHETIC_TEST")}.items():
            self.assertIn(O3, self.sql([self.SOURCE], [{**self.HUMAN, **change}]), label)
        self.assertNotIn(O3, self.sql([self.SOURCE], [self.HUMAN]))                                 # the control
        self.assertIn(O3, self.sql([self.SOURCE], [self.HUMAN, {**self.HUMAN, "manifest_sha256": "b" * 64, "retrieved_by": "agent"}]))

    def test_no_evidence_fails_closed_and_every_failure_is_reported(self):
        self.assertEqual(self.sql([], []), (O1, O2, O3))
        self.assertEqual(self.sql([self.SOURCE], [self.MEMBER]), (O1, O2, O3))

    def test_the_predicates_are_independent(self):
        passing_o1 = {**self.SOURCE, "synthetic": False}
        passing_o2 = {**self.SOURCE, "terms_check": PERMITTING}
        self.assertEqual(self.sql([passing_o1], [self.MEMBER]), (O2, O3))
        self.assertEqual(self.sql([passing_o2], [self.MEMBER]), (O1, O3))
        self.assertEqual(self.sql([self.SOURCE], [self.HUMAN]), (O1, O2))
        self.assertEqual(self.sql([{**self.SOURCE, "synthetic": False, "terms_check": PERMITTING}], [self.HUMAN]), ())

    def test_sql_and_python_agree_on_a_grid_of_inputs(self):
        sources = {"none": [], "synthetic": [self.SOURCE], "real": [{**self.SOURCE, "synthetic": False}],
                   "real+permit": [{**self.SOURCE, "synthetic": False, "terms_check": PERMITTING}],
                   "synthetic+permit": [{**self.SOURCE, "terms_check": PERMITTING}],
                   "real+negative": [{**self.SOURCE, "synthetic": False, "terms_check": {**PERMITTING, "permits_internal_development_use": False}}],
                   "real+bad date": [{**self.SOURCE, "synthetic": False, "terms_check": {**PERMITTING, "checked_on": "2001-02-30"}}],
                   "real+blank": [{**self.SOURCE, "synthetic": False, "terms_check": {**PERMITTING, "checked_by": ""}}],
                   "real+one": [{**self.SOURCE, "synthetic": False, "terms_check": {**PERMITTING, "permits_internal_development_use": 1}}],
                   "two mixed": [{**self.SOURCE, "source_id": "a.one", "synthetic": False, "terms_check": PERMITTING},
                                 {**self.SOURCE, "source_id": "b.two", "synthetic": True}],
                   "two real": [{**self.SOURCE, "source_id": "a.one", "synthetic": False, "terms_check": PERMITTING},
                                {**self.SOURCE, "source_id": "b.two", "synthetic": False, "terms_check": PERMITTING}]}
        members = {"none": [], "synthetic": [self.MEMBER], "human": [self.HUMAN], "agent": [{**self.HUMAN, "retrieved_by": "agent"}],
                   "v2": [{**self.HUMAN, "schema": "v2"}], "licensed": [{**self.HUMAN, "usage_scope": "LICENSED_DISPLAY"}],
                   "two": [self.HUMAN, {**self.HUMAN, "manifest_sha256": "b" * 64}],
                   "two mixed": [self.HUMAN, {**self.MEMBER, "manifest_sha256": "b" * 64}]}
        for s_label, s in sources.items():
            for m_label, m in members.items():
                self.assertEqual(self.sql(s, m), origin_report(s, m).failed, (s_label, m_label))

    def test_the_function_writes_nothing_and_cannot_be_called_by_a_role(self):
        before, native = self.rows(), self.rows(native=True)
        self.assertEqual(self.owner.execute("SELECT provolatile FROM pg_proc WHERE oid=to_regprocedure(%s)", (f"{self.s}.rwp_origin(jsonb,jsonb)",)).fetchone()[0], "i")
        self.owner.execute("BEGIN READ ONLY")
        try:
            self.sql([self.SOURCE], [self.MEMBER])                           # a write here would raise "read-only transaction"
        finally:
            self.owner.execute("ROLLBACK")
        self.assertEqual((self.rows(), self.rows(native=True)), (before, native))
        for who in ("loader", "executor", "publisher"):
            conn = self.conn(who)
            self.assertDenied(lambda c=conn: c.execute(f"SELECT {self.s}.rwp_origin('[]'::jsonb,'[]'::jsonb)"))


class RealSourceRecordsFitTheRegistryTests(ProvCase):
    """R8 G2: the terms checks of the three `SOURCES.json` records the HG4 release uses (the tracked file, read; nothing stored) fit the registry's shape rule in
    Python AND in SQL (`rwp_validate_bundle`, called by value in a READ ONLY transaction). The same records with `notes` padded past 1024 bytes are refused by both."""
    INSTALL = "provsrc"
    SOURCES = ("alphavantage.us", "openfigi", "calendar.manual")

    def records(self):
        document = json.loads((Path(__file__).resolve().parents[2] / "data" / "marketdata" / "SOURCES.json").read_text("utf-8"))
        return {r["source_id"]: r for r in document["sources"]}

    def bundle_of(self, record, notes=None):
        check = dict(record["terms_check"])
        if notes is not None:
            check["notes"] = notes
        return candidate(PAYLOAD, scope="REAL", salt="src-" + record["source_id"], v1=True, synthetic=False, terms_check=check, terms_url=record["terms_url"],
                         retrieved_by="human", usage_scope="INTERNAL_DEVELOPMENT_ONLY")

    def validate_sql(self, cand):
        self.owner.execute("BEGIN READ ONLY")
        try:
            return self.owner.execute(f"SELECT {self.s}.rwp_validate_bundle(%s,%s,%s,%s,%s)", (cand.bundle.context_bytes, *self.arrays(cand))).fetchone()[0]
        finally:
            self.owner.execute("ROLLBACK")

    def test_the_three_real_terms_checks_pass_both_validators_and_an_oversized_note_fails_both(self):
        records = self.records()
        for source in self.SOURCES:
            record = records[source]
            self.assertLessEqual(len(record["terms_check"]["notes"].encode("utf-8")), 1024, source)
            cand = self.bundle_of(record)
            with self.subTest(source):
                self.assertTrue(rp.validate_bundle(scope_of("REAL"), cand.bundle, **cand.args()))          # Python: no refusal
                self.assertEqual(list(self.validate_sql(cand)), [])                                         # SQL: no shape error, no failed code
            big = self.bundle_of(record, notes="n" * 1025)
            with self.subTest(source + " oversized"):
                self.assertEqual(self.error_of(lambda: rp.validate_bundle(scope_of("REAL"), big.bundle, **big.args())).code, "RW_PROV_SHAPE")
                self.database_code(lambda: self.validate_sql(big), "RW_PROV_SHAPE")


class CandidateParityTests(ProvCase):
    """A table of structural cases: the Python validator and the SQL put function must give the SAME answer (accepted, or the same code).
    Cases about bytes the two cannot see the same way (a changed envelope's digest, a stored witness) are not in the table."""

    def cases(self, scope):
        s = lambda **kw: candidate(PAYLOAD, scope=scope, salt="parity", **kw)  # noqa: E731
        base = s()
        v1 = s(v1=True)
        sources = json.loads(base.bundle.context_bytes)["source_records"]
        two = s(acquisitions=(1, 2))
        multi = lambda c, **ch: with_context(c, **ch)  # noqa: E731
        return {
            "v2 baseline": (base, None), "v1 baseline": (v1, None), "two acquisitions": (two, None),
            "promotable": (multi(base, promotable=True), "RW_PROV_SCOPE_REFUSED"), "admitted": (multi(base, source_admitted=True), "RW_PROV_SCOPE_REFUSED"),
            "state": (multi(base, state="QUALIFIED"), "RW_PROV_SCOPE_REFUSED"),
            "v1 human": (with_manifest_fields(v1, retrieved_by="human"), "RW_PROV_SCOPE_REFUSED"),
            "v1 internal usage": (with_manifest_fields(v1, usage_scope="INTERNAL_DEVELOPMENT_ONLY"), "RW_PROV_SCOPE_REFUSED"),
            "terms check stored": (s(terms_check=PERMITTING), "RW_PROV_SCOPE_REFUSED"), "terms url stored": (s(terms_url="https://fictional.invalid/t"), "RW_PROV_SCOPE_REFUSED"),
            "mixed origin": (multi(base, source_records=[source_record("a.one", synthetic=True), source_record("b.two", synthetic=False)]), "RW_ORIGIN_MIXED"),
            "unused source": (multi(base, source_records=sources + [dict(sources[0], source_id="unused.source")]), "RW_PROV_BINDING_DIFFERS"),
            "role is not the manifest kind": (with_members(base, (replace(base.members[0], role="QUOTE"),)), "RW_PROV_BINDING_DIFFERS"),
            "duplicate member": (with_members(two, (two.members[0], two.members[0])), "RW_PROV_SHAPE"),
            "unsorted manifests": (replace(two, bundle=replace(two.bundle, manifests=tuple(reversed(two.bundle.manifests)))), "RW_PROV_SHAPE"),
            "no envelope for a v2 member": (replace(base, bundle=replace(base.bundle, envelopes=())), "RW_PROV_INPUT_MISSING"),
            "extra payload": (replace(base, bundle=replace(base.bundle, payloads=tuple(sorted(base.bundle.payloads + ((h(b"extra"), b"extra"),))))), "RW_PROV_BINDING_DIFFERS"),
        }

    def python_code(self, scope, cand):
        try:
            rp.validate_bundle(scope_of(scope), cand.bundle, **cand.args())
        except ProvenanceError as error:
            return error.code
        return None

    def sql_code(self, cand):
        before = self.rows()
        try:
            self.put_sql(self.loader, cand)
        except psycopg.errors.RaiseException as error:
            self.assertEqual(self.rows(), before)                          # refused: nothing partial
            return (error.diag.message_primary or "").splitlines()[0]
        return None

    def test_the_two_validators_give_the_same_answer_on_the_table(self):
        for scope in TEST_SCOPES:
            for label, (cand, expected) in self.cases(scope).items():
                with self.subTest(scope=scope, case=label):
                    self.assertEqual(self.python_code(scope, cand), expected)
                    self.assertEqual(self.sql_code(cand), expected)


class RealScopeCandidateTests(ProvCase):
    """A REAL install: the install-kind guard in both directions, and the origin refusal listing every failed code."""
    INSTALL = "provreal"
    KIND = "REAL"

    def test_a_real_candidate_is_refused_with_every_failed_code_by_both_validators(self):
        for v1 in (True, False):
            cand = candidate(PAYLOAD, scope="REAL", salt="real", v1=v1)
            with self.subTest(v1=v1):
                before = self.rows()
                python = self.error_of(lambda: rp.validate_bundle(scope_of("REAL"), cand.bundle, **cand.args()))
                self.assertEqual((python.code, python.codes[1:]), (rp.ORIGIN_REFUSED, (O1, O2, O3)))
                error = self.database_code(lambda: self.put_sql(self.loader, cand), rp.ORIGIN_REFUSED)
                self.assertEqual(self.detail_codes(error), [O1, O2, O3])
                self.assertEqual(self.rows(), before)
                store_error = self.error_of(lambda: self.save(cand))
                self.assertEqual(store_error.codes, (rp.ORIGIN_REFUSED, O1, O2, O3))
                self.assertEqual(self.rows(), before)

    def test_mixed_origin_is_refused_in_the_real_scope_as_in_the_test_scopes(self):
        cand = with_context(candidate(PAYLOAD, scope="REAL", salt="real-mixed"),
                            source_records=[source_record("a.one", synthetic=True), source_record("b.two", synthetic=False)])
        self.database_code(lambda: self.put_sql(self.loader, cand), "RW_ORIGIN_MIXED")

    def test_a_test_scope_candidate_is_refused_for_the_install_kind(self):
        for scope in TEST_SCOPES:
            cand = candidate(PAYLOAD, scope=scope, salt="kind")
            before = self.rows()
            self.database_code(lambda: self.put_sql(self.loader, cand), "RW_INSTALL_KIND")
            self.assertEqual(self.rows(), before)


class TestInstallRefusesRealCandidatesTests(ProvCase):
    def test_a_real_scope_candidate_is_refused_for_the_install_kind_before_its_origin(self):
        cand = candidate(PAYLOAD, scope="REAL", salt="kind")
        before = self.rows()
        self.database_code(lambda: self.put_sql(self.loader, cand), "RW_INSTALL_KIND")
        self.assertEqual(self.rows(), before)


# =====================================================================================================================
# Candidates are immutable and unreferenced
# =====================================================================================================================
class CandidatesImmutableAndUnreferencedTests(ProvCase):
    TABLES = provstore.TABLES

    def test_no_row_of_the_registry_can_be_changed_or_removed(self):
        live = self.live("TEST_SWITCH")
        samples = {"rwp_payload": "size_bytes=size_bytes", "rwp_acquisition": "envelope=envelope", "rwp_manifest": "manifest=manifest",
                   "rwp_context": "context=context", "rwp_registration": "backend_pid=backend_pid"}
        for table in self.TABLES:
            self.assertGreater(self.count(table), 0, table)
            before = self.count(table)
            for statement in (f"UPDATE {self.s}.{table} SET {samples[table]}", f"DELETE FROM {self.s}.{table}"):
                self.database_code(lambda s=statement: self.owner.execute(s), "RW_PROV_STORAGE_CONFLICT")
            self.assertEqual(self.count(table), before, table)

    def test_truncate_is_refused_by_a_trigger_or_by_the_foreign_key(self):
        self.live("TEST_SWITCH")
        referenced = {"rwp_payload", "rwp_acquisition", "rwp_context"}                    # another table's key points at them: PostgreSQL's own refusal comes first
        for table in self.TABLES:
            before = self.count(table)
            try:
                self.owner.execute(f"TRUNCATE {self.s}.{table}")
            except psycopg.errors.RaiseException as error:
                self.assertEqual(error.diag.message_primary, "RW_PROV_STORAGE_CONFLICT", table)
                self.assertNotIn(table, referenced)
            except psycopg.errors.FeatureNotSupported:
                self.assertIn(table, referenced)
            else:
                self.fail("TRUNCATE succeeded on " + table)
            self.assertEqual(self.count(table), before, table)

    def test_nothing_outside_the_registry_references_a_candidate(self):
        rows = self.owner.execute(
            "SELECT c.conname,r.relname,f.relname FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid JOIN pg_class f ON f.oid=c.confrelid "
            "JOIN pg_namespace n ON n.oid=r.relnamespace WHERE c.contype='f' AND n.nspname=%s AND (f.relname LIKE 'rwp\\_%%' OR r.relname LIKE 'rwp\\_%%')", (self.s,)).fetchall()
        self.assertGreater(len(rows), 0)
        for name, referencing, referenced in rows:
            if referenced.startswith("rwp_"):
                self.assertTrue(referencing.startswith("rwp_"), (name, referencing, referenced))            # only registry tables reference candidates
            else:
                self.assertEqual((referencing, referenced), ("rwp_context", "rw_snapshot"), name)         # the one key that leaves the registry points OUT
        # No view, trigger or function of the md_* or the other gateway tables names a candidate table.
        names = ("rwp_payload", "rwp_acquisition", "rwp_manifest", "rwp_context", "rwp_registration")
        # R3 adds exactly one reader outside the registry: `rw_link_verify`, the seal-side check of the mandatory link (design 2.6 item 4,
        # PD-0059): it READS a registered context and its registration by key; no key of any table points at a candidate.
        definitions = {r[0]: r[1] for r in self.owner.execute(
            "SELECT p.proname,pg_get_functiondef(p.oid) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname=%s "
            "AND p.proname NOT LIKE 'rwp\\_%%' AND p.prokind='f' AND p.prolang=(SELECT oid FROM pg_language WHERE lanname='plpgsql')", (self.s,)).fetchall()}
        readers = sorted(name for name, definition in definitions.items() if any(n in definition for n in names))
        self.assertEqual(readers, ["rw_link_verify"])

    def test_the_whole_gateway_cycle_leaves_every_candidate_row_unchanged(self):
        live = self.live("TEST_SWITCH")
        before = self.rows()
        executor = self.conn("executor")
        self.admit_and_commit(executor, live.ctx, 1, "ARCHIVE_READ", live.owner_id, live.root_id)
        with self.bundle_guard_off():            # E11 crafted for the commit (R3: an unsealed create lease does not commit)
            begin(executor)
            try:
                lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
                self.guarded(executor, lease, live)
                commit(executor)
            finally:
                rollback(executor)
        renewed = self.renew(live.ctx, 1, valid_until=self.db_now() + fx.seconds(200), evidence=fx.hg4_shape(self.bound(), sources=(SOURCE_ID,)))
        self.assertEqual(renewed.status, 0, renewed.text)
        self.assertEqual(self.rows(), before)


# =====================================================================================================================
# The registry's membership refusal (R2 review L-4)
# =====================================================================================================================
class RegistryMembershipTests(ProvCase):
    """`rwp_caller` refuses a registry role that is a member of any role or has any member (`pg_auth_members`, both sides). The kit's
    roles are NOINHERIT, so a membership gives no privilege; the check is what refuses it. Memberships are granted by the DISPOSABLE
    database's administrative role (E11 crafted fixture) and revoked in `finally`, in an install of this class's own."""
    INSTALL = "provmember"

    def probe(self, conn):
        """A put and a get by `conn`; the candidate is registered (or refused) with the same call each time."""
        cand = candidate(PAYLOAD + self.tag("member").encode(), salt=self.tag("member"))
        return (lambda: self.put_sql(conn, cand)), (lambda: self.get_sql(conn, cand.context_sha256, None)), cand

    def assert_refused(self, conn):
        put, get, _cand = self.probe(conn)
        before = self.rows()
        self.database_code(put, "RW_PROV_ROLE_REFUSED")
        self.database_code(get, "RW_PROV_ROLE_REFUSED")
        self.assertEqual(self.rows(), before)

    def test_the_control_without_a_membership_the_loader_registers_and_reads(self):
        put, get, cand = self.probe(self.loader)
        put()
        self.assertIsNotNone(get())                                  # the read side passes the role check too
        self.assertEqual(self.count("rwp_context", "context_sha256=%s", (cand.context_sha256,)), 1)

    def test_a_role_that_is_a_member_of_the_loader_makes_the_loader_refused_and_is_itself_refused(self):
        self.inst.set_membership("publisher", "loader", True)
        try:
            self.assert_refused(self.loader)                     # the loader now has a member (`roleid = loader`)
            member = self.conn("publisher")
            member.execute(f'SET ROLE "{self.inst.roles["loader"]}"')           # a member may SET ROLE to the loader
            self.assert_refused(member)                          # session_user is the member, not the loader
        finally:
            self.inst.set_membership("publisher", "loader", False)
        put, _get, cand = self.probe(self.loader)
        put()                                                    # revoked: the same session registers again
        self.assertEqual(self.count("rwp_context", "context_sha256=%s", (cand.context_sha256,)), 1)

    def test_a_loader_that_is_a_member_of_another_role_is_refused(self):
        self.inst.set_membership("loader", "publisher", True)
        try:
            self.assert_refused(self.loader)                     # the loader is a member (`member = loader`)
        finally:
            self.inst.set_membership("loader", "publisher", False)
        put, _get, cand = self.probe(self.loader)
        put()
        self.assertEqual(self.count("rwp_context", "context_sha256=%s", (cand.context_sha256,)), 1)

    def test_the_executors_membership_refuses_its_guarded_load_the_same_way(self):
        live = self.live("TEST_SWITCH")
        self.inst.set_membership("executor", "publisher", True)
        try:
            executor = self.conn("executor")
            begin(executor)
            try:
                lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
                self.assertEqual(self.error_of(lambda: self.guarded(executor, lease, live)).code, "RW_PROV_ROLE_REFUSED")
            finally:
                rollback(executor)
        finally:
            self.inst.set_membership("executor", "publisher", False)
        executor = self.conn("executor")
        begin(executor)
        try:
            lease = self.admit(executor, live.ctx, 1, "EXECUTE_CREATE", live.owner_id, live.root_id)
            self.assertEqual(self.guarded(executor, lease, live).bundle, live.cand.bundle)         # revoked: the control loads
        finally:
            rollback(executor)


# =====================================================================================================================
# The loader and LOGIN: exit statement R2 (b)
# =====================================================================================================================
class LoaderWithoutLoginTests(ProvCase):
    """EXIT STATEMENT (b): the install and the per-call checks and a loader that cannot log in. The installer accepts a loader without
    LOGIN; the registry's per-call check REQUIRES LOGIN, so a loader the owner has set NOLOGIN registers and reads nothing, even from
    a session opened earlier. (PD-0070 decision 1: the owner sets the loader NOLOGIN while no load runs and LOGIN for the load.)"""
    INSTALL = "provnologin"
    LOADER_LOGIN = False

    def test_the_install_with_a_nologin_loader_succeeded_and_its_check_passes_again(self):
        flags = self.owner.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname=%s", (self.inst.roles["loader"],)).fetchone()
        self.assertEqual(flags, (False,))
        # The installer's catalog check, run again by the owner on the installed objects.
        r = self.inst.roles
        with self.owner.transaction():
            provstore.verify_registry_install(self.owner, self.s, r["owner"], r["executor"], r["loader"], r["publisher"])

    def test_a_loader_that_cannot_log_in_cannot_connect(self):
        prov = KIT.prov
        with self.assertRaises(psycopg.OperationalError):
            psycopg.connect(prov.dsn(prov.db, self.inst.roles["loader"], "irrelevant"), connect_timeout=5)

    def test_the_loader_registers_after_the_publish_once_login_is_enabled_and_is_refused_again_when_it_is_disabled(self):
        salt = self.tag("login")
        payload = PAYLOAD + salt.encode()
        unbound = candidate(payload, scope="TEST_SWITCH", salt=salt)
        snap = self.snapshot_for(unbound, "TEST_SWITCH")
        self.publish(snap, valid_in=120.0, evidence=fx.hg4_shape(self.bound(), sources=(SOURCE_ID,)))
        bound = candidate(payload, scope="TEST_SWITCH", salt=salt, financial_context=snap.context_id)
        self.inst.set_login("loader", True)
        try:
            loader = self.inst.connect("loader")
            self.addCleanup(loader.close)
            registry = provstore.RealProvenanceStore(loader, self.s, loader_role=self.inst.roles["loader"])
            _, saved = self.save(bound, registry=registry)
            self.assertIsInstance(saved, provstore.CommittedRegistration)
            self.assertEqual(self.load(bound, registry=registry).bundle, bound.bundle)
        finally:
            self.inst.set_login("loader", False)
        # The session opened while LOGIN was on is still open. The registry's per-call check now refuses it, on put and on get.
        self.assertEqual(loader.execute("SELECT current_user::text").fetchone()[0], self.inst.roles["loader"])
        again = candidate(payload + b"2", scope="TEST_SWITCH", salt=salt)
        before = self.rows()
        self.assertEqual(self.error_of(lambda: self.save(again, registry=registry)).code, "RW_PROV_ROLE_REFUSED")
        self.assertEqual(self.error_of(lambda: self.load(bound, registry=registry)).code, "RW_PROV_ROLE_REFUSED")
        self.database_code(lambda: self.put_sql(loader, again), "RW_PROV_ROLE_REFUSED")
        self.database_code(lambda: self.get_sql(loader, bound.context_sha256, None), "RW_PROV_ROLE_REFUSED")
        self.assertEqual(self.rows(), before)

    def test_the_executors_guarded_load_does_not_depend_on_the_loaders_login(self):
        live_salt = self.tag("exec")
        payload = PAYLOAD + live_salt.encode()
        unbound = candidate(payload, scope="TEST_SWITCH", salt=live_salt)
        snap = self.snapshot_for(unbound, "TEST_SWITCH")
        self.publish(snap, valid_in=120.0, evidence=fx.hg4_shape(self.bound(), sources=(SOURCE_ID,)))
        bound = candidate(payload, scope="TEST_SWITCH", salt=live_salt, financial_context=snap.context_id)
        self.inst.set_login("loader", True)
        try:
            loader = self.inst.connect("loader")
            self.addCleanup(loader.close)
            self.save(bound, registry=provstore.RealProvenanceStore(loader, self.s, loader_role=self.inst.roles["loader"]))
        finally:
            self.inst.set_login("loader", False)
        owner_id, root_id = self.craft_root(snap.context_id)
        executor = self.conn("executor")
        begin(executor)
        try:
            lease = self.admit(executor, snap.context_id, 1, "EXECUTE_CREATE", owner_id, root_id)
            context = provstore.load_guarded(executor, self.s, self.inst.roles["executor"], lease, bound.context_sha256,
                                             expected_members=bound.members, witnesses=bound.witnesses)
            self.assertEqual(context.bundle, bound.bundle)
        finally:
            rollback(executor)


if __name__ == "__main__":
    import unittest
    unittest.main()
