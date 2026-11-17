"""Invented-only acquisition metadata; no raw data, files, network or admission."""
import copy
import hashlib
import json
import unittest
from dataclasses import FrozenInstanceError, replace
from unittest.mock import patch

from marketdata import acquisition as a
from marketdata.manifest import FileManifest, ManifestError
from marketdata.manifest_v2 import FileManifestV2, read_manifest_metadata, verify_acquisition_binding


def h(text):
    return hashlib.sha256(text.encode()).hexdigest()


def encode(obj):
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def envelope_obj():
    return {
        "schema": "finweb.marketdata.acquisition_envelope/1",
        "actor": {"kind": "AGENT", "agent_id": "/root/invented_collector", "role": "engineer"},
        "authorization": {"kind": "HUMAN_DECISION", "decision_record": "decisions/product/PD-9001-invented-evaluation.md",
                          "decision_sha256": h("invented decision"), "approval_receipt_sha256": h("invented approval receipt")},
        "tool": {"name": "invented_collector.py", "version": "1.0.0", "sha256": h("invented frozen tool")},
        "request": {"fingerprint_schema": "fictional.request_spec/1", "sha256": h("invented full request including scoped purpose"),
                    "source_id": "fictional.source", "provider": "InventedProvider", "product": "invented_split_rows",
                    "method": "GET", "host": "fictional.invalid", "path": "/api/splits/FICTION",
                    "parameters": [["from", "2001-02-03"], ["to", "2001-02-03"], ["fmt", "json"]]},
        "attempt": {"max_attempts": 1, "ordinal": 1, "reservation_receipt_sha256": h("invented reservation"),
                    "execution_receipt_sha256": h("invented outer execution receipt")},
        "result": {"state": "COMPLETE", "http_status": 200, "payload_sha256": h("invented body digest only"),
                   "size_bytes": 73, "retrieved_at": "2001-02-04T03:02:01Z"},
        "evidence": [{"role": role, "sha256": h("invented artifact " + role)} for role in
                     ("APPROVAL_PACKET", "REQUEST_SPEC", "EXECUTION_METADATA", "EXECUTION_REVIEW")],
        "visibility": {"raw": "PRIVATE_LOCAL_ONLY", "model": "APPROVED_METADATA_ONLY"},
    }


def manifest_obj(envelope):
    return {
        "schema": "finweb.marketdata.file_manifest/2", "file_sha256": h("invented body digest only"),
        "size_bytes": 73, "payload_filename": "invented.json", "payload_format": "fictional_split_rows/1",
        "source_id": "fictional.source", "data_kind": "CORPORATE_ACTION", "market": None,
        "retrieval_time": "2001-02-04T03:02:01Z", "retrieved_by": "agent",
        "request": [["from", "2001-02-03"], ["to", "2001-02-03"], ["fmt", "json"]],
        "declared_adjustment": "RAW", "adjustment_anchor": None, "declared_currency": None,
        "declared_delay": "UNKNOWN", "source_identifiers": ["FICTION.US"],
        "script": {"name": "invented_collector.py", "version": "1.0.0", "script_sha256": h("invented frozen tool")},
        "libraries": [], "usage_scope": "INTERNAL_DEVELOPMENT_ONLY", "coverage": [["from", "2001-02-03"], ["to", "2001-02-03"]],
        "acquisition": {"schema": "finweb.marketdata.acquisition_ref/1", "envelope_sha256": envelope.sha256},
    }


def fixture():
    e = a.AcquisitionEnvelope.from_bytes(encode(envelope_obj()))
    m = FileManifestV2.from_bytes(encode(manifest_obj(e)))
    w = a.TrustedAcquisitionWitness(e.sha256, m.sha256, "/root/invented_collector", "engineer",
                                     h("invented full request including scoped purpose"))
    return e, m, a.EnvelopeIndex(((e.sha256, e.to_bytes()),)), w


class EnvelopeParsingTests(unittest.TestCase):
    def invalid(self, obj, code=a.AcquisitionCode.SHAPE_INVALID):
        with self.assertRaises(a.AcquisitionError) as caught:
            a.AcquisitionEnvelope.from_bytes(encode(obj))
        self.assertIs(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code.value)

    def test_canonical_roundtrip_preserves_original_digest_and_bytes(self):
        raw = encode(envelope_obj())
        e = a.AcquisitionEnvelope.from_bytes(raw)
        self.assertEqual(e.to_bytes(), raw)
        self.assertEqual(e.sha256, hashlib.sha256(raw).hexdigest())
        self.assertEqual(e.to_obj(), envelope_obj())

    def test_immutable_bytes_and_fresh_nested_objects(self):
        e = fixture()[0]
        with self.assertRaises(FrozenInstanceError):
            e.content = b"{}"
        copied = e.to_obj()
        copied["actor"]["kind"] = "HUMAN"
        copied["request"]["parameters"][0][1] = "2099-01-01"
        self.assertEqual(e.to_obj()["actor"]["kind"], "AGENT")
        self.assertEqual(e.to_obj()["request"]["parameters"][0][1], "2001-02-03")

    def test_unknown_schema_is_typed_and_never_downgraded(self):
        obj = envelope_obj()
        obj["schema"] = "finweb.marketdata.acquisition_envelope/2"
        self.invalid(obj, a.AcquisitionCode.SCHEMA_UNSUPPORTED)

    def test_exact_keys_at_every_level(self):
        original = envelope_obj()
        for key in original:
            for missing in (False, True):
                obj = copy.deepcopy(original)
                if missing:
                    del obj[key]
                else:
                    obj["unexpected"] = True
                with self.subTest(key=key, missing=missing):
                    self.invalid(obj)
        for key in ("actor", "authorization", "tool", "request", "attempt", "result", "visibility"):
            obj = envelope_obj()
            obj[key]["caller_trust"] = True
            with self.subTest(nested=key):
                self.invalid(obj)

    def test_actor_and_human_approval_stay_separate(self):
        for field, val in (("kind", "HUMAN"), ("agent_id", "human-approved"), ("role", True)):
            obj = envelope_obj()
            obj["actor"][field] = val
            self.invalid(obj)
        for record in ("/private/project/decision.md", "../PD-9001.md", "file:///decision.md"):
            obj = envelope_obj()
            obj["authorization"]["decision_record"] = record
            self.invalid(obj)
        obj = envelope_obj()
        obj["terms_checked_by"] = "HUMAN"
        self.invalid(obj)

    def test_request_projection_forbids_tokens_headers_email_urls_and_duplicates(self):
        for pair in (["api_token", "demo"], ["key", "fictional"], ["Authorization", "Bearer-fixture"],
                     ["fmt", "https://fictional.invalid/path"], ["fmt", "someone@example.invalid"],
                     ["fmt", "json"]):
            obj = envelope_obj()
            obj["request"]["parameters"].append(pair)
            self.invalid(obj)
        for key, val in (("host", "https://fictional.invalid"), ("host", "user@fictional.invalid"),
                         ("path", "/api/../secret"), ("path", "/api?key=fixture"), ("method", "POST")):
            obj = envelope_obj()
            obj["request"][key] = val
            self.invalid(obj)
        for path in ("/Users", "/Users/example/.local/response.json", "/PRIVATE/tmp/result.json",
                     "/tmp/private.json", "/var/cache", "/etc/passwd", "/Volumes/Disk/x", "/home/x",
                     "/root", "/ROOT/evidence", "/api/.local/response", "/api/.LOCAL/response"):
            obj = envelope_obj()
            obj["request"]["path"] = path
            self.invalid(obj)
        obj = envelope_obj()
        obj["request"]["path"] = "/api/root-level/splits"
        self.assertEqual(a.AcquisitionEnvelope.from_bytes(encode(obj)).to_obj()["request"]["path"], obj["request"]["path"])

    def test_completion_status_attempt_counts_and_integer_types(self):
        for state in ("FAILED", "UNKNOWN", "CANDIDATE_OBSERVED"):
            obj = envelope_obj()
            obj["result"]["state"] = state
            self.invalid(obj)
        for value in (True, "200", 201, 0):
            obj = envelope_obj()
            obj["result"]["http_status"] = value
            self.invalid(obj)
        for key in ("max_attempts", "ordinal"):
            for val in (True, 0, 2, "1"):
                obj = envelope_obj()
                obj["attempt"][key] = val
                self.invalid(obj)
        for val in (True, -1, "73", 9223372036854775808):
            obj = envelope_obj()
            obj["result"]["size_bytes"] = val
            self.invalid(obj)

    def test_canonical_utc_seconds_and_required_tool_identity(self):
        for val in (None, "2001-02-04T03:02:01+00:00", "2001-02-04T03:02:01.000Z",
                    "2001-02-30T00:00:00Z", "2001-02-04T24:00:00Z"):
            obj = envelope_obj()
            obj["result"]["retrieved_at"] = val
            self.invalid(obj)
        for key in ("name", "version", "sha256"):
            obj = envelope_obj()
            obj["tool"][key] = None
            self.invalid(obj)

    def test_all_four_evidence_roles_required_once_and_in_order(self):
        original = envelope_obj()
        for evidence in ([], original["evidence"][:3], list(reversed(original["evidence"])),
                         [original["evidence"][0]] * 4, original["evidence"] + [original["evidence"][0]]):
            obj = envelope_obj()
            obj["evidence"] = evidence
            self.invalid(obj)
        # Deliberately distinct artifact identities need not equal decisions/full specs.
        e = a.AcquisitionEnvelope.from_bytes(encode(original))
        self.assertNotEqual(e.to_obj()["evidence"][1]["sha256"], original["request"]["sha256"])

    def test_noncanonical_utf8_json_duplicate_keys_and_scalar_coercions_refuse(self):
        raw = encode(envelope_obj())
        bad = (raw[:-1], b"\xef\xbb\xbf" + raw, raw + b" ", raw.replace(b"\n", b"\r\n"),
               json.dumps(envelope_obj(), separators=(",", ":")).encode(), b"\xff", b"{}{}",
               b'{"schema":"x","schema":"y"}\n', b'{"x":NaN}\n', b'{"x":Infinity}\n',
               b'{"x":1e0}\n', b'{"x":1.0}\n', b'[]\n')
        for value in bad:
            with self.subTest(value=value[:20]):
                with self.assertRaises(a.AcquisitionError):
                    a.AcquisitionEnvelope.from_bytes(value)
        for value in (bytearray(raw), raw.decode()):
            with self.assertRaises(a.AcquisitionError):
                a.AcquisitionEnvelope.from_bytes(value)

    def test_nfc_controls_and_surrogates_reject_without_normalizing(self):
        for value in ("e\u0301", "line\nfeed", "tab\t", "zero\u200bwidth"):
            obj = envelope_obj()
            obj["actor"]["role"] = value
            self.invalid(obj)
        with self.assertRaises(a.AcquisitionError):
            a.AcquisitionEnvelope.from_bytes(b'{"x":"\\ud800"}\n')

    def test_pre_tree_bounds_and_exact_lexical_boundaries(self):
        oversized = (b" " * 65537, encode({"x": "z" * 4097}), encode({"x": [None] * 4096}),
                     b"[" * 9 + b"0" + b"]" * 9, b'{"x":12345678901234567890}\n')
        with patch.object(a.json, "loads", side_effect=AssertionError("tree reached")) as tree:
            for raw in oversized:
                with self.assertRaises(a.AcquisitionError):
                    a.parse_canonical_metadata(raw)
            tree.assert_not_called()
        for raw in (encode({"x": "z" * 4096}), encode({"x": [None] * 4095}),
                    b"[" * 8 + b"0" + b"]" * 8):
            with patch.object(a.json, "loads", side_effect=AssertionError("boundary tree reached")):
                with self.assertRaisesRegex(AssertionError, "boundary tree reached"):
                    a.parse_canonical_metadata(raw)


class ManifestAndBindingTests(unittest.TestCase):
    def test_v2_agent_roundtrip_and_no_claimed_permission(self):
        e, m, index, w = fixture()
        self.assertEqual(FileManifestV2.from_bytes(m.to_bytes()).to_bytes(), m.to_bytes())
        self.assertEqual(m.sha256, hashlib.sha256(m.to_bytes()).hexdigest())
        self.assertEqual(m.to_obj()["retrieved_by"], "agent")
        result = verify_acquisition_binding(m, index, w)
        self.assertEqual(result.state, "INTEGRITY_BOUND_NOT_ADMITTED")
        self.assertFalse(result.promotable)
        self.assertFalse(hasattr(result, "rights_granted"))

    def test_manifest_exact_fields_scope_actor_and_nonnullable_binding(self):
        e = fixture()[0]
        original = manifest_obj(e)
        mutations = [("retrieved_by", "human"), ("retrieved_by", "synthetic"),
                     ("usage_scope", "SYNTHETIC_TEST"), ("usage_scope", "LICENSED_DISPLAY"),
                     ("size_bytes", True), ("source_identifiers", [[]]),
                     ("source_identifiers", ["X", "X"]), ("payload_filename", "../x.json")]
        for key, val in mutations:
            obj = copy.deepcopy(original)
            obj[key] = val
            with self.subTest(key=key, val=val):
                with self.assertRaises(a.AcquisitionError):
                    FileManifestV2.from_bytes(encode(obj))
        for key in ("name", "version", "script_sha256"):
            obj = copy.deepcopy(original)
            obj["script"][key] = None
            with self.assertRaises(a.AcquisitionError):
                FileManifestV2.from_bytes(encode(obj))
        for key in original:
            obj = copy.deepcopy(original)
            del obj[key]
            with self.assertRaises(a.AcquisitionError):
                FileManifestV2.from_bytes(encode(obj))

    def test_v1_original_reader_and_serializer_unchanged_and_agent_refused(self):
        obj = manifest_obj(fixture()[0])
        del obj["acquisition"]
        obj["schema"] = "finweb.marketdata.file_manifest/1"
        obj["retrieved_by"] = "synthetic"
        raw = encode(obj)
        legacy = FileManifest.from_json(raw.decode())
        self.assertEqual(legacy.to_json().encode(), raw)
        self.assertIsInstance(read_manifest_metadata(raw), FileManifest)
        self.assertEqual(read_manifest_metadata(raw).to_json().encode(), raw)
        obj["retrieved_by"] = "agent"
        with self.assertRaises(ManifestError):
            FileManifest.from_json(encode(obj).decode())
        with self.assertRaises(a.AcquisitionError):
            read_manifest_metadata(encode(obj))

    def test_opt_in_dispatcher_is_stricter_than_legacy_and_never_downgrades(self):
        e, m, _, _ = fixture()
        self.assertIsInstance(read_manifest_metadata(m.to_bytes()), FileManifestV2)
        with self.assertRaises(ManifestError):
            FileManifest.from_json(m.to_bytes().decode())
        obj = manifest_obj(e)
        obj["schema"] = "finweb.marketdata.file_manifest/99"
        with self.assertRaises(a.AcquisitionError) as caught:
            read_manifest_metadata(encode(obj))
        self.assertIs(caught.exception.code, a.AcquisitionCode.SCHEMA_UNSUPPORTED)
        obj["schema"] = "finweb.marketdata.file_manifest/1"
        obj["retrieved_by"] = "human"
        del obj["acquisition"]
        noncanonical = json.dumps(obj).encode()
        self.assertIsInstance(FileManifest.from_json(noncanonical.decode()), FileManifest)
        with self.assertRaises(a.AcquisitionError):
            read_manifest_metadata(noncanonical)

    def test_witness_required_and_caller_flags_cannot_attest_actor(self):
        _, m, index, w = fixture()
        for value in (None, True, {"approved": True}, {"actor_verified": True}):
            with self.assertRaises(a.AcquisitionError) as caught:
                verify_acquisition_binding(m, index, value)
            self.assertIs(caught.exception.code, a.AcquisitionCode.AUTHORITY_MISSING)
        for changed in (replace(w, actor_agent_id="/root/other"), replace(w, actor_role="pm")):
            with self.assertRaises(a.AcquisitionError) as caught:
                verify_acquisition_binding(m, index, changed)
            self.assertIs(caught.exception.code, a.AcquisitionCode.ACTOR_UNVERIFIED)

    def test_all_independent_expected_digests_are_exact(self):
        _, m, index, w = fixture()
        for name in ("expected_envelope_sha256", "expected_manifest_sha256", "approved_full_request_sha256"):
            with self.subTest(name=name):
                with self.assertRaises(a.AcquisitionError) as caught:
                    verify_acquisition_binding(m, index, replace(w, **{name: h("different " + name)}))
                self.assertIs(caught.exception.code, a.AcquisitionCode.BINDING_DIFFERS)

    def test_crossbinding_rejects_even_when_whole_manifest_digest_is_expected(self):
        e, m, index, w = fixture()
        mutations = [("file_sha256", h("other body")), ("size_bytes", 74),
                     ("retrieval_time", "2001-02-04T03:02:02Z"), ("source_id", "fictional.other"),
                     ("request", list(reversed(m.to_obj()["request"]))) ]
        for key, value in mutations:
            obj = m.to_obj()
            obj[key] = value
            changed = FileManifestV2.from_bytes(encode(obj))
            with self.subTest(key=key):
                with self.assertRaises(a.AcquisitionError) as caught:
                    verify_acquisition_binding(changed, index, replace(w, expected_manifest_sha256=changed.sha256))
                self.assertIs(caught.exception.code, a.AcquisitionCode.BINDING_DIFFERS)
        for key in ("name", "version", "script_sha256"):
            obj = m.to_obj()
            obj["script"][key] = h("different tool") if key == "script_sha256" else "different"
            changed = FileManifestV2.from_bytes(encode(obj))
            with self.assertRaises(a.AcquisitionError):
                verify_acquisition_binding(changed, index, replace(w, expected_manifest_sha256=changed.sha256))

    def test_swapped_approval_attempt_tool_request_and_evidence_changes_refuse(self):
        e, m, _, w = fixture()
        for section, key in (("authorization", "decision_sha256"), ("authorization", "approval_receipt_sha256"),
                             ("tool", "sha256"), ("request", "sha256"),
                             ("attempt", "reservation_receipt_sha256"), ("attempt", "execution_receipt_sha256")):
            obj = e.to_obj()
            obj[section][key] = h("swapped artifact")
            changed_e = a.AcquisitionEnvelope.from_bytes(encode(obj))
            changed_m_obj = m.to_obj()
            changed_m_obj["acquisition"]["envelope_sha256"] = changed_e.sha256
            changed_m = FileManifestV2.from_bytes(encode(changed_m_obj))
            with self.assertRaises(a.AcquisitionError):
                verify_acquisition_binding(changed_m, a.EnvelopeIndex(((changed_e.sha256, changed_e.to_bytes()),)), w)


class IndexAndSafetyTests(unittest.TestCase):
    def test_exact_selected_digest_only_no_fallback_or_body_lookup(self):
        e, _, _, _ = fixture()
        index = a.EnvelopeIndex(((h("not selected"), b"not parsed because not selected"), (e.sha256, e.to_bytes())))
        self.assertEqual(index.resolve(e.sha256).to_bytes(), e.to_bytes())
        with self.assertRaises(a.AcquisitionError) as caught:
            index.resolve(h("missing"))
        self.assertIs(caught.exception.code, a.AcquisitionCode.INPUT_UNAVAILABLE)
        with self.assertRaises(a.AcquisitionError) as caught:
            a.EnvelopeIndex(((e.sha256, b"{}\n"),)).resolve(e.sha256)
        self.assertIs(caught.exception.code, a.AcquisitionCode.BINDING_DIFFERS)

    def test_index_bound_duplicates_types_and_freezing(self):
        e = fixture()[0]
        entries = tuple((h("fixture" + str(i)), b"not selected") for i in range(16))
        self.assertEqual(len(a.EnvelopeIndex(entries).entries), 16)
        for value in (list(entries), entries + ((h("17"), b"x"),), ((e.sha256, e.to_bytes()),) * 2,
                      ((e.sha256, bytearray(e.to_bytes())),), (("/private/leaf", b"x"),)):
            with self.assertRaises(a.AcquisitionError):
                a.EnvelopeIndex(value)
        with self.assertRaises(FrozenInstanceError):
            a.EnvelopeIndex(()).entries = entries

    def test_metadata_digests_are_not_payload_identity_or_request_fingerprint(self):
        e, m, _, _ = fixture()
        self.assertNotEqual(e.sha256, e.to_obj()["result"]["payload_sha256"])
        self.assertNotEqual(m.sha256, m.to_obj()["file_sha256"])
        projection_hash = hashlib.sha256(encode({"parameters": e.to_obj()["request"]["parameters"]})).hexdigest()
        self.assertNotEqual(projection_hash, e.to_obj()["request"]["sha256"])

    def test_typed_error_text_never_echoes_input(self):
        obj = envelope_obj()
        obj["request"]["parameters"] = [["api_token", "invented-sensitive-marker"]]
        with self.assertRaises(a.AcquisitionError) as caught:
            a.AcquisitionEnvelope.from_bytes(encode(obj))
        self.assertEqual(str(caught.exception), "ACQUISITION_SHAPE_INVALID")
        self.assertNotIn("invented-sensitive-marker", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
