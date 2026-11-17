"""F1 R4b: the sidecar acquisition record, its reader, and the O5 validator (design 4.2, 6.1; design 7.1, R4b row). Pure tests: no database.

Every sidecar here is INVENTED and lives in memory only. No sidecar file is written for an invented payload (design 4.2: stored, it would
differ from a real acquisition only by the source's synthetic flag; conformance R2-L1 (i)). The validator takes sidecars BY VALUE and
writes nothing: a test runs it with every file-writing door closed, and a static test reads the module for them.

Cases follow the table of design 4.2, row O5:
  failing (code must be listed): in the REAL scope a member with the legacy null slot, a sidecar whose payload or manifest digest differs, whose
  approver role is not the owner's, or whose decision triple is missing;
  control (code must be absent): a member with an in-memory sidecar that is valid in every respect, in the REAL scope with synthetic sources,
  so O1 and O2 are still listed.
"""
from __future__ import annotations

import ast
import dataclasses
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

import real_gateway_fixtures as fx  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from marketdata.manifest import SourceRecord as EngineSource, source_registry_digest  # noqa: E402
from persistence import real_proposal as rp, real_provenance as prov, real_sidecar as sc  # noqa: E402
from persistence.real_scope import SCOPES, ScopeError, resolve_scope  # noqa: E402
from persistence.real_workspace_store import RealPublisher, EXIT_DONE, EXIT_REFUSED  # noqa: E402
from test_real_publisher_tool import CTX, FakeConnection, LATER  # noqa: E402

SRC = HERE.parents[1] / "src"
REAL = resolve_scope("REAL")
TEST_SWITCH = resolve_scope("TEST_SWITCH", test_switch=True)
SYNTHETIC = resolve_scope("SYNTHETIC_TEST")
ALL_SCOPES = (SYNTHETIC, TEST_SWITCH)


def h(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def good(payload="p1", manifest="m1", **changes):
    """The bytes of a sidecar that is valid in every respect, for the file (payload, manifest). `changes` replaces keyword arguments."""
    args = dict(payload_sha256=h(payload), manifest_sha256=h(manifest), pd_id="PD-9001", git_commit="a" * 40, doc_sha256="b" * 64,
                request="invented request as approved", tool="invented tool", terms_check_reference="invented terms reference")
    args.update(changes)
    return sc.encode_sidecar(**args)


def member(payload="p1", manifest="m1", data=None, source="syn.alpha"):
    """A snapshot member for the file; its provenance slot is the digest of `data` (None: the legacy null)."""
    return rp.Member(h(payload), h(manifest), source, None if data is None else sc.sidecar_digest(data), "syn.adapter", "1")


def codes(scope, members, sidecars=(), sha=None):
    return sc.o5_failures(scope, members, sidecars).codes(sha)


def replaced(data, **changes):
    document = json.loads(data)
    document.update(changes)
    return canonical_json(document).encode("utf-8")


class ReaderTests(unittest.TestCase):
    def test_an_encoded_sidecar_reads_back_and_its_digest_is_the_sha256_of_its_bytes(self):
        data = good()
        side = sc.read_sidecar(data)
        self.assertEqual((side.payload_sha256, side.manifest_sha256), (h("p1"), h("m1")))
        self.assertEqual((side.approver_role, side.pd_id, side.git_commit, side.doc_sha256), (sc.APPROVER_ROLE, "PD-9001", "a" * 40, "b" * 64))
        self.assertEqual(side.digest, hashlib.sha256(data).hexdigest())
        self.assertEqual(sc.sidecar_digest(data), side.digest)
        self.assertEqual(sc.encode_sidecar(payload_sha256=h("p1"), manifest_sha256=h("m1"), pd_id="PD-9001", git_commit="a" * 40, doc_sha256="b" * 64,
                                           request="invented request as approved", tool="invented tool", terms_check_reference="invented terms reference"), data)

    def test_the_approver_role_is_a_role_and_not_a_personal_name(self):
        self.assertEqual(sc.APPROVER_ROLE, "designated human product owner")
        self.assertEqual(json.loads(good())["approver_role"], "designated human product owner")

    def test_bytes_that_are_not_a_sidecar_are_refused_with_the_schema_code(self):
        valid = json.loads(good())
        cases = {
            "not bytes": "text", "empty": b"", "junk": b"not json", "a list": b"[]", "oversize": b" " * (sc.MAX_SIDECAR_BYTES + 1),
            "not canonical (spaces)": json.dumps(valid, indent=1).encode(), "duplicate key": b'{"schema":"a","schema":"b"}',
            "a float": canonical_json({**valid, "request": 1}).encode()[:-1] + b',"x":1.5}',
            "wrong schema": replaced(good(), schema="finweb.acquisition_sidecar/2"),
            "an extra key": replaced(good(), personal_name="a person"),
            "a missing key": canonical_json({k: v for k, v in valid.items() if k != "tool"}).encode(),
            "a short digest": replaced(good(), payload_sha256="abc"), "an upper-case digest": replaced(good(), manifest_sha256="A" * 64),
            "an empty request": replaced(good(), request=""), "a request that is not text": replaced(good(), request=5),
            "a role that is not text": replaced(good(), approver_role=None),
        }
        for label, data in cases.items():
            with self.subTest(label):
                with self.assertRaises(sc.SidecarError) as caught:
                    sc.read_sidecar(data)
                self.assertEqual(caught.exception.code, sc.O5_SCHEMA)

    def test_the_approver_role_and_the_triple_are_o5_predicates_not_reader_errors(self):
        # A sidecar that fails them can be READ and then reported by O5 (a reader that raised would hide the other failures).
        side = sc.read_sidecar(good(approver_role="the product owner", pd_id=None, git_commit=None, doc_sha256=None))
        self.assertEqual((side.approver_role, side.pd_id, side.git_commit, side.doc_sha256), ("the product owner", None, None, None))
        self.assertIsNone(sc.read_sidecar(replaced(good(), decision=None)).pd_id)

    def test_reading_writes_nothing_and_takes_bytes_only(self):
        with mock.patch("builtins.open", side_effect=AssertionError("opened a file")), mock.patch.object(Path, "write_bytes", side_effect=AssertionError), \
                mock.patch.object(Path, "write_text", side_effect=AssertionError):
            sc.read_sidecar(good())
            sc.sidecar_digest(good())
            sc.encode_sidecar(payload_sha256=h("a"), manifest_sha256=h("b"), pd_id=None, git_commit=None, doc_sha256=None, request="r", tool="t",
                              terms_check_reference="x")
        with self.assertRaises(sc.SidecarError):
            sc.sidecar_digest("a path, not bytes")


class O5FailingAndControlCasesTests(unittest.TestCase):
    """Design 4.2, row O5. Each failing case varies ONLY the input of the predicate under test, and asserts that the predicate's code is in
    the full failure list; the control differs in that input alone and asserts the code is absent."""

    def case(self, data, *, payload="p1", manifest="m1"):
        return codes(REAL, [member(payload, manifest, data)], [data])

    def test_a_valid_sidecar_passes_every_o5_predicate_in_the_real_scope(self):
        data = good()
        report = sc.o5_failures(REAL, [member(data=data)], [data])
        self.assertEqual((report.failures, report.ok, report.bypassed), ((), True, False))
        self.assertEqual(sc.require_o5(REAL, [member(data=data)], [data]).failures, ())

    def test_the_legacy_null_slot_is_refused_in_the_real_scope(self):
        self.assertIn(sc.O5_LEGACY_NULL, codes(REAL, [member()]))
        self.assertNotIn(sc.O5_LEGACY_NULL, self.case(good()))                                              # control: the same member with its slot filled

    def test_a_member_with_no_sidecar_among_those_given_is_missing(self):
        data = good()
        self.assertIn(sc.O5_MISSING, codes(REAL, [member(data=data)], []))
        self.assertIn(sc.O5_MISSING, codes(REAL, [member(data=data)], [good(payload="another file", manifest="another")]))
        self.assertNotIn(sc.O5_MISSING, self.case(data))

    def test_a_sidecar_whose_payload_digest_differs_is_listed(self):
        self.assertIn(sc.O5_PAYLOAD, self.case(good(payload_sha256=h("some other payload"))))
        self.assertNotIn(sc.O5_PAYLOAD, self.case(good()))

    def test_a_sidecar_whose_manifest_digest_differs_is_listed(self):
        self.assertIn(sc.O5_MANIFEST, self.case(good(manifest_sha256=h("some other manifest"))))
        self.assertNotIn(sc.O5_MANIFEST, self.case(good()))

    def test_a_sidecar_whose_approver_role_is_not_the_owners_is_listed(self):
        for role in ("the product owner", "engineer", "main session", "designated human product owner ", "Designated Human Product Owner", "human"):
            with self.subTest(role):
                self.assertIn(sc.O5_ROLE, self.case(good(approver_role=role)))
        self.assertNotIn(sc.O5_ROLE, self.case(good()))

    def test_a_sidecar_whose_decision_triple_is_missing_or_malformed_is_listed(self):
        cases = {
            "no decision": replaced(good(), decision=None), "all three None": good(pd_id=None, git_commit=None, doc_sha256=None),
            "pd id missing": good(pd_id=None), "commit missing": good(git_commit=None), "doc digest missing": good(doc_sha256=None),
            "pd id malformed": good(pd_id="pd-9001"), "pd id too short": good(pd_id="PD-1"), "commit too short": good(git_commit="a" * 39),
            "commit upper case": good(git_commit="A" * 40), "doc digest too short": good(doc_sha256="b" * 63),
            "an extra key in the triple": replaced(good(), decision={"pd_id": "PD-9001", "git_commit": "a" * 40, "doc_sha256": "b" * 64, "x": 1}),
            "a triple that is not an object": replaced(good(), decision=["PD-9001", "a" * 40, "b" * 64]),
        }
        document = json.loads(good())
        del document["decision"]
        cases["the key absent"] = canonical_json(document).encode("utf-8")
        for label, data in cases.items():
            with self.subTest(label):
                self.assertIn(sc.O5_TRIPLE, self.case(data))
                self.assertNotIn(sc.O5_SCHEMA, self.case(data))                                              # the outline is fine: this is O5's own predicate
        self.assertNotIn(sc.O5_TRIPLE, self.case(good()))

    def test_bytes_that_are_not_a_sidecar_list_the_schema_code_and_nothing_that_needed_a_parse(self):
        junk = b"not a sidecar"
        self.assertEqual(self.case(junk), (sc.O5_SCHEMA,))
        self.assertEqual(sc.sidecar_failures(replaced(good(), extra=1), payload_sha256=h("p1"), manifest_sha256=h("m1"), slot=h("x")), (sc.O5_SCHEMA,))

    def test_the_slot_must_be_the_digest_of_the_sidecars_bytes(self):
        data = good()
        self.assertEqual(sc.sidecar_failures(data, payload_sha256=h("p1"), manifest_sha256=h("m1"), slot=sc.sidecar_digest(data)), ())
        self.assertEqual(sc.sidecar_failures(data, payload_sha256=h("p1"), manifest_sha256=h("m1"), slot=h("another record")), (sc.O5_SLOT,))
        self.assertEqual(sc.sidecar_failures(data, payload_sha256=h("p1"), manifest_sha256=h("m1"), slot=None), (sc.O5_SLOT,))

    def test_every_failed_predicate_of_every_member_is_listed_not_the_first(self):
        bad = good(payload_sha256=h("other"), manifest_sha256=h("other"), approver_role="a person", pd_id=None)
        listed = self.case(bad)
        self.assertEqual(listed, tuple(sorted((sc.O5_PAYLOAD, sc.O5_MANIFEST, sc.O5_ROLE, sc.O5_TRIPLE))))
        two = [member("p1", "m1", bad), member("p2", "m2", good("p2", "m2")), member("p3", "m3")]
        report = sc.o5_failures(REAL, two, [bad, good("p2", "m2")])
        self.assertEqual(report.codes(h("p1")), listed)
        self.assertEqual(report.codes(h("p2")), ())
        self.assertEqual(report.codes(h("p3")), tuple(sorted((sc.O5_LEGACY_NULL, sc.O5_MISSING))))
        with self.assertRaises(sc.SidecarError) as caught:
            sc.require_o5(REAL, two, [bad, good("p2", "m2")])
        self.assertEqual(caught.exception.code, sc.O5_FAILED)
        self.assertEqual(set(caught.exception.failures), set(report.failures))

    def test_a_sidecar_for_another_file_does_not_stand_in(self):
        other = good("p2", "m2")
        stolen = rp.Member(h("p1"), h("m1"), "syn.alpha", sc.sidecar_digest(other), "a", "1")          # p1's slot names the record of p2
        self.assertEqual(codes(REAL, [stolen], [other]), tuple(sorted((sc.O5_PAYLOAD, sc.O5_MANIFEST))))

    def test_members_may_be_the_dicts_of_a_snapshot(self):
        data = good()
        self.assertEqual(codes(REAL, [member(data=data).as_dict()], [data]), ())
        self.assertIn(sc.O5_LEGACY_NULL, codes(REAL, [member().as_dict()]))


class BypassInTestScopesTests(unittest.TestCase):
    def test_o5_is_bypassed_in_both_test_scopes_whatever_the_members_hold(self):
        data = good(approver_role="a person", pd_id=None)
        for scope in ALL_SCOPES:
            with self.subTest(scope.name):
                for members, sidecars in (([member()], []), ([member(data=data)], [data]), ([member(data=data)], []), ([member(), member("p2", "m2")], [b"junk"])):
                    report = sc.o5_failures(scope, members, sidecars)
                    self.assertEqual((report.failures, report.ok, report.bypassed), ((), True, True))
                self.assertEqual(sc.require_o5(scope, [member()]).failures, ())

    def test_the_legacy_null_is_accepted_in_a_test_scope_proposal_and_refused_in_the_real_scope(self):
        content = fx.content("legacy")
        self.assertTrue(all(m.acquisition_record_sha256 is None for m in content["members"]))
        for scope in ALL_SCOPES:
            self.assertEqual(rp.verify_proposal(rp.write_proposal(scope, **content)).scope.name, scope.name)
        with self.assertRaises(rp.ProposalError) as caught:
            rp.write_proposal(REAL, **content)
        self.assertEqual(caught.exception.code, sc.O5_LEGACY_NULL)

    def test_a_scope_must_be_a_scope_value(self):
        for bad in ("REAL", "TEST_SWITCH", None, {"origin_axis": "REAL"}):
            with self.assertRaises(ScopeError, msg=repr(bad)):
                sc.o5_failures(bad, [member()])

    def test_the_validator_accepts_a_scope_definition_and_a_resolved_scope_and_does_not_widen_the_switch(self):
        for scope in (REAL, SCOPES["REAL"]):
            self.assertIn(sc.O5_LEGACY_NULL, codes(scope, [member()]))
        # a resolved scope for a test scope needs the reviewed switch; the validator neither needs nor grants it
        with self.assertRaises(ScopeError):
            resolve_scope("TEST_SWITCH")


class TestScopeStoresNoSidecarDigestTests(unittest.TestCase):
    """TR4B-M1 (design 4.2, L-4): the digest of an INVENTED sidecar is an invented human attestation; it is never written to a snapshot, in any scope.
    In a test scope the provenance slot is null, in the writer, in the verifier and in the publisher. The sidecar here is invented and in memory only."""

    CODE = "RW_O5_SLOT_IN_TEST_SCOPE"

    def with_slot(self, tag, index=0):
        content = fx.content(tag)
        index %= len(content["members"])
        first = content["members"][index]
        side = good(payload_sha256=first.payload_sha256, manifest_sha256=first.manifest_sha256)
        content["members"] = [dataclasses.replace(m, acquisition_record_sha256=sc.sidecar_digest(side)) if i == index else m
                              for i, m in enumerate(content["members"])]
        return content, side

    def publish(self, data, conn):
        return RealPublisher(conn, "rw_t").publish(data, rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=fx.hg4_shape(fx.FAR), actor=fx.ACTOR, ref=fx.REF)

    def test_the_code_is_the_one_the_writer_the_verifier_and_the_publisher_share(self):
        self.assertEqual(sc.O5_SLOT_IN_TEST_SCOPE, self.CODE)

    def test_the_writer_refuses_a_filled_slot_in_both_test_scopes(self):
        for scope in ALL_SCOPES:
            for index in (0, -1):
                with self.subTest(scope.name, member=index):
                    content, _ = self.with_slot("w-" + scope.name, index)
                    with self.assertRaises(rp.ProposalError) as caught:
                        rp.write_proposal(scope, **content)
                    self.assertEqual(caught.exception.code, self.CODE)

    def test_the_verifier_refuses_bytes_whose_test_scope_slot_is_filled_even_with_a_fresh_context_id(self):
        """The reviewer's case, by editing valid bytes: set a slot and recompute context_id so that nothing else is wrong."""
        for scope in ALL_SCOPES:
            with self.subTest(scope.name):
                data = rp.write_proposal(scope, **fx.content("v-" + scope.name))
                self.assertEqual(rp.verify_proposal(data).scope.name, scope.name)                      # control: the unedited bytes verify
                document = json.loads(data)
                snapshot = document["snapshot"]
                snapshot["members"][0]["acquisition_record_sha256"] = sc.sidecar_digest(good("zz", "zz"))
                document["context_id"] = hashlib.sha256(canonical_json(snapshot).encode("utf-8")).hexdigest()
                edited = canonical_json(document).encode("utf-8")
                with self.assertRaises(rp.ProposalError) as caught:
                    rp.verify_proposal(edited)
                self.assertEqual(caught.exception.code, self.CODE)

    def test_the_publisher_refuses_such_bytes_before_any_statement(self):
        for scope in ALL_SCOPES:
            with self.subTest(scope.name):
                document = json.loads(rp.write_proposal(scope, **fx.content("p-" + scope.name)))
                snapshot = document["snapshot"]
                snapshot["members"][0]["acquisition_record_sha256"] = sc.sidecar_digest(good("zz", "zz"))
                document["context_id"] = hashlib.sha256(canonical_json(snapshot).encode("utf-8")).hexdigest()
                conn = FakeConnection(rw_publish=[(CTX, 1, True)])
                result = self.publish(canonical_json(document).encode("utf-8"), conn)
                self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, self.CODE))
                self.assertEqual(conn.log, [])
                self.assertEqual(len(conn.calls("rw_publish")), 0)
                self.assertIn("nothing was recorded", result.text)

    def test_the_publisher_checks_the_slots_itself_when_the_verifier_would_pass_the_bytes(self):
        """The publisher's own check is not shadowed by the verifier's: with the verifier stubbed to accept (as a future verifier change might), the
        publisher still refuses, before any statement."""
        content, _ = self.with_slot("stub")
        stub = mock.Mock()
        stub.scope = SYNTHETIC
        stub.snapshot.content = {"members": [m.as_dict() for m in content["members"]]}
        stub.snapshot.data = b"{}"
        conn = FakeConnection(rw_publish=[(CTX, 1, True)])
        with mock.patch.object(rp, "verify_proposal", return_value=stub):
            result = self.publish(b"ignored by the stub", conn)
        self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, self.CODE))
        self.assertEqual(conn.log, [])

    def test_the_unit_check_is_a_no_op_in_the_real_scope_and_lists_every_member_in_a_test_scope(self):
        data = good()
        filled = [member(data=data), member("p2", "m2", data=good("p2", "m2")), member("p3", "m3")]
        self.assertIsNone(sc.require_null_slots_in_test_scope(REAL, filled))                              # REAL: O5 decides, not this check
        for scope in ALL_SCOPES:
            with self.subTest(scope.name):
                with self.assertRaises(sc.SidecarError) as caught:
                    sc.require_null_slots_in_test_scope(scope, filled)
                self.assertEqual(caught.exception.code, self.CODE)
                self.assertEqual(tuple(sha for sha, _ in caught.exception.failures), tuple(sorted((h("p1"), h("p2")))))
                self.assertEqual({code for _, code in caught.exception.failures}, {self.CODE})
                self.assertIsNone(sc.require_null_slots_in_test_scope(scope, [member(), member("p2", "m2")]))   # control: all null passes
                self.assertIsNone(sc.require_null_slots_in_test_scope(scope, [m.as_dict() for m in [member()]]))

    def test_controls_a_real_proposal_still_carries_its_slots_and_a_test_proposal_still_carries_nulls(self):
        content = fx.content("control")
        real_members = [rp.Member(m.payload_sha256, m.manifest_sha256, m.source_id,
                                  sc.sidecar_digest(good(payload_sha256=m.payload_sha256, manifest_sha256=m.manifest_sha256)), m.adapter_id, m.adapter_version)
                        for m in content["members"]]
        real = rp.verify_proposal(rp.write_proposal(REAL, **dict(content, members=real_members)))
        self.assertTrue(all(m["acquisition_record_sha256"] for m in real.snapshot.content["members"]))
        for scope in ALL_SCOPES:
            test = rp.verify_proposal(rp.write_proposal(scope, **content))
            self.assertTrue(all(m["acquisition_record_sha256"] is None for m in test.snapshot.content["members"]))


class IndependenceFromO1ToO3Tests(unittest.TestCase):
    """Design 4.2: candidate validation evaluates O1 to O3 and O5 independently and reports every predicate that fails. The control is a valid
    in-memory sidecar in the REAL scope with synthetic sources: O1 and O2 are still listed, no O5 code is."""

    SOURCES = [{"source_id": "syn.alpha", "synthetic": True, "terms_check": None}]
    ORIGIN_MEMBERS = [{"manifest_sha256": h("m1"), "schema": prov.MANIFEST_V1, "retrieved_by": "synthetic", "usage_scope": "SYNTHETIC_TEST"}]

    def failures(self, members, sidecars=(), **kw):
        """The combined verdict. With no invented attestation it is the product function `candidate_failures`; with one (`terms_checks`,
        `acquisitions`, by value) the test calls `origin_report` itself and joins the O5 codes the way the product function does, because no
        product call site may pass an attestation (test_real_provenance)."""
        if not kw:
            return sc.candidate_failures(REAL, self.SOURCES, self.ORIGIN_MEMBERS, members, sidecars)
        return tuple(prov.origin_report(self.SOURCES, self.ORIGIN_MEMBERS, **kw).failed) + sc.o5_failures(REAL, members, sidecars).codes()

    def test_the_control_lists_o1_and_o2_and_no_o5_code(self):
        data = good()
        listed = self.failures([member(data=data)], [data])
        self.assertEqual(listed, (prov.O1, prov.O2, prov.O3))
        self.assertFalse([c for c in listed if c.startswith("RW_O5")])

    def test_the_control_with_invented_human_attestations_by_value_still_lists_o1_and_each_o5_failure_adds_its_own_code(self):
        data = good()
        permit = {"checked_by": "invented", "checked_on": "2026-01-02", "permits_internal_development_use": True, "notes": ""}
        invented = {h("m1"): {"schema": prov.MANIFEST_V1, "retrieved_by": "human", "usage_scope": "INTERNAL_DEVELOPMENT_ONLY"}}
        kw = dict(terms_checks={"syn.alpha": permit}, acquisitions=invented)
        self.assertEqual(self.failures([member(data=data)], [data], **kw), (prov.O1,))                  # O2 and O3 pass on invented attestations; O1 is by value too
        for label, members, sidecars, expected in (
                ("the legacy null", [member()], [], {sc.O5_LEGACY_NULL, sc.O5_MISSING}),
                ("a payload digest that differs", [member(data=good(payload_sha256=h("x")))], [good(payload_sha256=h("x"))], {sc.O5_PAYLOAD}),
                ("a manifest digest that differs", [member(data=good(manifest_sha256=h("x")))], [good(manifest_sha256=h("x"))], {sc.O5_MANIFEST}),
                ("a role that is not the owner's", [member(data=good(approver_role="x"))], [good(approver_role="x")], {sc.O5_ROLE}),
                ("a triple that is missing", [member(data=good(pd_id=None))], [good(pd_id=None)], {sc.O5_TRIPLE})):
            with self.subTest(label):
                listed = self.failures(members, sidecars, **kw)
                self.assertEqual(listed[0], prov.O1)
                self.assertEqual({c for c in listed if c.startswith("RW_O5")}, expected)
                self.assertEqual(len(listed), len(set(listed)))

    def test_o5_does_not_depend_on_the_origin_verdict_and_the_reverse(self):
        data = good()
        clean = [{"source_id": "syn.alpha", "synthetic": False, "terms_check": {"checked_by": "invented", "checked_on": "2026-01-02",
                                                                              "permits_internal_development_use": True, "notes": ""}}]
        human = [{"manifest_sha256": h("m1"), "schema": prov.MANIFEST_V1, "retrieved_by": "human", "usage_scope": "INTERNAL_DEVELOPMENT_ONLY"}]
        # in-memory records that pass O1 to O3 (a test-local value; never stored, never passed to a store)
        self.assertEqual(sc.candidate_failures(REAL, clean, human, [member(data=data)], [data]), ())
        self.assertEqual(sc.candidate_failures(REAL, clean, human, [member()], []), tuple(sorted((sc.O5_LEGACY_NULL, sc.O5_MISSING))))
        for scope in ALL_SCOPES:                                                                                      # bypassed: only the origin codes remain
            self.assertEqual(sc.candidate_failures(scope, self.SOURCES, self.ORIGIN_MEMBERS, [member()], []), (prov.O1, prov.O2, prov.O3))


class ProposalAndPublisherTests(unittest.TestCase):
    """The REAL scope in memory only: nothing here is stored, published to a database or marked as anything but an invented proof of refusal."""

    def real_content(self, tag="real"):
        content = fx.content(tag)
        sidecars = {}
        members = []
        for m in content["members"]:
            data = good(payload_sha256=m.payload_sha256, manifest_sha256=m.manifest_sha256)
            sidecars[m.source_id] = data
            members.append(rp.Member(m.payload_sha256, m.manifest_sha256, m.source_id, sc.sidecar_digest(data), m.adapter_id, m.adapter_version))
        content["members"] = members
        return content, list(sidecars.values())

    def test_the_verifier_refuses_real_bytes_whose_slot_is_the_legacy_null(self):
        # a test-scope proposal re-labelled as REAL (bytes edited in memory, hashes refreshed) is a REAL proposal with null slots
        document = json.loads(rp.write_proposal(TEST_SWITCH, **fx.content("relabel")))
        snapshot = document["snapshot"]
        snapshot.update(scope="REAL", origin=SCOPES["REAL"].origin_fields())
        data = canonical_json(document).encode("utf-8")
        with self.assertRaises(rp.ProposalError) as caught:
            rp.verify_proposal(data)
        self.assertEqual(caught.exception.code, sc.O5_LEGACY_NULL)

    def test_real_bytes_with_filled_slots_pass_the_verifier_and_o5_with_their_sidecars(self):
        content, sidecars = self.real_content()
        data = rp.write_proposal(REAL, **content)
        verified = rp.verify_proposal(data)
        self.assertEqual(verified.scope.name, "REAL")
        self.assertEqual(sc.o5_failures(verified.scope, verified.snapshot.content["members"], sidecars).failures, ())

    def test_the_publisher_refuses_a_real_proposal_without_valid_sidecars_before_any_statement(self):
        content, sidecars = self.real_content("pub")
        data = rp.write_proposal(REAL, **content)
        args = dict(rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=fx.hg4_shape(fx.FAR), actor=fx.ACTOR, ref=fx.REF)
        bad = [good(payload_sha256=json.loads(s)["payload_sha256"], manifest_sha256=json.loads(s)["manifest_sha256"], approver_role="a person") for s in sidecars]
        for label, given in (("none", ()), ("one missing", sidecars[:-1]), ("junk", [b"junk"]), ("valid bytes but for other files", [good("zz", "zz")])):
            conn = FakeConnection()
            result = RealPublisher(conn, "rw_t").publish(data, sidecars=given, **args)
            self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, sc.O5_FAILED), label)
            self.assertEqual(conn.log, [], label)
            self.assertIn("nothing was recorded", result.text)
        conn = FakeConnection()
        result = RealPublisher(conn, "rw_t").publish(data, sidecars=bad, **args)
        self.assertEqual((result.status, result.data["code"]), (EXIT_REFUSED, sc.O5_FAILED))
        self.assertEqual(conn.log, [])

    def test_the_publisher_reaches_the_database_when_every_member_has_a_valid_sidecar(self):
        content, sidecars = self.real_content("pub2")
        data = rp.write_proposal(REAL, **content)
        conn = FakeConnection(rw_publish=[(CTX, 1, True)])
        result = RealPublisher(conn, "rw_t").publish(data, rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=fx.hg4_shape(fx.FAR), actor=fx.ACTOR,
                                                     ref=fx.REF, sidecars=sidecars)
        self.assertEqual((result.status, result.outcome), (EXIT_DONE, "PUBLISHED"))
        self.assertEqual(len(conn.calls("rw_publish")), 1)

    def test_a_test_scope_publish_ignores_sidecars_and_needs_none(self):
        data = rp.write_proposal(SYNTHETIC, **fx.content("pub3"))
        for given in ((), [b"junk"]):
            conn = FakeConnection(rw_publish=[(CTX, 1, True)])
            result = RealPublisher(conn, "rw_t").publish(data, rights=fx.ALL_RIGHTS, valid_until=LATER, evidence=fx.hg4_shape(fx.FAR), actor=fx.ACTOR,
                                                         ref=fx.REF, sidecars=given)
            self.assertEqual((result.status, result.outcome), (EXIT_DONE, "PUBLISHED"))

    def test_the_command_line_reads_sidecar_files_read_only_and_a_missing_one_is_a_typed_refusal(self):
        from persistence import real_workspace_store as store
        parsed = store._build_parser().parse_args(["--socket", "s", "--database", "d", "--user", "u", "--schema", "x", "publish", "--proposal", "p",
                                                   "--evidence-file", "e", "--actor", "a", "--pd", "PD-1", "--commit", "c", "--sha", "s",
                                                   "--sidecar", "one", "--sidecar", "two"])
        self.assertEqual(parsed.sidecar, ["one", "two"])
        content, sidecars = self.real_content("cli")
        with tempfile.TemporaryDirectory() as tmp:
            proposal, evidence = Path(tmp, "p.json"), Path(tmp, "e.json")
            proposal.write_bytes(rp.write_proposal(REAL, **content))
            evidence.write_text(json.dumps([e.as_json() for e in fx.hg4_shape(fx.FAR)]))
            base = ["--socket", "/tmp/.s.PGSQL.5432", "--database", "d", "--user", "u", "--schema", "rw_t", "publish", "--proposal", str(proposal),
                    "--evidence-file", str(evidence), "--valid-until", "2030-01-01T00:00:00Z", "--actor", fx.ACTOR, "--pd", "PD-9001",
                    "--commit", "a" * 40, "--sha", "b" * 64]
            paths = []
            for n, data in enumerate(sidecars):
                paths.append(Path(tmp, "s%d.json" % n))
                paths[-1].write_bytes(data)
            out = io.StringIO()
            conn = FakeConnection(rw_install_info=[("TEST", 4)], rw_publish=[(CTX, 1, True)])      # R6: the tool reads the install kind first
            status = store.main(base + sum((["--sidecar", str(p)] for p in paths), []), connect=lambda a: conn, out=out)
            self.assertEqual(status, 0, out.getvalue())
            before = [p.read_bytes() for p in paths]
            self.assertEqual(before, sidecars)                                                                # the tool only read them
            out, conn = io.StringIO(), FakeConnection()
            status = store.main(base + ["--sidecar", str(Path(tmp, "missing.json"))], connect=lambda a: conn, out=out)
            self.assertEqual(status, EXIT_REFUSED)
            self.assertIn("RW_INPUT_UNREADABLE", out.getvalue())
            self.assertEqual(conn.log, [])
            out, conn = io.StringIO(), FakeConnection(rw_install_info=[("TEST", 4)])
            status = store.main(base, connect=lambda a: conn, out=out)                                        # no sidecar given for a REAL proposal
            self.assertEqual(status, EXIT_REFUSED)
            self.assertIn(sc.O5_FAILED, out.getvalue())
            # R6: the only statement is the read of the install kind (the target is decided from the database); nothing was written
            self.assertEqual([entry[1] for entry in conn.log if "rw_install_info" not in entry[1]], [])


class RegistryDigestTests(unittest.TestCase):
    """Disposition note 5.3, obligation 1: `used_source_digest` is the ENGINE's `source_registry_digest`. The expected value is derived here from
    the engine's own record form, written out by hand, and not from the code under test."""

    def test_the_used_source_digest_is_the_sha256_of_the_canonical_engine_records_of_the_members_sources(self):
        content = fx.content("digest", unused_sources=("syn.unused",))
        registry = json.loads(rp.write_proposal(SYNTHETIC, **content))["snapshot"]["registry"]

        def record(source):
            return {"source_id": source, "name": "Invented source " + source, "upstream_provider": "invented-provider", "independence_group": "group-" + source,
                    "terms_url": "", "synthetic": True, "terms_check": None}
        used = [record(s) for s in sorted(fx.SOURCES)]
        every = [record(s) for s in sorted(fx.SOURCES + ("syn.unused",))]
        self.assertEqual(registry["used_source_digest"], hashlib.sha256(canonical_json(used).encode("utf-8")).hexdigest())
        self.assertEqual(registry["full_registry_digest"], hashlib.sha256(canonical_json(every).encode("utf-8")).hexdigest())
        engine = [EngineSource(s, "Invented source " + s, "invented-provider", "group-" + s, "", None, True) for s in sorted(fx.SOURCES)]
        self.assertEqual(registry["used_source_digest"], source_registry_digest(engine))

    def test_a_null_terms_url_is_a_null_in_the_digest_and_not_an_empty_string(self):
        records = [rp.SourceRecord(s, "n", "p", "g", None, None) for s in fx.SOURCES]
        content = {**fx.content("nullurl"), "source_records": records}
        registry = json.loads(rp.write_proposal(SYNTHETIC, **content))["snapshot"]["registry"]
        by_hand = [{"source_id": s, "name": "n", "upstream_provider": "p", "independence_group": "g", "terms_url": None, "synthetic": True, "terms_check": None}
                   for s in sorted(fx.SOURCES)]
        self.assertEqual(registry["used_source_digest"], hashlib.sha256(canonical_json(by_hand).encode("utf-8")).hexdigest())
        empty = {**fx.content("nullurl"), "source_records": [rp.SourceRecord(s, "n", "p", "g", "", None) for s in fx.SOURCES]}
        self.assertNotEqual(json.loads(rp.write_proposal(SYNTHETIC, **empty))["snapshot"]["registry"]["used_source_digest"], registry["used_source_digest"])

    def test_a_real_scope_terms_check_is_the_engines_four_fields_and_is_part_of_the_digest(self):
        check = {"checked_by": "invented", "checked_on": "2026-01-02", "permits_internal_development_use": True, "notes": "n"}
        content, _sidecars = ProposalAndPublisherTests().real_content("terms")
        records = [rp.SourceRecord(r.source_id, r.name, r.upstream_provider, r.independence_group, r.terms_url, check) for r in content["source_records"]]
        with_check = json.loads(rp.write_proposal(REAL, **{**content, "source_records": records}))["snapshot"]["registry"]
        by_hand = [{"source_id": s, "name": "Invented source " + s, "upstream_provider": "invented-provider", "independence_group": "group-" + s,
                    "terms_url": "", "synthetic": False, "terms_check": check} for s in sorted(fx.SOURCES)]
        self.assertEqual(with_check["used_source_digest"], hashlib.sha256(canonical_json(by_hand).encode("utf-8")).hexdigest())
        without = json.loads(rp.write_proposal(REAL, **content))["snapshot"]["registry"]
        self.assertNotEqual(with_check["used_source_digest"], without["used_source_digest"])
        for label, bad in (("a missing field", {k: v for k, v in check.items() if k != "notes"}), ("an extra field", {**check, "x": 1}),
                           ("a date not in ISO form", {**check, "checked_on": "20260102"}), ("a date that is not a date", {**check, "checked_on": "2026-13-45"}),
                           ("a flag that is not a bool", {**check, "permits_internal_development_use": 1}), ("a blank checker", {**check, "checked_by": " "}),
                           ("notes that are not text", {**check, "notes": None})):
            with self.subTest(label):
                records = [rp.SourceRecord(r.source_id, r.name, r.upstream_provider, r.independence_group, r.terms_url, bad) for r in content["source_records"]]
                with self.assertRaises(rp.ProposalError) as caught:
                    rp.write_proposal(REAL, **{**content, "source_records": records})
                self.assertEqual(caught.exception.code, "RW_PROPOSAL_SHAPE")

    def test_a_record_with_a_priority_is_not_representable(self):
        with self.assertRaises(TypeError):
            rp.SourceRecord("syn.a", "n", "p", "g", "", None, 1)
        data = rp.write_proposal(SYNTHETIC, **fx.content("prio"))
        document = json.loads(data)
        document["snapshot"]["source_records"][0]["source_priority"] = 1
        with self.assertRaises(rp.ProposalError) as caught:
            rp.verify_proposal(canonical_json(document).encode("utf-8"))
        self.assertEqual(caught.exception.code, "RW_PROPOSAL_SHAPE")

    def test_the_two_digests_are_the_engines_and_move_with_each_record_field(self):
        base = json.loads(rp.write_proposal(SYNTHETIC, **fx.content("move")))["snapshot"]["registry"]["used_source_digest"]
        for field in ("name", "upstream_provider", "independence_group", "terms_url"):
            records = [rp.SourceRecord(*[(getattr(r, f) + "x") if f == field and r.source_id == "syn.alpha" else getattr(r, f)
                                         for f in ("source_id", "name", "upstream_provider", "independence_group", "terms_url", "terms_check")])
                       for r in fx.content("move")["source_records"]]
            moved = json.loads(rp.write_proposal(SYNTHETIC, **{**fx.content("move"), "source_records": records}))["snapshot"]["registry"]["used_source_digest"]
            self.assertNotEqual(moved, base, field)


class StaticTests(unittest.TestCase):
    """The reader, the encoder and the validator take bytes and write nothing, and read nothing else (design 4.2, 7.1 R4b exit)."""

    def source_names(self, name):
        tree = ast.parse((SRC / "persistence" / name).read_text("utf8"))
        return tree, {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}

    def test_the_sidecar_module_has_no_file_clock_environment_or_connection_door(self):
        tree, names = self.source_names("real_sidecar.py")
        for forbidden in ("open", "Path", "write", "write_bytes", "write_text", "environ", "getenv", "time", "datetime", "psycopg", "execute", "connect", "os", "sys",
                          "subprocess", "random", "uuid", "tempfile", "shutil"):
            self.assertNotIn(forbidden, names, forbidden)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        self.assertEqual(imported, {"__future__", "dataclasses", "hashlib", "json", "re", "marketdata.canonical", "persistence.real_scope", "persistence"})

    def test_the_publisher_only_reads_the_sidecar_files_it_is_given(self):
        # the tool opens a sidecar through `_read_input` (a read) and nowhere else; it has no sidecar writer
        names = self.source_names("real_workspace_store.py")[1]
        self.assertIn("_read_input", names)
        self.assertNotIn("encode_sidecar", names)


if __name__ == "__main__":
    unittest.main()
