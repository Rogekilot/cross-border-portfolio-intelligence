"""Offline contracts only; no PostgreSQL, native process, provider or browser."""
from copy import deepcopy
import json
import sys
from pathlib import Path
import unittest
import uuid

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from persistence.guarded_csv_report_store import (GuardedCsvReportStore, command_bytes, digest, encoded,  # noqa: E402
    final_report, encode_cursor, decode_cursor, export_report)
from persistence.web_account_store import AccountStoreError  # noqa: E402

ROOT, OP = uuid.UUID(int=11), uuid.UUID(int=12)
NOW = "2026-10-20T00:00:00.000000Z"


def report(dispositions):
    rows = [dict(row_number=i + 1, physical_start=i + 2, physical_end=i + 2, cells=["=1+1"], classification="NON_DATA" if d == "EXCLUDED" else "ECONOMIC",
        reason="explicit exclusion" if d == "EXCLUDED" else "", fields={}, errors=[dict(code="BAD", field="amount", detail="Unresolved")] if d == "QUARANTINED" else [],
        event=None, source_identity=None, source_key=None, existing_event_id="prior" if d == "ALREADY_IMPORTED" else None,
        disposition=d, event_id="prior" if d == "ALREADY_IMPORTED" else "candidate") for i, d in enumerate(dispositions)]
    return dict(schema="finweb.csv_import/1", report_id=str(uuid.uuid4()), portfolio_id=str(ROOT), operation_id=str(OP), expected_revision_id=str(ROOT),
        proposal_digest="a" * 64, persisted=False, status="READY", file=dict(filename="f.csv", sha256="b" * 64, byte_count=1, bom=False),
        proposal=dict(kind="TRANSACTIONS", operation_id=str(OP), expected_revision_id=str(ROOT), corrections=[]), parser={}, rows=rows,
        counts=dict(total=len(rows), economic=sum(d != "EXCLUDED" for d in dispositions), ready=dispositions.count("READY"), quarantined=dispositions.count("QUARANTINED"),
            excluded=dispositions.count("EXCLUDED"), already_imported=dispositions.count("ALREADY_IMPORTED"), imported=0), batch_errors=[], revision_id=None, created_at=None)


class ReportContracts(unittest.TestCase):
    def test_duplicate_is_report_only_with_original_link(self):
        value = final_report(report(["ALREADY_IMPORTED"]), ROOT, OP, NOW)
        self.assertEqual((value["status"], value["persisted"], value["counts"]["imported"], value["revision_id"]), ("ALREADY_IMPORTED", True, 0, None))
        self.assertEqual(value["rows"][0]["event_id"], "prior")

    def test_quarantine_and_explicit_exclusion_are_durable_reports(self):
        for ds in (["QUARANTINED"], ["EXCLUDED"], ["READY", "QUARANTINED"]):
            with self.subTest(ds=ds):
                original = report(list(ds)); frozen = deepcopy(original)
                value = final_report(original, ROOT, OP, NOW)
                self.assertEqual(value["status"], "REPORT_ONLY")
                self.assertTrue(all(row["event_id"] is None for row in value["rows"]))
                self.assertEqual(original, frozen)

    def test_whole_batch_refusal_keeps_ready_intent_but_no_event_claim(self):
        value = report(["READY"])
        value["batch_errors"] = [dict(code="NATIVE_CASH_NEGATIVE", detail="Native cash refuses")]
        final = final_report(value, ROOT, OP, NOW)
        self.assertEqual((final["counts"]["ready"], final["counts"]["imported"], final["rows"][0]["event_id"]), (1, 0, None))

    def test_clean_new_events_require_financial_branch(self):
        with self.assertRaises(AccountStoreError) as ctx:
            final_report(report(["READY"]), ROOT, OP, NOW)
        self.assertEqual((ctx.exception.status, ctx.exception.code), (409, "F3_CSV_REPORT_FINANCIAL_REQUIRED"))

    def test_source_conflict_is_never_a_saved_report(self):
        value = report(["QUARANTINED"])
        value["rows"][0]["errors"][0]["code"] = "SOURCE_KEY_CONFLICT"
        with self.assertRaises(AccountStoreError) as ctx:
            final_report(value, ROOT, OP, NOW)
        self.assertEqual(ctx.exception.code, "SOURCE_KEY_CONFLICT")

    def test_holdings_limitation_is_explicit(self):
        value = report(["QUARANTINED"]); value["proposal"]["kind"] = "HOLDINGS"
        with self.assertRaises(AccountStoreError) as ctx:
            final_report(value, ROOT, OP, NOW)
        self.assertEqual(ctx.exception.code, "F3_CSV_REPORT_HOLDINGS_UNSUPPORTED")

    def test_request_identity_binds_receipt_and_exact_proposal(self):
        value = report(["EXCLUDED"])["proposal"]
        first = command_bytes(ROOT, ROOT, "a" * 64, value, "b" * 64)
        self.assertNotEqual(first, command_bytes(ROOT, ROOT, "a" * 64, value, "c" * 64))
        self.assertNotEqual(first, command_bytes(ROOT, ROOT, "a" * 64, {**value, "filename": "other.csv"}, "b" * 64))
        self.assertEqual(json.loads(first)["request_sha256"], digest(encoded(dict(proposal=value, preview_receipt="b" * 64))))

    def test_cursor_is_canonical_and_strict(self):
        token = encode_cursor(dict(created_at=NOW, report_id=str(ROOT)))
        self.assertEqual(decode_cursor(token), (NOW, str(ROOT)))
        for bad in (token + "=", token + ".bad", "a" * 513, "%%%"):
            with self.subTest(bad=bad), self.assertRaises(AccountStoreError):
                decode_cursor(bad)

    def test_report_unknown_has_no_financial_or_report_payload(self):
        store = object.__new__(GuardedCsvReportStore)
        value = store.unknown(ROOT, OP)
        self.assertEqual(set(value), {"schema", "profile", "disposition", "synthetic", "portfolio_id", "operation_id", "reconcile_url"})
        self.assertIn("/import-report-operations/", value["reconcile_url"])

    def test_success_does_not_claim_financial_issuance(self):
        store = object.__new__(GuardedCsvReportStore)
        raw = encoded(dict(report=final_report(report(["EXCLUDED"]), ROOT, OP, NOW), workspace_result=None))
        row = dict(root_id=ROOT, operation_id=OP, base_revision_id=ROOT, report_id=uuid.uuid4(), response=raw, response_sha256=digest(raw))
        value = store.committed(row)
        self.assertEqual(set(value), set("schema profile disposition synthetic portfolio_id operation_id base_revision_id report_id response_json response_sha256 archive_url reconcile_url".split()))
        self.assertEqual(value["disposition"], "REPORT_COMMITTED")
        self.assertEqual(value["response_json"].encode(), raw)

    def test_csv_export_protects_untrusted_cells(self):
        value = final_report(report(["EXCLUDED"]), ROOT, OP, NOW)
        raw, media = export_report(value, "csv")
        self.assertTrue(media.startswith("text/csv")); self.assertIn("apostrophe", raw)
        raw, _ = export_report(value, "json")
        self.assertEqual(json.loads(raw)["rows"][0]["cells"], ["=1+1"])
