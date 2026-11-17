"""F1 R3, PostgreSQL: the gateway SEAL for both branches, the BUNDLE GUARD, the mandatory LINK, the ARCHIVE, replay, O4 and the origin-label row
guard.

Design 7.1 R3 row, 4.2 build table, 4.4. EVERY test here runs on an E11 CRAFTED PROBE: the bundle is written through the executor role's own
connection by `real_bundle_probe` (R3 has no create code; R5 builds it), with the bytes built from the format the SQL checks. Each test is
therefore marked "E11 crafted probe, not product evidence" in its docstring. What the probes show is the SQL: that a complete, linked bundle
seals and commits atomically, that the same bundle with any one part wrong does not, that a refused COMMIT leaves no row, and that a
committed bundle survives the connection that wrote it. R3 has no outcome code and claims nothing about a product create, about the real
branch's accepted side (invented data is never `synthetic = false`; the first accepted real result is R8) or about acknowledgement loss.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402

import real_gateway_fixtures as fx  # noqa: E402
from real_bundle_probe import AS_OF, ProbeMixin, canon, sha  # noqa: E402
from real_gateway_kit import Worker, begin, commit, rollback, setUpModule, tearDownModule, wait_until  # noqa: E402,F401
from real_provenance_case import ProvCase  # noqa: E402

PROBE = "E11 crafted probe, not product evidence"


class SealCase(ProbeMixin, ProvCase):
    INSTALL = "seal"
    W = 30

    def tables_for(self, root_id):
        """Row counts of every table the create writes, for one root, read by the trusted owner connection."""
        queries = {
            "portfolio": ("portfolio", "portfolio_id=%s"), "rw_root": ("rw_root", "portfolio_id=%s"), "rw_revision": ("rw_revision", "portfolio_id=%s"),
            "account": ("account", "portfolio_id=%s"), "rw_root_link": ("rw_root_link", "root_id=%s"), "rw_lease": ("rw_lease", "root_id=%s"),
            "rw_artifact": ("rw_artifact", "root_id=%s"), "rw_operation": ("rw_operation", "root_id=%s"), "rw_journal": ("rw_journal", "root_id=%s"),
            "ledger_event": ("ledger_event", "account_id IN (SELECT account_id FROM %s.account WHERE portfolio_id=%%s)" % self.s),
        }
        return {name: self.count(table, where, (root_id,)) for name, (table, where) in queries.items()}

    def assertNothingLeft(self, root_id):
        self.assertEqual(set(self.tables_for(root_id).values()), {0}, self.tables_for(root_id))

    def refused_seal(self, setup, code, *, detail=None, scope_edit=None, **kw):
        """Open a create, write the bundle with `kw`, seal it and expect `code`; rolls back and checks that nothing is left."""
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op, **kw)
            error = self.assertRefused(code, lambda: self.seal(executor, bundle, kw.get("prov", setup.prov)), detail=detail)
        finally:
            rollback(executor)
        self.assertNothingLeft(setup.root_id)
        return error


class AcceptedCreateTests(SealCase):
    def test_a_complete_linked_synthetic_bundle_seals_and_commits_atomically(self):
        """E11 crafted probe, not product evidence (T06 crafted part): root, revision, portfolio, account, ledger event, artifact and operation
        become visible together, the lease is SEALED, and the journal names exactly what was written."""
        setup = self.probe_setup("SYNTHETIC_TEST")
        executor = self.conn("executor")
        op, bundle = self.create_and_commit(executor, setup)
        counts = self.tables_for(setup.root_id)
        self.assertEqual({k: v for k, v in counts.items() if k != "rw_journal"},
                         {"portfolio": 1, "rw_root": 1, "rw_revision": 1, "account": 1, "rw_root_link": 1, "rw_lease": 1, "rw_artifact": 1,
                          "rw_operation": 1, "ledger_event": 1})
        self.assertEqual(counts["rw_journal"], 5)               # portfolio, account, ledger_event, rw_root, rw_revision: one INSERT each
        self.assertEqual(self.owner.execute(f"SELECT phase FROM {self.s}.rw_lease WHERE root_id=%s", (setup.root_id,)).fetchone()[0], "SEALED")
        self.assertEqual(sorted(r[0] for r in self.owner.execute(
            f"SELECT table_name FROM {self.s}.rw_journal WHERE root_id=%s", (setup.root_id,)).fetchall()),
            ["account", "ledger_event", "portfolio", "rw_revision", "rw_root"])
        (stored,) = self.owner.execute(f"SELECT issued,response,envelope,provenance_context_sha256 FROM {self.s}.rw_artifact a JOIN {self.s}.rw_operation o "
                                       "USING(owner_id,operation_id) WHERE a.root_id=%s", (setup.root_id,)).fetchall()
        self.assertEqual((bytes(stored[0]), bytes(stored[1]), bytes(stored[2]), stored[3]), (bundle.issued, bundle.response, bundle.envelope, setup.prov))

    def test_O7_a_response_that_carries_the_claim_record_seals_and_commits_and_is_stored_unchanged(self):
        """E11 crafted probe, not product evidence (O-7, PD-0082 Q1: no SQL change). The REAL branch's stored response carries the claim record under `claim_record` (an object of
        text, lists and objects). The seal requires the response to be the root's and the revision's persisted snapshot and checks named keys of it, not a closed key set, so a
        response with the extra key seals; the bytes archived are the bytes written. Crafted on the SYNTHETIC_TEST scope (the real branch cannot be sealed before R8)."""
        setup = self.probe_setup("SYNTHETIC_TEST", label="claim-record")
        record = {"schema": "finweb.claim_record/1", "valuing": [],
                  "members": [{"data_kind": "QUOTE", "source_id": "invented.source", "payload_sha256": "a" * 64},
                              {"data_kind": "CALENDAR", "source_id": "invented.calendar", "payload_sha256": "b" * 64}]}
        response = self.response_of(setup, claim_record=record)
        op, bundle = self.create_and_commit(self.conn("executor"), setup, response_for_root=response,
                                            edit=lambda p, r=response: p.update(response=json.loads(json.dumps(r))))
        stored = self.owner.execute(f"SELECT a.response, r.snapshot_json, v.snapshot_json FROM {self.s}.rw_artifact a JOIN {self.s}.rw_root r ON r.portfolio_id=a.root_id "
                                    f"JOIN {self.s}.rw_revision v ON v.revision_id=a.revision_id WHERE a.root_id=%s", (setup.root_id,)).fetchone()
        self.assertEqual(bytes(stored[0]), bundle.response)
        self.assertEqual(json.loads(bytes(stored[0]))["claim_record"], record)
        self.assertEqual(json.loads(stored[1])["claim_record"], record)
        self.assertEqual(json.loads(stored[2]), json.loads(bytes(stored[0])))

    def test_h1_the_seal_accepts_exactly_the_bytes_the_existing_fictional_integration_issues(self):
        """Technical review H-1, fictional branch. E11 crafted probe (the write path is crafted: R3 has no create code); the BYTES are not: the
        issued Result, the question and the binding are what `financial_service_integration.issue_local_service` returns when the test calls it,
        sealed unedited and committed. The check below calls the service a second time with the same identifiers and compares: the archived
        bytes are the service's, byte for byte (determinism), and the envelope carries the service's own question and binding bytes."""
        import real_service_producers as producers
        setup = self.probe_setup("SYNTHETIC_TEST", label="h1-fict")
        op, bundle = self.create_and_commit(self.conn("executor"), setup)
        self.assertEqual(bundle.issued, bundle.parts["service_issued_bytes"])                 # nothing edited
        revision, pin = bundle.parts["revision"], bundle.ledger_pin
        again = producers.issue_fictional(owner=setup.owner_id, root=setup.root_id, revision=revision, operation=op, pin=pin, generation=1)
        row = self.owner.execute(f"SELECT issued,envelope FROM {self.s}.rw_artifact WHERE root_id=%s", (setup.root_id,)).fetchone()
        self.assertEqual(bytes(row[0]), again.issued_bytes)
        envelope = json.loads(bytes(row[1]))
        self.assertEqual((bytes.fromhex(envelope["question_hex"]), bytes.fromhex(envelope["binding_hex"])), (again.question_bytes, again.binding_bytes))
        self.assertEqual(json.loads(again.issued_bytes)["manifest"]["valuation_manifest"]["synthetic"], True)     # a fictional result states it

    def test_h1_the_real_branch_is_shown_the_performance_services_own_output_and_refuses_it(self):
        """Technical review H-1, real branch. E11 crafted probe (the write path), service bytes (the output of `performance_service`, reached
        through the integration's PERFORMANCE_SYNTHETIC_REFUSAL selector). Before R8 the only output the real service produces is the refusal of
        the synthetic world, which states synthetic = true: it is sealed to be REFUSED by O4a and by the two bindings that need a release and a
        confirmation policy the refusal does not carry. The ACCEPTED side of the real branch is R8's (no invented result is `synthetic = false`)."""
        import real_service_producers as producers
        setup = self.probe_setup("TEST_SWITCH", label="h1-real")
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op)
            again = producers.issue_real_refusal(owner=setup.owner_id, root=setup.root_id, revision=bundle.parts["revision"], operation=op,
                                                 pin=bundle.ledger_pin, generation=1)
            self.assertEqual(bundle.issued, again)                                              # the service's bytes, unedited
            self.assertEqual(sorted(json.loads(again)), ["manifest", "manifest_id", "metrics", "result_digest"])
            error = self.assertRefused("RW_SEAL_REFUSED", lambda: self.seal(executor, bundle, setup.prov))
        finally:
            rollback(executor)
        # R4b pin change (disposition note 5.3, obligation 3): RW_REAL_REGISTRY_DIFFERS is no longer listed. The probe's snapshot now carries the
        # service world's own source record, and the product builder computes `registry.used_source_digest` with the engine's
        # `source_registry_digest` (R4b), which is what the service puts in `manifest.source_registry_digest`; before R4b the snapshot's digest
        # was over the proposal's own dicts and the code was listed on every real-branch refusal. The other three codes are unchanged: the
        # refusal is of the SYNTHETIC world (O4a), and it carries neither the snapshot's release nor its confirmation policy.
        self.assertEqual(error.diag.message_detail.split(","),
                         ["RW_O4A_SYNTHETIC_RESULT", "RW_REAL_RELEASE_DIFFERS", "RW_REAL_POLICY_DIFFERS"])
        self.assertNothingLeft(setup.root_id)

    def test_a_committed_bundle_is_durable_after_the_writing_connection_drops(self):
        """E11 crafted probe, not product evidence (T09 crafted part, SQL-level only): the connection that wrote the commit is closed, and the
        rows are read back from a new session. This is a fact about PostgreSQL's commit, not about product behaviour (no outcome code)."""
        setup = self.probe_setup("SYNTHETIC_TEST")
        writer = self.inst.connect("executor")
        try:
            begin(writer)
            op = uuid.uuid4()
            lease = self.admit(writer, setup.ctx, 1, "EXECUTE_CREATE", setup.owner_id, setup.root_id, op=op, new_root=True)
            bundle = self.write_all_and_bundle(writer, setup, op)
            self.seal(writer, bundle, setup.prov)
            commit(writer)
            pid = writer.info.backend_pid
        finally:
            writer.close()
        self.assertIsNotNone(lease)
        gone = self.admin.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s", (pid,)).fetchone()[0]
        self.assertEqual(gone, 0)
        self.assertEqual(self.count("rw_artifact", "root_id=%s", (setup.root_id,)), 1)
        self.assertEqual(self.count("rw_root", "portfolio_id=%s", (setup.root_id,)), 1)

    def test_the_bundle_guard_is_the_gate_a_commit_without_a_seal_is_refused_and_leaves_no_row(self):
        """E11 crafted probe, not product evidence (T06/T07 crafted parts): every write is made, the seal is not, and COMMIT is refused with the
        bundle guard's code; the refused COMMIT leaves no row of any table (admit's root link and lease included)."""
        setup = self.probe_setup("SYNTHETIC_TEST")
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            self.write_all_and_bundle(executor, setup, op)
            self.assertRefused("RW_UNSEALED", lambda: commit(executor))
        finally:
            rollback(executor)
        self.assertNothingLeft(setup.root_id)

    def test_an_open_create_lease_with_no_writes_cannot_commit_either(self):
        """E11 crafted probe, not product evidence: an EXECUTE_CREATE lease commits only sealed, so an empty create is refused at COMMIT. (With no
        portfolio row the registered root's deferred foreign key is refused first; with the portfolio written, the bundle guard is.)"""
        setup = self.probe_setup("SYNTHETIC_TEST")
        executor = self.conn("executor")
        try:
            self.open_create(executor, setup)
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                commit(executor)
        finally:
            rollback(executor)
        self.assertNothingLeft(setup.root_id)
        try:
            self.open_create(executor, setup)
            self.write_portfolio(executor, setup)
            self.assertRefused("RW_UNSEALED", lambda: commit(executor))
        finally:
            rollback(executor)
        self.assertNothingLeft(setup.root_id)

    def test_the_seal_is_only_for_an_open_create_lease(self):
        """E11 crafted probe, not product evidence: a read lease cannot seal, and a sealed lease cannot seal twice."""
        setup = self.probe_setup("SYNTHETIC_TEST")
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op)
            self.seal(executor, bundle, setup.prov)
            self.assertRefused("RW_SEAL_REFUSED", lambda: self.seal(executor, bundle, setup.prov), detail="LEASE")
        finally:
            rollback(executor)
        self.assertNothingLeft(setup.root_id)
        reader = self.conn("executor")
        live = self.live("SYNTHETIC_TEST")
        begin(reader)
        try:
            self.admit(reader, live.ctx, 1, "ARCHIVE_READ", live.owner_id, live.root_id)
            self.assertRefused("RW_SEAL_REFUSED", lambda: reader.execute(
                f"SELECT {self.s}.rw_seal(%s,%s,%s,%s,%s)", (uuid.uuid4(), b"{}", b"{}", b"{}", live.cand.context_sha256)), detail="LEASE")
        finally:
            rollback(reader)


class MandatoryLinkTests(SealCase):
    """Case B06 / PD-0059: a sealed create stands on exactly one registered provenance candidate bound to the lease's context."""

    def test_the_seal_refuses_without_a_registered_candidate_of_this_context(self):
        """E11 crafted probe, not product evidence. Each refusal leaves nothing behind; the control is the accepted create above."""
        setup = self.probe_setup("SYNTHETIC_TEST")
        other = self.live("SYNTHETIC_TEST", label="other")
        for label, prov, code in (("no digest", None, "RW_LINK_MISSING"), ("an unregistered digest", "0" * 64, "RW_LINK_MISSING"),
                                  ("not a digest", "not-a-digest", "RW_LINK_MISSING"),
                                  ("another context's candidate", other.cand.context_sha256, "RW_LINK_DIFFERS")):
            with self.subTest(label):
                executor = self.conn("executor")
                op = uuid.uuid4()
                try:
                    self.open_create(executor, setup, op)
                    bundle = self.write_all_and_bundle(executor, setup, op)
                    self.assertRefused(code, lambda p=prov: self.seal(executor, bundle, p))
                finally:
                    rollback(executor)
                self.assertNothingLeft(setup.root_id)

    def test_an_ordinary_lease_without_the_link_never_commits(self):
        """E11 crafted probe, not product evidence (T03: 'ordinary lease without the link refused'): a context that was published and never had a
        candidate registered, a lease admitted on it, a full bundle written, and no digest the registry knows. The create cannot seal, so it cannot commit."""
        snap, _valid, _result = self.publish(scope="SYNTHETIC_TEST")
        owner_id, root_id = uuid.uuid4(), uuid.uuid4()
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
        from real_bundle_probe import Setup
        setup = Setup(None, owner_id, root_id, "SYNTHETIC_TEST", snap.context_id, "1" * 64, snap.content)
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op)
            self.assertRefused("RW_LINK_MISSING", lambda: self.seal(executor, bundle, "1" * 64))
            rollback(executor)
            begin(executor)
            self.admit(executor, setup.ctx, 1, "EXECUTE_CREATE", owner_id, root_id, op=uuid.uuid4(), new_root=True)
            self.write_portfolio(executor, setup)
            self.assertRefused("RW_UNSEALED", lambda: commit(executor))
        finally:
            rollback(executor)
        self.assertNothingLeft(root_id)

    def test_a_candidate_with_other_members_than_the_snapshot_is_refused(self):
        """E11 crafted probe, not product evidence: the registered candidate must name the same members as the published snapshot."""
        live = self.live("SYNTHETIC_TEST", label="members")
        setup = self.probe_setup("SYNTHETIC_TEST", label="members2")
        # a second candidate registered for the first context's digest, with a different payload set, cannot bind: the registry refuses it,
        # so the link check's own member comparison is shown on a crafted registry row instead
        self.assertNotEqual(live.cand.context_sha256, setup.prov)
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op)
            self.assertRefused("RW_LINK_DIFFERS", lambda: self.seal(executor, bundle, live.cand.context_sha256))
        finally:
            rollback(executor)
        self.assertNothingLeft(setup.root_id)

    def craft_candidate(self, setup, mutate):
        """E11 crafted registry rows: a COPY of the setup's registered candidate with `mutate(document)` applied, stored under its own digest and
        bound to the SAME financial context, with a registration row. The owner role of the disposable database writes them (the registry's
        put function would refuse the members; nothing else refuses the INSERT). Returns the new candidate digest."""
        raw = bytes(self.owner.execute(f"SELECT context FROM {self.s}.rwp_context WHERE context_sha256=%s", (setup.prov,)).fetchone()[0])
        document = json.loads(raw)
        mutate(document)
        data = canon(document)
        digest = sha(data)
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.rwp_context(context_sha256,context,financial_context_sha256) VALUES(%s,%s,%s)", (digest, data, setup.ctx))
            self.owner.execute(
                f"INSERT INTO {self.s}.rwp_registration(operation_id,request,request_sha256,context_sha256,response,response_sha256,backend_pid,xid,committed_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,1,'crafted',now())", (uuid.uuid4(), b"{}", sha(b"{}"), digest, b"{}", sha(b"{}")))
        return digest

    def test_the_link_compares_the_candidates_members_with_the_snapshots(self):
        """E11 crafted probe, not product evidence (technical review L-4: the member comparison of `rw_link_verify` was a surviving mutant). A
        candidate that is registered, bound to this very context, of the right scope and state, and differs ONLY in its members is refused at
        the seal with RW_LINK_DIFFERS. The control differs from it by an extra key alone (same members) and seals and commits."""
        setup = self.probe_setup("SYNTHETIC_TEST", label="members-cmp")
        import dataclasses
        for label, mutate in (("a member's payload differs", lambda d: d["members"][0].update(payload_sha256="0" * 64)),
                              ("a member's manifest differs", lambda d: d["members"][0].update(manifest_sha256="0" * 64)),
                              ("a member is missing", lambda d: d["members"].pop()),
                              ("a member is added", lambda d: d["members"].append(dict(d["members"][0], payload_sha256="f" * 64)))):
            with self.subTest(label):
                digest = self.craft_candidate(setup, mutate)
                executor = self.conn("executor")
                op = uuid.uuid4()
                try:
                    self.open_create(executor, setup, op)
                    bundle = self.write_all_and_bundle(executor, setup, op)
                    self.assertRefused("RW_LINK_DIFFERS", lambda: self.seal(executor, bundle, digest))
                finally:
                    rollback(executor)
                self.assertNothingLeft(setup.root_id)
        control = self.craft_candidate(setup, lambda d: d.update(note="crafted copy, same members"))
        op, _bundle = self.create_and_commit(self.conn("executor"), dataclasses.replace(setup, prov=control))
        self.assertEqual(self.count("rw_artifact", "root_id=%s", (setup.root_id,)), 1)

    def test_a_link_changed_after_the_commit_is_refused_by_the_archive(self):
        """E11 crafted probe, not product evidence: the archive re-verifies the link of the stored operation. The operation row is edited by the owner
        role with the row-immutability trigger switched off (a crafted drift), and the archive read then refuses."""
        setup = self.probe_setup("SYNTHETIC_TEST")
        executor = self.conn("executor")
        op, _bundle = self.create_and_commit(executor, setup)
        reader = self.conn("executor")
        self.admit_and_commit(reader, setup.ctx, 1, "ARCHIVE_READ", setup.owner_id, setup.root_id)
        begin(reader)
        try:
            self.admit(reader, setup.ctx, 1, "ARCHIVE_READ", setup.owner_id, setup.root_id)
            self.assertEqual(len(reader.execute(f"SELECT * FROM {self.s}.rw_archive(%s,%s)", (setup.owner_id, op)).fetchall()), 1)      # the control
        finally:
            rollback(reader)
        with self.owner.transaction():
            self.owner.execute(f"ALTER TABLE {self.s}.rw_operation DISABLE TRIGGER rw_immutable")
            self.owner.execute(f"UPDATE {self.s}.rw_operation SET provenance_context_sha256=%s WHERE operation_id=%s", ("2" * 64, op))
            self.owner.execute(f"ALTER TABLE {self.s}.rw_operation ENABLE TRIGGER rw_immutable")
        begin(reader)
        try:
            self.admit(reader, setup.ctx, 1, "ARCHIVE_READ", setup.owner_id, setup.root_id)
            self.assertRefused("RW_LINK_MISSING", lambda: reader.execute(f"SELECT * FROM {self.s}.rw_archive(%s,%s)", (setup.owner_id, op)))
        finally:
            rollback(reader)


class O4AndLabelTests(SealCase):
    """O4a, O4b and the origin-label row guard (design 4.2). The ACCEPTED side of the real branch needs a result with synthetic = false, which
    invented data never has (the first one is R8), so R3 shows the real branch's REFUSALS and the fictional branch's acceptance."""

    def test_the_test_switch_branch_is_refused_by_o4a_and_never_accepted(self):
        """E11 crafted probe, not product evidence: a TEST_SWITCH create runs the REAL branch on synthetic data. Its result states synthetic = true,
        so O4a refuses it; no bundle of that scope seals."""
        setup = self.probe_setup("TEST_SWITCH")
        error = self.refused_seal(setup, "RW_SEAL_REFUSED", detail="RW_O4A_SYNTHETIC_RESULT")
        self.assertNotIn("RW_O4B_F8B_MODE", error.diag.message_detail.split(","))                # the refusal's split detection is the dry run

    def test_a_test_switch_result_that_claims_synthetic_false_is_a_label_mismatch(self):
        """E11 crafted probe, not product evidence: invented data is never marked synthetic = false. A TEST_SWITCH result that says so passes O4a and
        is refused by the origin-label guard (the result's flag is the scope's axis), so the first accepted false is a real run's alone."""
        setup = self.probe_setup("TEST_SWITCH", label="false")
        error = self.refused_seal(setup, "RW_SEAL_REFUSED", detail="RW_ORIGIN_MISMATCH", synthetic=False)
        self.assertNotIn("RW_O4A_SYNTHETIC_RESULT", error.diag.message_detail.split(","))

    def test_o4a_reads_the_manifest_flag_and_every_metric_flag_each_on_its_own(self):
        """E11 crafted probe, not product evidence. The performance service states `synthetic` on the manifest and on each metric; O4a fails
        when ANY of them is not false. Each place is isolated: the manifest says false and the metrics say true, then the reverse, then one
        metric of several. (A mutant that read only one of the two places passed the first version of this module.)"""
        setup = self.probe_setup("TEST_SWITCH", label="o4a-each")

        def manifest_only(p):
            p["issued"]["manifest"]["synthetic"] = False

        def metrics_only(p):
            for metric in p["issued"]["metrics"]:
                metric["synthetic"] = False

        for label, edit in (("the manifest alone says false", manifest_only), ("every metric says false, the manifest true", metrics_only)):
            with self.subTest(label):
                error = self.refused_seal(setup, "RW_SEAL_REFUSED", edit=edit)
                self.assertIn("RW_O4A_SYNTHETIC_RESULT", error.diag.message_detail.split(","))
                self.assertIn("RW_ORIGIN_MISMATCH", error.diag.message_detail.split(","))                # and the label guard, which reads the same flags

    def test_the_real_branchs_release_and_policy_bindings_hold_when_the_manifest_carries_the_snapshots(self):
        """E11 crafted probe, not product evidence. The real branch's two bindings compare fields of the service's manifest with the snapshot:
        `release_id` (or `parent_release_id`) and the F8B confirmation policy's digest (`detection_policy`). The refusal the performance service
        issues carries neither (its codes are listed above); with both set to the snapshot's, those two codes are gone and only O4a remains.
        This is the one place the bindings are shown to PASS: the real branch has no accepted bundle before R8."""
        import real_service_producers as producers
        release_id, policy_digest = producers.service_constants()
        setup = self.probe_setup("TEST_SWITCH", label="bindings")
        self.assertEqual(setup.snapshot["release"]["release_id"], release_id)
        self.assertEqual(setup.snapshot["f8b_policy_digest"], policy_digest)
        for label, edit in (("release_id", lambda p: p["issued"]["manifest"].update(release_id=release_id)),
                            ("parent_release_id", lambda p: p["issued"]["manifest"].update(parent_release_id=release_id))):
            def both(p, edit=edit):
                edit(p)
                p["issued"]["manifest"]["detection_policy"] = [["digest", policy_digest]]
                p["issued"]["manifest"]["source_registry_digest"] = setup.snapshot["registry"]["used_source_digest"]       # (5.3: passes)
            with self.subTest(label):
                error = self.refused_seal(setup, "RW_SEAL_REFUSED", edit=both)
                self.assertEqual(error.diag.message_detail.split(","), ["RW_O4A_SYNTHETIC_RESULT"])
        def manifest(release=None, policy=None, parent=None):
            def edit(p):
                m = p["issued"]["manifest"]
                m["source_registry_digest"] = setup.snapshot["registry"]["used_source_digest"]                           # (5.3: passes)
                if release is not None:
                    m["release_id"] = release
                if parent is not None:
                    m["parent_release_id"] = parent
                if policy is not None:
                    m["detection_policy"] = policy
            return edit
        right = [["digest", policy_digest]]
        wrong = "0" * 64
        for label, edit, codes in (
                ("a release without a policy", manifest(release=release_id), ["RW_REAL_POLICY_DIFFERS"]),
                ("a policy without a release", manifest(policy=right), ["RW_REAL_RELEASE_DIFFERS"]),
                ("another release", manifest(release=wrong, policy=right), ["RW_REAL_RELEASE_DIFFERS"]),
                ("another policy digest", manifest(release=release_id, policy=[["digest", wrong]]), ["RW_REAL_POLICY_DIFFERS"]),
                ("the policy's tag is not 'digest'", manifest(release=release_id, policy=[["hash", policy_digest]]), ["RW_REAL_POLICY_DIFFERS"]),
                ("the parent release is the snapshot's and release_id is not (the parent is read first)", manifest(release=wrong, parent=release_id, policy=right), []),
                ("the parent release is not the snapshot's and release_id is", manifest(release=release_id, parent=wrong, policy=right), ["RW_REAL_RELEASE_DIFFERS"])):
            with self.subTest(label):
                error = self.refused_seal(setup, "RW_SEAL_REFUSED", edit=edit)
                self.assertEqual(error.diag.message_detail.split(","), ["RW_O4A_SYNTHETIC_RESULT"] + codes)

    def test_the_real_branch_binds_the_snapshots_projection_digest_to_the_database(self):
        """E11 crafted probe, not product evidence (disposition 5.1). The seal reads `md_release.projection_digest` for the snapshot's release and
        compares it with the snapshot's. Control: the service world's release is stored (a crafted row) with the digest the snapshot carries, and
        the code is absent. Failing cases: a snapshot that carries another digest than the stored one; a release the database does not hold (no
        row refuses)."""
        unstored = hashlib.sha256(b"a release this database does not hold").hexdigest()
        for label, kw, present in (("the stored digest equals the snapshot's", {}, False),
                                   ("the snapshot carries another digest", {"projection": "9" * 64}, True),
                                   ("the release is not stored", {"release_id": unstored}, True)):
            with self.subTest(label):
                setup = self.probe_setup("TEST_SWITCH", label="proj-" + label[4:9], **kw)
                error = self.refused_seal(setup, "RW_SEAL_REFUSED")
                self.assertEqual("RW_REAL_PROJECTION_DIFFERS" in error.diag.message_detail.split(","), present)

    def test_the_real_branch_binds_the_registry_digest_the_service_issued_to_the_snapshots(self):
        """E11 crafted probe, not product evidence (disposition 5.3). `manifest.source_registry_digest` must equal the snapshot's
        `registry.used_source_digest`. R4b changed the expected value of one case: the probe's snapshot now carries the service world's own source
        record and the product builder computes the snapshot's digest with the engine's `source_registry_digest` (R4b obligation 1), so the
        digest the SERVICE issues is the snapshot's and the code is ABSENT without any edit (it was listed on every real-branch output before).
        The pre-R4b encoding (a digest of the proposal's own record dicts) is added as a failing case: it is not the engine's."""
        import hashlib
        from marketdata.canonical import canonical_json
        setup = self.probe_setup("TEST_SWITCH", label="registry")
        used = setup.snapshot["registry"]["used_source_digest"]
        old_encoding = hashlib.sha256(canonical_json(setup.snapshot["source_records"]).encode("utf-8")).hexdigest()
        self.assertNotEqual(old_encoding, used)
        for label, value, present in (("the service's own digest", None, False), ("the snapshot's digest", used, False),
                                      ("another digest", "0" * 64, True), ("the full-registry digest", setup.snapshot["registry"]["full_registry_digest"], None),
                                      ("the digest of the proposal's own record dicts (the encoding before R4b)", old_encoding, True),
                                      ("empty", "", True)):
            with self.subTest(label):
                def edit(p, value=value):
                    if value is not None:
                        p["issued"]["manifest"]["source_registry_digest"] = value
                error = self.refused_seal(setup, "RW_SEAL_REFUSED", edit=edit)
                if present is not None:
                    self.assertEqual("RW_REAL_REGISTRY_DIFFERS" in error.diag.message_detail.split(","), present)

    def test_the_real_branch_binds_the_snapshots_members_to_the_releases_files(self):
        """E11 crafted probe, not product evidence (re-review RR-L4). The manifest's source registry digest covers the sources with a file in the
        release the database holds; the snapshot's is over its members' sources. The seal therefore compares the snapshot's members (file hash and
        source id) with the release's files (`md_release_file` joined to `md_file`), read from the database. The probe makes the crafted release's
        files those of each case (`setup.release_files`) before the bundle is made. Control: the files equal the members (code absent). Failing
        cases: the release holds a further file (of a source no member names, and of a member's source), lacks the member, holds the member's hash
        under another source, holds another file of the member's source, and the release is not stored at all."""
        cases = (
            ("the release's files are the snapshot's members", lambda files, base: files, False),
            ("the release holds a further file of a source no member names", lambda files, base: files + [(hashlib.sha256(b"extra/" + base).hexdigest(), "syn.other")], True),
            ("the release holds a further file of a member's source", lambda files, base: files + [(hashlib.sha256(b"extra/" + base).hexdigest(), files[0][1])], True),
            ("the release lacks the member", lambda files, base: [], True),
            ("the release holds the member's hash under another source", lambda files, base: [(files[0][0], "syn.other")], True),
            ("the release holds another file of the member's source", lambda files, base: [(hashlib.sha256(b"other/" + base).hexdigest(), files[0][1])], True),
        )
        for n, (label, change, present) in enumerate(cases):
            with self.subTest(label):
                setup = self.probe_setup("TEST_SWITCH", label="members-%d" % n)
                setup.release_files = change(list(setup.release_files), setup.ctx.encode())
                error = self.refused_seal(setup, "RW_SEAL_REFUSED")
                self.assertEqual("RW_REAL_MEMBERS_DIFFER" in error.diag.message_detail.split(","), present)
        with self.subTest("the release is not stored"):
            setup = self.probe_setup("TEST_SWITCH", label="members-unstored", release_id=hashlib.sha256(b"a release this database does not hold").hexdigest())
            error = self.refused_seal(setup, "RW_SEAL_REFUSED")
            self.assertIn("RW_REAL_MEMBERS_DIFFER", error.diag.message_detail.split(","))

    def test_the_stored_result_must_carry_the_roots_origin_labels(self):
        """E11 crafted probe, not product evidence (disposition 5.4, built for either answer on the wording). The gateway's `response` carries the
        four origin labels and the seal compares them with the stored root's. The root row and the revision hold the same (edited) response, so the
        structural response checks pass and only this conjunct can refuse: a missing origin, one label changed, an extra key, the other axis."""
        for scope in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            setup = self.probe_setup(scope, label="resp-origin-" + scope)
            good = self.response_of(setup)["origin"]
            cases = (("missing", lambda r: r.pop("origin")),
                     ("personal_holdings changed", lambda r: r["origin"].update(personal_holdings=True)),
                     ("market_origin changed", lambda r: r["origin"].update(market_origin="OTHER")),
                     ("ledger_origin changed", lambda r: r["origin"].update(ledger_origin="OTHER")),
                     ("synthetic (inside origin) flipped", lambda r: r["origin"].update(synthetic=not r["origin"]["synthetic"])),
                     ("personal_holdings absent", lambda r: r["origin"].pop("personal_holdings")),
                     ("ledger_origin absent", lambda r: r["origin"].pop("ledger_origin")),
                     ("market_origin absent", lambda r: r["origin"].pop("market_origin")),
                     ("synthetic (inside origin) absent", lambda r: r["origin"].pop("synthetic")),
                     ("an extra key", lambda r: r["origin"].update(extra=1)),
                     ("null", lambda r: r.update(origin=None)),
                     ("the other axis", lambda r: r.update(origin={"market_origin": "REAL_SOURCE", "ledger_origin": "PROJECT_CONSTRUCTED_NONPERSONAL_UAT",
                                                                    "personal_holdings": False, "synthetic": False})))
            for label, change in cases:
                with self.subTest(scope + ": " + label):
                    response = self.response_of(setup)
                    change(response)
                    error = self.refused_seal(setup, "RW_SEAL_REFUSED", response_for_root=response, edit=lambda p, r=response: p.update(response=json.loads(json.dumps(r))))
                    self.assertIn("RW_ORIGIN_MISMATCH", error.diag.message_detail.split(","))
            self.assertEqual(good, self.response_of(setup)["origin"])

    def test_o4b_the_f8b_split_detection_must_be_a_dry_run_on_the_real_branch(self):
        """E11 crafted probe, not product evidence: a result whose split detection is not the dry run is listed with O4a (every failed predicate at once)."""
        setup = self.probe_setup("TEST_SWITCH", label="o4b")
        error = self.refused_seal(setup, "RW_SEAL_REFUSED", split="F8B_LIVE")
        # R4b pin change: RW_REAL_REGISTRY_DIFFERS is gone for the reason given at test_h1_the_real_branch_is_shown_the_performance_services_own_output.
        self.assertEqual(error.diag.message_detail.split(","),
                         ["RW_O4A_SYNTHETIC_RESULT", "RW_O4B_F8B_MODE", "RW_REAL_RELEASE_DIFFERS", "RW_REAL_POLICY_DIFFERS"])

    def test_the_fictional_branch_has_its_own_predicates(self):
        """E11 crafted probe, not product evidence (T10 shape, SQL part): on SYNTHETIC_TEST a result that is not synthetic or whose split detection is
        live is refused with the fictional codes, and never with the O4 codes."""
        setup = self.probe_setup("SYNTHETIC_TEST", label="fict")
        error = self.refused_seal(setup, "RW_SEAL_REFUSED", split="F8B_LIVE")
        self.assertEqual(error.diag.message_detail.split(","), ["RW_FICTIONAL_F8B_MODE"])
        error = self.refused_seal(setup, "RW_SEAL_REFUSED", synthetic=False)
        detail = error.diag.message_detail.split(",")
        self.assertIn("RW_FICTIONAL_NOT_SYNTHETIC", detail)
        self.assertIn("RW_ORIGIN_MISMATCH", detail)
        self.assertFalse([c for c in detail if c.startswith("RW_O4")])

    def test_the_fictional_branch_binds_the_release_and_the_f8b_policy_to_the_snapshot(self):
        """E11 crafted probe, not product evidence. The CP5 result states the release it read (`valuation_manifest.release_id`) and the F8B
        confirmation policy it ran under (`valuation_manifest.detection_policy`); the snapshot names both. The service's own bytes agree with the
        snapshot (the accepted create above); a result that states another release, or another policy digest, or a policy not in the digest form,
        is refused with its own predicate code and no other."""
        setup = self.probe_setup("SYNTHETIC_TEST", label="fict-bind")

        def valuation(**changes):
            return lambda p: p["issued"]["manifest"]["valuation_manifest"].update(changes)

        for label, edit, code in (
                ("another release", valuation(release_id="0" * 64), "RW_FICTIONAL_RELEASE_DIFFERS"),
                ("another policy digest", valuation(detection_policy=[["digest", "0" * 64]]), "RW_FICTIONAL_POLICY_DIFFERS"),
                ("the policy is not in the digest form", valuation(detection_policy=[["hash", setup.snapshot["f8b_policy_digest"]]]), "RW_FICTIONAL_POLICY_DIFFERS"),
                ("no policy", valuation(detection_policy=None), "RW_FICTIONAL_POLICY_DIFFERS")):
            with self.subTest(label):
                error = self.refused_seal(setup, "RW_SEAL_REFUSED", edit=edit)
                self.assertEqual(error.diag.message_detail.split(","), [code])

    def test_the_origin_label_row_guard_refuses_a_root_with_the_other_axis_labels(self):
        """E11 crafted probe, not product evidence: a root row that carries the REAL labels under a test-scope context is a mismatch. (The table
        allows both label sets, so the guard is the seal's; the converse, test labels under a REAL context, needs a REAL install and is the pure
        mapping's test in test_real_labels.)"""
        setup = self.probe_setup("SYNTHETIC_TEST", label="labels")
        real = {"market_origin": "REAL_SOURCE", "ledger_origin": "PROJECT_CONSTRUCTED_NONPERSONAL_UAT", "personal_holdings": False, "synthetic": False}
        error = self.refused_seal(setup, "RW_SEAL_REFUSED", root_origin=real)
        self.assertIn("RW_ORIGIN_MISMATCH", error.diag.message_detail.split(","))

    def test_a_real_origin_string_in_a_test_scope_root_or_result_is_refused(self):
        """E11 crafted probe, not product evidence: 'a TEST_SWITCH root and output carry no real-origin string'. The marker anywhere in the root's
        wording or the issued result refuses the seal."""
        setup = self.probe_setup("TEST_SWITCH", label="marker")
        for label, kw in (("root name", {"name": "has REAL_SOURCE in it"}),
                          ("issued result", {"edit": lambda parts: parts["issued"]["metrics"][0].update(note="REAL_SOURCE")})):
            with self.subTest(label):
                error = self.refused_seal(setup, "RW_SEAL_REFUSED", **kw)
                self.assertIn("RW_ORIGIN_MISMATCH", error.diag.message_detail.split(","))

    def test_every_synthetic_flag_the_service_states_is_the_scopes_axis(self):
        """E11 crafted probe, not product evidence (replaces the old manifest-origin object, which neither service issues): the services state
        `synthetic` in the manifest, in the nested valuation manifest of the CP5 result, and on each metric. Each place on its own, set to the
        other axis, is a label mismatch; the envelope's and the response's flags likewise."""
        for scope in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            setup = self.probe_setup(scope, label="flags-" + scope)

            def manifest(p):
                p["issued"]["manifest"]["synthetic"] = False

            def nested(p):
                p["issued"]["manifest"]["valuation_manifest"]["synthetic"] = False

            def metric(p):
                p["issued"]["metrics"][0]["synthetic"] = False

            cases = [("manifest", manifest), ("a metric", metric)] + ([("valuation manifest", nested)] if scope == "SYNTHETIC_TEST" else [])
            for label, edit in cases:
                with self.subTest(scope + " " + label):
                    error = self.refused_seal(setup, "RW_SEAL_REFUSED", edit=edit)
                    self.assertIn("RW_ORIGIN_MISMATCH", error.diag.message_detail.split(","))
            with self.subTest(scope + " envelope"):
                error = self.refused_seal(setup, "RW_SEAL_REFUSED", edit_envelope=lambda e: e.update(synthetic=False))
                self.assertIn("RW_ORIGIN_MISMATCH", error.diag.message_detail.split(","))
            with self.subTest(scope + " response"):
                def response_flag(p):
                    p["response"]["synthetic"] = False
                resp = self.response_of(setup, False)
                error = self.refused_seal(setup, "RW_SEAL_REFUSED", edit=response_flag, response_for_root=resp)
                self.assertIn("RW_ORIGIN_MISMATCH", error.diag.message_detail.split(","))


    def test_a_fictional_snapshot_whose_source_record_carries_a_terms_check_is_not_acceptable(self):
        """E11 crafted probe, not product evidence (technical review L-4: the no-terms-check predicate of `rw_check_fictional` was a surviving
        mutant). The function is called by the owner role of the disposable database with the documents of a real bundle and a crafted context
        object whose snapshot has a terms check on a source record (publish cannot store one for a test scope). The unedited context returns no
        code (the control); the edited one returns exactly RW_FICTIONAL_SOURCE_DIFFERS."""
        from psycopg.types.json import Jsonb
        setup = self.probe_setup("SYNTHETIC_TEST", label="terms")
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op)
            snapshot = json.loads(bytes(self.owner.execute(f"SELECT snapshot FROM {self.s}.rw_snapshot WHERE context_id=%s", (setup.ctx,)).fetchone()[0]))
            envelope, issued, response = json.loads(bundle.envelope), json.loads(bundle.issued), json.loads(bundle.response)
            ctx = {"snapshot": snapshot, "scope": "SYNTHETIC_TEST", "owner_id": str(setup.owner_id), "root_id": str(setup.root_id),
                   "revision_id": str(bundle.parts["revision"]), "operation_id": str(op), "ledger_pin": bundle.ledger_pin, "generation": 1,
                   "context_id": setup.ctx, "as_of": AS_OF, "reporting_currency": "USD"}

            def codes(context):
                return self.owner.execute(f"SELECT {self.s}.rw_check_fictional(%s,%s,%s,%s)", (Jsonb(envelope), Jsonb(issued), Jsonb(response), Jsonb(context))).fetchone()[0]
            self.assertEqual(codes(ctx), [])                                                       # the control
            self.assertIsNone(snapshot["source_records"][0]["terms_check"])
            edited = json.loads(json.dumps(ctx))
            edited["snapshot"]["source_records"][0]["terms_check"] = {"permits": True}
            self.assertEqual(codes(edited), ["RW_FICTIONAL_SOURCE_DIFFERS"])
        finally:
            rollback(executor)

    def test_publish_refuses_a_test_scope_snapshot_with_the_wrong_origin_or_a_real_origin_string(self):
        """Technical review L-4 (the test-scope origin check of `rw_publish` was a surviving mutant). The publisher role calls the function with
        bytes of a SYNTHETIC_TEST snapshot whose origin labels are the REAL ones, and with bytes that carry the string REAL_SOURCE in a field the
        origin object does not cover. Each is refused with exactly RW_ORIGIN_MISMATCH and nothing is stored. The control publishes."""
        import copy
        from marketdata.canonical import canonical_json
        from psycopg.types.json import Jsonb
        snap = self.snapshot("SYNTHETIC_TEST")
        document = json.loads(snap.data)
        real = {"market_origin": "REAL_SOURCE", "ledger_origin": "PROJECT_CONSTRUCTED_NONPERSONAL_UAT", "personal_holdings": False, "synthetic": False}
        wrong_origin = copy.deepcopy(document)
        wrong_origin["origin"] = {**document["origin"], "synthetic": False}
        wrong_origin2 = copy.deepcopy(document)
        wrong_origin2["origin"] = real
        marker = copy.deepcopy(document)
        marker["note"] = "mentions REAL_SOURCE here"
        publisher = self.conn("publisher")
        for label, doc in (("the origin says synthetic = false", wrong_origin), ("the origin is the real labels", wrong_origin2), ("a real-origin string", marker)):
            with self.subTest(label):
                data = canonical_json(doc).encode()
                error = self.assertRefused("RW_PUBLISH_REFUSED", lambda: publisher.execute(
                    f"SELECT * FROM {self.s}.rw_publish(%s,%s,NULL,%s,'a','PD-9001',%s,%s)", (data, Jsonb(fx.ALL_RIGHTS), Jsonb([]), "a" * 40, "b" * 64)))
                self.assertEqual(error.diag.message_detail.split(","), ["RW_ORIGIN_MISMATCH"])
                self.assertEqual(self.count("rw_snapshot", "context_id=%s", (sha(data),)), 0)
        self.publish(snap)                                                                         # the control: the unedited bytes publish

    def test_every_o4a_and_label_predicate_is_listed_with_the_others_when_several_fail_at_once(self):
        """E11 crafted probe, not product evidence: failed predicates are reported together, in a fixed order, not one at a time."""
        setup = self.probe_setup("TEST_SWITCH", label="together")
        error = self.refused_seal(setup, "RW_SEAL_REFUSED", split="F8B_LIVE", synthetic=False)
        # R4b pin change: RW_REAL_REGISTRY_DIFFERS is gone for the reason given at test_h1_the_real_branch_is_shown_the_performance_services_own_output
        # (the snapshot's registry digest is the engine's and equals the service's); the order and the other four codes are unchanged.
        self.assertEqual(error.diag.message_detail.split(","),
                         ["RW_ORIGIN_MISMATCH", "RW_O4B_F8B_MODE", "RW_REAL_RELEASE_DIFFERS", "RW_REAL_POLICY_DIFFERS"])


class FenceMultiRootTests(SealCase):
    def test_a_transfer_to_an_account_of_another_root_is_refused_by_the_fence_and_one_inside_the_root_is_not(self):
        """E11 crafted probe, not product evidence (technical review L-4: RW_MULTI_ROOT_REFUSED was a surviving mutant). A cash transfer whose
        counterparty account belongs to another root is refused at the write with RW_MULTI_ROOT_REFUSED; the control, a transfer between two
        accounts of the lease's own root, is written. Both are rolled back; nothing is left."""
        other = self.probe_setup("SYNTHETIC_TEST", label="mr-other")
        self.create_and_commit(self.conn("executor"), other)
        (foreign,) = self.owner.execute(f"SELECT account_id FROM {self.s}.account WHERE portfolio_id=%s", (other.root_id,)).fetchone()
        setup = self.probe_setup("SYNTHETIC_TEST", label="mr-own")
        executor = self.conn("executor")
        op = uuid.uuid4()
        insert = (f"INSERT INTO {self.s}.ledger_event(event_id,account_id,event_type,event_date,currency,amount,counterparty_account_id) "
                  "VALUES(%s,%s,'TRANSFER_OUT',DATE '2026-01-03','USD',5,%s)")
        try:
            self.open_create(executor, setup, op)
            self.write_portfolio(executor, setup)
            first = self.write_account_and_event(executor, setup)
            second = uuid.uuid4()
            executor.execute(f"INSERT INTO {self.s}.account(account_id,portfolio_id,name) VALUES(%s,%s,'invented second account')", (second, setup.root_id))
            executor.execute(insert, (uuid.uuid4(), first, second))                                  # the control: inside the root
            self.assertEqual(executor.execute(f"SELECT count(*) FROM {self.s}.ledger_event WHERE counterparty_account_id=%s", (second,)).fetchone()[0], 1)
            executor.execute("SAVEPOINT cross_root")
            self.assertRefused("RW_MULTI_ROOT_REFUSED", lambda: executor.execute(insert, (uuid.uuid4(), first, foreign)))
            executor.execute("ROLLBACK TO cross_root")
        finally:
            rollback(executor)
        self.assertNothingLeft(setup.root_id)


class IdentityRowsTests(SealCase):
    """Coordinator's question B (R3, after the fix round): does R5's create need to READ or WRITE `issuer`, `instrument` or `listing` on the
    executor connection? These tests pin the facts the answer rests on. E11 crafted probe, not product evidence: the identity rows are written by
    the owner role of the disposable database (no product identity writer exists; tech plan 15.17 item 8), the create write path is crafted."""

    def seed(self):
        import marketdata_exit_kit as x
        import pg_market_kit as pk
        if self.count("issuer") == 0:
            pk.insert_identity(self.owner, x.identity())
        return x.identity().snapshot()[2][0].listing_id

    position = ("INSERT INTO {s}.ledger_event(event_id,account_id,event_type,event_date,currency,quantity,listing_id) "
                "VALUES(%s,%s,'OPENING_POSITION',DATE '2026-01-02','USD',10,%s)")

    def test_a_create_writes_a_position_that_names_a_listing_it_holds_no_privilege_on(self):
        """The executor holds no privilege on `issuer`, `instrument` or `listing` (the fence module's test). Under an open create lease it still
        inserts an OPENING_POSITION that names an EXISTING listing: the foreign-key check runs as the owner of the referenced table, and no
        executor-fired migration trigger reads an identity table. The same insert for a listing that does not exist is a foreign-key violation,
        so the create DEPENDS on the identity rows and does not write them. The whole create then seals and commits."""
        listing = self.seed()
        setup = self.probe_setup("SYNTHETIC_TEST", label="identity")
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            self.write_portfolio(executor, setup)
            account = self.write_account_and_event(executor, setup)
            executor.execute("SAVEPOINT missing")
            with self.assertRaises(psycopg.errors.ForeignKeyViolation):
                executor.execute(self.position.format(s=self.s), (uuid.uuid4(), account, uuid.uuid4()))
            executor.execute("ROLLBACK TO missing")
            executor.execute(self.position.format(s=self.s), (uuid.uuid4(), account, listing))
            self.assertDenied(lambda: executor.execute(f"SELECT 1 FROM {self.s}.listing LIMIT 1"))
        finally:
            rollback(executor)
        self.assertNothingLeft(setup.root_id)
        self.create_and_commit_with_position(setup, listing)

    def create_and_commit_with_position(self, setup, listing):
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            self.write_portfolio(executor, setup)
            account = self.write_account_and_event(executor, setup)
            executor.execute(self.position.format(s=self.s), (uuid.uuid4(), account, listing))
            pin = self.pin_of(executor, setup)
            response = self.response_of(setup)
            revision = self.write_root_and_revision(executor, setup, op, pin, response)
            bundle = self.make_bundle(setup, op, revision, pin)
            bundle.parts["revision"] = revision
            self.seal(executor, bundle, setup.prov)
            commit(executor)
        finally:
            rollback(executor)
        self.assertEqual(self.count("ledger_event", "listing_id=%s AND account_id IN (SELECT account_id FROM %s.account WHERE portfolio_id=%%s)" % ("%s", self.s), (listing, setup.root_id)), 1)

    def test_a_lease_less_insert_of_an_identity_row_by_the_executor_is_refused(self):
        """The executor cannot create the rows either (so a create that needs a NEW identity row is the question the note puts to the main session)."""
        executor = self.conn("executor")
        for table, values in (("issuer", "(%s,'invented issuer','US')"), ("instrument", "(%s,%s,'COMMON_STOCK')"), ("listing", "(%s,%s,'XNAS','NASDAQ','XYZ','USD',NULL,true)")):
            with self.subTest(table):
                args = (uuid.uuid4(),) if table == "issuer" else (uuid.uuid4(), uuid.uuid4())
                self.assertDenied(lambda t=table, v=values, a=args: executor.execute(f"INSERT INTO {self.s}.{t} VALUES {v}", a))


class StructuralRefusalTests(SealCase):
    """Each structural check of the artifact raises its own code and rolls back. E11 crafted probes, not product evidence."""

    def test_each_part_of_the_bundle_that_does_not_match_is_refused_with_its_own_code(self):
        setup = self.probe_setup("SYNTHETIC_TEST", label="struct")
        def issued(**changes):
            return lambda p: p["issued"].update(changes)

        def manifest(**changes):
            return lambda p: p["issued"]["manifest"].update(changes)

        def valuation(**changes):
            return lambda p: p["issued"]["manifest"]["valuation_manifest"].update(changes)

        def capital_policy(**changes):
            return lambda p: p["issued"]["manifest"]["capital_policy"].update(changes)

        cases = (
            ("response differs from the stored root", "RW_RESPONSE_DIFFERS", dict(edit=lambda p: p["response"].update(extra=1))),
            ("result digest wrong", "RW_NATIVE_DIGEST_DIFFERS", dict(edit_envelope=lambda e: e.update(result_digest="0" * 64))),
            ("envelope names another root", "RW_ENVELOPE_DIFFERS", dict(edit_envelope=lambda e: e.update(root_id=str(uuid.uuid4())))),
            ("envelope names another scope", "RW_ENVELOPE_DIFFERS", dict(edit_envelope=lambda e: e.update(scope="TEST_SWITCH"))),
            ("envelope has an extra key", "RW_ENVELOPE_SHAPE", dict(edit_envelope=lambda e: e.update(unexpected=1))),
            ("binding names another release", "RW_BINDING_DIFFERS", dict(edit_binding=lambda b: b.update(release_id="0" * 64))),
            ("question names another operation", "RW_QUESTION_DIFFERS", dict(edit=lambda p: p["question"].update(operation_id=str(uuid.uuid4())))),
            ("issued result has an extra key", "RW_ISSUED_SHAPE", dict(edit=issued(extra=1))),
            ("manifest names another portfolio", "RW_MANIFEST_DIFFERS", dict(edit=manifest(portfolio_id=str(uuid.uuid4())))),
            ("manifest names another day", "RW_MANIFEST_DIFFERS", dict(edit=manifest(as_of="2026-01-04"))),
            ("valuation manifest names another ledger version", "RW_VALUATION_DIFFERS", dict(edit=valuation(ledger_version=999))),
            ("capital policy is not the candidate's", "RW_POLICY_DIFFERS", dict(edit=capital_policy(origin="USER"))),
            ("identity digest is not the facts' digest", "RW_IDENTITY_DIFFERS", dict(edit=manifest(identity_digest="0" * 64))),
        )
        for label, code, kw in cases:
            with self.subTest(label):
                self.refused_seal(setup, code, **kw)

    def test_the_issued_documents_own_digests_are_recomputed_not_trusted(self):
        """E11 crafted probe, not product evidence (L-4 follow-up: the fictional result-digest recomputation was a surviving mutant). The issued
        document is changed AFTER the service's derivations, and the envelope and the binding are built to agree with what it now says, so
        only the issued document itself is wrong: a result digest that is not the digest of the result, a manifest id that is not the digest of
        the manifest, a result whose content changed under an unchanged digest."""
        for scope, content in (("SYNTHETIC_TEST", "clusters"), ("TEST_SWITCH", "metrics")):
            setup = self.probe_setup(scope, label="digests-" + scope)
            cases = (
                ("result digest is not the digest of the result", lambda i: i.update(result_digest="0" * 64)),
                ("manifest id is not the digest of the manifest", lambda i: i.update(manifest_id="0" * 64)),
                ("the result changed under its digest", lambda i: i[content].append({"invented": 1}) if content == "clusters"
                 else i[content][0].update(invented=1)),
            )
            for label, late in cases:
                with self.subTest(scope + ": " + label):
                    self.refused_seal(setup, "RW_NATIVE_DIGEST_DIFFERS", edit_issued=late)

    def test_every_manifest_the_seal_sees_names_the_root_and_a_null_portfolio_is_refused(self):
        """E11 crafted probe, not product evidence (PD-0073 condition 1; the quant's note, test 1). portfolio_id is inside manifest_id, so a manifest
        is tied to one root. On BOTH branches: the top-level manifest, the CP5 result's nested valuation manifest, and a manifest-shaped object
        injected anywhere in the issued document each must carry the root's id; a null, an absent key and another portfolio are all refused with
        RW_MANIFEST_DIFFERS. The controls (a nested manifest that names the root) pass this check: on the fictional branch the bundle commits, on
        the real branch it is refused by the predicates and not by this code."""
        other = str(uuid.uuid4())
        nested = {"schema": "finweb.computation_manifest/1", "portfolio_id": None}
        for scope in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            setup = self.probe_setup(scope, label="root-bind-" + scope)
            root = str(setup.root_id)
            fictional = scope == "SYNTHETIC_TEST"

            def top(**kw):
                return lambda p: p["issued"]["manifest"].update(kw)

            def drop_top(p):
                p["issued"]["manifest"].pop("portfolio_id")

            def inject(value):
                def edit(p):
                    where = p["issued"]["clusters"][0] if fictional and p["issued"]["clusters"] else p["issued"]["metrics"][0]
                    where["injected"] = dict(nested, portfolio_id=value) if value != "ABSENT" else {"schema": nested["schema"]}
                return edit

            def inject_obj(obj):
                def edit(p):
                    where = p["issued"]["clusters"][0] if fictional and p["issued"]["clusters"] else p["issued"]["metrics"][0]
                    where["injected"] = obj
                return edit

            cases = [("top-level null", top(portfolio_id=None)), ("top-level another portfolio", top(portfolio_id=other)),
                     ("top-level absent", drop_top), ("injected null", inject(None)), ("injected another portfolio", inject(other)),
                     ("injected without the key", inject("ABSENT")),
                     # re-review RR-L1: the reviewer's four escapes (another root's portfolio_id under a spelling the old pattern did not match)
                     ("RR-L1 schema with a digit", inject_obj({"schema": "finweb.cp6_manifest/1", "portfolio_id": other})),
                     ("RR-L1 schema with an upper-case letter", inject_obj({"schema": "finweb.Risk_manifest/1", "portfolio_id": other})),
                     ("RR-L1 schema with a hyphen", inject_obj({"schema": "finweb.risk-manifest/1", "portfolio_id": other})),
                     ("RR-L1 no schema key", inject_obj({"portfolio_id": other})),
                     # the new rules beyond the four: a portfolio_id that is not a string, an unlisted manifest schema that names the root (or
                     # no portfolio at all) is refused, and so is a listed schema with the key absent
                     ("portfolio_id is a number", inject_obj({"portfolio_id": 7})),
                     ("unlisted manifest schema naming the root", inject_obj({"schema": "finweb.cp6_history_manifest/1", "portfolio_id": root})),
                     ("unlisted manifest schema in capitals, no portfolio", inject_obj({"schema": "FINWEB.NEW_MANIFEST/1"})),
                     ("listed schema, key absent (computation)", inject_obj({"schema": "finweb.computation_manifest/1"})),
                     ("a file manifest that carries another portfolio", inject_obj({"schema": "finweb.marketdata.file_manifest/2", "portfolio_id": other}))]
            if fictional:
                vm = lambda **kw: (lambda p: p["issued"]["manifest"]["valuation_manifest"].update(kw))   # noqa: E731
                cases += [("valuation manifest null", vm(portfolio_id=None)), ("valuation manifest another portfolio", vm(portfolio_id=other))]
            for label, edit in cases:
                with self.subTest(scope + ": " + label):
                    self.refused_seal(setup, "RW_MANIFEST_DIFFERS", edit=edit)
            controls = (("an injected manifest that names the root", lambda r: inject(r)),
                        ("a market-data file manifest v1, which has no portfolio_id", lambda r: inject_obj({"schema": "finweb.marketdata.file_manifest/1"})),
                        ("a market-data file manifest v2, which has no portfolio_id", lambda r: inject_obj({"schema": "finweb.marketdata.file_manifest/2"})),
                        ("an object that names the root and has no schema", lambda r: inject_obj({"portfolio_id": r})))
            for n, (label, make) in enumerate(controls):
                with self.subTest(scope + ": control, " + label):
                    cs = setup if n == 0 else self.probe_setup(scope, label="root-bind-%s-%d" % (scope, n))
                    if fictional:
                        op, _bundle = self.create_and_commit(self.conn("executor"), cs, edit=make(str(cs.root_id)))
                        self.assertEqual(self.count("rw_artifact", "root_id=%s", (cs.root_id,)), 1)
                    else:
                        error = self.refused_seal(cs, "RW_SEAL_REFUSED", edit=make(str(cs.root_id)))
                        self.assertNotIn("RW_MANIFEST_DIFFERS", error.diag.message_detail.split(","))

    def test_each_part_of_the_real_branchs_service_output_that_does_not_match_is_refused_with_its_own_code(self):
        """E11 crafted probe, not product evidence: the same for the performance service's `ComputationResult` shape (flat manifest)."""
        setup = self.probe_setup("TEST_SWITCH", label="struct-real")
        cases = (
            ("result digest wrong", "RW_NATIVE_DIGEST_DIFFERS", dict(edit_envelope=lambda e: e.update(result_digest="0" * 64))),
            ("issued result has an extra key", "RW_ISSUED_SHAPE", dict(edit=lambda p: p["issued"].update(extra=1))),
            ("issued result lacks its metrics", "RW_ISSUED_SHAPE", dict(edit=lambda p: p["issued"].pop("metrics"))),
            ("manifest names another portfolio", "RW_MANIFEST_DIFFERS", dict(edit=lambda p: p["issued"]["manifest"].update(portfolio_id=str(uuid.uuid4())))),
            ("manifest names another ledger version", "RW_MANIFEST_DIFFERS", dict(edit=lambda p: p["issued"]["manifest"].update(ledger_version=999))),
            ("manifest is a scenario", "RW_MANIFEST_DIFFERS", dict(edit=lambda p: p["issued"]["manifest"].update(state_kind="HYPOTHETICAL"))),
            # re-review RR-L3 (mutants N7, N8, N9: these three structural checks of the real branch had no test)
            ("N7 manifest schema is another listed manifest (risk) naming the root", "RW_MANIFEST_DIFFERS",
             dict(edit=lambda p: p["issued"]["manifest"].update(schema="finweb.risk_manifest/1"))),
            ("N7 manifest schema is not a manifest schema at all", "RW_MANIFEST_DIFFERS",
             dict(edit=lambda p: p["issued"]["manifest"].update(schema="finweb.other/1"))),
            ("N8 manifest is an account-scoped NAV", "RW_MANIFEST_DIFFERS",
             dict(edit=lambda p: p["issued"]["manifest"].update(scope="ACCOUNT:" + str(uuid.uuid4())))),
            ("N8 manifest scope is absent", "RW_MANIFEST_DIFFERS", dict(edit=lambda p: p["issued"]["manifest"].pop("scope"))),
            ("N9 manifest is as of another date", "RW_MANIFEST_DIFFERS", dict(edit=lambda p: p["issued"]["manifest"].update(as_of="2026-01-06"))),
            ("N9 manifest has no as_of", "RW_MANIFEST_DIFFERS", dict(edit=lambda p: p["issued"]["manifest"].pop("as_of"))),
            ("manifest names another reporting currency", "RW_MANIFEST_DIFFERS", dict(edit=lambda p: p["issued"]["manifest"].update(reporting_currency="HKD"))),
            ("the real envelope has the fictional keys", "RW_ENVELOPE_SHAPE", dict(edit_envelope=lambda e: e.update(question_hex="00"))),
        )
        for label, code, kw in cases:
            with self.subTest(label):
                self.refused_seal(setup, code, **kw)

    def test_a_seal_with_a_wrong_pin_or_revision_is_refused_at_the_seal_or_the_commit(self):
        """E11 crafted probe, not product evidence: the seal records the ledger pin of the rows written, so a bundle that names another pin
        differs from the stored revision."""
        setup = self.probe_setup("SYNTHETIC_TEST", label="pin")
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op, edit_envelope=lambda e: e.update(ledger_pin=e["ledger_pin"] + 1))
            self.assertRefused("RW_ENVELOPE_DIFFERS", lambda: self.seal(executor, bundle, setup.prov))
        finally:
            rollback(executor)
        self.assertNothingLeft(setup.root_id)

    def test_the_byte_bounds_are_checked_before_anything_is_parsed(self):
        """E11 crafted probe, not product evidence: oversized or undersized byte strings are a shape refusal (no parse, no allocation of a document)."""
        setup = self.probe_setup("SYNTHETIC_TEST", label="bounds")
        executor = self.conn("executor")
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op)
            for label, args in (("issued too short", (bundle.parts["revision"], b"1", bundle.response, bundle.envelope)),
                                ("envelope too long", (bundle.parts["revision"], bundle.issued, bundle.response, b"x" * 70000)),
                                ("null response", (bundle.parts["revision"], bundle.issued, None, bundle.envelope))):
                with self.subTest(label):
                    self.assertRefused("RW_SHAPE", lambda a=args: executor.execute(f"SELECT {self.s}.rw_seal(%s,%s,%s,%s,%s)", (*a, setup.prov)))
                    # a refusal inside a transaction aborts it in PostgreSQL; the next sub-case starts a new one
                    rollback(executor)
                    begin(executor)
                    self.admit(executor, setup.ctx, 1, "EXECUTE_CREATE", setup.owner_id, setup.root_id, op=op, new_root=True)
                    bundle = self.write_all_and_bundle(executor, setup, op)
        finally:
            rollback(executor)
        self.assertNothingLeft(setup.root_id)


class ReplayAndArchiveTests(SealCase):
    """T08 crafted parts: exact replay, idempotency conflict, poisoned stored bytes. E11 crafted probes, not product evidence."""

    def committed(self, label="replay"):
        setup = self.probe_setup("SYNTHETIC_TEST", label=label)
        op, bundle = self.create_and_commit(self.conn("executor"), setup)
        return setup, op, bundle

    def test_exact_replay_reads_the_stored_bundle_and_cannot_write(self):
        """The same operation id, owner, root, context and command digest admits as a REPLAY (read-only phase): the archive returns the committed
        bytes and every economic write is refused."""
        setup, op, bundle = self.committed()
        executor = self.conn("executor")
        begin(executor)
        try:
            self.admit(executor, setup.ctx, 1, "EXECUTE_CREATE", setup.owner_id, setup.root_id, op=op)
            row =executor.execute(f"SELECT issued,response,envelope FROM {self.s}.rw_archive(%s,%s)", (setup.owner_id, op)).fetchone()
            self.assertEqual((bytes(row[0]), bytes(row[1]), bytes(row[2])), (bundle.issued, bundle.response, bundle.envelope))
            self.assertRefused("RW_WRITE_REFUSED", lambda: self.write_portfolio(executor, setup))
        finally:
            rollback(executor)
        self.assertEqual(self.count("rw_artifact", "root_id=%s", (setup.root_id,)), 1)
        self.assertEqual(self.count("rw_lease", "root_id=%s", (setup.root_id,)), 1)             # the replay lease was rolled back

    def test_a_replay_that_commits_writes_nothing_and_stays_a_replay(self):
        """A replay lease commits (it is not a create lease), with no journal row and no new lease of the create phase."""
        setup, op, _bundle = self.committed("replay2")
        executor = self.conn("executor")
        begin(executor)
        try:
            self.admit(executor, setup.ctx, 1, "EXECUTE_CREATE", setup.owner_id, setup.root_id, op=op)
            commit(executor)
        finally:
            rollback(executor)
        phases = sorted(r[0] for r in self.owner.execute(f"SELECT phase FROM {self.s}.rw_lease WHERE root_id=%s", (setup.root_id,)).fetchall())
        self.assertEqual(phases, ["REPLAY", "SEALED"])
        self.assertEqual(self.count("rw_journal", "root_id=%s", (setup.root_id,)), 5)

    def test_a_different_command_root_or_context_on_a_used_operation_id_is_a_conflict(self):
        setup, op, _bundle = self.committed("conflict")
        executor = self.conn("executor")
        other_root = uuid.uuid4()
        for label, kwargs, code in (("another command", dict(command="2" * 64), "RW_IDEMPOTENCY_CONFLICT"),
                                    ("another root", dict(root=other_root), "RW_IDEMPOTENCY_CONFLICT")):
            with self.subTest(label):
                begin(executor)
                try:
                    self.assertRefused(code, lambda k=kwargs: executor.execute(
                        f"SELECT {self.s}.rw_admit(%s,%s,%s,1,'EXECUTE_CREATE',%s,%s,false)",
                        (setup.owner_id, k.get("root", setup.root_id), setup.ctx, op, k.get("command", "1" * 64))))
                finally:
                    rollback(executor)

    def test_a_read_lease_reads_the_archive_and_other_leases_do_not(self):
        """The archive needs a lease on the same owner, root and context; with none, or with another owner, root or context, it refuses."""
        setup, op, bundle = self.committed("archive")
        other = self.live("SYNTHETIC_TEST", label="archive-other")
        executor = self.conn("executor")
        self.assertRefused("RW_LEASE_REQUIRED", lambda: executor.execute(f"SELECT * FROM {self.s}.rw_archive(%s,%s)", (setup.owner_id, op)))
        begin(executor)
        try:
            self.admit(executor, setup.ctx, 1, "ARCHIVE_READ", setup.owner_id, setup.root_id)
            row = executor.execute(f"SELECT * FROM {self.s}.rw_archive(%s,%s)", (setup.owner_id, op)).fetchone()
            self.assertEqual(bytes(row[0]), bundle.issued)
            self.assertRefused("RW_NOT_FOUND", lambda: executor.execute(f"SELECT * FROM {self.s}.rw_archive(%s,%s)", (uuid.uuid4(), op)))
        finally:
            rollback(executor)
        begin(executor)
        try:
            self.admit(executor, other.ctx, 1, "ARCHIVE_READ", other.owner_id, other.root_id)
            self.assertRefused("RW_NOT_FOUND", lambda: executor.execute(f"SELECT * FROM {self.s}.rw_archive(%s,%s)", (setup.owner_id, op)))
        finally:
            rollback(executor)

    def test_poisoned_stored_bytes_are_refused_by_the_archive(self):
        """T08 'poisoned foreign JSON', crafted: the stored envelope is replaced, with its digest kept consistent, by bytes that are not the
        canonical JSON of an envelope. The owner role switches the immutability trigger off for the crafted edit (E11) and on again. The archive
        refuses every variant with a typed code and returns no byte."""
        setup, op, _bundle = self.committed("poison")
        reader = self.conn("executor")
        original = bytes(self.owner.execute(f"SELECT envelope FROM {self.s}.rw_artifact WHERE operation_id=%s", (op,)).fetchone()[0])
        variants = {"not json": b"not json at all", "json array": b"[1,2,3]", "extra whitespace": original.replace(b",", b", ", 1),
                    "not utf8": b"\xff\xfe\xfd{}"}
        try:
            for label, poison in variants.items():
                with self.subTest(label):
                    self.craft_envelope(op, poison)
                    begin(reader)
                    try:
                        self.admit(reader, setup.ctx, 1, "ARCHIVE_READ", setup.owner_id, setup.root_id)
                        with self.assertRaises(psycopg.errors.RaiseException) as caught:
                            reader.execute(f"SELECT * FROM {self.s}.rw_archive(%s,%s)", (setup.owner_id, op))
                        self.assertIn(caught.exception.diag.message_primary, ("RW_ENVELOPE_SHAPE", "RW_ARCHIVE_BOUNDS"))
                    finally:
                        rollback(reader)
        finally:
            self.craft_envelope(op, original)
        begin(reader)
        try:
            self.admit(reader, setup.ctx, 1, "ARCHIVE_READ", setup.owner_id, setup.root_id)
            self.assertEqual(len(reader.execute(f"SELECT * FROM {self.s}.rw_archive(%s,%s)", (setup.owner_id, op)).fetchall()), 1)     # restored: control
        finally:
            rollback(reader)

    def craft_response(self, setup, op, bundle, response):
        """E11 crafted drift: the owner role of the disposable database (the immutability triggers off, then on) rewrites the stored response in all
        four places that must agree (the artifact, the envelope's digest of it, the root's and the revision's copy)."""
        data = canon(response)
        digest = sha(data)
        envelope = json.loads(bundle.envelope)
        envelope["response_sha256"] = digest
        env = canon(envelope)
        with self.owner.transaction():
            for table in ("rw_artifact", "rw_root", "rw_revision"):
                self.owner.execute(f"ALTER TABLE {self.s}.{table} DISABLE TRIGGER USER")           # the fence fires for the owner too (as craft_root)
            self.owner.execute(f"UPDATE {self.s}.rw_artifact SET response=%s,response_sha256=%s,envelope=%s,envelope_sha256=%s WHERE operation_id=%s",
                               (data, digest, env, sha(env), op))
            for table in ("rw_root", "rw_revision"):
                self.owner.execute(f"UPDATE {self.s}.{table} SET snapshot_json=%s,snapshot_sha256=%s WHERE portfolio_id=%s", (data.decode(), digest, setup.root_id))
            for table in ("rw_artifact", "rw_root", "rw_revision"):
                self.owner.execute(f"ALTER TABLE {self.s}.{table} ENABLE TRIGGER USER")

    def test_the_archive_read_returns_the_four_origin_fields_and_refuses_a_result_that_lacks_them(self):
        """E11 crafted probe, not product evidence (PD-0073 condition 3, the R3 surface; the quant's note, test 3). The archive read is the only R3
        surface that returns a stored result (rw_precheck and rw_list_roots return identifiers). (a) After an accepted create, the response it
        returns holds the four origin fields and they equal the root row's columns. (b) Control: the stored response rewritten to the same content
        is returned. (c) The stored response rewritten WITHOUT the origin, with every digest and copy consistent, is refused by the archive (the
        seal's check runs again at every read) and no byte is returned. Reproduce, export and the read tail are R5's code and call this function
        (obligation line in the disposition note)."""
        setup = self.probe_setup("SYNTHETIC_TEST", label="archive-origin")
        op, bundle = self.create_and_commit(self.conn("executor"), setup)
        root = self.owner.execute(f"SELECT market_origin,ledger_origin,personal_holdings,synthetic FROM {self.s}.rw_root WHERE portfolio_id=%s", (setup.root_id,)).fetchone()
        reader = self.conn("executor")

        def read():
            begin(reader)
            try:
                self.admit(reader, setup.ctx, 1, "ARCHIVE_READ", setup.owner_id, setup.root_id)
                return reader.execute(f"SELECT response FROM {self.s}.rw_archive(%s,%s)", (setup.owner_id, op)).fetchone()
            finally:
                rollback(reader)
        returned = json.loads(bytes(read()[0]))
        self.assertEqual(tuple(returned["origin"][k] for k in ("market_origin", "ledger_origin", "personal_holdings", "synthetic")), tuple(root))
        self.assertEqual(set(returned["origin"]), {"market_origin", "ledger_origin", "personal_holdings", "synthetic"})
        self.craft_response(setup, op, bundle, returned)                                              # (b) control: same content, rewritten
        self.assertEqual(json.loads(bytes(read()[0])), returned)
        stripped = {k: v for k, v in returned.items() if k != "origin"}
        self.craft_response(setup, op, bundle, stripped)                                              # (c)
        begin(reader)
        try:
            self.admit(reader, setup.ctx, 1, "ARCHIVE_READ", setup.owner_id, setup.root_id)
            error = self.assertRefused("RW_SEAL_REFUSED", lambda: reader.execute(f"SELECT response FROM {self.s}.rw_archive(%s,%s)", (setup.owner_id, op)))
            self.assertIn("RW_ORIGIN_MISMATCH", error.diag.message_detail.split(","))
        finally:
            rollback(reader)

    def craft_envelope(self, op, data):
        with self.owner.transaction():
            self.owner.execute(f"ALTER TABLE {self.s}.rw_artifact DISABLE TRIGGER rw_immutable")
            self.owner.execute(f"UPDATE {self.s}.rw_artifact SET envelope=%s, envelope_sha256=%s WHERE operation_id=%s", (data, sha(data), op))
            self.owner.execute(f"ALTER TABLE {self.s}.rw_artifact ENABLE TRIGGER rw_immutable")


class DeadlineCase(SealCase):
    INSTALL = "sealdl"
    W = 3


class CreatePhaseDeadlineTests(DeadlineCase):
    """Design 3.2, R3 (E11): refused at the next economic write and at the seal once past complete_by; paused between the seal and the COMMIT
    with the bundle guard and the other deferrable constraints fired by name, refused at COMMIT by the deadline guard. All with every session
    timeout at 0, so the connection's own timeouts are not the bound. E11 crafted probes, not product evidence."""

    def stalled(self):
        return self.conn("executor", options=self.stall_options())

    def test_positive_control_a_create_that_finishes_inside_its_deadline_commits(self):
        setup = self.probe_setup("SYNTHETIC_TEST", valid_in=120.0)
        executor = self.stalled()
        op, _ = self.create_and_commit(executor, setup)
        self.assertEqual(self.count("rw_artifact", "root_id=%s", (setup.root_id,)), 1)

    def test_an_economic_write_at_or_after_complete_by_is_refused_and_rolls_back(self):
        for label, valid_in in (("W decides", 120.0), ("the cap decides", 2.0)):
            with self.subTest(label):
                setup = self.probe_setup("SYNTHETIC_TEST", valid_in=valid_in, label=label)
                executor = self.stalled()
                try:
                    _op, lease = self.open_create(executor, setup)
                    self.assertEqual(lease.complete_by < setup.live.valid, valid_in > self.inst.w_seconds)
                    self.wait_for_db_time(lease.complete_by)
                    self.assertRefused("RW_WRITE_REFUSED", lambda: self.write_portfolio(executor, setup))
                finally:
                    rollback(executor)
                self.assertNothingLeft(setup.root_id)

    def test_the_seal_at_or_after_complete_by_is_refused(self):
        """Both orderings of the cap (L-5): W decides (valid_in 120 s, complete_by = admitted_at + W) and the cap decides (valid_in 2 s,
        complete_by = valid_until). Each is checked against the lease's own recorded ordering."""
        for label, valid_in in (("W decides", 120.0), ("the cap decides", 2.0)):
            with self.subTest(label):
                setup = self.probe_setup("SYNTHETIC_TEST", valid_in=valid_in, label="seal-" + label[:3])
                executor = self.stalled()
                op = uuid.uuid4()
                try:
                    _op, lease = self.open_create(executor, setup, op)
                    self.assertEqual(lease.complete_by < setup.live.valid, valid_in > self.inst.w_seconds)
                    self.assertEqual(lease.complete_by == setup.live.valid, valid_in <= self.inst.w_seconds)
                    bundle = self.write_all_and_bundle(executor, setup, op)
                    self.wait_for_db_time(lease.complete_by)
                    self.assertRefused("RW_DEADLINE", lambda: self.seal(executor, bundle, setup.prov))
                finally:
                    rollback(executor)
                self.assertNothingLeft(setup.root_id)

    def test_paused_between_the_seal_and_the_commit_is_refused_at_commit_by_the_deadline_guard(self):
        """The bundle guard and the other deferrable constraints are fired by NAME after the seal (the deadline guard is not named); the stall past
        complete_by is refused at COMMIT with RW_DEADLINE, the whole transaction is rolled back and no row remains."""
        for label, valid_in in (("W decides", 120.0), ("the cap decides", 2.0)):                       # L-5: both orderings of the cap
            with self.subTest(label):
                setup = self.probe_setup("SYNTHETIC_TEST", valid_in=valid_in, label="commit-" + label[:3])
                executor = self.stalled()
                op = uuid.uuid4()
                try:
                    _op, lease = self.open_create(executor, setup, op)
                    self.assertEqual(lease.complete_by < setup.live.valid, valid_in > self.inst.w_seconds)
                    bundle = self.write_all_and_bundle(executor, setup, op)
                    self.seal(executor, bundle, setup.prov)
                    for name in ("rw_bundle_complete", "rw_root_link_portfolio_fkey", "ledger_event_transfer_pairing"):
                        executor.execute(f'SET CONSTRAINTS "{self.s}"."{name}" IMMEDIATE')
                    self.wait_for_db_time(lease.complete_by)
                    self.assertRefused("RW_DEADLINE", lambda: commit(executor))
                finally:
                    rollback(executor)
                self.assertNothingLeft(setup.root_id)

    def test_the_control_the_same_pause_inside_the_deadline_commits(self):
        setup = self.probe_setup("SYNTHETIC_TEST", valid_in=120.0, label="ctl")
        executor = self.stalled()
        op = uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op)
            self.seal(executor, bundle, setup.prov)
            for name in ("rw_bundle_complete", "rw_root_link_portfolio_fkey", "ledger_event_transfer_pairing"):
                executor.execute(f'SET CONSTRAINTS "{self.s}"."{name}" IMMEDIATE')
            commit(executor)
        finally:
            rollback(executor)
        self.assertEqual(self.count("rw_artifact", "root_id=%s", (setup.root_id,)), 1)


class WriteAfterTheSealTests(SealCase):
    """Mutation M1 of R3's own run (the fence without its phase test) passed the fence module: nothing there wrote after a seal. A SEALED
    lease is no longer OPEN, so each barrier on its own refuses a further economic write at statement time. E11 crafted: the owner role of
    the disposable database switches the other two barriers of the account table off, then on again in `finally`."""

    def only(self, barrier):
        with self.owner.transaction():
            for trigger, name in (("zz_rw_write", "fence"), ("zz_rw_journal", "journal")):
                self.owner.execute(f"ALTER TABLE {self.s}.account {'ENABLE' if barrier == name else 'DISABLE'} TRIGGER {trigger}")
            self.owner.execute(f"ALTER TABLE {self.s}.account {'ENABLE' if barrier == 'policy' else 'DISABLE'} ROW LEVEL SECURITY")

    def test_a_write_after_the_seal_is_refused_by_each_barrier_on_its_own(self):
        for barrier in ("fence", "journal", "policy", "all"):
            with self.subTest(barrier):
                if barrier == "all":
                    with self.owner.transaction():
                        for trigger in ("zz_rw_write", "zz_rw_journal"):
                            self.owner.execute(f"ALTER TABLE {self.s}.account ENABLE TRIGGER {trigger}")
                        self.owner.execute(f"ALTER TABLE {self.s}.account ENABLE ROW LEVEL SECURITY")
                else:
                    self.only(barrier)
                setup = self.probe_setup("SYNTHETIC_TEST", label="after-seal-" + barrier)
                executor = self.conn("executor")
                op = uuid.uuid4()
                try:
                    self.open_create(executor, setup, op)
                    bundle = self.write_all_and_bundle(executor, setup, op)
                    self.seal(executor, bundle, setup.prov)
                    executor.execute("SAVEPOINT late")
                    with self.assertRaises((psycopg.errors.RaiseException, psycopg.errors.InsufficientPrivilege)) as caught:
                        executor.execute(f"INSERT INTO {self.s}.account(account_id,portfolio_id,name) VALUES(%s,%s,'late account')", (uuid.uuid4(), setup.root_id))
                    if barrier == "policy":
                        self.assertIsInstance(caught.exception, psycopg.errors.InsufficientPrivilege)
                    else:
                        self.assertIn("RW_WRITE_REFUSED", str(caught.exception))
                    executor.execute("ROLLBACK TO late")
                finally:
                    rollback(executor)
                    with self.owner.transaction():
                        for trigger in ("zz_rw_write", "zz_rw_journal"):
                            self.owner.execute(f"ALTER TABLE {self.s}.account ENABLE TRIGGER {trigger}")
                        self.owner.execute(f"ALTER TABLE {self.s}.account ENABLE ROW LEVEL SECURITY")
                self.assertNothingLeft(setup.root_id)


class BundleGuardAsLastLineTests(SealCase):
    def test_a_write_after_the_seal_with_the_other_barriers_off_is_caught_by_the_state_digest(self):
        """E11 crafted probe, not product evidence: the owner role of the disposable database switches the fence, the journal and the row policy of
        the account table off, the executor adds a second account after the seal, and COMMIT is refused by the bundle guard (the state digest and the
        journal count no longer match the sealed ones). The barriers are switched on again in `finally`."""
        setup = self.probe_setup("SYNTHETIC_TEST", label="late")
        executor = self.conn("executor")
        op = uuid.uuid4()
        def barriers(on):
            with self.owner.transaction():
                for trigger in ("zz_rw_write", "zz_rw_journal"):
                    self.owner.execute(f"ALTER TABLE {self.s}.account {'ENABLE' if on else 'DISABLE'} TRIGGER {trigger}")
                self.owner.execute(f"ALTER TABLE {self.s}.account {'ENABLE' if on else 'DISABLE'} ROW LEVEL SECURITY")
        barriers(False)
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op)
            self.seal(executor, bundle, setup.prov)
            executor.execute(f"INSERT INTO {self.s}.account(account_id,portfolio_id,name) VALUES(%s,%s,'late account')", (uuid.uuid4(), setup.root_id))
            self.assertRefused("RW_JOURNAL_DIFFERS", lambda: commit(executor))
        finally:
            rollback(executor)
            barriers(True)
        self.assertNothingLeft(setup.root_id)


class CreatePhaseWithdrawalCase(SealCase):
    INSTALL = "sealwd"
    W = 3


class CreatePhaseWithdrawalTests(CreatePhaseWithdrawalCase):
    """Technical review M-2: the two create-phase items of design 3.2 "Withdrawal and cancellation" that are marked R3. R1 showed them for a READ
    lease; R3 changed what an in-flight create holds (`rw_admit` now also takes the operation lock, the advisory lock `rw.op:<schema>:<owner>:<op>`,
    and the create holds uncommitted rows in five fenced tables), so they are shown again on a create. The create is the E11 crafted probe (no
    product create exists before R5); the lease, the admit, the locks, the drain mark and the publisher tool are the product's."""

    def advisory(self, pid):
        return self.admin.execute("SELECT count(*) FROM pg_locks WHERE pid=%s AND locktype='advisory' AND granted", (pid,)).fetchone()[0]

    def pid(self, conn):
        return conn.execute("SELECT pg_backend_pid()").fetchone()[0]

    def test_a_stalled_create_holds_up_a_withdrawal_the_publisher_cannot_end_it_and_the_owner_can(self):
        """E11 crafted probe, not product evidence (3.2, marked R3). A create is admitted (root and operation advisory locks, head share lock),
        writes its five rows, and stalls past complete_by with every session timeout at 0. The withdrawal records its mark, reports 'not yet
        effective' and NAMES the blocking lease; the publisher role can neither terminate nor cancel the backend; the owner role ends it; the
        withdrawal then proceeds, and no economic row, lease row or advisory lock is left."""
        setup = self.probe_setup("SYNTHETIC_TEST", valid_in=120.0, label="stalled-create")
        executor = self.conn("executor", options=self.stall_options())
        stalled_pid = self.pid(executor)
        op = uuid.uuid4()
        _op, lease = self.open_create(executor, setup, op)
        self.write_all_and_bundle(executor, setup, op)                                    # portfolio, account, event, root, revision: uncommitted
        self.assertGreaterEqual(self.advisory(stalled_pid), 2)                            # the root lock and the operation lock are in place
        self.wait_for_db_time(lease.complete_by)                                          # stalled past its deadline: it can no longer seal
        result = self.tool(lock_timeout_ms=1000).withdraw(setup.ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual((result.status, result.outcome), (3, "NOT_YET_EFFECTIVE"), result.text)
        self.assertIn("blocking lease: backend %d, complete_by " % stalled_pid, result.text)
        self.assertIn("not yet effective for in-flight work", result.text)
        (mark,) = self.marks(setup.ctx)
        self.assertEqual(len(self.history(setup.ctx)), 1)                                 # no generation while the create is in flight
        publisher = self.conn("publisher")
        self.assertDenied(lambda: publisher.execute("SELECT pg_terminate_backend(%s)", (stalled_pid,)))
        self.assertDenied(lambda: publisher.execute("SELECT pg_cancel_backend(%s)", (stalled_pid,)))
        self.assertTrue(self.admin.execute("SELECT pg_terminate_backend(%s)", (stalled_pid,)).fetchone()[0])      # the owner, the server's operator
        wait_until(lambda: self.admin.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s", (stalled_pid,)).fetchone()[0] == 0,
                   timeout=5.0, what="the stalled create's backend to end")
        self.assertEqual(self.advisory(stalled_pid), 0)
        finished = self.tool(lock_timeout_ms=5000).withdraw(setup.ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
        self.assertEqual((finished.status, finished.outcome), (0, "WITHDRAWN"), finished.text)
        self.assertIn("drain mark %d already recorded" % mark["mark_id"], finished.text)
        self.assertNothingLeft(setup.root_id)                                             # no economic row, journal row, lease row or artifact
        self.assertEqual(self.count("rw_lease", "context_id=%s", (setup.ctx,)), 0)

    def test_a_create_cancelled_by_a_statement_timeout_or_by_the_operator_rolls_back_wholly_and_the_withdrawal_proceeds(self):
        """E11 crafted probe, not product evidence (3.2, marked R3). The create is over its connection's statement timeout (QueryCanceled), and
        in a second case cancelled by the operator. Each rolls back wholly: no economic row, no lease row, and the root and operation advisory
        locks are released at once (the connection stays open), so the withdrawal that follows is not held up and finishes."""
        for how in ("statement timeout", "pg_cancel_backend"):
            with self.subTest(how):
                setup = self.probe_setup("SYNTHETIC_TEST", valid_in=120.0, label="cancelled-" + how[:4])
                options = ("-c timezone=UTC -c statement_timeout=1500 -c idle_in_transaction_session_timeout=0 -c lock_timeout=8000 -c transaction_timeout=0"
                           if how == "statement timeout" else self.stall_options())
                executor = self.conn("executor", options=options)
                pid = self.pid(executor)
                op = uuid.uuid4()
                self.open_create(executor, setup, op)
                self.write_all_and_bundle(executor, setup, op)
                self.assertGreaterEqual(self.advisory(pid), 2)
                if how == "statement timeout":
                    with self.assertRaises(psycopg.errors.QueryCanceled):
                        executor.execute("SELECT pg_sleep(10)")
                else:
                    def sleeper():
                        try:
                            executor.execute("SELECT pg_sleep(30)")
                        except psycopg.errors.QueryCanceled as error:
                            return type(error).__name__
                    worker = Worker(sleeper)
                    wait_until(lambda: self.admin.execute("SELECT count(*) FROM pg_stat_activity WHERE pid=%s AND state='active' AND query LIKE '%%pg_sleep%%'",
                                                          (pid,)).fetchone()[0] == 1, timeout=5.0, what="the create to be sleeping")
                    self.assertTrue(self.admin.execute("SELECT pg_cancel_backend(%s)", (pid,)).fetchone()[0])
                    self.assertEqual(worker.join(10), "QueryCanceled")
                rollback(executor)                                                        # the cancelled transaction is aborted; this ends it
                self.assertNothingLeft(setup.root_id)
                self.assertEqual(self.advisory(pid), 0)                                   # released with the transaction, the session still open
                started = time.monotonic()
                result = self.tool(lock_timeout_ms=5000).withdraw(setup.ctx, 1, actor=fx.ACTOR, ref=fx.REF_OTHER)
                self.assertEqual((result.status, result.outcome), (0, "WITHDRAWN"), result.text)
                self.assertLess(time.monotonic() - started, 4.0)                          # nothing held it up
                self.assertEqual(self.count("rw_lease", "context_id=%s", (setup.ctx,)), 0)


if __name__ == "__main__":
    import unittest
    unittest.main()
