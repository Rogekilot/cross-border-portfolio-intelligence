"""F1 R2: pure contract tests of the real gateway's candidate registry (persistence/real_provenance.py).

N2a's invented-byte cases, generalised to the three scopes, and the origin predicates O1 to O3 (design 4.2, E15), each with its own
failing case and, where the design allows one, a control that differs only in the input under test. No database, no file, no network.
The same predicates exist in SQL (`rwp_origin`); `test_postgres_real_provenance.py` runs them there and a parity table compares the two.

Rules this module keeps (design 4.2): invented data is never `synthetic = false` (the one exception is the I2 mixing case and the
by-value predicate inputs, which only a validator ever sees and which are never stored), and an invented permitting terms check or an
invented human acquisition exists only as an in-memory argument of a predicate.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import replace
import inspect
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import Mock, patch
import uuid

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from persistence import real_provenance as rp  # noqa: E402
from persistence import real_provenance_store as store  # noqa: E402
from persistence.real_provenance import (O1, O2, O3, ORIGIN_CODES, ProvenanceError, origin_report, registration_request,  # noqa: E402
                                         registration_response, validate_bundle, validate_loaded_bundle)
from persistence.real_scope import ScopeError, resolve_scope, scope_by_snapshot_field  # noqa: E402
from real_provenance_fixtures import candidate, encode, h, source_record, with_context, with_manifest_fields, with_members  # noqa: E402

TEST_SCOPES = ("SYNTHETIC_TEST", "TEST_SWITCH")
ALL_SCOPES = TEST_SCOPES + ("REAL",)
PERMITTING = {"checked_by": "invented-checker", "checked_on": "2001-02-03", "permits_internal_development_use": True, "notes": "invented"}
NEGATIVE = dict(PERMITTING, permits_internal_development_use=False)


def scope_of(name):
    return resolve_scope(name, test_switch=(name == "TEST_SWITCH"))


def validate(cand, scope="SYNTHETIC_TEST"):
    return validate_bundle(scope_of(scope), cand.bundle, **cand.args())


class CandidateContractTests(unittest.TestCase):
    """N2a's cases 01 to 16 under both test scopes (a candidate of the REAL scope is covered by the origin tests below)."""

    def each_scope(self, work):
        for name in TEST_SCOPES:
            with self.subTest(scope=name):
                work(name)

    def test_01_original_bytes_and_nonadmission(self):
        def work(name):
            cand = candidate(scope=name)
            value = validate(cand, name)
            self.assertEqual(value.bundle, cand.bundle)
            self.assertEqual(value.bundle.payloads[0][1], b"synthetic-payload-one\n")
            self.assertEqual((value.scope, value.state, value.promotable, value.source_admitted), (name, "INTEGRITY_BOUND_NOT_ADMITTED", False, False))
            self.assertFalse(hasattr(value, "rights"))
        self.each_scope(work)

    def test_02_many_acquisitions_share_payload_without_collapsing(self):
        def work(name):
            new = validate(candidate(acquisitions=(1, 2), scope=name), name)
            self.assertEqual((len(new.bundle.payloads), len(new.bundle.manifests), len(new.bundle.envelopes)), (1, 2, 2))
            self.assertEqual(new.members[0].payload_sha256, new.members[1].payload_sha256)
            self.assertNotEqual(new.members[0].manifest_sha256, new.members[1].manifest_sha256)
        self.each_scope(work)

    def test_03_empty_and_maximum_payload(self):
        self.assertEqual(validate(candidate(b"")).bundle.payloads[0][1], b"")
        self.assertEqual(len(validate(candidate(b"x" * 65536)).bundle.payloads[0][1]), 65536)

    def test_04_byte_limits_precede_metadata_tree(self):
        cand = candidate()
        huge = b"x" * 65537
        bad = replace(cand.bundle, payloads=((h(huge), huge),))
        with patch("persistence.real_provenance.parse_canonical_metadata", side_effect=AssertionError("tree reached")) as tree:
            with self.assertRaises(ProvenanceError):
                validate_bundle(scope_of("SYNTHETIC_TEST"), bad, **cand.args())
            tree.assert_not_called()

    def test_05_scope_flags_are_exact_and_no_rights(self):
        cand = candidate()
        for change in (dict(scope="REAL"), dict(scope="TEST_SWITCH"), dict(promotable=True), dict(source_admitted=True),
                       dict(state="QUALIFIED"), dict(promotable=0)):
            with self.subTest(change=change), self.assertRaises(ProvenanceError) as caught:
                validate(with_context(cand, **change))
            self.assertEqual(caught.exception.code, "RW_PROV_SCOPE_REFUSED")

    def test_06_independent_actor_and_full_request_witness(self):
        cand = candidate()
        for wrong in (replace(cand.witnesses[0], actor_agent_id="/root/other"),
                      replace(cand.witnesses[0], approved_full_request_sha256=h(b"another full request"))):
            with self.assertRaises(ProvenanceError) as caught:
                validate_bundle(scope_of("SYNTHETIC_TEST"), cand.bundle, expected_context_sha256=cand.context_sha256,
                                expected_members=cand.members, witnesses=(wrong,))
            self.assertEqual(caught.exception.code, "RW_PROV_BINDING_DIFFERS")

    def test_07_changed_bytes_do_not_keep_an_old_digest(self):
        cand = candidate()
        key, raw = cand.bundle.envelopes[0]
        with self.assertRaises(ProvenanceError) as caught:
            validate(replace(cand, bundle=replace(cand.bundle, envelopes=((key, raw + b" "),))))
        self.assertEqual(caught.exception.code, "RW_PROV_BINDING_DIFFERS")

    def test_08_missing_and_extraneous_artifacts(self):
        cand = candidate()
        for changed in (replace(cand.bundle, envelopes=()), replace(cand.bundle, payloads=tuple(sorted(cand.bundle.payloads + ((h(b"extra"), b"extra"),))))):
            with self.assertRaises(ProvenanceError):
                validate(replace(cand, bundle=changed))

    def test_09_digest_order_and_duplicate_members_refuse(self):
        cand = candidate(acquisitions=(1, 2))
        m = cand.members
        for changed in (replace(cand.bundle, manifests=tuple(reversed(cand.bundle.manifests))),
                        replace(cand.bundle, manifests=cand.bundle.manifests + cand.bundle.manifests[:1])):
            with self.assertRaises(ProvenanceError):
                validate(replace(cand, bundle=changed))
        with self.assertRaises(ProvenanceError):
            validate(with_members(cand, (m[0], m[0])))
        with self.assertRaises(ProvenanceError):
            validate_bundle(scope_of("SYNTHETIC_TEST"), cand.bundle, expected_context_sha256=cand.context_sha256,
                            expected_members=tuple(reversed(m)), witnesses=cand.witnesses)

    def test_10_manifest_kind_is_the_member_role(self):
        cand = candidate()
        wrong = replace(cand.members[0], role="QUOTE")
        with self.assertRaises(ProvenanceError) as caught:
            validate(with_members(cand, (wrong,)))
        self.assertEqual(caught.exception.code, "RW_PROV_BINDING_DIFFERS")

    def test_11_source_records_are_exact_selected_set(self):
        cand = candidate()
        sources = json.loads(cand.bundle.context_bytes)["source_records"]
        extra = dict(sources[0], source_id="unused.source")
        with self.assertRaises(ProvenanceError) as caught:
            validate(with_context(cand, source_records=sources + [extra]))
        self.assertEqual(caught.exception.code, "RW_PROV_BINDING_DIFFERS")
        # A test scope holds only synthetic sources: a non-synthetic flag on a single source is refused by the scope's own rule (I1).
        with self.assertRaises(ProvenanceError) as caught:
            validate(with_context(cand, source_records=[dict(sources[0], synthetic=False)]))
        self.assertEqual(caught.exception.code, "RW_PROV_SCOPE_REFUSED")

    def test_12_v1_compatibility_has_explicit_null_provenance(self):
        def work(name):
            cand = candidate(v1=True, scope=name)
            value = validate(cand, name)
            self.assertIsNone(value.members[0].envelope_sha256)
            self.assertEqual((cand.bundle.envelopes, cand.bundle.witnesses, cand.witnesses), ((), (), ()))
            # A human acquirer is an invented human attestation: a test scope refuses to hold one.
            human = with_manifest_fields(cand, retrieved_by="human")
            with self.assertRaises(ProvenanceError) as caught:
                validate(human, name)
            self.assertEqual(caught.exception.code, "RW_PROV_SCOPE_REFUSED")
            internal = with_manifest_fields(cand, usage_scope="INTERNAL_DEVELOPMENT_ONLY")
            with self.assertRaises(ProvenanceError) as caught:
                validate(internal, name)
            self.assertEqual(caught.exception.code, "RW_PROV_SCOPE_REFUSED")
        self.each_scope(work)

    def test_13_v2_is_not_downgraded_when_provenance_is_missing(self):
        cand = candidate()
        wrong = replace(cand.members[0], envelope_sha256=None, witness_sha256=None)
        changed = with_members(cand, (wrong,), envelopes=(), witnesses=())
        with self.assertRaises(ProvenanceError) as caught:
            validate_bundle(scope_of("SYNTHETIC_TEST"), changed.bundle, expected_context_sha256=changed.context_sha256,
                            expected_members=(wrong,), witnesses=())
        self.assertEqual(caught.exception.code, "RW_PROV_BINDING_DIFFERS")

    def test_14_noncanonical_context_and_independent_pin_mismatch(self):
        cand = candidate()
        with self.assertRaises(ProvenanceError):
            validate(replace(cand, bundle=replace(cand.bundle, context_bytes=cand.bundle.context_bytes[:-1])))
        with self.assertRaises(ProvenanceError) as caught:
            validate_bundle(scope_of("SYNTHETIC_TEST"), cand.bundle, expected_context_sha256=h(b"wrong context"), expected_members=cand.members,
                            witnesses=cand.witnesses)
        self.assertEqual(caught.exception.code, "RW_PROV_CONTEXT_DIFFERS")

    def test_15_no_io_or_environment_fallback(self):
        cand = candidate()
        with patch("builtins.open", side_effect=AssertionError("file fallback")), patch("os.getenv", side_effect=AssertionError("environment fallback")):
            self.assertEqual(validate(cand).bundle, cand.bundle)

    def test_16_request_response_exact_keys_and_selected_counts(self):
        value = validate(candidate(acquisitions=(1, 2)))
        op = uuid.UUID("90000000-0000-4000-8000-000000000001")
        b = value.bundle
        expected = encode(dict(schema="finweb.provenance_registration/1", scope="SYNTHETIC_TEST", operation_id=str(op),
                               context_sha256=h(b.context_bytes), payload_sha256s=[x[0] for x in b.payloads],
                               manifest_sha256s=[x[0] for x in b.manifests], envelope_sha256s=[x[0] for x in b.envelopes],
                               witness_sha256s=[x[0] for x in b.witnesses]))
        self.assertEqual(registration_request(op, value), expected)
        response = registration_response(op, expected, value)
        obj = json.loads(response)
        self.assertEqual(set(obj), set("schema scope state promotable source_admitted operation_id request_sha256 context_sha256 "
                                       "payload_count manifest_count envelope_count member_count".split()))
        self.assertEqual((obj["payload_count"], obj["manifest_count"], obj["envelope_count"], obj["member_count"]), (1, 2, 2, 2))
        self.assertEqual(response, json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())
        self.assertEqual(obj["request_sha256"], h(expected))
        self.assertEqual((obj["state"], obj["promotable"], obj["source_admitted"]), ("INTEGRITY_BOUND_NOT_ADMITTED", False, False))

    def test_17_autocommit_and_idle_are_checked_without_a_query(self):
        from types import SimpleNamespace
        from psycopg.pq import TransactionStatus
        for autocommit, state in ((False, TransactionStatus.IDLE), (True, TransactionStatus.INTRANS)):
            conn = SimpleNamespace(autocommit=autocommit, info=SimpleNamespace(transaction_status=state),
                                   execute=Mock(side_effect=AssertionError("query reached")))
            with self.assertRaises(ProvenanceError) as caught:
                store._entry(conn)
            self.assertEqual(caught.exception.code, "RW_OUTER_TRANSACTION_REQUIRED")
            conn.execute.assert_not_called()

    def test_18_preflight_refusal_cannot_touch_the_database(self):
        conn = Mock(side_effect=AssertionError("DB reached"))
        registry = store.RealProvenanceStore(conn, "rw_x", loader_role="rw_x_loader")
        cand = candidate()
        with self.assertRaises(ProvenanceError) as caught:
            registry.register(scope_of("SYNTHETIC_TEST"), uuid.uuid4(), cand.bundle, expected_context_sha256=h(b"wrong pin"),
                              expected_members=cand.members, witnesses=cand.witnesses)
        self.assertEqual(caught.exception.code, "RW_PROV_CONTEXT_DIFFERS")
        with self.assertRaises(ProvenanceError):
            registry.reconcile(scope_of("SYNTHETIC_TEST"), "not-uuid", expected_request_sha256="0" * 64,
                               expected_context_sha256=cand.context_sha256, expected_members=cand.members, witnesses=cand.witnesses)
        self.assertEqual(conn.mock_calls, [])

    def test_19_a_candidate_of_the_switch_scope_needs_the_switch_like_a_snapshot(self):
        cand = candidate(scope="TEST_SWITCH")
        for form in ("TEST_SWITCH", scope_by_snapshot_field("TEST_SWITCH"), replace(scope_by_snapshot_field("TEST_SWITCH"), requires_switch=False)):
            with self.subTest(form=type(form).__name__), self.assertRaises(ScopeError) as caught:
                validate_bundle(form, cand.bundle, **cand.args())
            self.assertEqual(caught.exception.code, "RW_SCOPE_UNRESOLVED")
        # Reading a stored candidate back takes the table's own ScopeDef (data), never a copy of it.
        definition = scope_by_snapshot_field("TEST_SWITCH")
        self.assertEqual(validate_loaded_bundle(definition, cand.bundle, **cand.args()).scope, "TEST_SWITCH")
        for form in (replace(definition, requires_switch=False), "TEST_SWITCH", None):
            with self.subTest(loaded=type(form).__name__), self.assertRaises(ProvenanceError) as caught:
                validate_loaded_bundle(form, cand.bundle, **cand.args())
            self.assertEqual(caught.exception.code, "RW_PROV_SCOPE_REFUSED")

    def test_20_a_scope_other_than_the_context_s_own_refuses(self):
        cand = candidate(scope="TEST_SWITCH")
        with self.assertRaises(ProvenanceError) as caught:
            validate(cand, "SYNTHETIC_TEST")
        self.assertEqual(caught.exception.code, "RW_PROV_SCOPE_REFUSED")


class OriginPredicateTests(unittest.TestCase):
    """O1, O2 and O3 each have a test of their own. A test varies ONLY the input of the predicate under test and asserts that predicate's
    code is in the full failure list (and, where a control is possible, absent in a case that differs only in that input). Invented
    attestations are passed BY VALUE; nothing here stores one."""

    SOURCES = [{"source_id": "fictional.source", "synthetic": True, "terms_check": None}]
    MEMBERS = [{"manifest_sha256": "a" * 64, "schema": "v1", "retrieved_by": "synthetic", "usage_scope": "SYNTHETIC_TEST"}]

    def report(self, sources=None, members=None, **by_value):
        return origin_report(self.SOURCES if sources is None else sources, self.MEMBERS if members is None else members, **by_value).failed

    def test_the_codes_are_the_design_codes(self):
        self.assertEqual((O1, O2, O3), ("RW_O1_SYNTHETIC_SOURCE", "RW_O2_TERMS_CHECK", "RW_O3_ACQUISITION"))
        self.assertEqual(ORIGIN_CODES, (O1, O2, O3))

    def test_the_invented_baseline_fails_all_three_and_reports_all_three(self):
        self.assertEqual(self.report(), (O1, O2, O3))             # no stopping at the first failure

    # ---- O1 ------------------------------------------------------------------------------------------------------------
    def test_o1_a_synthetic_source_fails_o1(self):
        self.assertIn(O1, self.report())
        for flag in (True, None, "false", 0, 1, "", []):
            with self.subTest(flag=flag):
                self.assertIn(O1, self.report(sources=[dict(self.SOURCES[0], synthetic=flag)]))     # only the JSON value false is not synthetic

    def test_o1_control_a_source_that_is_not_synthetic_does_not_list_o1(self):
        # By value only: the design has no stored control for O1 before R8 (it would be a source marked synthetic=false). The predicate's
        # own input is varied alone; the other two stay listed, so O1 is seen to be independent of them.
        self.assertEqual(self.report(sources=[dict(self.SOURCES[0], synthetic=False)]), (O2, O3))

    def test_o1_one_synthetic_source_among_many_fails(self):
        two = [dict(self.SOURCES[0], source_id="a.one", synthetic=False), dict(self.SOURCES[0], source_id="b.two", synthetic=True)]
        self.assertIn(O1, self.report(sources=two))
        self.assertNotIn(O1, self.report(sources=[dict(s, synthetic=False) for s in two]))

    # ---- O2 ------------------------------------------------------------------------------------------------------------
    def test_o2_a_missing_terms_check_fails_o2_and_o1_is_listed_too(self):
        self.assertEqual(self.report()[:2], (O1, O2))

    def test_o2_a_negative_or_malformed_terms_check_fails_o2(self):
        cases = {"negative": NEGATIVE, "string true": dict(PERMITTING, permits_internal_development_use="true"),
                 "one": dict(PERMITTING, permits_internal_development_use=1), "blank checker": dict(PERMITTING, checked_by="  "),
                 "no checker": {k: v for k, v in PERMITTING.items() if k != "checked_by"}, "bad date": dict(PERMITTING, checked_on="2001-13-45"),
                 "text date": dict(PERMITTING, checked_on="yesterday"), "number checker": dict(PERMITTING, checked_by=7), "not an object": "permits",
                 "list": [PERMITTING]}
        for label, check in cases.items():
            with self.subTest(label):
                self.assertIn(O2, self.report(terms_checks={"fictional.source": check}))
                self.assertIn(O2, self.report(sources=[dict(self.SOURCES[0], terms_check=check)]))

    def test_o2_control_a_permitting_terms_check_by_value_removes_only_o2(self):
        # The control is an INVENTED human attestation: an in-memory argument, never a stored row (design 4.2, technical re-review L-4).
        self.assertEqual(self.report(terms_checks={"fictional.source": PERMITTING}), (O1, O3))

    def test_o2_reads_the_sources_terms_check_directly_and_does_not_exempt_synthetic_sources(self):
        # `terms_attested` is true for any synthetic source in ingest; here a synthetic source with no terms check still fails O2.
        self.assertIn(O2, self.report(sources=[dict(self.SOURCES[0], synthetic=True, terms_check=None)]))
        permitting = [dict(self.SOURCES[0], terms_check=PERMITTING)]
        self.assertEqual(self.report(sources=permitting), (O1, O3))             # the source's own check is read; it is not exempted by the flag

    def test_o2_every_source_needs_a_permitting_check(self):
        two = [dict(self.SOURCES[0], source_id="a.one", terms_check=PERMITTING), dict(self.SOURCES[0], source_id="b.two", terms_check=None)]
        self.assertIn(O2, self.report(sources=two))
        self.assertNotIn(O2, self.report(sources=two, terms_checks={"b.two": PERMITTING}))

    # ---- O3 ------------------------------------------------------------------------------------------------------------
    def test_o3_an_agent_or_v2_member_or_other_usage_scope_fails_o3(self):
        for label, facts in {"agent": dict(retrieved_by="agent"), "v2": dict(schema="v2"), "usage": dict(usage_scope="LICENSED_DISPLAY"),
                             "synthetic acquirer": dict(retrieved_by="synthetic"), "synthetic usage": dict(usage_scope="SYNTHETIC_TEST")}.items():
            members = [{**self.MEMBERS[0], "schema": "v1", "retrieved_by": "human", "usage_scope": "INTERNAL_DEVELOPMENT_ONLY", **facts}]
            with self.subTest(label):
                self.assertIn(O3, self.report(members=members))

    def test_o3_control_a_human_internal_development_member_by_value_removes_only_o3(self):
        human = {"a" * 64: {"schema": "v1", "retrieved_by": "human", "usage_scope": "INTERNAL_DEVELOPMENT_ONLY"}}
        self.assertEqual(self.report(acquisitions=human), (O1, O2))

    def test_o3_reads_the_members_own_fields_not_the_sources_synthetic_flag(self):
        # ingest ties a file's usage scope to its source's synthetic flag; O3 does not: a non-synthetic source with a synthetic member fails O3.
        self.assertIn(O3, self.report(sources=[dict(self.SOURCES[0], synthetic=False)]))
        human = [dict(self.MEMBERS[0], retrieved_by="human", usage_scope="INTERNAL_DEVELOPMENT_ONLY")]
        self.assertNotIn(O3, self.report(members=human))          # and a synthetic source with a human member does not fail O3

    def test_o3_every_member_must_pass(self):
        ok = dict(self.MEMBERS[0], manifest_sha256="b" * 64, retrieved_by="human", usage_scope="INTERNAL_DEVELOPMENT_ONLY")
        self.assertNotIn(O3, self.report(members=[ok]))
        self.assertIn(O3, self.report(members=[ok, dict(ok, manifest_sha256="c" * 64, retrieved_by="agent")]))

    # ---- shared ----------------------------------------------------------------------------------------------------------
    def test_no_evidence_fails_closed(self):
        self.assertEqual(origin_report([], []).failed, (O1, O2, O3))
        self.assertEqual(self.report(sources=[]), (O1, O2, O3))
        self.assertEqual(self.report(members=[])[-1], O3)

    def test_the_predicates_are_independent_of_each_other(self):
        passing_o1 = [dict(self.SOURCES[0], synthetic=False)]
        passing_o2 = [dict(self.SOURCES[0], terms_check=PERMITTING)]
        human = [dict(self.MEMBERS[0], retrieved_by="human", usage_scope="INTERNAL_DEVELOPMENT_ONLY")]
        self.assertEqual(self.report(sources=passing_o1), (O2, O3))
        self.assertEqual(self.report(sources=passing_o2), (O1, O3))
        self.assertEqual(self.report(members=human), (O1, O2))
        self.assertEqual(self.report(sources=[dict(self.SOURCES[0], synthetic=False, terms_check=PERMITTING)], members=human), ())

    def test_a_test_scope_reports_the_failures_and_refuses_nothing(self):
        for name in TEST_SCOPES:
            for v1 in (True, False):
                value = validate(candidate(scope=name, v1=v1), name)
                with self.subTest(scope=name, v1=v1):
                    self.assertEqual(value.origin().failed, (O1, O2, O3))          # informational: the synthetic axis is what the switch bypasses

    def test_the_real_scope_refuses_a_candidate_and_lists_every_failed_code(self):
        for v1 in (True, False):
            cand = candidate(scope="REAL", v1=v1)
            with self.subTest(v1=v1), self.assertRaises(ProvenanceError) as caught:
                validate(cand, "REAL")
            self.assertEqual(caught.exception.code, rp.ORIGIN_REFUSED)
            self.assertEqual(caught.exception.codes, (rp.ORIGIN_REFUSED, O1, O2, O3))

    def test_the_real_scope_lists_o2_o3_with_one_changed_input_each(self):
        # Vary only the input of one predicate (by value) on the candidate's stored facts; the candidate path itself never stores a control.
        cand = candidate(scope="REAL", v1=True)
        with self.assertRaises(ProvenanceError) as caught:
            validate(cand, "REAL")
        self.assertEqual(caught.exception.codes[1:], (O1, O2, O3))
        context = validate(candidate(scope="TEST_SWITCH", v1=True), "TEST_SWITCH")
        self.assertEqual(context.origin(terms_checks={"fictional.source": PERMITTING}).failed, (O1, O3))
        self.assertEqual(context.origin(acquisitions={context.member_facts[0]["manifest_sha256"]: {
            "schema": "v1", "retrieved_by": "human", "usage_scope": "INTERNAL_DEVELOPMENT_ONLY"}}).failed, (O1, O2))

    # ---- I2, I1 -----------------------------------------------------------------------------------------------------------
    def test_mixed_origin_in_one_candidate_is_refused_in_every_scope(self):
        # I2. These bytes name a non-synthetic source; they are passed to a validator that refuses them and are never stored.
        base = candidate()
        for scope in ALL_SCOPES:
            sources = [source_record("a.one", synthetic=True), source_record("b.two", synthetic=False)]
            cand = with_context(candidate(scope=scope), source_records=sources)
            with self.subTest(scope=scope), self.assertRaises(ProvenanceError) as caught:
                validate(cand, scope)
            self.assertEqual(caught.exception.code, rp.ORIGIN_MIXED)
        self.assertIsNotNone(base)

    def test_a_test_scope_stores_no_invented_attestation(self):
        for name in TEST_SCOPES:
            for label, changes in {"terms check": dict(terms_check=PERMITTING), "terms url": dict(terms_url="https://fictional.invalid/terms")}.items():
                cand = candidate(scope=name, **changes)
                with self.subTest(scope=name, what=label), self.assertRaises(ProvenanceError) as caught:
                    validate(cand, name)
                self.assertEqual(caught.exception.code, "RW_PROV_SCOPE_REFUSED")


class ByValueAndWritesNothingTests(unittest.TestCase):
    """Design 4.2: "the validator functions take such inputs by value and write nothing" (technical re-review L-4)."""

    def test_the_predicates_take_attestations_as_arguments_and_nothing_else(self):
        for function in (rp.o1_fails, rp.o2_fails, rp.o3_fails, rp.origin_report):
            parameters = inspect.signature(function).parameters
            self.assertFalse({"path", "file", "conn", "connection", "schema", "environ"} & set(parameters), function.__name__)
        self.assertEqual(list(inspect.signature(rp.o2_fails).parameters), ["sources", "terms_checks"])
        self.assertEqual(list(inspect.signature(rp.o3_fails).parameters), ["members", "acquisitions"])
        origin = inspect.signature(rp.origin_report).parameters
        self.assertEqual(origin["terms_checks"].kind, inspect.Parameter.KEYWORD_ONLY)
        self.assertEqual(origin["acquisitions"].kind, inspect.Parameter.KEYWORD_ONLY)

    def test_they_write_nothing_retain_nothing_and_touch_no_file_network_or_environment(self):
        sources = [{"source_id": "fictional.source", "synthetic": True, "terms_check": None}]
        members = [{"manifest_sha256": "a" * 64, "schema": "v1", "retrieved_by": "synthetic", "usage_scope": "SYNTHETIC_TEST"}]
        checks, acquisitions = {"fictional.source": dict(PERMITTING)}, {"a" * 64: {"schema": "v1", "retrieved_by": "human", "usage_scope": "INTERNAL_DEVELOPMENT_ONLY"}}
        before = copy.deepcopy((sources, members, checks, acquisitions))
        import socket
        with patch("builtins.open", side_effect=AssertionError("file")), patch("os.getenv", side_effect=AssertionError("environment")), \
                patch("os.environ", {}), patch.object(socket.socket, "connect", side_effect=AssertionError("network")), \
                patch.object(Path, "write_text", side_effect=AssertionError("write")), patch.object(Path, "write_bytes", side_effect=AssertionError("write")):
            with_controls = origin_report(sources, members, terms_checks=checks, acquisitions=acquisitions).failed
        self.assertEqual(with_controls, (O1,))
        self.assertEqual((sources, members, checks, acquisitions), before)                    # inputs unchanged
        # Nothing is retained: the next evaluation without the controls reports the stored facts again.
        self.assertEqual(origin_report(sources, members).failed, (O1, O2, O3))
        context = validate(candidate(), "SYNTHETIC_TEST")
        self.assertEqual(context.origin(terms_checks={"fictional.source": PERMITTING}).failed, (O1, O3))
        self.assertEqual(context.origin().failed, (O1, O2, O3))
        self.assertNotIn("permits", repr(context.source_records))

    def test_no_product_call_site_passes_an_attestation(self):
        offenders = []
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text("utf8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for keyword in node.keywords:
                        if keyword.arg in ("terms_checks", "acquisitions"):
                            # real_provenance forwards its own caller's arguments (a name of the same spelling); nobody writes a value.
                            forwards = path.name == "real_provenance.py" and isinstance(keyword.value, ast.Name) and keyword.value.id == keyword.arg
                            if not forwards:
                                offenders.append("%s:%d" % (path.relative_to(SRC), node.lineno))
        self.assertEqual(offenders, [])

    def test_product_code_has_no_permitting_terms_check_literal(self):
        for path in (SRC / "persistence" / "real_provenance.py", SRC / "persistence" / "real_provenance_store.py", SRC / "persistence" / "real_roles.py"):
            tree = ast.parse(path.read_text("utf8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Dict):
                    keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
                    self.assertFalse("permits_internal_development_use" in keys and "checked_by" in keys, "%s:%d" % (path.name, node.lineno))


class _Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _ScriptedConnection:
    """A connection that answers the session query with `role` and the guarded-load call with `row`; it records what it was asked."""

    def __init__(self, role, row):
        from types import SimpleNamespace
        from psycopg.pq import TransactionStatus
        self.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.role, self.row, self.calls = role, row, []

    def execute(self, query, params=None):
        if isinstance(query, str):
            self.calls.append("session")
            return _Result((self.role, self.role, "none"))
        self.calls.append("load")
        return _Result(self.row)


class LoadGuardedPythonChecksTests(unittest.TestCase):
    """The Python half of the guarded load checks what the database returned against what the lease says (defence in depth: the database
    has already bound the registration to the lease's context). A scripted connection returns rows that the product path cannot produce, so
    each check is seen to fire; the control returns the matching row."""

    ROLE = "rw_x_executor"

    def build(self, *, scope="TEST_SWITCH", payload_member=None, bound_to=None, response=None, snapshot_scope=None):
        from persistence.real_workspace_store import AdmittedLease
        cand = candidate(scope=scope, salt="scripted")
        member = cand.members[0]
        snapshot = json.dumps({"scope": snapshot_scope or scope, "members": [
            {"payload_sha256": payload_member or member.payload_sha256, "manifest_sha256": member.manifest_sha256, "source_id": "fictional.source"}]}).encode()
        ctx = h(snapshot)
        bound = candidate(scope=scope, salt="scripted", financial_context=bound_to or ctx)
        arrays = [[raw for _k, raw in values] for values in (bound.bundle.payloads, bound.bundle.manifests, bound.bundle.envelopes, bound.bundle.witnesses)]
        row = (bound.bundle.context_bytes, *arrays, response)
        lease = AdmittedLease(snapshot, uuid.uuid4(), uuid.uuid4(), ctx, 1, uuid.uuid4(), "EXECUTE_CREATE", None)
        return bound, lease, row

    def call(self, bound, lease, row, role=None):
        conn = _ScriptedConnection(role or self.ROLE, row)
        value = store.load_guarded(conn, "rw_x", self.ROLE, lease, bound.context_sha256, expected_members=bound.members, witnesses=bound.witnesses)
        return value, conn

    def refusal(self, bound, lease, row, role=None):
        conn = _ScriptedConnection(role or self.ROLE, row)
        with self.assertRaises(ProvenanceError) as caught:
            store.load_guarded(conn, "rw_x", self.ROLE, lease, bound.context_sha256, expected_members=bound.members, witnesses=bound.witnesses)
        return caught.exception.code, conn

    def test_the_control_returns_the_validated_context(self):
        bound, lease, row = self.build()
        value, conn = self.call(bound, lease, row)
        self.assertEqual((value.bundle, value.scope, value.promotable), (bound.bundle, "TEST_SWITCH", False))
        self.assertEqual(conn.calls, ["session", "load"])

    def test_a_member_that_is_not_in_the_leases_snapshot_is_refused(self):
        bound, lease, row = self.build(payload_member=h(b"another payload"))
        self.assertEqual(self.refusal(bound, lease, row)[0], "RW_PROV_BINDING_DIFFERS")

    def test_a_candidate_bound_to_another_context_is_refused(self):
        bound, lease, row = self.build(bound_to=h(b"another context"))
        self.assertEqual(self.refusal(bound, lease, row)[0], "RW_PROV_CONTEXT_DIFFERS")

    def test_a_registration_response_is_not_a_context(self):
        bound, lease, row = self.build(response=b"{}")
        self.assertEqual(self.refusal(bound, lease, row)[0], "RW_PROV_CONTEXT_DIFFERS")

    def test_a_snapshot_that_does_not_hash_to_the_context_is_refused_before_any_load(self):
        from persistence.real_workspace_store import AdmittedLease
        bound, lease, row = self.build()
        forged = AdmittedLease(lease.snapshot + b" ", *[getattr(lease, f) for f in ("owner_id", "root_id", "context_id", "generation", "operation_id", "purpose", "complete_by")])
        code, conn = self.refusal(bound, forged, row)
        self.assertEqual(code, "RW_PROV_CONTEXT_DIFFERS")
        self.assertEqual(conn.calls, ["session"])                         # the database was not asked for a candidate

    def test_a_snapshot_with_an_unknown_scope_or_no_json_is_refused_before_any_load(self):
        from persistence.real_workspace_store import AdmittedLease
        bound, lease, row = self.build()
        for bad in (b"not json", b"{}", json.dumps({"scope": "OTHER", "members": []}).encode()):
            forged = AdmittedLease(bad, lease.owner_id, lease.root_id, h(bad), 1, lease.operation_id, "EXECUTE_CREATE", None)
            code, conn = self.refusal(bound, forged, row)
            self.assertEqual(code, "RW_PROV_SCOPE_REFUSED")
            self.assertEqual(conn.calls, ["session"])

    def test_a_candidate_of_another_scope_than_the_leases_snapshot_is_refused(self):
        bound, lease, row = self.build(scope="SYNTHETIC_TEST", snapshot_scope="TEST_SWITCH")
        self.assertEqual(self.refusal(bound, lease, row)[0], "RW_PROV_SCOPE_REFUSED")

    def test_a_session_that_is_not_the_executor_is_refused_before_any_load(self):
        bound, lease, row = self.build()
        code, conn = self.refusal(bound, lease, row, role="rw_x_publisher")
        self.assertEqual(code, "RW_PROV_ROLE_REFUSED")
        self.assertEqual(conn.calls, ["session"])

    def test_no_row_is_input_missing(self):
        bound, lease, _row = self.build()
        self.assertEqual(self.refusal(bound, lease, None)[0], "RW_PROV_INPUT_MISSING")


class _StopAtBody(Exception):
    pass


class _InstallerProbe:
    """A scripted connection that answers the installer's role and schema checks and stops at the first statement of the SQL body."""

    def __init__(self, can_login):
        self.can_login = can_login            # rolname -> rolcanlogin

    def execute(self, query, params=None):
        text = query if isinstance(query, str) else str(query)
        if "current_database" in text:
            return _Result(("finweb_it_probe",))
        if "FROM pg_roles" in text:
            rows = [(name, False, False, login) for name, login in self.can_login.items()]
            return type("Rows", (), {"fetchall": lambda self_: rows})()
        if "n.nspowner" in text:
            return _Result(("o", "o"))
        if "pg_has_role" in text:
            return _Result((False,))
        if "to_regclass" in text:
            return _Result((None,) if params and "rw_install" in params[0] else (1,))
        raise _StopAtBody


class InstallerRoleCheckTests(unittest.TestCase):
    """Exit statement R2 (b), the installer half: the install accepts a loader with or without LOGIN; the other three roles keep the R1 rule."""

    def run_install(self, **login):
        from persistence import real_workspace_store as workspace
        roles = {"o": False, "e": True, "l": True, "p": True, **login}
        names = workspace._check_install_inputs("rw_x", "o", "e", "l", "p", 4)
        workspace._install_gateway_body(_InstallerProbe(roles), names, "o", "e", "l", "p")

    def test_a_loader_with_or_without_login_passes_the_role_check(self):
        for loader_login in (True, False):
            with self.subTest(loader_login=loader_login), self.assertRaises(_StopAtBody):
                self.run_install(l=loader_login)

    def test_the_other_roles_keep_the_r1_rule(self):
        from persistence.real_workspace_context import RealWorkspaceError
        for label, change in {"executor without login": dict(e=False), "publisher without login": dict(p=False), "owner with login": dict(o=True)}.items():
            with self.subTest(label), self.assertRaises(RealWorkspaceError) as caught:
                self.run_install(**change)
            self.assertEqual(caught.exception.code, "RW_ROLE_DIFFERS")

    def test_the_registry_check_does_not_read_the_loaders_login(self):
        source = inspect.getsource(store.verify_registry_install)
        self.assertNotIn("rolcanlogin", source)
        self.assertIn("NOT r.rolcanlogin", (SRC / "persistence" / "real_provenance_v1.sql").read_text("utf8"))        # the per-call check does


class LoaderListPureTests(unittest.TestCase):
    """The loader's list as data (persistence/real_roles.py). The catalog assertion is in test_postgres_real_loader.py."""

    def test_the_list_is_exactly_the_design_list(self):
        from persistence import real_roles
        from persistence.market_data_store import MD_TABLES
        self.assertEqual(real_roles.MD_TABLES, tuple(MD_TABLES))
        self.assertEqual(len(real_roles.MD_TABLES), 13)
        self.assertEqual(real_roles.LOADER_INSERT_TABLES, real_roles.MD_TABLES)
        self.assertEqual(real_roles.LOADER_SELECT_TABLES, ("md_file", "md_release"))
        self.assertEqual(real_roles.LOADER_FUNCTIONS, (real_roles.REGISTRY_PUT, real_roles.REGISTRY_GET))
        expected = real_roles.loader_expected()
        self.assertEqual(expected["functions"], frozenset(("rwp_put_context", "rwp_get_context")))
        self.assertEqual({t for t, p in expected["table_privileges"].items() if p == frozenset(("INSERT", "SELECT"))}, {"md_file", "md_release"})
        self.assertEqual({p for privs in expected["table_privileges"].values() for p in privs}, {"INSERT", "SELECT"})

    def test_the_statements_grant_nothing_beyond_the_list(self):
        from persistence import real_roles
        statements = real_roles.loader_grant_statements("rw_x", "rw_x_loader")
        self.assertEqual(len(statements), 4)
        self.assertTrue(statements[0].startswith('GRANT INSERT ON "rw_x".md_file, '))
        self.assertTrue(statements[0].endswith(' TO "rw_x_loader"'))
        self.assertEqual(statements[1], 'GRANT SELECT ON "rw_x".md_file, "rw_x".md_release TO "rw_x_loader"')
        self.assertEqual(statements[2], 'GRANT EXECUTE ON FUNCTION "rw_x".rwp_put_context(uuid,bytea,bytea,bytea[],bytea[],bytea[],bytea[]) TO "rw_x_loader"')
        self.assertEqual(statements[3], 'GRANT EXECUTE ON FUNCTION "rw_x".rwp_get_context(text,uuid) TO "rw_x_loader"')
        text = " ".join(statements).upper()
        for forbidden in ("UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER", "ALL", "MAINTAIN", "WITH GRANT", "PUBLIC", "SEQUENCE", "SCHEMA"):
            self.assertIsNone(re.search(r"\b" + forbidden.replace(" ", r"\s+") + r"\b", text), forbidden)
        for table in real_roles.MD_TABLES:
            self.assertIn('"rw_x".%s' % table, statements[0], table)
        self.assertNotIn("md_quote", statements[1])

    def test_identifiers_are_validated_before_they_reach_the_statements(self):
        from persistence import real_roles
        from persistence.real_workspace_context import RealWorkspaceError
        for bad in ("Rw_x", "rw x", 'rw";drop', "", None, "a" * 64):
            with self.subTest(bad), self.assertRaises(RealWorkspaceError):
                real_roles.loader_grant_statements(bad, "rw_x_loader")
            with self.subTest(role=bad), self.assertRaises(RealWorkspaceError):
                real_roles.loader_grant_statements("rw_x", bad)

    def test_the_installer_applies_the_shared_list_and_no_sql_file_grants_the_loader(self):
        from persistence import real_roles, real_workspace_store as workspace
        source = inspect.getsource(workspace._install_gateway_body)
        # R3: the installer applies EVERY role's list from the shared module (the loader's among them), and no SQL file grants anything.
        self.assertIn("real_roles.apply_role_grants(conn, schema, executor_role, loader_role, publisher_role", source)
        self.assertEqual(workspace.GATEWAY_SQL_FILES, real_roles.sql_files("TEST"))
        for name in workspace.GATEWAY_SQL_FILES:
            text = (SRC / "persistence" / name).read_text("utf8")
            code = "\n".join(line.split("--")[0] for line in text.splitlines())
            self.assertEqual(re.findall(r"^GRANT .*?;", code, flags=re.S | re.M), [], name)
        self.assertEqual(real_roles.grant_statements("TEST", "rw_x", "rw_x_exec", "rw_x_loader", "rw_x_pub")[0],
                         'REVOKE EXECUTE ON ALL ROUTINES IN SCHEMA "rw_x" FROM PUBLIC')


class CountRowsParameterTests(unittest.TestCase):
    """`write_release(..., count_rows=False)` (design 7.1, R2 row): keyword-only; the default keeps today's behaviour."""

    def test_the_parameter_is_keyword_only_with_the_old_default(self):
        from persistence import market_data_store
        parameter = inspect.signature(market_data_store.write_release).parameters["count_rows"]
        self.assertEqual((parameter.kind, parameter.default), (inspect.Parameter.KEYWORD_ONLY, True))

    def test_a_non_bool_is_refused_before_any_statement(self):
        from persistence import market_data_store
        conn = Mock(side_effect=AssertionError("DB reached"))
        for bad in (None, 0, 1, "no", []):
            with self.subTest(bad), self.assertRaisesRegex(TypeError, "count_rows must be a bool"):
                market_data_store.write_release(conn, None, (), None, None, count_rows=bad)
        self.assertEqual(conn.mock_calls, [])
        # Control: a real bool passes the check (and then stops at the next one, which this test does not satisfy).
        for good in (True, False):
            with self.assertRaises(AttributeError):
                market_data_store.write_release(conn, None, (), None, None, count_rows=good)


if __name__ == "__main__":
    unittest.main()
