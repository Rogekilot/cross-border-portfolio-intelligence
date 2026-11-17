"""Author invented-byte N2a cases. No provider, files, DB or old fixture imports."""
import copy
from dataclasses import replace
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import uuid

from marketdata.acquisition import TrustedAcquisitionWitness
from marketdata.synthetic_provenance import (SyntheticArtifactBundle, SyntheticMemberKey,
    ProvenanceError, validate_bundle, registration_request, registration_response)
from persistence.synthetic_provenance_store import SyntheticProvenanceStore, _entry
from psycopg.pq import TransactionStatus


def h(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def invented_fixture(payload=b"synthetic-payload-one\n", acquisitions=(1,), *, financial_context=None, v1=False):
    """INVENTED agent/human fields are not real actions or permissions."""
    manifests, envelopes, raw_witnesses, members, witnesses = {}, {}, {}, [], []
    for n in acquisitions:
        request_pin = h(("invented full request " + str(n)).encode())
        tool_pin = h(b"invented frozen tool")
        time = "2001-02-" + str(n + 3).zfill(2) + "T03:02:01Z"
        parameters = [["from", "2001-02-03"], ["to", "2001-02-03"], ["fmt", "json"]]
        env = dict(schema="finweb.marketdata.acquisition_envelope/1",
            actor=dict(kind="AGENT", agent_id="/root/invented_collector", role="engineer"),
            authorization=dict(kind="HUMAN_DECISION", decision_record="decisions/product/PD-9001-invented-evaluation.md",
                decision_sha256=h(b"invented decision"), approval_receipt_sha256=h(b"invented receipt")),
            tool=dict(name="invented_collector.py", version="1.0.0", sha256=tool_pin),
            request=dict(fingerprint_schema="fictional.request_spec/1", sha256=request_pin, source_id="fictional.source",
                provider="InventedProvider", product="invented_rows", method="GET", host="fictional.invalid", path="/api/splits/FICTION", parameters=parameters),
            attempt=dict(max_attempts=1, ordinal=1, reservation_receipt_sha256=h(("reservation" + str(n)).encode()), execution_receipt_sha256=h(("execution" + str(n)).encode())),
            result=dict(state="COMPLETE", http_status=200, payload_sha256=h(payload), size_bytes=len(payload), retrieved_at=time),
            evidence=[dict(role=r, sha256=h(("invented " + r).encode())) for r in ("APPROVAL_PACKET", "REQUEST_SPEC", "EXECUTION_METADATA", "EXECUTION_REVIEW")],
            visibility=dict(raw="PRIVATE_LOCAL_ONLY", model="APPROVED_METADATA_ONLY"))
        eraw = encode(env)
        manifest = dict(schema="finweb.marketdata.file_manifest/2", file_sha256=h(payload), size_bytes=len(payload),
            payload_filename="invented.json", payload_format="fictional_rows/1", source_id="fictional.source", data_kind="CORPORATE_ACTION", market=None,
            retrieval_time=time, retrieved_by="agent", request=parameters, declared_adjustment="RAW", adjustment_anchor=None, declared_currency=None,
            declared_delay="UNKNOWN", source_identifiers=["FICTION.US"], script=dict(name="invented_collector.py", version="1.0.0", script_sha256=tool_pin),
            libraries=[], usage_scope="INTERNAL_DEVELOPMENT_ONLY", coverage=[["from", "2001-02-03"], ["to", "2001-02-03"]],
            acquisition=dict(schema="finweb.marketdata.acquisition_ref/1", envelope_sha256=h(eraw)))
        if v1:
            del manifest["acquisition"]
            manifest.update(schema="finweb.marketdata.file_manifest/1", retrieved_by="synthetic", usage_scope="SYNTHETIC_TEST")
        mraw = encode(manifest)
        manifests[h(mraw)] = mraw
        if v1:
            members.append(SyntheticMemberKey("CORPORATE_ACTION", h(payload), h(mraw), None, None))
        else:
            # Independent expected request/actor inputs exist before stored w JSON.
            witness = TrustedAcquisitionWitness(h(eraw), h(mraw), "/root/invented_collector", "engineer", request_pin)
            wraw = encode(dict(expected_envelope_sha256=h(eraw), expected_manifest_sha256=h(mraw), actor_agent_id="/root/invented_collector", actor_role="engineer", approved_full_request_sha256=request_pin))
            raw_witnesses[h(wraw)] = wraw
            envelopes[h(eraw)] = eraw
            witnesses.append(witness)
            members.append(SyntheticMemberKey("CORPORATE_ACTION", h(payload), h(mraw), h(eraw), h(wraw)))
    members = tuple(sorted(members, key=lambda x: x.sort_key()))
    ctx = encode(dict(schema="finweb.synthetic_provenance_context/1", scope="SYNTHETIC_TEST", state="INTEGRITY_BOUND_NOT_ADMITTED",
        promotable=False, source_admitted=False, financial_context_sha256=financial_context,
        source_records=[dict(source_id="fictional.source", name="Invented source", upstream_provider="InventedProvider", independence_group="InventedProvider", terms_url=None, terms_check=None, synthetic=True)],
        members=[x.to_obj() for x in members]))
    bundle = SyntheticArtifactBundle(ctx, ((h(payload), payload),), tuple(sorted(manifests.items())), tuple(sorted(envelopes.items())), tuple(sorted(raw_witnesses.items())))
    return bundle, members, tuple(sorted(witnesses, key=lambda x: x.expected_manifest_sha256))


def context_change(bundle, **changes):
    obj = json.loads(bundle.context_bytes)
    obj.update(changes)
    return replace(bundle, context_bytes=encode(obj))


def validate(fixture):
    b, members, witnesses = fixture
    return validate_bundle(b, expected_context_sha256=h(b.context_bytes), expected_members=members, witnesses=witnesses)


class SyntheticProvenanceContracts(unittest.TestCase):
    def test_01_original_bytes_and_nonadmission(self):
        fixture = invented_fixture()
        value = validate(fixture)
        self.assertEqual(value.bundle, fixture[0])
        self.assertEqual(value.bundle.payloads[0][1], b"synthetic-payload-one\n")
        self.assertEqual(len(value.bundle.payloads[0][1]), 22)
        self.assertEqual((value.scope, value.state, value.promotable, value.source_admitted), ("SYNTHETIC_TEST", "INTEGRITY_BOUND_NOT_ADMITTED", False, False))
        self.assertFalse(hasattr(value, "rights"))

    def test_02_many_acquisitions_share_payload_without_collapsing(self):
        old = validate(invented_fixture())
        new = validate(invented_fixture(acquisitions=(1, 2)))
        self.assertEqual(len(new.bundle.payloads), 1)
        self.assertEqual(len(new.bundle.manifests), 2)
        self.assertEqual(len(new.bundle.envelopes), 2)
        self.assertEqual(new.members[0].payload_sha256, new.members[1].payload_sha256)
        self.assertNotEqual(new.members[0].manifest_sha256, new.members[1].manifest_sha256)
        self.assertEqual(old.bundle, invented_fixture()[0])

    def test_03_empty_and_maximum_payload(self):
        self.assertEqual(validate(invented_fixture(b"")).bundle.payloads[0][1], b"")
        self.assertEqual(len(validate(invented_fixture(b"x" * 65536)).bundle.payloads[0][1]), 65536)

    def test_04_byte_limits_precede_metadata_tree(self):
        b, m, w = invented_fixture()
        huge = b"x" * 65537
        b = replace(b, payloads=((h(huge), huge),))
        with patch("marketdata.synthetic_provenance.parse_canonical_metadata", side_effect=AssertionError("tree reached")) as tree:
            with self.assertRaises(ProvenanceError):
                validate((b, m, w))
            tree.assert_not_called()

    def test_05_scope_flags_are_exact_and_no_rights(self):
        b, m, w = invented_fixture()
        for change in (dict(scope="REAL"), dict(promotable=True), dict(source_admitted=True), dict(state="QUALIFIED"), dict(promotable=0)):
            with self.subTest(change=change), self.assertRaises(ProvenanceError):
                validate((context_change(b, **change), m, w))

    def test_06_independent_actor_and_full_request_witness(self):
        b, m, w = invented_fixture()
        for wrong in (replace(w[0], actor_agent_id="/root/other"), replace(w[0], approved_full_request_sha256=h(b"another full request"))):
            with self.assertRaisesRegex(ProvenanceError, "NP_BINDING_DIFFERS"):
                validate((b, m, (wrong,)))

    def test_07_changed_bytes_do_not_keep_an_old_digest(self):
        b, m, w = invented_fixture()
        key, raw = b.envelopes[0]
        with self.assertRaisesRegex(ProvenanceError, "NP_BINDING_DIFFERS"):
            validate((replace(b, envelopes=((key, raw + b" "),)), m, w))

    def test_08_missing_and_extraneous_artifacts(self):
        b, m, w = invented_fixture()
        for changed in (replace(b, envelopes=()), replace(b, payloads=tuple(sorted(b.payloads + ((h(b"extra"), b"extra"),))))):
            with self.assertRaises(ProvenanceError):
                validate((changed, m, w))

    def test_09_digest_order_and_duplicate_members_refuse(self):
        b, m, w = invented_fixture(acquisitions=(1, 2))
        for changed in (replace(b, manifests=tuple(reversed(b.manifests))), replace(b, manifests=b.manifests + b.manifests[:1]), context_change(b, members=[m[0].to_obj(), m[0].to_obj()])):
            with self.assertRaises(ProvenanceError):
                validate((changed, m, w))
        with self.assertRaises(ProvenanceError):
            validate((b, tuple(reversed(m)), w))

    def test_10_manifest_kind_is_the_member_role(self):
        b, m, w = invented_fixture()
        wrong = replace(m[0], role="QUOTE")
        with self.assertRaisesRegex(ProvenanceError, "NP_BINDING_DIFFERS"):
            validate((context_change(b, members=[wrong.to_obj()]), (wrong,), w))

    def test_11_source_records_are_exact_selected_set(self):
        b, m, w = invented_fixture()
        sources = json.loads(b.context_bytes)["source_records"]
        extra = dict(sources[0], source_id="unused.source")
        with self.assertRaisesRegex(ProvenanceError, "NP_BINDING_DIFFERS"):
            validate((context_change(b, source_records=sources + [extra]), m, w))
        sources[0]["synthetic"] = False
        with self.assertRaisesRegex(ProvenanceError, "NP_SCOPE_REFUSED"):
            validate((context_change(b, source_records=sources), m, w))

    def test_12_v1_compatibility_has_explicit_null_provenance(self):
        b, members, witnesses = invented_fixture(v1=True)
        value = validate((b, members, witnesses))
        self.assertIsNone(value.members[0].envelope_sha256)
        self.assertEqual((b.envelopes, b.witnesses, witnesses), ((), (), ()))
        manifest = json.loads(b.manifests[0][1])
        manifest["retrieved_by"] = "human"
        raw = encode(manifest)
        member = replace(members[0], manifest_sha256=h(raw))
        changed = replace(context_change(b, members=[member.to_obj()]), manifests=((h(raw), raw),))
        with self.assertRaisesRegex(ProvenanceError, "NP_SCOPE_REFUSED"):
            validate((changed, (member,), ()))

    def test_13_v2_is_not_downgraded_when_provenance_is_missing(self):
        b, m, w = invented_fixture()
        wrong = replace(m[0], envelope_sha256=None, witness_sha256=None)
        b = replace(context_change(b, members=[wrong.to_obj()]), envelopes=(), witnesses=())
        with self.assertRaisesRegex(ProvenanceError, "NP_BINDING_DIFFERS"):
            validate((b, (wrong,), ()))

    def test_14_noncanonical_context_and_independent_pin_mismatch(self):
        b, m, w = invented_fixture()
        with self.assertRaises(ProvenanceError):
            validate((replace(b, context_bytes=b.context_bytes[:-1]), m, w))
        with self.assertRaisesRegex(ProvenanceError, "NP_CONTEXT_DIFFERS"):
            validate_bundle(b, expected_context_sha256=h(b"wrong context"), expected_members=m, witnesses=w)

    def test_15_no_io_or_environment_fallback(self):
        fixture = invented_fixture()
        with patch("builtins.open", side_effect=AssertionError("file fallback")), patch("os.getenv", side_effect=AssertionError("environment fallback")):
            self.assertEqual(validate(fixture).bundle, fixture[0])

    def test_16_request_response_exact_keys_and_selected_counts(self):
        value = validate(invented_fixture(acquisitions=(1, 2)))
        op = uuid.UUID("90000000-0000-4000-8000-000000000001")
        b = value.bundle
        expected = encode(dict(schema="finweb.synthetic_provenance_registration/1", scope="SYNTHETIC_TEST", operation_id=str(op), context_sha256=h(b.context_bytes), payload_sha256s=[x[0] for x in b.payloads], manifest_sha256s=[x[0] for x in b.manifests], envelope_sha256s=[x[0] for x in b.envelopes], witness_sha256s=[x[0] for x in b.witnesses]))
        self.assertEqual(registration_request(op, value), expected)
        response = registration_response(op, expected, value)
        obj = json.loads(response)
        self.assertEqual(set(obj), set("schema scope state promotable source_admitted operation_id request_sha256 context_sha256 payload_count manifest_count envelope_count member_count".split()))
        self.assertEqual((obj["payload_count"], obj["manifest_count"], obj["envelope_count"], obj["member_count"]), (1, 2, 2, 2))
        self.assertEqual(response, json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
        self.assertEqual(obj["request_sha256"], h(expected))

    def test_17_autocommit_and_idle_are_checked_without_a_query(self):
        for ac, state in ((False, TransactionStatus.IDLE), (True, TransactionStatus.INTRANS)):
            conn = SimpleNamespace(autocommit=ac, info=SimpleNamespace(transaction_status=state), execute=Mock(side_effect=AssertionError("query reached")))
            with self.assertRaisesRegex(ProvenanceError, "NP_OUTER_TRANSACTION_REQUIRED"):
                _entry(conn)
            conn.execute.assert_not_called()

    def test_18_preflight_refusal_cannot_open_a_connection(self):
        connect = Mock(side_effect=AssertionError("DB reached"))
        store = SyntheticProvenanceStore(connect, schema="n2a", loader_role="n2a_loader", executor_role="n2a_executor")
        b, m, w = invented_fixture()
        with self.assertRaisesRegex(ProvenanceError, "NP_CONTEXT_DIFFERS"):
            store.register(uuid.uuid4(), b, expected_context_sha256=h(b"wrong pin"), expected_members=m, witnesses=w)
        with self.assertRaises(ProvenanceError):
            store.reconcile("not-uuid", expected_request_sha256="0" * 64, expected_context_sha256=h(b.context_bytes), expected_members=m, witnesses=w)
        connect.assert_not_called()
