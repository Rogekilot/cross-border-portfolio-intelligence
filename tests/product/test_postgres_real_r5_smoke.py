"""F1 R5, PostgreSQL: the scoped contract's wire shapes filled from the PRODUCT service's outputs (design 2.4, 7.4), with no route installed.

(The file name is a leftover of the first run of the `SYNTHETIC_TEST` create; the content is the contract wiring. The main session may rename it.)

Each test builds the payload a route would send from what the service returned and the origin it STORED, and checks the contract's rules on it: the
four origin fields are the stored ones, the labels are derived from them, the claim-limit block carries the invented-data mark and no real-source
sentence for a `SYNTHETIC_TEST` root, the list carries no number, and a refusal or an unknown outcome has its own shape. Nothing is served.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from marketdata import claim_render  # noqa: E402
from persistence import real_tails  # noqa: E402
from real_gateway_kit import setUpModule, tearDownModule  # noqa: E402,F401
from real_r5_case import R5Case  # noqa: E402
from web_api import real_scoped_contract as contract  # noqa: E402


class ContractWiringTests(R5Case):
    INSTALL = "r5w"

    def committed(self):
        live, owner = self.fictional_live(), self.new_owner()
        created, body = self.create(live, owner)
        self.assertEqual(type(created).__name__, "Created", created)
        return live, owner, created, body

    def payload_of(self, archive, root, op, *, kind="create"):
        labels = archive.labels
        common = dict(root_id=root, operation_id=op, revision_id=archive.revision_id, ledger_pin=archive.ledger_pin, origin=archive.origin, labels=labels,
                      response_sha256=archive.response_sha256, issued_sha256=archive.issued_sha256, result=json.loads(archive.issued),
                      claim_limits=claim_render.render_claim_block(archive.origin))
        return (contract.committed_payload(replayed=False, **common) if kind == "create"
                else contract.read_payload(created_under_generation=json.loads(archive.envelope)["generation"], **common))

    def test_the_committed_create_and_the_read_are_built_from_the_stored_origin(self):
        """product path, shared tail on SYNTHETIC_TEST: the payloads carry the origin fields read from the stored response, the labels derived from
        them, the invented-data mark and no real-source sentence; the issued document is the stored one."""
        live, owner, created, body = self.committed()
        read = self.service.archive_read(self.conn("executor"), owner=owner, root=created.root_id, operation_id=created.operation_id,
                                         context_id=live.ctx, generation=1)
        for payload in (self.payload_of(created.archive, created.root_id, created.operation_id),
                        self.payload_of(read.value, created.root_id, created.operation_id, kind="read")):
            self.assertEqual(payload["origin"], {"market_origin": "SYNTHETIC_TEST", "ledger_origin": "INVENTED_TEST_LEDGER", "personal_holdings": False, "synthetic": True})
            self.assertEqual(payload["labels"]["origin_kind"], "INVENTED_TEST_DATA")
            self.assertEqual(payload["claim_limits"]["invented_data_mark"], claim_render.INVENTED_DATA_MARK)
            self.assertEqual(payload["claim_limits"]["items"], [])
            self.assertEqual(payload["result"]["manifest"]["synthetic"], True)
            self.assertNotIn("REAL_SOURCE", json.dumps(payload))
            self.assertEqual(payload["issued_sha256"], created.archive.issued_sha256)

    def test_reproduce_the_list_the_refusal_and_the_unknown_outcome_have_their_own_shapes(self):
        """product path, shared tail on SYNTHETIC_TEST: the reproduce payload, the list payload, the public refusal and the unknown payload."""
        live, owner, created, body = self.committed()
        again = self.service.reproduce(self.conn("executor"), owner=owner, root=created.root_id, operation_id=created.operation_id,
                                       context_id=live.ctx, generation=1)
        # TR5-M2: origin and labels come from the Reproduction itself (the archive read in the reproduce's own transaction), NOT from the create
        self.assertEqual(again.value.origin, created.archive.origin)                       # same stored fields, but read in this call
        payload = contract.reproduce_payload(root_id=created.root_id, operation_id=created.operation_id, origin=again.value.origin,
                                             labels=again.value.labels, status=again.value.status, detail=again.value.detail,
                                             issued_sha256=again.value.issued_sha256)
        self.assertEqual((payload["status"], payload["origin"]["synthetic"]), ("REPRODUCED", True))
        self.assertEqual(payload["origin"], again.value.origin)
        listed = self.service.list_roots(self.conn("executor"), owner=owner)
        wire = contract.list_payload(listed.value)
        self.assertEqual([r["root_id"] for r in wire["roots"]], [str(created.root_id)])
        self.assertEqual(wire["roots"][0]["origin"], created.archive.origin)
        refused = self.service.archive_read(self.conn("executor"), owner=self.new_owner(), root=created.root_id, operation_id=created.operation_id,
                                            context_id=live.ctx, generation=1)
        self.assertIsInstance(refused, real_tails.Refused)
        public = contract.refusal_payload(refused)
        self.assertEqual((public["error"]["code"], public["persisted"], public["operation_recorded"]), ("RW_NOT_FOUND", False, False))
        unknown = contract.unknown_payload(created.operation_id)
        self.assertEqual((unknown["state"], unknown["retried"]), ("UNKNOWN", False))

    def test_a_code_the_service_returned_in_this_run_is_public_or_maps_to_the_503_unavailable(self):
        """product path, shared tail on SYNTHETIC_TEST: the codes seen in this run (a refusal inside the transaction, an inventory refusal, a
        missing link, the owner-isolation refusal) each go through the contract's refusal payload; a code outside `ERRORS` is the 503
        `REAL_UNAVAILABLE` and is not reflected. (The exhaustive, derived version is a pure test: `RefusalVocabularyTests`.)"""
        live, owner = self.fictional_live(), self.new_owner()
        seen = {self.service.create(self.executor, owner=owner, body=self.intent(live), generation=1, link=None).code,
                self.service.archive_read(self.conn("executor"), owner=self.new_owner(), root=self.root_of(owner, self.intent(live)),
                                          operation_id=uuid.uuid4(), context_id=live.ctx, generation=1).code}
        self.assertEqual(seen, {"RW_LINK_MISSING", "RW_NOT_FOUND"})
        for code in seen:
            payload = contract.refusal_payload(SimpleNamespace(code=code))
            self.assertEqual(payload["error"]["code"], code if code in contract.ERRORS else "REAL_UNAVAILABLE")
        self.assertNotIn("RW_LINK_MISSING", json.dumps(contract.refusal_payload(SimpleNamespace(code="RW_LINK_MISSING"))))        # not reflected
