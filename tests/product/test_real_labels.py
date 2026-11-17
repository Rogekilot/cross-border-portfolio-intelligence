"""F1 R3, pure: origin labels (design 1.1, 4.2 [E16], 1 item 6, fact 11; `persistence.real_labels`) and the SOURCE AUDIT of the readers of `rw_*`.

  * The row-to-label mapping is a pure function of the stored row. It is tested here on in-memory rows of both origin values, built inside
    the test and never stored, served or passed to a connection.
  * A TEST_SWITCH (and SYNTHETIC_TEST) root and its output carry no real-origin string.
  * The render test: on an in-memory `REAL_SOURCE` row, none of the display wording (`fictional`, `sandbox`, `synthetic`, `invented`, case-
    insensitive) appears in any server-built string for the real root. The row is a fixture, not a use of a test scope (design 4.3, last
    paragraph); it carries no market number.
  * The source audit: (1) the set of files in `src/` and `web/src` that refer to an S2 object is pinned, so a new reader is a visible change;
    (2) no such file, outside identifiers, carries the audit terms; (3) the SQL that reads the S2 tables names `synthetic = true` only
    in `rw_origin_expected`, the SQL twin of the scope table; (4) the fact-11 files each have a written disposition, and none of them refers
    to an S2 object (the behavioural half, on a crafted root, is in `test_postgres_real_reader_audit.py`).
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for entry in (str(ROOT / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from persistence import real_labels, real_scope  # noqa: E402

DISPLAY_WORDING = re.compile(r"fictional|sandbox|synthetic|invented", re.I)


def row_of(scope_name, **change):
    """An in-memory root row for a scope, built from the scope table's own origin fields. Never stored."""
    row = dict(real_scope.SCOPES[scope_name].origin_fields())
    row.update(change)
    return row


class MappingTests(unittest.TestCase):
    def test_a_real_source_row_maps_to_the_constructed_account_labels(self):
        labels = real_labels.root_labels(row_of("REAL"))
        self.assertEqual((labels["market_origin"], labels["ledger_origin"], labels["personal_holdings"], labels["synthetic"]),
                         ("REAL_SOURCE", "PROJECT_CONSTRUCTED_NONPERSONAL_UAT", False, False))
        self.assertEqual(labels["origin_kind"], "REAL_SOURCE_CONSTRUCTED_ACCOUNT")
        self.assertIn("not the owner's holding", labels["holding_statement"])

    def test_a_test_scope_row_maps_to_the_invented_labels_in_both_test_scopes(self):
        for scope in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            with self.subTest(scope):
                labels = real_labels.root_labels(row_of(scope))
                self.assertEqual(labels["origin_kind"], "INVENTED_TEST_DATA")
                self.assertTrue(labels["synthetic"])
                self.assertIn("Invented", labels["origin_statement"])
                self.assertIn("not a holding", labels["holding_statement"])

    def test_the_labels_are_a_function_of_the_row_only(self):
        """Determinism and purity: the same row gives equal output; the input is not changed; the output is a new dict."""
        row = row_of("REAL")
        before = dict(row)
        first, second = real_labels.root_labels(row), real_labels.root_labels(dict(row))
        self.assertEqual(first, second)
        self.assertEqual(row, before)
        self.assertIsNot(first, row)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_the_label_follows_the_stored_fields_not_a_scope_or_a_mode_name(self):
        """No scope name, mode string or install kind is an input: the same four fields from any source give the same labels."""
        for extra in ({}, {"scope": "TEST_SWITCH"}, {"mode": "LOCAL_REAL_SOURCE_TEST_ACCOUNT"}):
            self.assertEqual(real_labels.root_labels({**row_of("REAL"), **extra})["origin_kind"], "REAL_SOURCE_CONSTRUCTED_ACCOUNT")

    def test_a_row_that_contradicts_itself_or_omits_a_field_is_refused_never_labelled(self):
        real, test = row_of("REAL"), row_of("SYNTHETIC_TEST")
        cases = {
            "RW_LABEL_ORIGIN_MISMATCH": [{**real, "synthetic": True}, {**test, "synthetic": False}, {**real, "ledger_origin": "INVENTED_TEST_LEDGER"},
                                         {**test, "market_origin": "REAL_SOURCE"}, {**real, "market_origin": "SOMETHING_ELSE"}],
            "RW_LABEL_FIELD_TYPE": [{**real, "personal_holdings": None}, {**real, "synthetic": "false"}, {**test, "personal_holdings": 0}],
            "RW_LABEL_PERSONAL_UNSUPPORTED": [{**real, "personal_holdings": True}, {**test, "personal_holdings": True}],
        }
        for field in ("market_origin", "ledger_origin", "personal_holdings", "synthetic"):
            cases.setdefault("RW_LABEL_MISSING_FIELD", []).append({k: v for k, v in real.items() if k != field})
        cases["RW_LABEL_MISSING_FIELD"] += [None, [], "REAL_SOURCE"]
        for code, rows in cases.items():
            for row in rows:
                with self.subTest(code=code, row=row):
                    with self.assertRaises(real_labels.LabelError) as caught:
                        real_labels.root_labels(row)
                    self.assertEqual(caught.exception.code, code)

    def test_the_mapping_covers_exactly_the_origins_the_scope_table_has(self):
        """The table in `real_labels` and `real_scope.SCOPES` agree: every scope's origin fields map, and nothing else does."""
        kinds = {name: real_labels.root_labels(dict(scope.origin_fields()))["origin_kind"] for name, scope in real_scope.SCOPES.items()}
        self.assertEqual(kinds, {"SYNTHETIC_TEST": "INVENTED_TEST_DATA", "TEST_SWITCH": "INVENTED_TEST_DATA", "REAL": "REAL_SOURCE_CONSTRUCTED_ACCOUNT"})


class RealOriginMarkerTests(unittest.TestCase):
    def test_a_test_switch_and_a_synthetic_test_root_and_output_carry_no_real_origin_string(self):
        for scope in ("TEST_SWITCH", "SYNTHETIC_TEST"):
            with self.subTest(scope):
                fields = real_scope.SCOPES[scope].origin_fields()
                labels = real_labels.root_labels(fields)
                for text in (json.dumps(fields), json.dumps(labels), *real_labels.label_strings(labels)):
                    self.assertNotIn(real_scope.REAL_ORIGIN_MARKER, text)
                    self.assertNotIn("PROJECT_CONSTRUCTED", text)

    def test_a_built_test_switch_snapshot_carries_no_real_origin_string(self):
        """The stored form of a TEST_SWITCH root: R1's builder, on invented members, in memory."""
        import real_gateway_fixtures as fx
        from persistence import real_proposal
        scope = real_scope.resolve_scope("TEST_SWITCH", test_switch=True)
        snapshot = real_proposal.build_snapshot(scope, **fx.content("labels/test-switch"))
        self.assertNotIn(real_scope.REAL_ORIGIN_MARKER, real_proposal.canonical_json(snapshot.content) if hasattr(snapshot, "content") else str(snapshot))
        self.assertNotIn(real_scope.REAL_ORIGIN_MARKER, real_proposal.proposal_bytes(snapshot).decode("utf-8"))


class RenderTests(unittest.TestCase):
    """Pure render test (design 1 item 6, fact 11, L-5): the server-built strings for a `REAL_SOURCE` row contain none of the display wording."""

    def test_no_display_wording_reaches_a_server_built_string_for_a_real_source_row(self):
        row = row_of("REAL")                                    # in-memory fixture; never stored, served or passed to a store
        self.assertEqual((row["market_origin"], row["synthetic"]), ("REAL_SOURCE", False))
        strings = real_labels.label_strings(real_labels.root_labels(row))
        self.assertGreaterEqual(len(strings), 5)
        for text in strings:
            self.assertIsNone(DISPLAY_WORDING.search(text), text)

    def test_the_control_the_wording_check_can_fail(self):
        """The check sees the words: the invented-origin strings contain them."""
        strings = real_labels.label_strings(real_labels.root_labels(row_of("TEST_SWITCH")))
        self.assertTrue(any(DISPLAY_WORDING.search(text) for text in strings))


# ======================================================================================================================================
# The source audit
# ======================================================================================================================================
S2_OBJECT = re.compile(r"\brw_(?:root|revision|artifact|operation|journal|seal|archive|md_\w+)\b|\brw_root_link\b|\bRW_ARCHIVE\b", re.I)
# Identifiers that carry the audit terms as part of a NAME (a table, a file, a function, a code), not as wording shown to anyone.
IDENTIFIER = re.compile(r"[\w./]*(?:fictional|sandbox)[\w./]*", re.I)
#: R5 (TR5-L1): the ONE code outside the pattern above that an S2-referencing file may spell: the financial service's refusal code, which the
#: contract lists in its public vocabulary and the tails name in a docstring. An EXPLICIT list of exact tokens, not a pattern, so that an origin
#: enum value (`SYNTHETIC_TEST`, `INVENTED_TEST_LEDGER`, `LOCAL_SYNTHETIC_ACCOUNT`, `SYNTHETIC_ONLY`) hard-coded into a reader is still found.
#: Adding a name here is a reviewed change.
ALLOWED_NAMES = ("SYNTHETIC_MARKET_DATA_REFUSED",)
ALLOWED_NAME = re.compile(r"\b(?:%s)\b" % "|".join(re.escape(n) for n in ALLOWED_NAMES))


def without_identifiers(text):
    """The text with the identifiers the audit exempts removed: names that carry `fictional` or `sandbox`, and the explicit `ALLOWED_NAMES`."""
    return ALLOWED_NAME.sub("", IDENTIFIER.sub("", text))
TEXT_SUFFIXES = {".py", ".sql", ".ts", ".tsx", ".json", ".css"}

# The files of src/ and web/src that refer to an S2 object today, written by hand. A new one must be added here WITH a reading of it.
S2_REFERENCING = {
    "src/persistence/real_catalog_audit.py": "the catalog audit: object names only",
    "src/persistence/real_fence_v1.sql": "the S2 storage, fence, seal, archive and md read functions: the gateway itself (readers/guards below)",
    "src/persistence/real_provenance_v1.sql": "the registry: refers to rw_root_link only (the mandatory link's key)",
    "src/persistence/real_roles.py": "the role lists: object names only",
    "src/persistence/real_workspace_v1.sql": "the R1 authority core: refers to the S2 tables through the link and the lease",
    # R5: the readers and writers of the real gateway's create, read, reproduce and list. Each takes every label from the stored fields via real_labels.
    "src/persistence/real_tails.py": "R5: the shared create and read tails and the reconciliation: rw_precheck and rw_archive by name; it labels nothing",
    "src/real_service/service.py": "R5: the create, archive read, reproduce and list over rw_*; every label is real_labels' over the stored root row, the column names are real_labels.ORIGIN_FIELDS",
    "src/web_api/real_scoped_contract.py": "R5: the scoped contract (pure, installed nowhere): names one gateway refusal code in its public vocabulary; labels come from the stored origin fields",
    # NOT in this set although R5 adds it: `market_data_store.read_release(lease_checked=True)` reads the thirteen rw_md_* functions, but it derives their
    # names from the table names in ONE helper (`_lease_function`) and spells none, so this audit does not see it. It is checked by the recorder tests
    # (`test_real_r5_pure`, `test_postgres_real_r5_real`) and by the read_release call-site audit instead. A reviewer may prefer to list it by name.
}

# Fact 11 (design): the hard-coded readers and labels of today, by file, with their disposition. The narrow terms are those of fact 11.
FACT_11_TERMS = re.compile(r"LOCAL_SYNTHETIC_ACCOUNT|synthetic=True|\"synthetic\": True|allow_synthetic=True|SYNTHETIC_ONLY")
FACT_11 = {
    "src/persistence/web_account_store.py": "list starts at web_saved_sandbox JOIN portfolio; a real root has no web_saved_sandbox row, so it is never listed; the real list is a new function over rw_root (R5) with labels from real_labels",
    "src/persistence/web_workspace_store.py": "every read begins at _initial (web_saved_sandbox JOIN portfolio, ownership first): a real root is NotFound; allow_synthetic=True is the saved sandbox's own evidence call",
    "src/persistence/web_csv_store.py": "ownership by WorkspaceStore._initial; synthetic=True labels the saved sandbox's export rows only",
    "src/persistence/guarded_http_store.py": "F2 fictional branch (guarded profile); labelled synthetic by design; not mounted for a real root; unchanged (T10)",
    "src/persistence/guarded_csv_report_store.py": "F2 fictional branch (guarded CSV report); as above",
    "src/persistence/guarded_workspace_store.py": "F2 fictional branch; as above; its gw_ tables are not the S2 tables",
    "src/web_api/account_routes.py": "routes of the saved-sandbox account API (mode Literal LOCAL_SYNTHETIC_ACCOUNT); the real-mode list route is a different contract (R5/R7)",
    "src/web_api/guarded_routes.py": "routes of the guarded fictional API; as above",
    "src/web_api/analytics_composer.py": "composes from a saved-sandbox record reached through WorkspaceStore; SYNTHETIC_ONLY limitation text; never fed a real root",
    "src/web_api/app.py": "the synthetic demo app: fixed fictional world; no store",
    "src/web_api/synthetic.py": "the fixed fictional world of the demo app; no store",
    "src/web_api/account_dev.py": "dev launcher of the saved-sandbox app (enable_saved_synthetic); not the real-mode launcher",
    "src/web_api/guarded_dev.py": "dev launcher of the guarded fictional app; not the real-mode launcher",
    "src/real_service/worlds.py": "R5: the invented world of the SYNTHETIC_TEST create (allow_synthetic for the fictional integration only); the real builder passes no opt-in, and the service refuses invented data (FF1-C08)",
    "src/financial_service_integration.py": "the F2 fictional integration (allow_synthetic=True; synthetic flag in its envelope); unchanged (T10); the real branch must call the service without the opt-in (FF1-C08, R5)",
    "src/performance_service/service.py": "the service REFUSES synthetic market data (SYNTHETIC_MARKET_DATA_REFUSED); the flag labels the refusal",
    "src/risk_service/service.py": "labelled opt-in allow_synthetic, default off; no root enumeration",
    "src/performance/engine.py": "marks a manifest synthetic when the data is; takes the flag from the input",
    "src/persistence/migrations/0017_web_accounts_and_saved_sandboxes.sql": "the saved-sandbox table's own mode/synthetic constraint: real roots are not stored there (S2)",
}
# web/src (non-test): hard-coded saved-sandbox types and wording. Dispositions; none refers to an S2 object, there being no real-mode route yet.
WEB_FACT_11 = {
    "web/src/account.ts": "types every saved portfolio as mode LOCAL_SYNTHETIC_ACCOUNT, synthetic true, and rejects another value: R7 builds a real-mode list TYPE; this one is not reused for a real root",
    "web/src/account-i18n.ts": "labels the saved sandbox list ('synthetic', 'fictional sandbox'): not reused; R7's real-mode strings come from the stored origin fields",
    "web/src/analytics.ts": "analytics of the saved sandbox",
    "web/src/i18n.ts": "general strings of the synthetic workbench",
    "web/src/transport.ts": "transport of the synthetic routes",
    "web/src/guarded.ts": "client of the guarded fictional API",
    "web/src/guarded-csv-report.ts": "client of the guarded CSV report API",
}


def tracked_text_files(*roots):
    for base in roots:
        for path in sorted((ROOT / base).rglob("*")):
            if path.is_file() and path.suffix in TEXT_SUFFIXES and "__pycache__" not in path.parts and "node_modules" not in path.parts:
                yield path


def relative(path):
    return str(path.relative_to(ROOT))


def is_test_file(path):
    return ".test." in path.name or path.name.startswith("test_")


class SourceAuditTests(unittest.TestCase):
    def test_the_files_that_refer_to_an_s2_object_are_the_pinned_set(self):
        found = {relative(p) for p in tracked_text_files("src", "web/src") if S2_OBJECT.search(p.read_text("utf-8", "replace"))}
        self.assertEqual(found, set(S2_REFERENCING))

    def test_no_python_or_client_file_that_refers_to_an_s2_object_carries_display_wording_or_a_hard_coded_label(self):
        """Outside identifiers, the object-name files carry none of the audit terms and none of fact 11's labels."""
        for name in S2_REFERENCING:
            path = ROOT / name
            if path.suffix == ".sql":
                continue
            with self.subTest(name):
                text = without_identifiers(path.read_text("utf-8"))
                self.assertIsNone(DISPLAY_WORDING.search(text), DISPLAY_WORDING.search(text) and text[max(0, DISPLAY_WORDING.search(text).start() - 60):DISPLAY_WORDING.search(text).end() + 40])
                self.assertIsNone(FACT_11_TERMS.search(text))
                self.assertNotIn("LOCAL_REAL_SOURCE_TEST_ACCOUNT", text)

    def test_the_exemption_is_an_explicit_list_and_hides_no_hard_coded_origin_value(self):
        """TR5-L1: the audit's exemption must not hide an origin enum value hard-coded into a reader (the reviewer's mutant appended
        `TEST_ORIGIN_DEFAULT = {"market_origin": "SYNTHETIC_TEST", "ledger_origin": "INVENTED_TEST_LEDGER"}` to `real_roles.py` and the widened
        pattern let it pass). Control: the one allowed name is exempt."""
        self.assertEqual(ALLOWED_NAMES, ("SYNTHETIC_MARKET_DATA_REFUSED",))
        self.assertIsNone(DISPLAY_WORDING.search(without_identifiers('"SYNTHETIC_MARKET_DATA_REFUSED": (409, "SERVICE", "x")')))
        for value in ("SYNTHETIC_TEST", "INVENTED_TEST_LEDGER", "LOCAL_SYNTHETIC_ACCOUNT", "SYNTHETIC_ONLY", "contains_synthetic", "is_synthetic"):
            with self.subTest(value):
                self.assertIsNotNone(DISPLAY_WORDING.search(without_identifiers('TEST_ORIGIN_DEFAULT = {"market_origin": "%s"}' % value)))
        mutant = (ROOT / "src/persistence/real_roles.py").read_text("utf-8") + (
            '\nTEST_ORIGIN_DEFAULT = {"market_origin": "SYNTHETIC_TEST", "ledger_origin": "INVENTED_TEST_LEDGER"}\n')
        self.assertIsNotNone(DISPLAY_WORDING.search(without_identifiers(mutant)))                         # the reviewer's mutant is found
        self.assertIsNone(DISPLAY_WORDING.search(without_identifiers((ROOT / "src/persistence/real_roles.py").read_text("utf-8"))))   # and the file itself is clean

    def test_the_labelling_module_is_not_a_reader_and_its_code_hard_codes_no_mode_or_scope(self):
        source = (ROOT / "src/persistence/real_labels.py").read_text("utf-8")
        self.assertIsNone(S2_OBJECT.search(source))
        for term in ("LOCAL_SYNTHETIC_ACCOUNT", "LOCAL_REAL_SOURCE_TEST_ACCOUNT", "TEST_SWITCH", "SYNTHETIC_TEST'", "install"):
            self.assertNotIn(term, source.split('"""', 2)[2] if term != "SYNTHETIC_TEST'" else source)
        self.assertNotIn("import psycopg", source)
        self.assertNotIn("connect", source.split('"""', 2)[2])

    def test_the_sql_that_reads_the_s2_tables_names_synthetic_true_only_in_the_scope_twin(self):
        """`synthetic = true` is written by the scope: `rw_origin_expected` (the SQL twin of the scope table) and nowhere else in the S2 readers."""
        literal = re.compile(r"\"synthetic\"\s*:\s*true|'synthetic'\s*,\s*true|synthetic\s*=\s*true|\bsynthetic\s+AND\b|synthetic\)\s*\)", re.I)
        for name in S2_REFERENCING:
            path = ROOT / name
            if path.suffix != ".sql":
                continue
            text = path.read_text("utf-8")
            twin = re.search(r"CREATE FUNCTION __RW_SCHEMA__\.rw_origin_expected.*?\$\$;", text, re.S)
            outside = text.replace(twin.group(0), "") if twin else text
            outside = re.sub(r"--[^\n]*", "", outside)           # comments
            with self.subTest(name):
                # the one other place is the root table's check, which ties the combination of labels the scope table produces
                allowed_check = re.search(r"CONSTRAINT rw_root_origin_ck CHECK\(.*?\)\),", outside, re.S)
                outside = outside.replace(allowed_check.group(0), "") if allowed_check else outside
                self.assertIsNone(literal.search(outside), literal.search(outside) and outside[max(0, literal.search(outside).start() - 80):literal.search(outside).end() + 80])
                self.assertNotIn("LOCAL_SYNTHETIC_ACCOUNT", outside)
                self.assertNotIn("LOCAL_REAL_SOURCE_TEST_ACCOUNT", outside)
        self.assertIn("rw_origin_expected", (ROOT / "src/persistence/real_workspace_v1.sql").read_text("utf-8"))

    def test_the_real_branch_sql_never_stamps_the_root_it_labels_from_a_constant(self):
        """The seal compares the root's stored fields with `rw_origin_expected(scope)`; the label is a column of the row (design 1.1)."""
        text = (ROOT / "src/persistence/real_fence_v1.sql").read_text("utf-8")
        self.assertIn("rw_origin_expected(", text)
        self.assertIn("root.synthetic", text)
        self.assertNotRegex(text, r"INSERT INTO __RW_SCHEMA__\.rw_root\s*\([^)]*\)\s*VALUES\s*\([^)]*\btrue\b")

    def test_fact_11_the_narrow_terms_hit_exactly_the_files_with_a_written_disposition(self):
        """The fact-11 files of `src/`, found by the fact's own terms, each have a disposition above, and none of them refers to an S2 object."""
        hits = {relative(p) for p in tracked_text_files("src")
                if p.suffix in (".py", ".sql") and not p.name.startswith("test_") and FACT_11_TERMS.search(p.read_text("utf-8", "replace"))}
        self.assertEqual(hits, set(FACT_11))
        for name in FACT_11:
            with self.subTest(name):
                self.assertIsNone(S2_OBJECT.search((ROOT / name).read_text("utf-8")))
                self.assertTrue(FACT_11[name])

    def test_fact_11_web_client_files_have_a_disposition_and_refer_to_no_s2_object(self):
        widened = {relative(p) for p in tracked_text_files("web/src") if not is_test_file(p) and DISPLAY_WORDING.search(p.read_text("utf-8", "replace"))}
        self.assertTrue(set(WEB_FACT_11) <= widened)
        for name in WEB_FACT_11:
            with self.subTest(name):
                text = (ROOT / name).read_text("utf-8")
                self.assertIsNone(S2_OBJECT.search(text))
                self.assertIsNotNone(DISPLAY_WORDING.search(text))
        account = (ROOT / "web/src/account.ts").read_text("utf-8")
        self.assertIn("LOCAL_SYNTHETIC_ACCOUNT", account)                    # the type R7 does not reuse (design fact 11, item 6)

    def test_the_saved_sandbox_readers_start_at_the_sandbox_table(self):
        """The text anchors of the dispositions: the list and the ownership check begin at web_saved_sandbox joined to portfolio."""
        accounts = (ROOT / "src/persistence/web_account_store.py").read_text("utf-8")
        self.assertIn("FROM web_saved_sandbox s JOIN portfolio p USING(portfolio_id) WHERE p.user_id=%s \"\n                \"ORDER BY s.created_at", accounts)
        workspace = (ROOT / "src/persistence/web_workspace_store.py").read_text("utf-8")
        self.assertIn("FROM web_saved_sandbox s JOIN portfolio p USING(portfolio_id) WHERE p.user_id=%s AND s.portfolio_id=%s", workspace)
        self.assertIn("self.workspace._initial(conn,user_id,ident)", (ROOT / "src/persistence/web_csv_store.py").read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
