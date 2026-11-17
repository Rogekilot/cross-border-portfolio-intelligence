"""CP7-E10: invented bytes/oracles only; no file store or provider response."""

import datetime
import hashlib
import json
import unittest
from dataclasses import replace
from decimal import Decimal, localcontext
from fractions import Fraction
from unittest.mock import patch

from marketdata.adapters import eodhd_split_candidate as candidate
from marketdata.adapters.base import AdapterRegistry, IssueCode, NoAdapterError
from marketdata.adapters.mock import MOCK_FORMAT, MOCK_SOURCE_ID, MockSyntheticAdapter, make_synthetic_payload
from marketdata.contracts import AdjustmentStatus, CorporateActionType, DataDelayStatus, UsageScope
from marketdata.manifest import DataKind, FileManifest


def body(rows=None):
    if rows is None:
        rows = [{"date": "2001-02-03", "split": "6.000000/2.000000"}]
    return json.dumps(rows, separators=(",", ":")).encode("utf-8")


def manifest(payload, **changes):
    value = FileManifest(
        file_sha256=hashlib.sha256(payload).hexdigest(), size_bytes=len(payload),
        payload_filename="fictional-split-candidate.json", payload_format=candidate.PAYLOAD_FORMAT,
        source_id=candidate.SOURCE_ID, data_kind=DataKind.CORPORATE_ACTION,
        retrieval_time=candidate.FICTIONAL_RETRIEVAL, retrieved_by="synthetic",
        declared_adjustment=AdjustmentStatus.RAW, usage_scope=UsageScope.SYNTHETIC_TEST,
        request=candidate.FICTIONAL_REQUEST, source_identifiers=(candidate.FICTIONAL_VENDOR_ID,),
        script_name="fictional_cp7e10_fixture", script_version="1",
        script_sha256=candidate.FIXTURE_RECIPE_SHA256, coverage=candidate.FICTIONAL_COVERAGE,
    )
    return replace(value, **changes)


def translate(payload=None, **changes):
    if payload is None:
        payload = body()
    return candidate.EodhdSplitCandidateAdapter().translate(manifest(payload, **changes), payload)


class FictionalClassificationTests(unittest.TestCase):
    def assert_refused(self, out, code):
        self.assertEqual(out.actions, ())
        self.assertEqual(len(out.issues), 1)
        self.assertIs(out.issues[0].code, code)

    def test_oracle_01_exact_invented_ordinary_mapping_and_ratio(self):
        out = translate()
        self.assertEqual(out.issues, ())
        self.assertEqual(len(out.actions), 1)
        self.assertIs(out.actions[0].action_type, CorporateActionType.SPLIT)
        self.assertEqual(out.actions[0].split_ratio.new_units, Decimal("6.000000"))
        self.assertEqual(out.actions[0].split_ratio.old_units, Decimal("2.000000"))

    def test_oracle_02_missing_or_unproven_semantics_same_ratio(self):
        for request in ((), tuple((k, "UNPROVEN" if k == "semantic_rule" else v)
                                  for k, v in candidate.FICTIONAL_REQUEST)):
            with self.subTest(request=request):
                self.assert_refused(translate(request=request), IssueCode.UNMAPPED_ACTION)

    def test_oracle_03_other_action_even_four_to_one(self):
        request = tuple((k, "OTHER" if k == "semantic_rule" else v) for k, v in candidate.FICTIONAL_REQUEST)
        self.assert_refused(translate(body([{"date": "2001-02-03", "split": "4/1"}]), request=request),
                            IssueCode.UNMAPPED_ACTION)

    def test_oracle_04_unknown_or_conflicting_mapping(self):
        for request in (tuple((k, "UNKNOWN" if k == "semantic_rule" else v)
                              for k, v in candidate.FICTIONAL_REQUEST),
                        candidate.FICTIONAL_REQUEST + (("semantic_rule", "OTHER"),)):
            with self.subTest(request=request):
                self.assert_refused(translate(request=request), IssueCode.UNMAPPED_ACTION)

    def test_oracle_05_known_numeric_match_without_classification(self):
        request = tuple((k, v) for k, v in candidate.FICTIONAL_REQUEST if k != "semantic_evidence_sha256")
        self.assert_refused(translate(body([{"date": "2001-02-03", "split": "8/2"}]), request=request),
                            IssueCode.UNMAPPED_ACTION)

    def test_oracle_06_caller_flags_checkbox_endpoint_cannot_grant(self):
        for extra in (("classification", "true"), ("checkbox", "checked"), ("endpoint", "/api/splits/FICT")):
            with self.subTest(extra=extra):
                self.assert_refused(translate(request=(extra,)), IssueCode.UNMAPPED_ACTION)
                self.assert_refused(translate(request=candidate.FICTIONAL_REQUEST + (extra,)), IssueCode.UNMAPPED_ACTION)

    def test_real_binding_null_and_no_constructor_authority(self):
        self.assertIsNone(candidate.REAL_CLASSIFICATION_BINDING)
        with self.assertRaises(TypeError):
            candidate.EodhdSplitCandidateAdapter(classification=True)
        with self.assertRaises(AttributeError):
            candidate.EodhdSplitCandidateAdapter().source_id = "real.source"

    def test_unbound_source_and_semantics_refuse_before_body_inspection(self):
        class Poison:
            def __len__(self):
                raise AssertionError("body inspected before classification")

            def decode(self, *args):
                raise AssertionError("body decoded before classification")

        m = manifest(body())
        adapter = candidate.EodhdSplitCandidateAdapter()
        for changed, code in ((replace(m, source_id="eodhd.real"), IssueCode.UNMAPPED_ACTION),
                              (replace(m, request=()), IssueCode.UNMAPPED_ACTION),
                              (replace(m, usage_scope=UsageScope.INTERNAL_DEVELOPMENT_ONLY), IssueCode.CONTRACT_VIOLATION),
                              (replace(m, retrieved_by="human"), IssueCode.CONTRACT_VIOLATION)):
            with self.subTest(code=code, changed=changed.source_id):
                self.assert_refused(adapter.translate(changed, Poison()), code)

    def test_every_binding_field_change_refuses(self):
        for key, value in candidate.FICTIONAL_REQUEST:
            request = tuple((k, v if k != key else value + "-different") for k, v in candidate.FICTIONAL_REQUEST)
            with self.subTest(key=key):
                self.assert_refused(translate(request=request), IssueCode.UNMAPPED_ACTION)
        for changes in (
            {"payload_format": "json"}, {"data_kind": DataKind.QUOTE},
            {"source_identifiers": ()}, {"source_identifiers": (candidate.FICTIONAL_VENDOR_ID, "SECOND")},
            {"source_identifiers": ("AAPL.US",)}, {"script_sha256": "a" * 64},
            {"script_name": None}, {"script_version": "2"}, {"coverage": ()},
            {"payload_filename": "other.json"}, {"retrieval_time": candidate.FICTIONAL_RETRIEVAL + datetime.timedelta(seconds=1)},
            {"market": "US"}, {"adjustment_anchor": "x"}, {"libraries": (("caller", "1"),)},
            {"declared_adjustment": AdjustmentStatus.UNDECLARED}, {"declared_delay": DataDelayStatus.END_OF_DAY},
            {"usage_scope": UsageScope.LICENSED_DISPLAY},
        ):
            with self.subTest(changes=changes):
                self.assert_refused(translate(**changes), IssueCode.CONTRACT_VIOLATION)

    def test_exact_manifest_and_bytes_are_required(self):
        adapter, m = candidate.EodhdSplitCandidateAdapter(), manifest(body())
        self.assert_refused(adapter.translate(object(), object()), IssueCode.CONTRACT_VIOLATION)
        self.assert_refused(adapter.translate(m, bytearray(body())), IssueCode.CONTRACT_VIOLATION)
        self.assert_refused(adapter.translate(m, "[]"), IssueCode.CONTRACT_VIOLATION)


class StrictParserTests(unittest.TestCase):
    def assert_file_refused(self, payload, code):
        out = translate(payload)
        self.assertEqual(out.actions, ())
        self.assertEqual([(i.row_ref, i.code) for i in out.issues], [("file", code)])
        return out

    def test_byte_hash_and_size_mismatch_refuse(self):
        for changes in ({"file_sha256": "a" * 64}, {"size_bytes": len(body()) + 1}):
            with self.subTest(changes=changes):
                out = translate(**changes)
                self.assertEqual(out.actions, ())
                self.assertIs(out.issues[0].code, IssueCode.CONTRACT_VIOLATION)

    def test_strict_utf8_bom_malformed_and_trailing_json(self):
        for payload in (b"\xff", b"\xef\xbb\xbf[]", b"[", b"[] []", b"[]x", b'[{"date":"x",}]'):
            with self.subTest(payload=payload):
                self.assert_file_refused(payload, IssueCode.UNKNOWN_FORMAT)

    def test_duplicate_keys_nonfinite_exponents_and_surrogates(self):
        for payload in (b'[{"date":"2001-02-03","split":"6/2","split":"3/1"}]',
                        b"[NaN]", b"[Infinity]", b"[-Infinity]", b"[1e0]", b"[1E-2]",
                        b'["\\ud800"]', b'[{"\\udfff":"x"}]'):
            with self.subTest(payload=payload):
                self.assert_file_refused(payload, IssueCode.CONTRACT_VIOLATION)

    def test_top_level_wrong_shape_and_empty_array(self):
        for value in ({}, "text", None, True, 1):
            with self.subTest(value=value):
                self.assert_file_refused(json.dumps(value).encode(), IssueCode.UNKNOWN_FORMAT)
        out = translate(b"[]")
        self.assertEqual((out.actions, out.issues), ((), ()))

    def test_row_shape_missing_unknown_fields_and_scalar_types(self):
        rows = [None, 1, [], {}, {"date": "2001-02-01"},
                {"date": "2001-02-02", "split": "6/2", "type": "SPLIT"},
                {"date": [], "split": "6/2"}, {"date": True, "split": "6/2"},
                {"date": "2001-02-04", "split": 3}, {"date": "2001-02-05", "split": None}]
        out = translate(body(rows))
        self.assertEqual(out.actions, ())
        self.assertEqual(len(out.issues), len(rows))
        self.assertEqual([i.row_ref for i in out.issues], [f"rows[{i}]" for i in range(len(rows))])
        self.assertEqual([i.code for i in out.issues], [IssueCode.UNPARSEABLE_ROW] * 3 +
                         [IssueCode.MISSING_FIELD] * 2 + [IssueCode.CONTRACT_VIOLATION] +
                         [IssueCode.UNPARSEABLE_ROW] * 4)

    def test_ratio_lexical_contract_and_positive_values(self):
        bad = ["1e0/1", "1E0/1", "-1/1", "+1/1", "01/1", "1./1", ".5/1", " 1/1", "1 /1",
               "1/ 1", "1//1", "1", "NaN/1", "Infinity/1", "1/0", "0/1", "0.000/1"]
        for ratio in bad:
            with self.subTest(ratio=ratio):
                out = translate(body([{"date": "2001-02-03", "split": ratio}]))
                self.assertEqual(out.actions, ())
                self.assertIs(out.issues[0].code, IssueCode.NON_POSITIVE_VALUE if ratio in bad[-3:] else IssueCode.UNPARSEABLE_ROW)

    def test_dates_are_canonical_valid_and_within_fixed_coverage(self):
        for value in ("20010203", "2001-2-03", "2001-02-30", "2001-W05-6", "2001-02-03T00:00:00", "0000-01-01"):
            with self.subTest(date=value):
                out = translate(body([{"date": value, "split": "6/2"}]))
                self.assertEqual(out.actions, ())
                self.assertIs(out.issues[0].code, IssueCode.UNPARSEABLE_ROW)
        for value in ("2000-12-31", "2002-01-01"):
            out = translate(body([{"date": value, "split": "6/2"}]))
            self.assertEqual(out.actions, ())
            self.assertIs(out.issues[0].code, IssueCode.CONTRACT_VIOLATION)

    def test_all_duplicate_date_rows_refuse_including_a_bad_ratio(self):
        rows = [{"date": "2001-02-03", "split": "6/2"}, {"date": "2001-02-03", "split": "bad"},
                {"date": "2001-02-04", "split": "1/10"}]
        out = translate(body(rows))
        self.assertEqual(len(out.actions), 1)
        self.assertEqual(out.actions[0].effective_date, datetime.date(2001, 2, 4))
        self.assertEqual([(i.row_ref, i.code) for i in out.issues],
                         [("rows[0]", IssueCode.CONTRACT_VIOLATION), ("rows[1]", IssueCode.CONTRACT_VIOLATION)])

    def test_valid_and_invalid_rows_are_all_accounted_for(self):
        rows = [{"date": "2001-02-01", "split": "3/1"}, {}, {"date": "2001-02-03", "split": "1/5"}, False]
        out = translate(body(rows))
        self.assertEqual(len(out.actions) + len(out.issues), 4)
        self.assertEqual([a.lineage.source_record_ref for a in out.actions], ["rows[0]", "rows[2]"])
        self.assertEqual([i.row_ref for i in out.issues], ["rows[1]", "rows[3]"])

    def test_body_exact_limit_and_one_byte_over(self):
        payload = body() + b" " * (candidate.MAX_BODY_BYTES - len(body()))
        self.assertEqual(len(translate(payload).actions), 1)
        self.assert_file_refused(payload + b" ", IssueCode.CONTRACT_VIOLATION)

    def test_nesting_bound_and_brackets_inside_strings(self):
        self.assert_file_refused(b"[" * 9 + b"0" + b"]" * 9, IssueCode.CONTRACT_VIOLATION)
        out = translate(b"[" * 8 + b"0" + b"]" * 8)
        self.assertIs(out.issues[0].code, IssueCode.UNPARSEABLE_ROW)
        out = translate(body([{"date": "2001-02-03", "split": "[[[\\\"/1"}]))
        self.assertIs(out.issues[0].code, IssueCode.UNPARSEABLE_ROW)

    def test_decoded_string_token_limit_counts_utf8_bytes(self):
        for text in ("x" * 4097, "é" * 2049):
            with self.subTest(length=len(text)):
                self.assert_file_refused(body([text]), IssueCode.CONTRACT_VIOLATION)
        out = translate(body(["x" * 4096]))
        self.assertIs(out.issues[0].code, IssueCode.UNPARSEABLE_ROW)

    def test_token_count_and_depth_limits_precede_json_tree_construction(self):
        oversized = (body(["x" * 4097]), body([None] * 4097), b"[" * 9 + b"0" + b"]" * 9,
                     b"[" + b"9" * 4097 + b"]", body(["é" * 2049]))
        with patch.object(candidate.json, "loads", side_effect=AssertionError("tree constructor reached")) as tree:
            for payload in oversized:
                with self.subTest(size=len(payload)):
                    self.assert_file_refused(payload, IssueCode.CONTRACT_VIOLATION)
            tree.assert_not_called()
        for payload in (body(["x" * 4096]), body([None] * 4096),
                        b"[" + b"9" * 4096 + b"]", b"[" * 8 + b"0" + b"]" * 8):
            with self.subTest(boundary=len(payload)):
                with patch.object(candidate.json, "loads", side_effect=AssertionError("tree boundary reached")):
                    with self.assertRaisesRegex(AssertionError, "tree boundary reached"):
                        translate(payload)

    def test_numeric_literal_limit_and_primitive_count(self):
        # No Python int conversion: even a 4096-digit JSON literal is bounded before use.
        out = translate(b"[" + b"9" * 4096 + b"]")
        self.assertIs(out.issues[0].code, IssueCode.UNPARSEABLE_ROW)
        self.assert_file_refused(b"[" + b"9" * 4097 + b"]", IssueCode.CONTRACT_VIOLATION)
        self.assert_file_refused(body([None] * 4097), IssueCode.CONTRACT_VIOLATION)
        out = translate(body([None] * 4096))
        self.assertIn("rows", out.issues[0].detail)

    def test_row_bound_accepts_128_and_refuses_129(self):
        start = datetime.date(2001, 1, 1)
        rows = [{"date": (start + datetime.timedelta(days=i)).isoformat(), "split": "3/1"} for i in range(129)]
        self.assertEqual(len(translate(body(rows[:128])).actions), 128)
        self.assert_file_refused(body(rows), IssueCode.CONTRACT_VIOLATION)

    def test_ratio_component_bounds_are_exact(self):
        text = "999999999999999999.999999999999/0.000000000001"
        out = translate(body([{"date": "2001-02-03", "split": text}]))
        self.assertEqual(out.issues, ())
        self.assertEqual(out.actions[0].split_ratio.new_units.as_tuple(), Decimal(text.split("/")[0]).as_tuple())
        for ratio in ("1000000000000000000/1", "1.0000000000001/1"):
            out = translate(body([{"date": "2001-02-03", "split": ratio}]))
            self.assertEqual(out.actions, ())
            self.assertIs(out.issues[0].code, IssueCode.UNPARSEABLE_ROW)


class CompatibilityAndLineageTests(unittest.TestCase):
    def test_ratio_scale_direction_equivalence_and_low_decimal_context(self):
        rows = [{"date": "2001-02-01", "split": "6.000000000001/2.000000000000"},
                {"date": "2001-02-02", "split": "9/3"}, {"date": "2001-02-03", "split": "1/10"}]
        with localcontext() as context:
            context.prec = 2
            out = translate(body(rows))
        self.assertEqual(out.issues, ())
        a, b, c = [action.split_ratio for action in out.actions]
        self.assertEqual(a.new_units.as_tuple(), Decimal("6.000000000001").as_tuple())
        self.assertEqual(a.old_units.as_tuple(), Decimal("2.000000000000").as_tuple())
        self.assertNotEqual(Fraction(a.new_units) / Fraction(a.old_units), Fraction(3))
        self.assertEqual(Fraction(b.new_units) / Fraction(b.old_units), Fraction(3))
        self.assertEqual((c.new_units, c.old_units), (Decimal(1), Decimal(10)))

    def test_identity_is_vendor_scoped_and_nothing_else_is_inferred(self):
        action = translate().actions[0]
        self.assertEqual(action.identifiers.vendor_id, "FICTITIOUS.SPLIT.001")
        self.assertEqual(action.identifiers.source_id, "fictional.eodhd_split_candidate")
        self.assertEqual((action.identifiers.ticker, action.identifiers.mic, action.identifiers.figi), (None, None, None))
        self.assertEqual((action.pay_date, action.record_date, action.paid_currency), (None, None, None))
        self.assertFalse(hasattr(action, "listing_id"))

    def test_lineage_has_exact_input_and_adapter_binding_and_lexical_ratio(self):
        payload = body()
        action = translate(payload).actions[0]
        lineage = action.lineage
        self.assertTrue(lineage.is_complete)
        self.assertTrue(lineage.is_synthetic)
        self.assertEqual((lineage.source_id, lineage.adapter_id, lineage.adapter_version),
                         (candidate.SOURCE_ID, candidate.ADAPTER_ID, "0.1.0"))
        self.assertEqual(lineage.file_sha256, hashlib.sha256(payload).hexdigest())
        self.assertEqual(lineage.source_record_ref, "rows[0]")
        self.assertEqual(lineage.source_value_text, "6.000000/2.000000")
        self.assertEqual(lineage.retrieved_at, candidate.FICTIONAL_RETRIEVAL)
        self.assertEqual(lineage.library_function, "fictional_split_rows")
        self.assertIsNone(lineage.market)
        self.assertIsNone(action.timing.source_time)

    def test_only_actions_and_issues_can_be_populated(self):
        out = translate()
        for field in ("quotes", "fx", "benchmarks", "identities", "adjusted", "reference", "calendars", "risk_free"):
            self.assertEqual(getattr(out, field), ())
        self.assertFalse(hasattr(out, "ledger_events"))
        self.assertEqual(translate(), translate())

    def test_registry_is_closed_by_default_and_only_explicit_fictional_key_works(self):
        m = manifest(body())
        with self.assertRaises(NoAdapterError):
            AdapterRegistry().for_manifest(m)
        private = AdapterRegistry([candidate.EodhdSplitCandidateAdapter()])
        self.assertIsInstance(private.for_manifest(m), candidate.EodhdSplitCandidateAdapter)
        with self.assertRaises(NoAdapterError):
            private.for_manifest(replace(m, source_id="eodhd"))
        with self.assertRaises(NoAdapterError):
            private.for_manifest(replace(m, payload_format="eodhd_splits_json/1"))

    def test_existing_mock_adapter_retains_its_invented_interface(self):
        payload = make_synthetic_payload(actions=({"ticker": "FICTION", "mic": "XNAS", "date": "2001-02-03",
                                                 "type": "SPLIT", "new_units": "7", "old_units": "2"},))
        m = replace(manifest(payload), source_id=MOCK_SOURCE_ID, payload_format=MOCK_FORMAT)
        adapter = MockSyntheticAdapter(DataKind.CORPORATE_ACTION)
        registry = AdapterRegistry([adapter])
        out = registry.for_manifest(m).translate(m, payload)
        self.assertEqual(out.issues, ())
        self.assertEqual(len(out.actions), 1)
        self.assertEqual((out.actions[0].split_ratio.new_units, out.actions[0].split_ratio.old_units),
                         (Decimal(7), Decimal(2)))


if __name__ == "__main__":
    unittest.main()
