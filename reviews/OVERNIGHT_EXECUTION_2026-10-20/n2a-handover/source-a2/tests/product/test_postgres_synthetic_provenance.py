"""Author N2a actual-PG groups; root injects CONFIG and owns native lifecycle.

No discovery, subprocess/startup, provider, browser, or old fixture input.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import unittest
from unittest.mock import patch
import uuid

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from marketdata.synthetic_provenance import ProvenanceError
from persistence.synthetic_provenance_store import (SyntheticProvenanceStore,
    CommittedSyntheticRegistration, UnknownSyntheticRegistration, TABLES)
from persistence.guarded_workspace_context import _scope_from_database
from test_synthetic_provenance import invented_fixture, encode, h

CONFIG = None
CASE_EVENTS = []
RIGHTS = {k: True for k in ("EXECUTE_CREATE", "ARCHIVE_READ", "ARCHIVE_EXPORT", "EXECUTE_REPRODUCE")}


class PostgresSyntheticProvenance(unittest.TestCase):
    def setUp(self):
        if CONFIG is None:
            self.skipTest("root-provisioned isolated N2a CONFIG required")
        self.schema = CONFIG["schema"]
        self.store = SyntheticProvenanceStore(lambda: CONFIG["connect"](CONFIG["loader_role"]), schema=self.schema,
            loader_role=CONFIG["loader_role"], executor_role=CONFIG["executor_role"])

    def q(self, conn, name, args=()):
        return conn.execute(sql.SQL("SELECT * FROM {}.{}(" + ",".join(["%s"] * len(args)) + ")").format(sql.Identifier(self.schema), sql.Identifier(name)), args)

    def save(self, fixture, op=None):
        b, m, w = fixture
        op = op or uuid.uuid4()
        value = self.store.register(op, b, expected_context_sha256=h(b.context_bytes), expected_members=m, witnesses=w)
        return op, value

    def load(self, fixture):
        b, m, w = fixture
        return self.store.load_context(h(b.context_bytes), expected_members=m, witnesses=w)

    def request(self, op, fixture):
        b, _, _ = fixture
        # Independent format construction, not author's product encoder.
        return encode(dict(schema="finweb.synthetic_provenance_registration/1", scope="SYNTHETIC_TEST", operation_id=str(op), context_sha256=h(b.context_bytes), payload_sha256s=[k for k, _ in b.payloads], manifest_sha256s=[k for k, _ in b.manifests], envelope_sha256s=[k for k, _ in b.envelopes], witness_sha256s=[k for k, _ in b.witnesses]))

    def recover(self, op, fixture):
        b, m, w = fixture
        return self.store.reconcile(op, expected_request_sha256=h(self.request(op, fixture)), expected_context_sha256=h(b.context_bytes), expected_members=m, witnesses=w)

    def snapshot(self, *, native=False):
        result = {}
        with CONFIG["connect"](CONFIG["owner_role"]) as conn:
            if native:
                tables = [r[0] for r in conn.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='r' AND left(c.relname,3)<>'np_' ORDER BY c.relname", (self.schema,)).fetchall()]
            else:
                tables = TABLES
            for table in tables:
                result[table] = conn.execute(sql.SQL("SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM {}.{} t").format(sql.Identifier(self.schema), sql.Identifier(table))).fetchone()[0]
        return result

    def test_p01_durable_original_and_empty_fresh_load(self):
        native = self.snapshot(native=True)
        for payload in (b"synthetic-payload-one\n", b""):
            fixture = invented_fixture(payload)
            _, saved = self.save(fixture)
            self.assertIsInstance(saved, CommittedSyntheticRegistration)
            loaded = self.load(fixture)
            self.assertEqual(loaded.bundle, fixture[0])
            self.assertEqual((loaded.state, loaded.promotable, loaded.source_admitted), ("INTEGRITY_BOUND_NOT_ADMITTED", False, False))
        self.assertEqual(self.snapshot(native=True), native)

    def test_p02_two_acquisitions_preserved_and_exact_replay_counts(self):
        native = self.snapshot(native=True)
        old, both = invented_fixture(acquisitions=(1,)), invented_fixture(acquisitions=(1, 2))
        _, old_saved = self.save(old)
        op, saved = self.save(both)
        self.assertIsInstance(saved, CommittedSyntheticRegistration)
        before = self.snapshot()
        _, replay = self.save(both, op)
        self.assertEqual(replay, saved)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.load(old).bundle, old[0])
        self.assertEqual(self.load(both).bundle, both[0])
        self.assertEqual((json.loads(saved.response_bytes)["payload_count"], json.loads(saved.response_bytes)["manifest_count"], json.loads(saved.response_bytes)["envelope_count"], json.loads(saved.response_bytes)["member_count"]), (1, 2, 2, 2))
        self.assertEqual(self.snapshot(native=True), native)

    def test_p03_conflict_missing_and_bad_selectors_have_no_partial_rows(self):
        first, other = invented_fixture(), invented_fixture(acquisitions=(2,))
        op, result = self.save(first)
        self.assertIsInstance(result, CommittedSyntheticRegistration)
        before, native = self.snapshot(), self.snapshot(native=True)
        # Static A1 finding: JSON null is SQL NULL under ->>; <> silently skips
        # the IF. Direct SQL must reject it too, before any partial bundle row.
        bad_context = json.loads(first[0].context_bytes)
        bad_context["schema"] = None
        bad_bundle = replace(first[0], context_bytes=encode(bad_context))
        bad_fixture = (bad_bundle, first[1], first[2])
        bad_op = uuid.uuid4()
        with CONFIG["connect"](CONFIG["loader_role"]) as conn:
            with self.assertRaises(psycopg.Error) as caught:
                self.q(conn, "np_put_context", (bad_op, self.request(bad_op, bad_fixture), bad_bundle.context_bytes,
                    *[list(raw for _, raw in values) for values in (bad_bundle.payloads, bad_bundle.manifests, bad_bundle.envelopes, bad_bundle.witnesses)]))
            self.assertEqual(caught.exception.diag.message_primary, "NP_UNSUPPORTED_PROVENANCE")
        self.assertEqual(self.snapshot(), before)
        with self.assertRaisesRegex(ProvenanceError, "NP_OPERATION_CONFLICT"):
            self.save(other, op)
        b, members, witnesses = first
        with self.assertRaisesRegex(ProvenanceError, "NP_INPUT_MISSING"):
            self.store.load_context(h(b"absent context"), expected_members=members, witnesses=witnesses)
        with CONFIG["connect"](CONFIG["loader_role"]) as conn:
            for args in ((None, None), (h(b.context_bytes), op), ("invalid", None)):
                with self.assertRaises(psycopg.Error) as caught:
                    self.q(conn, "np_get_context", args)
                self.assertEqual(caught.exception.diag.message_primary, "NP_SHAPE")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.snapshot(native=True), native)

    def test_p04_actual_outer_rollback_and_postcommit_ackloss(self):
        fixture = invented_fixture(acquisitions=(3,))
        before, native = self.snapshot(), self.snapshot(native=True)
        failed_op = uuid.uuid4()
        with patch.object(SyntheticProvenanceStore, "_before_commit", side_effect=psycopg.OperationalError("labelled precommit fault")):
            _, unknown = self.save(fixture, failed_op)
        self.assertIsInstance(unknown, UnknownSyntheticRegistration)
        self.assertEqual(self.snapshot(), before)
        self.assertIsInstance(self.recover(failed_op, fixture), UnknownSyntheticRegistration)
        committed_op = uuid.uuid4()
        with patch.object(SyntheticProvenanceStore, "_after_commit_ack", side_effect=psycopg.OperationalError("labelled postcommit fault")):
            _, unknown = self.save(fixture, committed_op)
        self.assertIsInstance(unknown, UnknownSyntheticRegistration)
        original = self.recover(committed_op, fixture)
        self.assertIsInstance(original, CommittedSyntheticRegistration)
        self.assertEqual(original.response_bytes, self.recover(committed_op, fixture).response_bytes)
        self.assertEqual(self.snapshot(native=True), native)

    def test_p05_actual_roles_and_original_f2_lease_read(self):
        # Legal original issuer metadata/rights fixture, BEFORE native baseline.
        # This is not financial computation or bytes-to-compute provenance.
        owner, root, op = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        snapshot = json.dumps(dict(scope="SYNTHETIC_TEST", fixture="N2a lease only", nonce=str(op)), sort_keys=True, separators=(",", ":")).encode()
        financial_context = h(snapshot)
        with CONFIG["connect"](CONFIG["issuer_role"]) as issuer:
            self.assertEqual(self.q(issuer, "gw_publish", (snapshot,)).fetchone()[0], financial_context)
            self.q(issuer, "gw_set_rights", (financial_context, 1, Jsonb(RIGHTS), "NONE"))
        with CONFIG["connect"](CONFIG["executor_role"]) as conn:
            conn.execute(sql.SQL("INSERT INTO {}.app_user VALUES(%s)").format(sql.Identifier(self.schema)), (owner,))
        fixture = invented_fixture(financial_context=financial_context)
        _, saved = self.save(fixture)
        self.assertIsInstance(saved, CommittedSyntheticRegistration)
        native = self.snapshot(native=True)
        b, members, witnesses = fixture
        with CONFIG["connect"](CONFIG["executor_role"]) as conn:
            with self.assertRaises(psycopg.Error) as caught:
                self.q(conn, "np_load_context", (h(b.context_bytes), "EXECUTE_CREATE"))
            self.assertEqual(caught.exception.diag.message_primary, "NP_LEASE_REQUIRED")
            # Real gw_root/lease are temporary and MUST disappear on rollback.
            with conn.transaction(force_rollback=True):
                admitted = self.q(conn, "gw_admit", (owner, root, financial_context, 1, "EXECUTE_CREATE", op, "1" * 64, True)).fetchone()[0]
                scope = _scope_from_database(conn, self.schema, bytes(admitted))
                loaded = self.store.load_guarded(conn, scope, h(b.context_bytes), expected_members=members, witnesses=witnesses)
                self.assertEqual(loaded.bundle, b)
                self.assertFalse(loaded.promotable)
                self.assertEqual(self.q(conn, "gw_scope").fetchone()[1], root)
        self.assertEqual(self.snapshot(native=True), native)
        with CONFIG["connect"](CONFIG["owner_role"]) as conn:
            for table in ("gw_root", "gw_lease", "gw_artifact", "gw_operation", "gw_journal"):
                column = "root_id"
                self.assertEqual(conn.execute(sql.SQL("SELECT count(*) FROM {}.{} WHERE {}=%s").format(sql.Identifier(self.schema), sql.Identifier(table), sql.Identifier(column)), (root,)).fetchone()[0], 0)
        for role in (CONFIG["loader_role"], CONFIG["executor_role"]):
            with CONFIG["connect"](role) as conn:
                self.assertEqual(conn.execute("SELECT current_user::text,session_user::text,current_setting('role')").fetchone(), (role, role, "none"))
                for statement in (sql.SQL("SELECT * FROM {}.np_payload").format(sql.Identifier(self.schema)), sql.SQL("UPDATE {}.np_payload SET size_bytes=size_bytes").format(sql.Identifier(self.schema)), sql.SQL("CREATE TABLE {}.np_illegal(value integer)").format(sql.Identifier(self.schema)), sql.SQL("SET ROLE {}").format(sql.Identifier(CONFIG["owner_role"]))):
                    with self.assertRaises(psycopg.Error) as caught:
                        conn.execute(statement)
                    self.assertEqual(caught.exception.sqlstate, "42501")
        self.assertEqual(self.snapshot(native=True), native)

    def test_p06_concurrent_exact_and_conflicting_operation(self):
        fixture = invented_fixture(acquisitions=(4,))
        native = self.snapshot(native=True)
        op = uuid.uuid4()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.save, fixture, op) for _ in range(2)]
            results = [f.result(timeout=20)[1] for f in futures]
        self.assertTrue(all(isinstance(x, CommittedSyntheticRegistration) for x in results))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.load(fixture).bundle, fixture[0])
        other = invented_fixture(acquisitions=(5,))
        op = uuid.uuid4()
        def offer(f):
            try:
                return self.save(f, op)[1]
            except ProvenanceError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(offer, f) for f in (fixture, other)]
            result = [f.result(timeout=20) for f in futures]
        self.assertEqual(sum(isinstance(x, CommittedSyntheticRegistration) for x in result), 1)
        self.assertEqual(sum(x == "NP_OPERATION_CONFLICT" for x in result), 1)
        self.assertEqual(self.snapshot(native=True), native)
