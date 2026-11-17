"""F1 R5, no database: the claim-limit render (design 7.4), the scoped contract (2.4), the shared tails on a fake connection, the static audits and
the pins of what R5 does not do.

Nothing here opens a connection. The fake connection records what the tails send and raises what the test says at the commit point, so the
classification of design 3.1 (E4) is tested on every branch without a database; the PostgreSQL modules run the same code on a real commit.
Labels: these are pure tests; the PostgreSQL modules carry the labels "product path, shared tail on SYNTHETIC_TEST", "E11 crafted probe, not
product evidence" and "first run at R8".
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import json
import re
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg.pq import TransactionStatus  # noqa: E402

from marketdata import claim_limits as cl, claim_render as cr  # noqa: E402
from persistence import market_data_store as mds, real_catalog_audit, real_labels, real_tails  # noqa: E402
from persistence.real_workspace_context import RealWorkspaceError  # noqa: E402
from web_api import real_scoped_contract as contract  # noqa: E402

# ---------------------------------------------------------------------------------------------------------------------------------------------
# The in-memory lineage fixtures of the claim-limit tests. NEVER stored, served or passed to a store or a route (design 4.3, 7.4): placeholder slot
# values, no market number.
# ---------------------------------------------------------------------------------------------------------------------------------------------
REAL_ORIGIN = {"market_origin": "REAL_SOURCE", "ledger_origin": "PROJECT_CONSTRUCTED_NONPERSONAL_UAT", "personal_holdings": False, "synthetic": False}
TEST_ORIGIN = {"market_origin": "SYNTHETIC_TEST", "ledger_origin": "INVENTED_TEST_LEDGER", "personal_holdings": False, "synthetic": True}


def real_source_lineage(**changes):
    # O-7 (the Quant's ruling of 2026-11-10): the valuation date and the price session are two fields, the reading date is a documentation reference, the convention
    # sets are a list, and the exposure window is its two arguments (the price session and the file's retrieval time).
    fixture = {"valuation_date": "<valuation date>", "price_session_date": "<price session>", "missed_sessions": "<missed>", "ledger_quantity": "<quantity>",
               "source_name": "<vendor>", "exchange_mic": "<exchange>", "vendor_call": "<call>", "documentation_reference": "<reference>",
               "adjustment_label_source": "DECLARED", "reporting_currency": "USD", "opening_cash": "<cash>", "metric_state": "AVAILABLE", "freshness": "CURRENT",
               "delay_status": "END_OF_DAY", "reconciliation_status": "SINGLE_SOURCE", "file_hashes": ["<hash 1>", "<hash 2>"],
               "ledger_version": "<L>", "convention_ids": ["<convention 1>", "<convention 2>"], "adjustment_label_status": "UNVERIFIABLE",
               "retrieval_time": "<R>", "v1_statement": "no V1 event in M"}
    fixture.update(changes)
    return fixture


class ClaimRenderTests(unittest.TestCase):
    def block(self, **changes):
        return cr.render_claim_block(REAL_ORIGIN, real_source_lineage(**changes))

    def test_the_block_says_the_seal_checks_the_ledger_by_its_pin_not_its_content_and_disclaims_the_right_things(self):
        """PD-0073 binding obligation and TR5-L2: the claim text states the seal's real limit, disclaims the instrument identity facts the
        computation used (currency, exchange, security type; disposition 5.2) and the manifest's origin, says nothing false about the context
        (for real-source output `rw_check_real` DOES bind the result to its context's snapshot), and never claims a check the seal does not make."""
        s4 = next(item["text"] for item in self.block()["items"] if item["id"] == "S4")
        self.assertIn("checks the ledger by its pin", s4)
        self.assertIn("not by its content", s4)
        self.assertIn("catch a different ledger", s4)
        self.assertIn("does not verify the instrument identity facts the computation used (trading currency, exchange and security type)", s4)
        self.assertIn("does not verify the origin recorded in the engine's manifest", s4)
        everything = " ".join(" ".join(item["text"].split()) for item in self.block()["items"])
        self.assertNotIn("context the result ran under", everything)               # the false disclaimer of the first version
        self.assertNotIn("identity of the account", everything)
        for item in self.block()["items"]:
            text = " ".join(item["text"].split())
            # no sentence has the seal VERIFY or CHECK identity, the context or the manifest origin; each sentence about those is a negation
            for claim in re.findall(r"[Tt]he seal[^.]*\.", text):
                if re.search(r"identity|context|manifest", claim):
                    self.assertIn("does not verify", claim, claim)
                    self.assertNotRegex(claim, r"seal (verifies|checks|confirms|guarantees)\b[^.]*(identity|context|manifest)")

    def test_the_real_source_block_is_complete_with_every_C_item_and_every_S_slot(self):
        block = self.block()
        self.assertEqual([item["id"] for item in block["items"]], list(cr.S_SLOTS + cr.C_IDS))
        self.assertEqual(set(block["slots"]), set(cr.S_SLOTS))
        self.assertEqual(cr.missing_items(block, REAL_ORIGIN), frozenset())
        self.assertEqual(cr.check_block(block, REAL_ORIGIN), [])
        self.assertIsNone(block["invented_data_mark"])

    def test_every_S_slot_is_filled_from_its_own_lineage_field(self):
        for slot, mapping in cr.SLOT_FIELDS.items():
            for slot_name, field in mapping.items():
                with self.subTest(slot=slot, field=field):
                    sentinel = "LIMITED" if field == "metric_state" else "SENTINEL-" + field          # a state that names no variant is refused: the state is a real one
                    block = self.block(**{field: sentinel})
                    value = block["slots"][slot][slot_name]
                    self.assertIn(sentinel, value)
                    text = next(i["text"] for i in block["items"] if i["id"] == slot)
                    self.assertIn(sentinel, text)

    def test_a_lineage_that_lacks_a_field_is_refused_never_rendered_with_a_hole(self):
        for slot, mapping in cr.SLOT_FIELDS.items():
            for field in mapping.values():
                with self.subTest(field=field):
                    lineage = real_source_lineage()
                    del lineage[field]
                    with self.assertRaises(cr.ClaimRenderError) as caught:
                        cr.render_claim_block(REAL_ORIGIN, lineage)
                    # the state picks the variant, so a lineage without one is refused as a state that names no block
                    self.assertEqual(caught.exception.code, "CLAIM_STATE_UNKNOWN" if field == "metric_state" else "CLAIM_LINEAGE_FIELD")
                    with self.assertRaises(cr.ClaimRenderError):
                        cr.render_claim_block(REAL_ORIGIN, real_source_lineage(**{field: "  "}))
        with self.assertRaises(cr.ClaimRenderError):
            cr.render_claim_block(REAL_ORIGIN, None)

    def test_removing_any_one_item_makes_the_completeness_check_fail(self):
        full = self.block()
        for item_id in cr.ALL_ITEM_IDS:
            with self.subTest(removed=item_id):
                cut = dict(full, items=[i for i in full["items"] if i["id"] != item_id])
                self.assertEqual(cr.missing_items(cut, REAL_ORIGIN), frozenset({item_id}))
                self.assertTrue(cr.check_block(cut, REAL_ORIGIN))

    def test_removing_any_one_slot_group_makes_the_completeness_check_fail(self):
        full = self.block()
        for slot in cr.S_SLOTS:
            with self.subTest(removed=slot):
                cut = dict(full, slots={k: v for k, v in full["slots"].items() if k != slot})
                self.assertIn(slot, cr.missing_items(cut, REAL_ORIGIN))
                emptied = dict(full, slots=dict(full["slots"], **{slot: dict(full["slots"][slot], **{next(iter(cr.SLOT_FIELDS[slot])): ""})}))
                self.assertIn(slot, cr.missing_items(emptied, REAL_ORIGIN))

    def test_a_caveat_a_shortened_text_dropped_is_found(self):
        """P3: C1 states the split label AND the dividend component are UNVERIFIABLE; C3 and S3 carry the single-source, no-comparison caveat."""
        full = self.block()
        by_id = {i["id"]: i for i in full["items"]}
        self.assertIn("dividend component", by_id["C1"]["text"])
        self.assertIn("UNVERIFIABLE", by_id["C1"]["text"])
        self.assertIn("SINGLE_SOURCE", by_id["S3"]["text"])
        self.assertIn("other source", by_id["C3"]["text"])
        for item_id, term in (("C1", "dividend component"), ("C1", "split"), ("C2", "closing-cross"), ("C3", "other source"), ("C4", "split history"),
                              ("C5", "zero records"), ("C6", "ledger fact"), ("C7", "another date"), ("S1", "RAW"), ("S2", "not a verification"),
                              ("S3", "SINGLE_SOURCE")):
            with self.subTest(item=item_id, term=term):
                cut = dict(full, items=[dict(i, text=i["text"].replace(term, "")) if i["id"] == item_id else i for i in full["items"]])
                self.assertTrue(any(term in p for p in cr.check_block(cut, REAL_ORIGIN)), cr.check_block(cut, REAL_ORIGIN))

    def test_the_quant_list_is_covered_item_by_item(self):
        covered = {q for i in self.block()["items"] for q in i["quant_ids"]}
        self.assertEqual(cl.missing_claim_limits(covered), frozenset())
        self.assertEqual(cl.unknown_claim_limits(covered), frozenset())
        self.assertIn("N-2", covered)                                               # the dividend component is an item of its own
        full = self.block()
        cut = dict(full, items=[dict(i, quant_ids=[q for q in i["quant_ids"] if q != "N-2"]) for i in full["items"]])
        self.assertTrue(any("N-2" in p for p in cr.check_block(cut, REAL_ORIGIN)))

    def test_the_label_source_is_the_lineages_and_a_memory_label_is_never_rendered_as_declared(self):
        declared = self.block(adjustment_label_source="DECLARED")
        memory = self.block(adjustment_label_source="MEMORY")
        self.assertIn("DECLARED", json.dumps(declared))
        self.assertNotIn("MEMORY", json.dumps(declared))
        self.assertIn("MEMORY", json.dumps(memory))
        self.assertNotIn("DECLARED", json.dumps(memory))
        self.assertNotIn("DECLARED", "\n".join(code_strings(SRC / "marketdata" / "claim_render.py")))      # not hard-coded in the renderer

    def test_over_a_synthetic_origin_the_block_carries_the_invented_data_mark_and_no_real_source_sentence(self):
        lineage = real_source_lineage(vendor_call="SENTINEL_CALL", source_name="SENTINEL_VENDOR", documentation_reference="SENTINEL_READING")
        block = cr.render_claim_block(TEST_ORIGIN, lineage)
        self.assertEqual(block["invented_data_mark"], cr.INVENTED_DATA_MARK)
        self.assertEqual(block["items"], [])
        self.assertEqual(block["slots"], {name: cr.INVENTED_DATA_MARK for name in cr.S_SLOTS})
        text = json.dumps(block)
        for forbidden in ("SENTINEL", "RAW", "close", "session", "vendor", "closing-cross", "UNVERIFIABLE", "SINGLE_SOURCE", "REAL_SOURCE"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(cr.missing_items(block, TEST_ORIGIN), frozenset())
        self.assertEqual(cr.check_block(block, TEST_ORIGIN), [])
        # a block that is not the mark is incomplete, and a real block is not a complete synthetic one
        self.assertTrue(cr.missing_items(self.block(), TEST_ORIGIN))
        self.assertTrue(cr.missing_items({"items": [], "slots": {}, "invented_data_mark": None}, TEST_ORIGIN))

    def test_every_non_real_origin_gets_the_mark_and_the_lineage_is_not_read(self):
        for origin in (TEST_ORIGIN, dict(TEST_ORIGIN, market_origin="SOMETHING_ELSE")):
            self.assertEqual(cr.render_claim_block(origin, None)["invented_data_mark"], cr.INVENTED_DATA_MARK)
        with self.assertRaises(cr.ClaimRenderError):
            cr.render_claim_block({}, None)                                           # the origin is required, never assumed

    def test_the_render_is_pure_and_deterministic(self):
        self.assertEqual(json.dumps(self.block(), sort_keys=True), json.dumps(self.block(), sort_keys=True))
        tree = ast.parse(inspect.getsource(cr))
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        self.assertTrue(imported <= {"__future__", "marketdata"}, imported)            # no connection, clock, network or file module
        self.assertNotRegex(inspect.getsource(cr), r"Alpha ?Vantage|alphavantage|TIME_SERIES")


# ---------------------------------------------------------------------------------------------------------------------------------------------
# The scoped contract
# ---------------------------------------------------------------------------------------------------------------------------------------------
def read_payload(**kw):
    """`contract.read_payload` with the read contract's /2 field defaulted (HG4 condition 2): these tests are about the origin, the labels and the block."""
    return contract.read_payload(**{"created_under_generation": 1, **kw})


def valid_intent(**changes):
    value = {"schema_version": contract.CREATE_SCHEMA, "operation_id": "11111111-1111-4111-8111-111111111111", "source_context_id": "a" * 64,
             "expected_release_id": "b" * 64, "name": "constructed probe", "reporting_currency": "USD", "as_of": "2026-01-05",
             "constructed_ledger_acknowledged": True,
             "opening_positions": [{"listing_id": "22222222-2222-4222-8222-222222222222", "quantity": "10", "cost_basis": None, "acquired_on": None}],
             "opening_cash": {"currency": "USD", "amount": "500"}}
    value.update(changes)
    return value


class ContractBindsLabelsAndBlockToOriginTests(unittest.TestCase):
    """TR5-M1. The reviewer's four accepted bad inputs, each now refused with `REAL_UNAVAILABLE`, and the controls that the matching good inputs
    pass (so a refusal here is the check and not a broken fixture). The REAL_SOURCE origin and lineage are in-memory fixtures, never stored."""

    def labels(self, origin):
        return {k: real_labels.root_labels(origin)[k] for k in contract.LABEL_FIELDS}

    def common(self, origin, block=None, labels=None, **changes):
        value = dict(root_id="r", operation_id="o", revision_id="v", ledger_pin=2, origin=origin, labels=labels or self.labels(origin),
                     response_sha256="1" * 64, issued_sha256="2" * 64, result={"metrics": []},
                     claim_limits=block if block is not None else cr.render_claim_block(origin, real_source_lineage() if origin == REAL_ORIGIN else None))
        value.update(changes)
        return value

    def refused(self, build, **kw):
        with self.assertRaises(contract.ContractRefusal) as caught:
            build(**kw)
        self.assertEqual(caught.exception.code, "REAL_UNAVAILABLE")

    def test_controls_the_matching_origin_labels_and_block_are_accepted_for_both_origins(self):
        for origin in (REAL_ORIGIN, TEST_ORIGIN):
            with self.subTest(origin["market_origin"]):
                self.assertEqual(read_payload(**self.common(origin))["origin"], origin)
                self.assertEqual(contract.committed_payload(**self.common(origin))["labels"], self.labels(origin))
                self.assertEqual(contract.reproduce_payload(root_id="r", operation_id="o", origin=origin, labels=self.labels(origin), status="REPRODUCED",
                                                            detail="", issued_sha256="2" * 64)["origin"], origin)

    def test_a_test_origin_with_the_real_labels_and_the_real_block_is_refused(self):
        real_labels_for_test = self.labels(REAL_ORIGIN)
        real_block = cr.render_claim_block(REAL_ORIGIN, real_source_lineage())
        for build in (contract.committed_payload, read_payload):
            with self.subTest(build.__name__):
                self.refused(build, **self.common(TEST_ORIGIN, block=real_block))                       # block of another origin
                self.refused(build, **self.common(TEST_ORIGIN, labels=real_labels_for_test))            # labels of another origin
                self.refused(build, **self.common(TEST_ORIGIN, labels=real_labels_for_test, block=real_block))   # the reviewer's probe 1
        self.refused(contract.reproduce_payload, root_id="r", operation_id="o", origin=TEST_ORIGIN, labels=real_labels_for_test, status="REPRODUCED",
                     detail="", issued_sha256=None)

    def test_a_real_origin_with_the_invented_data_block_is_refused(self):
        for build in (contract.committed_payload, read_payload):
            with self.subTest(build.__name__):
                self.refused(build, **self.common(REAL_ORIGIN, block=cr.render_claim_block(TEST_ORIGIN)))          # the reviewer's probe 2
                self.refused(build, **self.common(REAL_ORIGIN, labels=self.labels(TEST_ORIGIN)))

    def test_a_real_block_missing_any_one_item_or_slot_or_term_is_refused(self):
        full = cr.render_claim_block(REAL_ORIGIN, real_source_lineage())
        for item_id in cr.ALL_ITEM_IDS:                                                                           # the reviewer's probe 3 for every item
            with self.subTest(removed=item_id):
                thin = dict(full, items=[i for i in full["items"] if i["id"] != item_id])
                self.refused(read_payload,**self.common(REAL_ORIGIN, block=thin))
        weak = dict(full, items=[dict(i, text=i["text"].replace("UNVERIFIABLE", "x")) if i["id"] == "C1" else i for i in full["items"]])
        self.refused(read_payload,**self.common(REAL_ORIGIN, block=weak))                               # a required term removed
        self.refused(read_payload,**self.common(REAL_ORIGIN, block=dict(full, items=["not an item"])))  # a malformed item is a refusal, not a crash

    def test_a_digest_that_is_not_64_lowercase_hex_is_refused(self):
        for bad in ("x", "", "A" * 64, "1" * 63, "1" * 65, None, 5):                                              # the reviewer's probe 4 and its neighbours
            for field in ("response_sha256", "issued_sha256"):
                with self.subTest(field=field, value=bad):
                    self.refused(read_payload,**self.common(TEST_ORIGIN, **{field: bad}))
                    self.refused(contract.committed_payload, **self.common(TEST_ORIGIN, **{field: bad}))
        self.refused(contract.reproduce_payload, root_id="r", operation_id="o", origin=TEST_ORIGIN, labels=self.labels(TEST_ORIGIN), status="REPRODUCED",
                     detail="", issued_sha256="x")
        self.assertIsNone(contract.reproduce_payload(root_id="r", operation_id="o", origin=TEST_ORIGIN, labels=self.labels(TEST_ORIGIN),
                                                     status="SOURCE_REFUSED", detail="c", issued_sha256=None)["issued_sha256"])

    def test_an_origin_that_contradicts_itself_is_refused_even_with_the_labels_of_its_other_half(self):
        torn = dict(REAL_ORIGIN, synthetic=True)
        self.refused(read_payload,**self.common(torn, block=cr.render_claim_block(TEST_ORIGIN), labels=self.labels(TEST_ORIGIN)))


class ContractRendersTheBlockTests(unittest.TestCase):
    """TR5-L5 (R7 first fix). The scoped contract re-renders the claim block from its slots and requires byte equality, and a reproduce result
    names a digest unless the service produced no result. The reviewer's four probes, each accepted before the fix and now refused with
    `REAL_UNAVAILABLE`; the controls show the unchanged good block passes, so a refusal is the check and not a broken fixture."""

    def labels(self, origin):
        return {k: real_labels.root_labels(origin)[k] for k in contract.LABEL_FIELDS}

    def read(self, block, origin=REAL_ORIGIN):
        return read_payload(root_id="r", operation_id="o", revision_id="v", ledger_pin=2, origin=origin, labels=self.labels(origin),
                                     response_sha256="1" * 64, issued_sha256="2" * 64, result={"metrics": []}, claim_limits=block)

    def refused(self, block, origin=REAL_ORIGIN):
        for build in (self.read, lambda b, o=origin: contract.committed_payload(
                root_id="r", operation_id="o", revision_id="v", ledger_pin=2, origin=o, labels=self.labels(o), response_sha256="1" * 64,
                issued_sha256="2" * 64, result={}, claim_limits=b, replayed=False)):
            with self.assertRaises(contract.ContractRefusal) as caught:
                build(block)
            self.assertEqual(caught.exception.code, "REAL_UNAVAILABLE")

    def full(self):
        return cr.render_claim_block(REAL_ORIGIN, real_source_lineage())

    @staticmethod
    def edit(block, item_id, change):
        return dict(block, items=[dict(i, text=change(i["text"])) if i["id"] == item_id else i for i in block["items"]])

    def test_control_the_unchanged_rendering_is_accepted_for_both_origins(self):
        self.assertEqual(self.read(self.full())["claim_limits"], self.full())
        self.assertEqual(self.read(cr.render_claim_block(TEST_ORIGIN), TEST_ORIGIN)["claim_limits"], cr.render_claim_block(TEST_ORIGIN))

    def test_probe_1_the_seal_limit_sentence_deleted_from_S4_is_refused(self):
        thin = self.edit(self.full(), "S4", lambda text: text.replace(" " + cr.SEAL_LIMIT, ""))
        self.assertNotEqual(thin, self.full())
        self.assertNotIn(cr.SEAL_LIMIT, next(i["text"] for i in thin["items"] if i["id"] == "S4"))
        self.assertEqual(cr.check_block(thin, REAL_ORIGIN), [])          # the completeness check alone accepted it: that was the gap
        self.refused(thin)

    def test_probe_2_a_sentence_appended_to_S4_is_refused(self):
        fat = self.edit(self.full(), "S4", lambda text: text + " The seal verifies the identity of every listing.")
        self.assertEqual(cr.check_block(fat, REAL_ORIGIN), [])
        self.refused(fat)

    def test_probe_3_a_slot_value_that_disagrees_with_the_item_text_is_refused(self):
        torn = self.full()
        torn["slots"]["S1"]["quantity"] = "999"
        self.assertEqual(cr.check_block(torn, REAL_ORIGIN), [])
        self.refused(torn)

    def test_probe_4_a_reproduced_result_without_a_digest_is_refused(self):
        labels = self.labels(TEST_ORIGIN)
        for status in ("REPRODUCED", "RESULT_DIFFERS"):
            with self.subTest(status):
                with self.assertRaises(contract.ContractRefusal) as caught:
                    contract.reproduce_payload(root_id="r", operation_id="o", origin=TEST_ORIGIN, labels=labels, status=status, detail="d", issued_sha256=None)
                self.assertEqual(caught.exception.code, "REAL_UNAVAILABLE")
                self.assertEqual(contract.reproduce_payload(root_id="r", operation_id="o", origin=TEST_ORIGIN, labels=labels, status=status, detail="d",
                                                            issued_sha256="2" * 64)["issued_sha256"], "2" * 64)         # control
        for status in ("SOURCE_REFUSED", "INPUT_MISMATCH"):
            self.assertIsNone(contract.reproduce_payload(root_id="r", operation_id="o", origin=TEST_ORIGIN, labels=labels, status=status, detail="d",
                                                         issued_sha256=None)["issued_sha256"])
        self.assertEqual(contract.DIGEST_OPTIONAL_STATUSES, ("INPUT_MISMATCH", "SOURCE_REFUSED"))

    def test_two_slots_that_disagree_about_one_lineage_field_are_refused_even_when_each_text_follows_its_own_slot(self):
        """The label source fills S1, S2 and S5; a block whose S2 says MEMORY and whose S1 and S5 say DECLARED is not a rendering of any lineage."""
        lineage_a, lineage_b = real_source_lineage(), real_source_lineage(adjustment_label_source="MEMORY")
        a, b = cr.render_claim_block(REAL_ORIGIN, lineage_a), cr.render_claim_block(REAL_ORIGIN, lineage_b)
        mixed = dict(a, items=[b["items"][1] if i["id"] == "S2" else i for i in a["items"]], slots=dict(a["slots"], S2=b["slots"]["S2"]))
        self.assertEqual(cr.check_block(mixed, REAL_ORIGIN), [])
        with self.assertRaises(cr.ClaimRenderError) as caught:
            cr.lineage_from_slots(mixed["slots"])
        self.assertEqual(caught.exception.code, "CLAIM_SLOTS_DISAGREE")
        self.refused(mixed)

    def test_slots_with_a_missing_or_extra_group_or_value_are_refused(self):
        for mutate in (lambda s: s.pop("S5"), lambda s: s.update(S6={}), lambda s: s["S1"].pop("call"), lambda s: s["S1"].update(extra="x"),
                       lambda s: s["S3"].update(cash=5)):
            with self.subTest(mutate=mutate):
                block = self.full()
                mutate(block["slots"])
                self.refused(block)

    def test_a_test_origin_block_with_anything_added_or_any_slot_changed_is_refused(self):
        marked = cr.render_claim_block(TEST_ORIGIN)
        self.refused(dict(marked, invented_data_mark=marked["invented_data_mark"] + " x"), TEST_ORIGIN)
        self.refused(dict(marked, slots=dict(marked["slots"], S1="x")), TEST_ORIGIN)

    def test_the_equality_check_is_in_the_contract_and_not_in_a_caller(self):
        source = inspect.getsource(contract._claim_block)
        self.assertIn("lineage_from_slots", source)
        self.assertIn("render_claim_block", source)
        self.assertIn("canonical_json(block) != canonical_json(expected)", source)


def reachable_refusal_codes():
    """The refusal codes the R5 service can return, DERIVED, not written by hand (TR5-L4): every `RW_`, `REAL_`, `LOCAL_` or service-refusal
    code spelled as a whole string constant in the modules the create, read, reproduce and list paths run (the service, the tails, the scope and
    provenance and store helpers, the fictional integration whose `LocalServiceRefusal` code the service re-raises), plus every code the gateway SQL
    raises (`RAISE EXCEPTION 'RW_...'`), which reaches the service through `database_refusal`. `REAL_SOURCE` is an origin value, not a code."""
    pattern = re.compile(r"^(RW_[A-Z0-9_]+|REAL_[A-Z0-9_]+|LOCAL_[A-Z0-9_]+|SYNTHETIC_MARKET_DATA_REFUSED)$")
    files = sorted((SRC / "real_service").glob("*.py")) + [SRC / "persistence" / name for name in (
        "real_tails.py", "real_scope.py", "real_provenance.py", "real_provenance_store.py", "real_workspace_store.py", "real_workspace_context.py")]
    files.append(SRC / "financial_service_integration.py")
    codes = set()
    for path in files:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and pattern.match(node.value):
                codes.add(node.value)
    for path in sorted((SRC / "persistence").glob("real_*_v1.sql")):
        codes.update(re.findall(r"RAISE EXCEPTION\s+'(RW_[A-Z0-9_]+)'", path.read_text()))
    from real_service import worlds
    codes.add(worlds.REFUSAL_CODE)                  # the financial service's own refusal reaches the service as this value, not as a literal
    return codes - {"REAL_SOURCE"}


class RefusalVocabularyTests(unittest.TestCase):
    def test_every_code_the_service_can_return_is_public_or_is_the_503_real_unavailable_and_is_never_reflected(self):
        """The mapping, stated: a reachable code that is a key of `ERRORS` is sent with its own status, kind and fixed text; EVERY OTHER reachable
        code (for example the fictional integration's `LOCAL_SERVICE_RESULT_REFUSED`, the tail's `RW_UNKNOWN_DEFERRABLE`, `RW_LINK_MISSING`, the
        provenance codes, `RW_SHAPE`) is sent as `REAL_UNAVAILABLE`, status 503, kind CONFIGURATION, and the code itself is not reflected. That
        fails closed; it is not a typed 409. The set is derived from the sources, with a non-vacuity floor."""
        derived = reachable_refusal_codes()
        for named in ("LOCAL_SERVICE_RESULT_REFUSED", "RW_UNKNOWN_DEFERRABLE", "RW_DEFERRABLE_INVENTORY_DIFFERS", "RW_LINK_MISSING", "RW_SHAPE",   # not public
                      "RW_NOT_FOUND", "RW_DEADLINE", "RW_MD_READ_REFUSED", "RW_WORLD_DIFFERS", "RW_RELEASE_REFUSED", "SYNTHETIC_MARKET_DATA_REFUSED"):   # public
            self.assertIn(named, derived)
        self.assertGreaterEqual(len(derived), 100)
        status, kind, _ = contract.ERRORS["REAL_UNAVAILABLE"]
        self.assertEqual((status, kind), (503, "CONFIGURATION"))
        public, mapped = [], []
        for code in sorted(derived):
            payload = contract.refusal_payload(SimpleNamespace(code=code))
            if code in contract.ERRORS:
                public.append(code)
                self.assertEqual(payload["error"]["code"], code)
                self.assertEqual((payload["error"]["kind"]), contract.ERRORS[code][1])
            else:
                mapped.append(code)
                self.assertEqual((payload["error"]["code"], payload["error"]["kind"]), ("REAL_UNAVAILABLE", "CONFIGURATION"), code)
                self.assertNotIn(code, json.dumps(payload))
        self.assertIn("RW_NOT_FOUND", public)
        self.assertIn("LOCAL_SERVICE_RESULT_REFUSED", mapped)
        # no dead entry: every public code is one the service can actually return (REAL_UNAVAILABLE is the fallback itself)
        self.assertEqual(set(contract.ERRORS) - derived, set())


class DefenceInDepthGuardTests(unittest.TestCase):
    """TR5-L3. Two guards that another barrier also covers today (the SQL admission's install-kind guard; `read_release`'s registry-against-usage
    -scope refusal), so no end-to-end test can see them go. Each is exercised here with the other barrier taken away (a stub), so removing the
    guard fails a test. Crafted probes of the Python guards, not product evidence of the database."""

    def test_the_create_refuses_a_scope_that_cannot_exist_in_this_install_even_when_the_database_would_admit_it(self):
        """E11 crafted probe, not product evidence. `store.admit` is stubbed to admit (as if the SQL guard were absent) a context whose snapshot
        names a test scope, on an install that reports kind REAL: `_stage_create` must refuse with RW_INSTALL_KIND before the link, the world or any
        write. Control: the same call on an install reporting kind TEST gets past the guard (it stops at the release binding, a later step)."""
        import json
        import unittest.mock as mock
        from persistence import real_scope
        from real_service import service as svc
        snapshot = json.dumps({"scope": "SYNTHETIC_TEST", "release": {"release_id": "a" * 64}}).encode()
        lease = SimpleNamespace(snapshot=snapshot, context_id="c" * 64, generation=1)
        service = svc.RealWorkspaceService("s", executor_role="r", connect=lambda: None)

        def stage(kind):
            reached = []
            with mock.patch.object(svc.store, "admit", lambda *a, **k: lease), mock.patch.object(svc, "query_one", lambda *a, **k: None), \
                    mock.patch.object(real_scope, "read_install_kind", lambda conn, schema: (kind, 600)), \
                    mock.patch.object(svc.RealWorkspaceService, "_require_link", lambda *a, **k: reached.append("link")):
                try:
                    service._stage_create(object(), owner="o", root="r", operation_id="p", intent={"expected_release_id": "b" * 64}, command="d",
                                          context_id="c" * 64, generation=1, link=None)
                except RealWorkspaceError as refusal:
                    return refusal.code, reached
            return None, reached

        self.assertEqual(stage("REAL"), ("RW_INSTALL_KIND", []))
        self.assertEqual(stage("TEST"), ("RW_CONTEXT_BINDING_DIFFERS", []))           # control: past the install-kind guard, stopped by the next check

    def test_the_world_verifier_refuses_a_port_whose_synthetic_flag_differs_from_the_scopes(self):
        """E11 crafted probe, not product evidence (I2, synthetic and real origins never mix). Every digest of the snapshot matches the invented
        world; only the port's `contains_synthetic` is flipped. Control: the unflipped world passes the same verifier."""
        import uuid
        from persistence import real_digests, real_proposal, real_scope
        from real_service import worlds
        scope = real_scope.resolve_scope("SYNTHETIC_TEST")
        fictional = worlds.build_fictional_world(uuid.UUID(int=0))
        stub = real_proposal.Member("0" * 64, "0" * 64, worlds.FICTIONAL_SOURCE, None, "r5.adapter", "1")
        content = real_proposal.build_snapshot(scope, **fictional.snapshot_fields([stub], scope)).content
        world = fictional.world
        projection = real_digests.projection_digest(world.release, world.port.export(), world.calendars)
        self.assertIs(worlds.verify_world(content, scope, world, projection_digest=projection), world)             # control

        class Flipped:
            def __init__(self, port):
                self._port = port
                self.contains_synthetic = not port.contains_synthetic

            def __getattr__(self, name):
                return getattr(self._port, name)

        import dataclasses
        flipped = dataclasses.replace(world, port=Flipped(world.port))
        with self.assertRaises(worlds.WorldError) as caught:
            worlds.verify_world(content, scope, flipped, projection_digest=projection)
        self.assertEqual((caught.exception.code, caught.exception.detail), ("RW_WORLD_DIFFERS", "contains_synthetic"))


class ScopedContractTests(unittest.TestCase):
    def test_a_valid_intent_parses_and_the_request_has_no_mode_field(self):
        parsed = contract.parse_intent(json.dumps(valid_intent()).encode())
        self.assertEqual(parsed, valid_intent())
        self.assertNotIn("mode", parsed)
        with self.assertRaises(contract.ContractRefusal):
            contract.parse_intent(json.dumps(dict(valid_intent(), mode="X")).encode())

    def test_invalid_intents_are_refused_with_one_code(self):
        bad = [dict(valid_intent(), extra=1), {k: v for k, v in valid_intent().items() if k != "name"}, valid_intent(schema_version="x"),
               valid_intent(constructed_ledger_acknowledged=False), valid_intent(operation_id="not-a-uuid"), valid_intent(source_context_id="A" * 64),
               valid_intent(as_of="2026-1-5"), valid_intent(name=" padded"), valid_intent(reporting_currency="EUR"),
               valid_intent(opening_positions=[]), valid_intent(opening_cash={"currency": "EUR", "amount": "1"}),
               valid_intent(opening_positions=[{"listing_id": "22222222-2222-4222-8222-222222222222", "quantity": "10", "cost_basis": "1", "acquired_on": None}])]
        for value in bad:
            with self.subTest(value=str(value)[:80]):
                with self.assertRaises(contract.ContractRefusal) as caught:
                    contract.parse_intent(json.dumps(value).encode())
                self.assertEqual(caught.exception.code, "REAL_REQUEST_INVALID")
        for raw in (b"", b"{", b'{"a":1}', b'{"schema_version":1.5}', b'{"a":"b","a":"c"}', b"[" * 20 + b"]" * 20, b"\xef\xbb\xbf{}", b"x" * 40000,
                    json.dumps(valid_intent(opening_cash={"currency": "USD", "amount": 500})).encode()):
            with self.assertRaises(contract.ContractRefusal):
                contract.parse_intent(raw)

    def test_the_route_table_has_the_four_routes_and_no_export_and_no_other_write(self):
        self.assertEqual([r[0] for r in contract.ROUTES], ["create", "list", "read", "reproduce"])
        self.assertEqual({r[3] for r in contract.ROUTES}, {"EXECUTE_CREATE", "ARCHIVE_READ", "EXECUTE_REPRODUCE"})
        self.assertNotIn("ARCHIVE_EXPORT", {r[3] for r in contract.ROUTES})
        self.assertEqual([r[0] for r in contract.ROUTES if r[1] != "GET"], ["create", "reproduce"])

    def test_the_wire_shapes(self):
        origin = dict(TEST_ORIGIN)
        labels = {k: real_labels.root_labels(origin)[k] for k in contract.LABEL_FIELDS}
        block = cr.render_claim_block(origin)
        created = contract.committed_payload(root_id="r", operation_id="o", revision_id="v", ledger_pin=2, origin=origin, labels=labels,
                                             response_sha256="1" * 64, issued_sha256="2" * 64, result={"metrics": []}, claim_limits=block)
        self.assertEqual(set(created), {"schema_version", "state", "persisted", "replayed", "root_id", "operation_id", "revision_id", "ledger_pin",
                                        "origin", "labels", "response_sha256", "issued_sha256", "result", "claim_limits"})
        self.assertEqual((created["state"], created["persisted"], created["origin"]), ("COMMITTED", True, origin))
        read = read_payload(root_id="r", operation_id="o", revision_id="v", ledger_pin=2, origin=origin, labels=labels,
                                     response_sha256="1" * 64, issued_sha256="2" * 64, result={}, claim_limits=block)
        self.assertEqual(read["schema_version"], contract.READ_SCHEMA)
        self.assertEqual(contract.READ_SCHEMA, "finweb.cp7.real_scoped_read/2")
        self.assertEqual(read["created_under_generation"], 1)
        self.assertNotIn("created_under_generation", created)                                           # the create result is unchanged
        required = dict(root_id="r", operation_id="o", revision_id="v", ledger_pin=2, origin=origin, labels=labels, response_sha256="1" * 64,
                        issued_sha256="2" * 64, result={}, claim_limits=block)
        with self.assertRaises(TypeError):
            contract.read_payload(**required)                                                           # the field is required, never defaulted by the contract
        for bad in (0, -1, 1.5, "1", None, True, False):
            with self.subTest(created_under_generation=bad), self.assertRaises(contract.ContractRefusal) as caught:
                contract.read_payload(created_under_generation=bad, **required)
            self.assertEqual(caught.exception.code, "REAL_UNAVAILABLE")
        self.assertEqual(contract.read_payload(created_under_generation=7, **required)["created_under_generation"], 7)
        reproduced = contract.reproduce_payload(root_id="r", operation_id="o", origin=origin, labels=labels, status="RESULT_DIFFERS", detail="d", issued_sha256="3" * 64)
        self.assertEqual(reproduced["detail"], "d")
        self.assertEqual(contract.reproduce_payload(root_id="r", operation_id="o", origin=origin, labels=labels, status="REPRODUCED", detail="x",
                                                    issued_sha256="2" * 64)["detail"], "")
        with self.assertRaises(contract.ContractRefusal):
            contract.reproduce_payload(root_id="r", operation_id="o", origin=origin, labels=labels, status="ROLLED_BACK", detail="", issued_sha256=None)
        unknown = contract.unknown_payload("op")
        self.assertEqual((unknown["state"], unknown["retried"]), ("UNKNOWN", False))
        self.assertNotIn("ROLLED_BACK", json.dumps(unknown))

    def test_origin_fields_are_taken_exactly_from_the_stored_response_and_never_repaired(self):
        labels = {k: real_labels.root_labels(TEST_ORIGIN)[k] for k in contract.LABEL_FIELDS}
        block = cr.render_claim_block(TEST_ORIGIN)
        common = dict(root_id="r", operation_id="o", revision_id="v", ledger_pin=1, labels=labels, response_sha256="1" * 64, issued_sha256="2" * 64,
                      result={}, claim_limits=block)
        for origin in (None, {}, dict(TEST_ORIGIN, extra=1), {k: v for k, v in TEST_ORIGIN.items() if k != "synthetic"}, dict(TEST_ORIGIN, synthetic="true"),
                       dict(TEST_ORIGIN, personal_holdings=0)):
            with self.subTest(origin=str(origin)):
                with self.assertRaises(contract.ContractRefusal) as caught:
                    read_payload(origin=origin, **common)
                self.assertEqual(caught.exception.code, "REAL_UNAVAILABLE")
        with self.assertRaises(contract.ContractRefusal):
            read_payload(origin=TEST_ORIGIN, **dict(common, labels={"origin_kind": "K"}))
        with self.assertRaises(contract.ContractRefusal):
            read_payload(origin=TEST_ORIGIN, **dict(common, claim_limits={"items": []}))

    def test_the_list_entry_shapes_and_the_refusal_entry_carries_none_of_the_stored_fields(self):
        ok = contract.list_entry(root_id="r2", operation_id="o2", context_id="c", generation=1, created_at="2026-01-01T00:00:00+00:00", origin=TEST_ORIGIN)
        self.assertEqual(set(ok), {"root_id", "operation_id", "context_id", "generation", "created_at", "origin"})
        self.assertEqual(ok["operation_id"], "o2")
        refused = contract.list_entry(root_id="r1", context_id="c", status="RW_LAPSED")
        self.assertEqual(refused, {"root_id": "r1", "context_id": "c", "status": "RW_LAPSED"})
        for bad in (dict(status="RW_LAPSED", origin=TEST_ORIGIN), dict(status="NOT_A_CODE"), dict(status="RW_LAPSED", generation=1), dict(generation=1),
                    dict(status="RW_LAPSED", operation_id="o"),                                              # a refused entry carries no operation id
                    dict(generation=1, created_at="2026-01-01T00:00:00+00:00", origin=TEST_ORIGIN)):          # a readable entry must carry one
            with self.assertRaises(contract.ContractRefusal):
                contract.list_entry(root_id="r", context_id="c", **bad)
        payload = contract.list_payload([ok, refused])
        self.assertEqual([e["root_id"] for e in payload["roots"]], ["r1", "r2"])
        self.assertEqual(contract.list_payload([])["roots"], [])                      # empty only when the owner has no root
        for entry in payload["roots"]:
            self.assertNotRegex(json.dumps(entry), r"ledger_pin|metric|nav|price|value")        # no financial number

    def test_the_refusal_vocabulary_is_closed_and_nothing_is_reflected(self):
        class Error(Exception):
            code = "RW_LAPSED"
            detail = "secret detail"
        self.assertEqual(contract.refusal_payload(Error())["error"]["code"], "RW_LAPSED")
        self.assertNotIn("secret", json.dumps(contract.refusal_payload(Error())))
        other = contract.refusal_payload(SimpleNamespace(code="SOMETHING_INTERNAL"))
        self.assertEqual(other["error"]["code"], "REAL_UNAVAILABLE")
        self.assertNotIn("SOMETHING_INTERNAL", json.dumps(other))
        self.assertEqual(contract.refusal_payload(Error())["persisted"], False)
        for code in ("RW_LAPSED", "RW_WITHDRAWN", "RW_WITHDRAWAL_PENDING", "RW_DEADLINE", "RW_NOT_FOUND", "RW_GENERATION_DIFFERS", "SYNTHETIC_MARKET_DATA_REFUSED"):
            self.assertIn(code, contract.ERRORS)

    def test_the_module_is_a_pure_leaf_and_hard_codes_no_origin(self):
        source = (SRC / "web_api" / "real_scoped_contract.py").read_text()
        tree = ast.parse(source)
        imported = ({n.module + "." + a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names}
                    | {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})
        self.assertTrue(imported <= {"__future__.annotations", "datetime", "json", "re", "uuid", "decimal.Decimal", "types.MappingProxyType",
                                     "marketdata.canonical.canonical_json", "marketdata.claim_render", "persistence.real_labels"}, imported)
        # the two pure modules it takes the shape of the block and the stored origin fields from: nothing else of `persistence` is reached, and no
        # store, connection or service module is in its import closure
        closure = import_closure("web_api.real_scoped_contract")
        self.assertEqual({m for m in closure if m.startswith("persistence.")}, {"persistence.real_labels"})
        self.assertEqual({m for m in closure if m.startswith(("web_api.", "real_service", "performance"))}, {"web_api.real_scoped_contract"})
        strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        joined = "\n".join(strings)
        for forbidden in ("REAL_SOURCE", "SYNTHETIC_TEST", "INVENTED_TEST_LEDGER", "PROJECT_CONSTRUCTED", "LOCAL_REAL_SOURCE_TEST_ACCOUNT", "TEST_SWITCH"):
            self.assertNotIn(forbidden, joined)
        self.assertNotRegex(source, r"synthetic\s*=\s*(True|False)|\"synthetic\":\s*(True|False)")

    def test_it_is_installed_in_the_real_mode_app_and_nowhere_else(self):
        """Design 2.4: R7 installs the reviewed module in the real-mode app. The service that validates the intent imports it, and so does the one
        module that installs its four routes; no other module of `src/` does, and the dev app, the guarded app and the account app never do."""
        importers = sorted(str(p.relative_to(SRC)) for p in SRC.rglob("*.py") if "real_scoped_contract" in p.read_text() and p.name != "real_scoped_contract.py")
        # The supplementary run's loopback tool (`real_tools/r8_http_check.py`, PD-0087/PD-0088, TR8S M-1) is the one other importer, on purpose: it must compare a refused
        # response byte for byte with THE CONTRACT'S OWN refusal body (`canonical_json(refusal_payload(ContractRefusal(code)))`) and use its schema constants, ERRORS table
        # and `validate_intent`. A copy of them in the tool would drift from the contract the server uses, and the comparison would then prove nothing. It installs no route
        # and serves nothing; it only reads constants and builds expected bytes.
        self.assertEqual(importers, ["real_service/service.py", "real_tools/r8_http_check.py", "web_api/real_mode_routes.py"])
        tool = (SRC / "real_tools" / "r8_http_check.py").read_text()
        self.assertEqual(sorted(set(re.findall(r"contract\.([A-Za-z_]+)", tool))),
                         sorted({"CREATE_RESULT_SCHEMA", "CREATE_SCHEMA", "ContractRefusal", "ERRORS", "HASH", "LIST_SCHEMA", "READ_SCHEMA", "REPRODUCE_SCHEMA", "REPRODUCE_STATUSES",
                                 "UNKNOWN_SCHEMA", "refusal_payload", "validate_intent"}))
        for p in (SRC / "web_api").glob("*.py"):
            if p.name not in ("real_scoped_contract.py", "real_mode_routes.py"):
                self.assertNotIn("real_scoped_contract", p.read_text(), p.name)
        for name in ("app.py", "dev.py", "guarded_dev.py", "account_dev.py", "account_routes.py", "real_launcher.py"):
            text = (SRC / "web_api" / name).read_text()
            self.assertNotIn("real_scoped", text)
            self.assertNotIn("/api/real/v1", text)

    def test_E5s_closed_contract_is_unchanged_and_still_closed(self):
        from web_api import real_workspace_contract as e5
        self.assertEqual(e5.SCHEMA, "finweb.cp7.real_interface_contract/1")
        catalogue = e5.ClosedCatalogue((e5.ClosedContext("a" * 64, "b" * 64, "UNQUALIFIED"),))
        intent = {"schema_version": e5.REQUEST_SCHEMA, "operation_id": "11111111-1111-4111-8111-111111111111", "mode": e5.MODE,
                  "source_context_id": "a" * 64, "expected_release_id": "b" * 64, "name": "x", "reporting_currency": "USD", "as_of": "2026-01-05",
                  "constructed_ledger_acknowledged": True,
                  "opening_positions": [{"listing_id": "22222222-2222-4222-8222-222222222222", "quantity": "1", "cost_basis": None, "acquired_on": None}],
                  "opening_cash": {"currency": "USD", "amount": "1"}}
        with self.assertRaises(e5.ContractRefusal) as caught:
            e5.refuse_intent(catalogue, intent)
        self.assertEqual(caught.exception.code, "REAL_CONTEXT_NOT_QUALIFIED")
        self.assertNotEqual(contract.SCHEMA, e5.SCHEMA)


# ---------------------------------------------------------------------------------------------------------------------------------------------
# The tails on a fake connection
# ---------------------------------------------------------------------------------------------------------------------------------------------
INVENTORY = [(n, t, k) for n, t, k in sorted(real_catalog_audit.EXPECTED_DEFERRABLE)]


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class FakeConn:
    """Records what is sent; `at_commit` (an exception instance) is raised at the commit point, and `status_after` is the state the connection
    is left in; `inventory` is what the catalog query returns."""

    def __init__(self, *, at_commit=None, status_after=TransactionStatus.IDLE, inventory=None):
        self.closed = False
        self.events = []
        self.info = SimpleNamespace(transaction_status=TransactionStatus.IDLE)
        self.at_commit, self.status_after = at_commit, status_after
        self.inventory = INVENTORY if inventory is None else inventory

    def execute(self, query, params=None, **kw):
        text = query if isinstance(query, str) else repr(query)
        self.events.append(" ".join(text.split()))
        if "pg_constraint" in text:
            return FakeResult(self.inventory)
        return FakeResult([])

    @contextmanager
    def transaction(self):
        self.events.append("BEGIN")
        self.info.transaction_status = TransactionStatus.INTRANS
        try:
            yield self
        except BaseException:
            self.events.append("ROLLBACK")
            self.info.transaction_status = TransactionStatus.IDLE
            raise
        self.events.append("COMMIT")
        if self.at_commit is not None:
            self.info.transaction_status = self.status_after
            raise self.at_commit
        self.info.transaction_status = TransactionStatus.IDLE

    def constraints(self):
        return [e for e in self.events if "SET CONSTRAINTS" in e]


def gateway_error(code="RW_DEADLINE"):
    return psycopg.errors.RaiseException(code)


class FireByNameTests(unittest.TestCase):
    def test_every_inventory_constraint_but_the_deadline_guard_is_named_and_none_is_all(self):
        conn = FakeConn()
        fired = real_tails.fire_by_name(conn, "s")
        self.assertEqual(set(fired), {n for n, _t, _k in INVENTORY} - {real_tails.DEADLINE_GUARD})
        self.assertGreaterEqual(len(conn.constraints()), 1)
        for event in conn.constraints():
            self.assertIsNone(re.search(r"SET CONSTRAINTS\s+ALL\b", event, re.I), event)
            self.assertNotIn(real_tails.DEADLINE_GUARD, event)
        self.assertEqual(len(conn.constraints()), len(fired))

    def test_the_guard_is_never_fired_whatever_order_the_catalog_returns(self):
        for order in (INVENTORY, list(reversed(INVENTORY))):
            conn = FakeConn(inventory=order)
            real_tails.fire_by_name(conn, "s")
            self.assertFalse(any(real_tails.DEADLINE_GUARD in e for e in conn.constraints()))

    def test_an_unknown_deferrable_constraint_is_refused_before_anything_is_fired(self):
        conn = FakeConn(inventory=INVENTORY + [("surprise_fk", "account", "f")])
        with self.assertRaises(RealWorkspaceError) as caught:
            real_tails.fire_by_name(conn, "s")
        self.assertEqual(caught.exception.code, "RW_UNKNOWN_DEFERRABLE")
        self.assertIn("surprise_fk", caught.exception.detail)
        self.assertEqual(conn.constraints(), [])

    def test_a_missing_expected_constraint_is_refused(self):
        conn = FakeConn(inventory=[row for row in INVENTORY if row[0] != "rw_bundle_complete"])
        with self.assertRaises(RealWorkspaceError) as caught:
            real_tails.fire_by_name(conn, "s")
        self.assertEqual((caught.exception.code, caught.exception.detail), ("RW_DEFERRABLE_INVENTORY_DIFFERS", "rw_bundle_complete"))
        self.assertEqual(conn.constraints(), [])


class CreateTailClassificationTests(unittest.TestCase):
    def run_create(self, conn, stage=None):
        tail = real_tails.CreateTail(conn, "s", lock_timeout_ms=5)
        return tail.run(stage or (lambda c: "VALUE"), operation_id="op")

    def test_a_commit_that_succeeds_delivers_the_value_after_firing_by_name_and_before_returning(self):
        conn = FakeConn()
        order = []
        outcome = self.run_create(conn, lambda c: order.append(list(c.events)) or "VALUE")
        self.assertEqual(outcome, real_tails.Done("VALUE"))
        self.assertTrue(outcome.persisted)
        events = conn.events
        self.assertEqual(events[0], "BEGIN")
        self.assertLess(events.index("COMMIT"), len(events))
        self.assertTrue(all(i < events.index("COMMIT") for i, e in enumerate(events) if "SET CONSTRAINTS" in e))      # fired BEFORE the commit
        self.assertEqual(len(conn.constraints()), len(INVENTORY) - 1)

    def test_a_gateway_code_at_the_commit_on_an_idle_connection_is_a_definite_refusal(self):
        outcome = self.run_create(FakeConn(at_commit=gateway_error("RW_DEADLINE")))
        self.assertEqual((type(outcome).__name__, outcome.code, outcome.persisted), ("Refused", "RW_DEADLINE", False))

    def test_a_gateway_code_at_the_commit_on_a_connection_that_is_not_idle_is_unknown(self):
        outcome = self.run_create(FakeConn(at_commit=gateway_error("RW_DEADLINE"), status_after=TransactionStatus.INERROR))
        self.assertEqual(type(outcome).__name__, "Unknown")

    def test_every_other_error_at_the_commit_is_unknown_even_on_an_idle_connection(self):
        for error in (psycopg.OperationalError("lost"), psycopg.errors.CheckViolation("no gateway code"), psycopg.errors.LockNotAvailable("lock"),
                      psycopg.errors.DeadlockDetected("deadlock"), psycopg.errors.QueryCanceled("cancel"), psycopg.InterfaceError("driver"),
                      psycopg.errors.RaiseException("NOT_A_GATEWAY_CODE"), psycopg.errors.SerializationFailure("serialization")):
            with self.subTest(error=type(error).__name__):
                outcome = self.run_create(FakeConn(at_commit=error))
                self.assertEqual((type(outcome).__name__, outcome.disposition), ("Unknown", "UNKNOWN"))

    def test_a_closed_connection_at_the_commit_is_unknown(self):
        conn = FakeConn(at_commit=gateway_error("RW_DEADLINE"))
        conn.closed = True
        self.assertEqual(type(self.run_create(conn)).__name__, "Unknown")

    def test_a_refusal_in_the_stage_rolls_back_and_nothing_is_fired_and_nothing_is_committed(self):
        conn = FakeConn()

        def refuse(c):
            raise RealWorkspaceError("RW_WORLD_DIFFERS", "identity_digest")
        outcome = self.run_create(conn, refuse)
        self.assertEqual((type(outcome).__name__, outcome.code, outcome.detail), ("Refused", "RW_WORLD_DIFFERS", "identity_digest"))
        self.assertIn("ROLLBACK", conn.events)
        self.assertNotIn("COMMIT", conn.events)
        self.assertEqual(conn.constraints(), [])

    def test_a_service_refusal_carries_the_services_bytes_and_rolls_back(self):
        conn = FakeConn()

        def refuse(c):
            raise real_tails.ServiceRefusal("SYNTHETIC_MARKET_DATA_REFUSED", b"{}")
        outcome = self.run_create(conn, refuse)
        self.assertEqual((outcome.code, outcome.issued_bytes, outcome.persisted), ("SYNTHETIC_MARKET_DATA_REFUSED", b"{}", False))
        self.assertNotIn("COMMIT", conn.events)
        self.assertEqual(conn.constraints(), [])

    def test_a_lock_timeout_before_the_commit_is_a_definite_refusal_and_at_the_commit_is_unknown(self):
        def locked(c):
            raise psycopg.errors.LockNotAvailable("lock")
        before = self.run_create(FakeConn(), locked)
        self.assertEqual((type(before).__name__, before.code), ("Refused", "RW_LOCK_TIMEOUT"))
        at = self.run_create(FakeConn(at_commit=psycopg.errors.LockNotAvailable("lock")))
        self.assertEqual(type(at).__name__, "Unknown")

    def test_an_error_with_no_gateway_code_before_the_commit_on_a_usable_connection_is_a_definite_rollback(self):
        def failing(c):
            raise psycopg.errors.DeadlockDetected("deadlock")
        outcome = self.run_create(FakeConn(), failing)
        self.assertEqual((type(outcome).__name__, outcome.code, outcome.detail), ("Refused", "RW_STATEMENT_FAILED", "DeadlockDetected"))

    def test_nothing_is_retried(self):
        calls = []
        self.run_create(FakeConn(at_commit=psycopg.OperationalError("lost")), lambda c: calls.append(1) or "V")
        self.assertEqual(calls, [1])

    def test_a_non_idle_connection_is_refused_before_anything_is_sent(self):
        conn = FakeConn()
        conn.info.transaction_status = TransactionStatus.INTRANS
        with self.assertRaises(RealWorkspaceError) as caught:
            self.run_create(conn)
        self.assertEqual(caught.exception.code, "RW_OUTER_TRANSACTION_REQUIRED")
        self.assertEqual(conn.events, [])

    def test_the_search_path_is_pinned_inside_the_transaction_with_pg_temp_last(self):
        conn = FakeConn()
        self.run_create(conn)
        pins = [e for e in conn.events if "search_path" in e]
        self.assertEqual(len(pins), 1)
        self.assertLess(conn.events.index("BEGIN"), conn.events.index(pins[0]))
        self.assertIn("pg_temp", pins[0])


class ReadTailTests(unittest.TestCase):
    def test_the_value_is_returned_after_the_commit_and_no_constraint_is_ever_named(self):
        conn = FakeConn()
        seen = []
        outcome = real_tails.ReadTail(conn, "s").run(lambda c: seen.append(list(c.events)) or "VALUE")
        self.assertEqual(outcome, real_tails.Done("VALUE"))
        self.assertNotIn("COMMIT", seen[0])                                           # the body ran before the commit
        self.assertEqual(conn.events[-1], "COMMIT")
        self.assertEqual(conn.constraints(), [])
        self.assertFalse(any("CONSTRAINTS" in e.upper() for e in conn.events))

    def test_a_deadline_refusal_at_the_commit_delivers_no_value(self):
        outcome = real_tails.ReadTail(FakeConn(at_commit=gateway_error("RW_DEADLINE")), "s").run(lambda c: "SECRET")
        self.assertEqual((type(outcome).__name__, outcome.code), ("Refused", "RW_DEADLINE"))
        self.assertFalse(hasattr(outcome, "value"))
        self.assertNotIn("SECRET", repr(outcome))

    def test_an_unclassified_error_at_the_commit_is_unknown_with_no_value(self):
        outcome = real_tails.ReadTail(FakeConn(at_commit=psycopg.OperationalError("lost")), "s").run(lambda c: "SECRET")
        self.assertEqual(type(outcome).__name__, "Unknown")
        self.assertFalse(hasattr(outcome, "value"))

    def test_a_refusal_in_the_body_is_a_definite_refusal_with_no_value(self):
        def refuse(c):
            raise RealWorkspaceError("RW_LAPSED")
        outcome = real_tails.ReadTail(FakeConn(), "s").run(refuse)
        self.assertEqual((type(outcome).__name__, outcome.code), ("Refused", "RW_LAPSED"))


class ReconcileTests(unittest.TestCase):
    def reconcile(self, connect):
        import uuid
        return real_tails.reconcile(connect, "s", owner=uuid.UUID(int=1), root=uuid.UUID(int=2), operation_id=uuid.UUID(int=3), command_sha256="1" * 64,
                                    context_id="a" * 64, generation=1)

    def test_an_absent_operation_is_unknown_never_rolled_back_and_the_new_connection_is_closed(self):
        conn = FakeConn()
        conn.close = lambda: setattr(conn, "closed", True)
        reconciled = self.reconcile(lambda: conn)
        self.assertEqual((reconciled.status, reconciled.reason), ("UNKNOWN", "ABSENT"))
        self.assertTrue(conn.closed)

    def test_no_connection_is_unknown(self):
        def refuse():
            raise psycopg.OperationalError("down")
        reconciled = self.reconcile(refuse)
        self.assertEqual((reconciled.status, reconciled.reason), ("UNKNOWN", "NO_CONNECTION"))

    def test_a_commit_time_error_of_the_reconciliation_itself_is_unknown(self):
        conn = FakeConn(at_commit=psycopg.OperationalError("lost"))
        conn.close = lambda: None
        self.assertEqual(self.reconcile(lambda: conn).status, "UNKNOWN")

    def test_the_result_has_no_rolled_back_state(self):
        values = set(re.findall(r'Reconciled\("([A-Z_]+)"', inspect.getsource(real_tails)))
        self.assertEqual(values, {"COMMITTED", "UNKNOWN"})
        self.assertNotRegex(inspect.getsource(real_tails.reconcile), r"ROLLED|ROLLBACK")


# ---------------------------------------------------------------------------------------------------------------------------------------------
# read_release(lease_checked=...) on a recording connection
# ---------------------------------------------------------------------------------------------------------------------------------------------
class RecordingStatements:
    def __init__(self):
        self.statements = []

    def execute(self, query, params=None):
        self.statements.append((" ".join(query.split()), params))
        return FakeResult([(False,)] if "contains_synthetic" in query else [])


class LeaseCheckedReadTests(unittest.TestCase):
    @staticmethod
    def reads(lease_checked):
        from real_r5_case import md_table_reads, rw_md_calls
        conn = RecordingStatements()
        contents, _calendars = mds._read_contents(conn, "REL", "s", lease_checked)
        statements = [s for s, _p in conn.statements]
        return conn.statements, md_table_reads(statements), rw_md_calls(statements), contents

    def test_the_keyword_is_keyword_only_and_defaults_to_the_table_read(self):
        parameter = inspect.signature(mds.read_release).parameters["lease_checked"]
        self.assertEqual((parameter.kind, parameter.default), (inspect.Parameter.KEYWORD_ONLY, False))

    def test_lease_checked_reads_only_through_the_functions_and_passes_the_release_first(self):
        statements, tables, functions, _contents = self.reads(True)
        self.assertEqual(tables, [])
        self.assertGreaterEqual(len(functions), 8)
        for text, params in statements:
            self.assertEqual(params[0], "REL")
            self.assertEqual(params[0:2], ("REL", "REL"))                             # the function's argument, then the WHERE's

    def test_the_default_reads_the_tables_and_no_function(self):
        statements, tables, functions, _contents = self.reads(False)
        self.assertGreaterEqual(len(tables), 8)
        self.assertEqual(functions, [])
        self.assertTrue(all(p == ("REL",) for _s, p in statements))

    def test_the_two_forms_select_the_same_columns_in_the_same_order(self):
        def normalise(text):
            return re.sub(r'FROM "s"\.(rw_)?(md_\w+)(\(%s\) AS md_\w+)?', r"FROM T:\2", text)
        a = [normalise(s) for s, _p in self.reads(True)[0]]
        b = [normalise(s) for s, _p in self.reads(False)[0]]
        self.assertEqual(a, b)

    def test_the_matcher_strips_the_schema_qualifier_and_quotes(self):
        from real_r5_case import md_table_reads, referenced_tables
        self.assertEqual(referenced_tables('SELECT 1 FROM "s".md_quote WHERE x'), ["md_quote"])
        self.assertEqual(referenced_tables('SELECT 1 FROM "some_schema".md_quote q JOIN s.md_file f ON 1=1'), ["md_quote", "md_file"])
        self.assertEqual(md_table_reads(['SELECT 1 FROM "s".md_quote WHERE x']), ['SELECT 1 FROM "s".md_quote WHERE x'])
        self.assertEqual(md_table_reads(['SELECT 1 FROM "s".rw_md_quote(%s) AS md_quote']), [])


# ---------------------------------------------------------------------------------------------------------------------------------------------
# The static audits
# ---------------------------------------------------------------------------------------------------------------------------------------------
def docstring_nodes(tree):
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                skip.add(id(first.value))
    return skip


def code_strings(path):
    tree = ast.parse(Path(path).read_text())
    skip = docstring_nodes(tree)
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in skip]


def import_closure(start):
    def path_of(name):
        p = SRC / (name.replace(".", "/") + ".py")
        if p.exists():
            return p
        p = SRC / name.replace(".", "/") / "__init__.py"
        return p if p.exists() else None
    seen, todo = set(), [start]
    while todo:
        name = todo.pop()
        path = path_of(name)
        if name in seen or path is None:
            continue
        seen.add(name)
        for n in ast.walk(ast.parse(path.read_text())):
            if isinstance(n, ast.Import):
                todo.extend(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
                todo.append(n.module)
                todo.extend(n.module + "." + a.name for a in n.names)
    return seen


R5_MODULES = ("real_service/service.py", "real_service/worlds.py", "persistence/real_tails.py")
CREATE_READ_FILES = ("real_service/service.py", "real_service/worlds.py")
#: the four sites of `SET CONSTRAINTS ALL` that exist at HEAD (design 3.2, technical round-2 observation)
ALL_SITES = {"persistence/guarded_csv_report_store.py", "persistence/guarded_workspace_store.py", "persistence/web_csv_store.py",
             "persistence/web_workspace_store.py"}


class StaticAuditTests(unittest.TestCase):
    def test_neither_branchs_create_nor_its_read_reproduce_or_list_code_has_its_own_commit_set_constraints_or_classification(self):
        for relative in CREATE_READ_FILES:
            path = SRC / relative
            strings = "\n".join(code_strings(path)).upper()
            self.assertIsNone(re.search(r"\bCOMMIT\b", strings), relative)
            self.assertNotIn("SET CONSTRAINTS", strings, relative)
            self.assertIsNone(re.search(r"\bROLLBACK\b", strings), relative)
            tree = ast.parse(path.read_text())
            attributes = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
            names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            self.assertFalse(attributes & {"commit", "rollback", "_classify", "_transact", "_before_commit", "_after_commit", "transaction"}, relative)
            self.assertFalse(names & {"database_refusal", "OneTransaction", "TransactionStatus"}, relative)
            self.assertNotIn("autocommit", attributes)

    def test_the_service_runs_every_create_through_the_create_tail_and_every_read_through_the_read_tail(self):
        source = (SRC / "real_service/service.py").read_text()
        tree = ast.parse(source)
        methods = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        calls = lambda name: {c.func.attr for c in ast.walk(methods[name]) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)}   # noqa: E731
        self.assertIn("_create_tail", calls("create"))
        for name in ("archive_read", "reproduce", "list_roots", "roots_of"):
            self.assertIn("_read_tail", calls(name), name)
        self.assertIn("reconcile", calls("reconcile"))
        # the only transaction runners are the two tail factories (R7 adds `roots_of`, step 1 of the list on its own, through the read tail)
        runners = [n.name for n in methods.values() if any(isinstance(c, ast.Attribute) and c.attr == "run" for c in ast.walk(n))]
        self.assertEqual(sorted(runners), ["archive_read", "create", "list_roots", "reproduce", "roots_of"])

    def test_set_constraints_appears_in_exactly_one_statement_of_the_new_code_and_never_with_all(self):
        found = []
        for relative in R5_MODULES + ("web_api/real_scoped_contract.py", "marketdata/claim_render.py"):
            for text in code_strings(SRC / relative):
                if "SET CONSTRAINTS" in text.upper():
                    found.append((relative, text))
        self.assertEqual(found, [("persistence/real_tails.py", "SET CONSTRAINTS {}.{} IMMEDIATE")])
        self.assertNotRegex(found[0][1], r"(?i)\bALL\b")
        tails = (SRC / "persistence/real_tails.py").read_text()
        guard_uses = [n for n in ast.walk(ast.parse(tails)) if isinstance(n, ast.Name) and n.id == "DEADLINE_GUARD" and isinstance(n.ctx, ast.Load)]
        self.assertEqual(len(guard_uses), 1)                                       # only the skip in fire_by_name names the guard

    def test_the_set_constraints_all_sites_at_head_are_the_four_and_the_new_code_reaches_none(self):
        sites = set()
        for path in SRC.rglob("*.py"):
            if any(re.search(r"SET CONSTRAINTS ALL", s, re.I) for s in code_strings(path)):
                sites.add(str(path.relative_to(SRC)))
        self.assertEqual(sites, ALL_SITES)
        forbidden = {s[:-3].replace("/", ".") for s in ALL_SITES}
        for relative in R5_MODULES + ("web_api/real_scoped_contract.py", "marketdata/claim_render.py"):
            closure = import_closure(relative[:-3].replace("/", "."))
            self.assertEqual(closure & forbidden, set(), relative)
        self.assertEqual(import_closure("persistence.market_data_store") & forbidden, set())

    def test_every_call_of_read_release_under_src_on_the_real_path_passes_lease_checked(self):
        sites = []
        for path in SRC.rglob("*.py"):
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", None)) == "read_release":
                    keywords = {k.arg: k.value for k in node.keywords}
                    sites.append((str(path.relative_to(SRC)), keywords.get("lease_checked")))
        self.assertEqual(len(sites), 1, sites)                                      # at HEAD there is no other call under src/
        relative, value = sites[0]
        self.assertEqual(relative, "real_service/worlds.py")
        self.assertIsInstance(value, ast.Constant)
        self.assertIs(value.value, True)

    def test_no_gateway_sql_was_added_after_R3(self):
        """R5 adds no gateway SQL (technical TR3-L6): a later change reopens R3's review and re-runs the catalog audit. The digests are those of the
        committed files at R5's start; a reviewed gateway change updates them on purpose."""
        pinned = {"real_fence_v1.sql": "5c64d1ba63ff7c2ec5f3e0080d3395190e161db13a2fdf03c2abd3f07ca056f7",
                  "real_workspace_v1.sql": "46deeac711f0681c3a520785b6b001d1101228f6ba042ac0c5f680473d088215",
                  "real_provenance_v1.sql": "b645884c50fa5b02818a9c2e56616c6236d18cab6c6a7707c1fe309ee28343b9",
                  "real_workspace_fictional_v1.sql": "e485cac3a62d61415288f30cadc726b91268b6494e8fece3c818dd091024cd0d"}
        for name, digest in pinned.items():
            self.assertEqual(hashlib.sha256((SRC / "persistence" / name).read_bytes()).hexdigest(), digest, name)
        self.assertEqual(sorted(p.name for p in (SRC / "persistence").glob("real_*.sql")), sorted(pinned))

    def test_the_new_code_writes_no_origin_string_and_no_mode_and_never_marks_a_value_synthetic(self):
        for relative in R5_MODULES:
            strings = "\n".join(code_strings(SRC / relative))
            for forbidden in ("REAL_SOURCE", "SYNTHETIC_TEST", "INVENTED_TEST_LEDGER", "PROJECT_CONSTRUCTED", "LOCAL_REAL_SOURCE_TEST_ACCOUNT"):
                self.assertNotIn(forbidden, strings, relative)
        source = "".join((SRC / r).read_text() for r in R5_MODULES)
        self.assertNotRegex(source, r"synthetic\s*=\s*False|\"synthetic\":\s*False")

    def test_the_real_envelope_has_the_key_set_the_seal_accepts(self):
        sql = (SRC / "persistence/real_fence_v1.sql").read_text()
        match = re.search(r"CREATE FUNCTION __RW_SCHEMA__\.rw_check_real.*?rw_keys\(p_env,ARRAY\[(.*?)\]\)", sql, re.S)
        accepted = set(re.findall(r"'([a-z0-9_]+)'", match.group(1)))
        from persistence import real_scope
        from real_service.service import real_envelope
        import uuid
        lease = SimpleNamespace(context_id="a" * 64, generation=1)
        result = SimpleNamespace(manifest=SimpleNamespace(manifest_id="m" * 64), result_digest="d" * 64)
        scope = real_scope.SCOPES["REAL"]
        envelope = real_envelope(scope=scope, owner=uuid.UUID(int=1), root=uuid.UUID(int=2), operation_id=uuid.UUID(int=3), revision=uuid.UUID(int=4),
                                 pin=2, lease=lease, issued=b"{}", response={"a": 1}, result=result)
        self.assertEqual(set(envelope), accepted)
        self.assertEqual(envelope["schema"], "finweb.real.issued_envelope/1")
        self.assertEqual((envelope["scope"], envelope["synthetic"]), (scope.name, scope.synthetic))                # both from the scope table

    def test_every_pg_test_of_R5_says_what_it_is(self):
        labels = ("product path, shared tail on SYNTHETIC_TEST", "E11 crafted probe, not product evidence", "first run at R8",
                  "product path, real branch to the service's refusal")
        for name in ("test_postgres_real_r5_tails.py", "test_postgres_real_r5_real.py"):
            tree = ast.parse((HERE / name).read_text())
            for cls in (n for n in tree.body if isinstance(n, ast.ClassDef)):
                for fn in (n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test")):
                    doc = ast.get_docstring(fn) or ""
                    self.assertTrue(any(label in doc for label in labels), "%s.%s.%s has no label" % (name, cls.name, fn.name))

    def test_the_digest_functions_are_one_implementation_shared_by_the_run_and_the_product(self):
        """R5 moved R4b's six digest functions to `persistence.real_digests` (product code never imports `real_tools`); the run's names are THE
        SAME objects, so the qualification run and the world builder cannot disagree."""
        from persistence import real_digests
        from real_tools import qualification
        for name in ("identity_digest", "calendar_digest", "convention_digest", "profile_digest", "release_digest", "projection_digest"):
            self.assertIs(getattr(qualification, name), getattr(real_digests, name), name)
        for relative in R5_MODULES + ("persistence/real_digests.py",):
            self.assertFalse(any(m == "real_tools" or m.startswith("real_tools.") for m in import_closure(relative[:-3].replace("/", "."))), relative)

    def test_the_rendered_block_has_exactly_the_key_set_the_contract_checks(self):
        for origin, lineage in ((REAL_ORIGIN, real_source_lineage()), (TEST_ORIGIN, None)):
            self.assertEqual(frozenset(cr.render_claim_block(origin, lineage)), cr.BLOCK_KEYS)

    def test_the_service_layer_sits_above_persistence_and_nothing_below_the_engine_imports_it(self):
        """`persistence` must not import the performance engine (tests/product/test_performance_boundaries.py); the world builder and the service
        do call it, so they live in `real_service`, which nothing in `persistence`, `marketdata` or `domain` imports."""
        for sub in ("persistence", "marketdata", "domain", "product_contract"):
            for path in sorted((SRC / sub).rglob("*.py")):
                for node in ast.walk(ast.parse(path.read_text())):
                    names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                             else [node.module or ""] + [a.name for a in node.names] if isinstance(node, ast.ImportFrom) else [])
                    self.assertFalse(any(n == "real_service" or n.startswith("real_service.") for n in names), str(path))

    def test_nothing_in_R5_claims_a_re_proof_of_acknowledgement_loss_for_the_real_branch(self):
        real_tests = (HERE / "test_postgres_real_r5_real.py").read_text()
        self.assertNotIn("_after_commit", real_tests)
        self.assertNotIn("reconcile", real_tests)


if __name__ == "__main__":
    unittest.main()
