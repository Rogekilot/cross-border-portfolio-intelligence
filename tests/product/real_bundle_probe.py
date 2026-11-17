"""The E11 CRAFTED CREATE PROBE of the F1 R3 tests. Not a test module.

It writes a complete create bundle (the S2 root, its first revision, the portfolio, one account and one ledger event) through the
executor role's own connection, the way the R5 create tail will, and seals it with the arguments the SEAL function takes. The bundle
bytes (envelope, issued result, response, question, binding) are built HERE, from the format the SQL checks; the real service does not
exist before R5 and the real branch's service is refused first (design 4.4), so every probe built on this module is marked
"E11 crafted probe, not product evidence". Everything is invented and synthetic; nothing here stores `synthetic = false` for a stored
root, and the one probe that states `synthetic = false` in a RESULT does so to be REFUSED (O4a), against a root that is labelled synthetic.

The probe needs a published context with its provenance candidate registered and bound to it: `ProvCase.live` provides both (the
mandatory link, PD-0059). The probe uses a fresh, unregistered root and a fresh app_user; `admit(..., new_root=True)` registers the
root link exactly as the real create does.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from marketdata.canonical import canonical_json  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402,F401

from real_gateway_kit import begin, commit, rollback  # noqa: E402,F401

AS_OF = "2026-01-05"                              # the date of the integration's inline world (real_service_producers.AS_OF)
CURRENCY = "USD"


def canon(obj):
    return canonical_json(obj).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


@dataclass
class Setup:
    """What a probe needs: the published, bound context and a fresh owner and root."""
    live: object
    owner_id: uuid.UUID
    root_id: uuid.UUID
    scope: str
    ctx: str
    prov: str
    snapshot: dict
    release_files: object = None     # [(file_sha256, source_id)] the crafted release holds; default: the snapshot's members (RR-L4)


@dataclass
class Bundle:
    issued: bytes
    response: bytes
    envelope: bytes
    revision_id: uuid.UUID
    ledger_pin: int
    parts: dict = field(default_factory=dict)


class ProbeMixin:
    """Mixed into a `ProvCase` subclass."""

    # ---- the setup ----------------------------------------------------------------------------------------------------------
    SERVICE_PROJECTION = hashlib.sha256(b"projection of the service world (invented)").hexdigest()

    def probe_setup(self, scope="SYNTHETIC_TEST", *, valid_in=120.0, label="", load_release=True, projection=None, release_id=None):
        """`load_release`: the real branch checks the snapshot's projection digest against `md_release` (disposition note 5.1), so a crafted
        `md_release` row (E11: written by the owner role of the disposable database; nothing else is stored in it) for the service world's
        release id, with the digest the snapshot carries, is written once for a TEST_SWITCH setup. `projection` makes the snapshot carry
        another digest than the stored one."""
        import real_service_producers as producers
        service_release, policy_digest = producers.service_constants()
        # a snapshot that carries the release and the F8B policy digest the services under test issue (the seal's two bindings, design 4.4);
        # `release_id` names another release instead (one the database does not hold)
        live = self.live(scope, valid_in=valid_in, label=label, source_id=producers.unit.SOURCE,
                         content={**self.service_content(release_id or service_release, policy_digest),
                                  "projection_digest": projection or self.SERVICE_PROJECTION})
        if load_release and scope == "TEST_SWITCH":
            with self.owner.transaction():
                self.owner.execute(
                    f"INSERT INTO {self.s}.md_release(release_id,name,convention_set_id,release_content,contains_synthetic,projection_digest) "
                    "VALUES(%s,'crafted service world (invented)','crafted',%s,true,%s) ON CONFLICT DO NOTHING",
                    (service_release, Jsonb({"crafted": "E11 probe, not product evidence"}), self.SERVICE_PROJECTION))
        owner_id, root_id = uuid.uuid4(), uuid.uuid4()
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner_id,))
        return Setup(live, owner_id, root_id, scope, live.ctx, live.cand.context_sha256, live.snap.content,
                     [(m["payload_sha256"], m["source_id"]) for m in live.snap.content["members"]])

    def align_release(self, setup, release_id=None):
        """E11 crafted probe, not product evidence (RR-L4). The real branch compares the snapshot's members with the files the database holds for
        the snapshot's release (`md_release_file` joined to `md_file`: file hash and source id). The service world's release is ONE row shared by
        every setup of the class (its id is what the service issues), but each setup's members differ, so before a bundle is made the owner makes
        the release's file rows those of THIS setup (`setup.release_files`): the table triggers are disabled for this crafted edit only, as in
        `craft_response`. A release the database does not hold is left alone."""
        release_id = release_id or setup.snapshot["release"]["release_id"]
        if setup.scope != "TEST_SWITCH":
            return
        files = list(setup.release_files)
        with self.owner.transaction():
            if self.owner.execute(f"SELECT 1 FROM {self.s}.md_release WHERE release_id=%s", (release_id,)).fetchone() is None:
                return
            for table in ("md_file", "md_release_file"):
                self.owner.execute(f"ALTER TABLE {self.s}.{table} DISABLE TRIGGER USER")
            try:
                for sha256, source_id in files:
                    self.owner.execute(
                        f"INSERT INTO {self.s}.md_file(file_sha256,source_id,data_kind,usage_scope,retrieval_time,declared_adjustment,manifest) "
                        "VALUES(%s,%s,'QUOTE','SYNTHETIC_TEST',now(),'crafted',%s) ON CONFLICT (file_sha256) DO UPDATE SET source_id=EXCLUDED.source_id",
                        (sha256, source_id, Jsonb({"crafted": "E11 probe, not product evidence"})))
                self.owner.execute(f"DELETE FROM {self.s}.md_release_file WHERE release_id=%s", (release_id,))
                for ordinal, (sha256, _source_id) in enumerate(files):
                    self.owner.execute(
                        f"INSERT INTO {self.s}.md_release_file(release_id,file_sha256,ordinal,has_fx_window) VALUES(%s,%s,%s,false)",
                        (release_id, sha256, ordinal))
            finally:
                for table in ("md_file", "md_release_file"):
                    self.owner.execute(f"ALTER TABLE {self.s}.{table} ENABLE TRIGGER USER")

    @staticmethod
    def response_of(setup, synthetic=True, **changes):
        """The gateway's own `response` document (the persisted snapshot): it carries the four origin labels of the scope (disposition note 5.4),
        which the seal compares with the stored root's."""
        from persistence import real_scope
        response = {"portfolio_id": str(setup.root_id), "as_of": AS_OF, "persisted": True, "reporting_currency": CURRENCY, "synthetic": synthetic,
                    "origin": real_scope.SCOPES[setup.scope].origin_fields()}
        response.update(changes)
        return response

    @staticmethod
    def service_content(release_id, policy_digest):
        """The snapshot content the services under test need: their release, their F8B policy digest, and (R4b) their SOURCE REGISTRY. The
        integration's inline world serves one source record; the snapshot carries the same record, so its `used_source_digest` (the engine's
        `source_registry_digest`, computed by the product builder) is the digest the service issues in `manifest.source_registry_digest`
        and the seal's registry binding PASSES for a snapshot built the way R4b builds one (disposition note 5.3)."""
        import real_service_producers as producers
        from persistence.real_proposal import SourceRecord
        source = producers.unit.SOURCE
        return {"release_id": release_id, "f8b_policy_digest": policy_digest,
                "source_records": [SourceRecord(source, "F2 unit", "fictional unit", source, None, None)]}

    def open_create(self, executor, setup, op=None, *, new_root=True):
        """BEGIN on `executor` and admit the EXECUTE_CREATE lease of the probe's root (the real create's first two steps)."""
        op = op or uuid.uuid4()
        begin(executor)
        lease = self.admit(executor, setup.ctx, 1, "EXECUTE_CREATE", setup.owner_id, setup.root_id, op=op, new_root=new_root)
        return op, lease

    # ---- the economic writes, by the executor ----------------------------------------------------------------------------------
    def write_portfolio(self, executor, setup):
        executor.execute(f"INSERT INTO {self.s}.portfolio(portfolio_id,user_id,reporting_currency) VALUES(%s,%s,%s)",
                         (setup.root_id, setup.owner_id, CURRENCY))

    def write_account_and_event(self, executor, setup):
        account = uuid.uuid4()
        executor.execute(f"INSERT INTO {self.s}.account(account_id,portfolio_id,name) VALUES(%s,%s,'invented account')", (account, setup.root_id))
        executor.execute(
            f"INSERT INTO {self.s}.ledger_event(event_id,account_id,event_type,event_date,currency,amount) "
            "VALUES(%s,%s,'OPENING_CASH',DATE '2026-01-02',%s,100)", (uuid.uuid4(), account, CURRENCY))
        return account

    def pin_of(self, executor, setup):
        return executor.execute(f"SELECT max(e.ledger_seq) FROM {self.s}.ledger_event e JOIN {self.s}.account a USING(account_id) "
                                "WHERE a.portfolio_id=%s", (setup.root_id,)).fetchone()[0]

    def write_root_and_revision(self, executor, setup, op, pin, bundle_response, *, command="1" * 64, root_origin=None, name="invented probe root"):
        """The S2 root row and its first revision. `root_origin` overrides the root's four origin fields (a crafted mismatch)."""
        from persistence import real_scope
        origin = root_origin or real_scope.SCOPES[setup.scope].origin_fields()
        text = canonical_json(bundle_response)
        digest = sha(text.encode("utf-8"))
        executor.execute(
            f"INSERT INTO {self.s}.rw_root(portfolio_id,context_id,market_origin,ledger_origin,personal_holdings,synthetic,name,account_label,"
            "opening_label,request_json,snapshot_json,snapshot_sha256,ledger_version,created_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,'invented account','invented opening','{}',%s,%s,%s,now())",
            (setup.root_id, setup.ctx, origin["market_origin"], origin["ledger_origin"], origin["personal_holdings"], origin["synthetic"],
             name, text, digest, pin))
        revision = uuid.uuid4()
        executor.execute(
            f"INSERT INTO {self.s}.rw_revision(revision_id,portfolio_id,parent_revision_id,operation_id,operation,command_sha256,as_of,ledger_version,"
            "selection_version,policies_json,policies_state,snapshot_json,snapshot_sha256,created_at) "
            "VALUES(%s,%s,%s,%s,'CREATE',%s,%s,%s,0,'{}','NOT_STATED',%s,%s,now())",
            (revision, setup.root_id, revision, op, command, AS_OF, pin, text, digest))
        return revision

    # ---- the bundle bytes -----------------------------------------------------------------------------------------------------
    def make_bundle(self, setup, op, revision, pin, *, synthetic=True, split=None, generation=1, edit=None, edit_binding=None, edit_envelope=None,
                    edit_issued=None):
        """The sealed bundle, from the bytes THE SERVICE ISSUES (R3 fix round, H-1): the fictional branch calls the existing integration
        (`issue_local_service`, selector CP5_DIVERSIFICATION: its Result, its question, its binding), the real branch the performance service
        (`ComputationResult`). Only the envelope and the response, which are the gateway's own documents, are built here.

        With no edit the issued bytes are the service's, byte for byte. `synthetic=False` / `split=...` and `edit(parts)` change the PARSED
        documents (parts: response, issued, question, binding) and then re-derive what the service derives from them (the manifest id, the
        result digest, and for the fictional branch the binding), so a probe isolates one predicate; `edit_binding` and `edit_envelope` change
        those two documents last, after the derivations."""
        import json
        import real_service_producers as producers
        fictional = setup.scope == "SYNTHETIC_TEST"
        self.align_release(setup)                                             # (real branch: the release's files are this setup's; RR-L4)
        ids = dict(owner=setup.owner_id, root=setup.root_id, revision=revision, operation=op, pin=pin, generation=generation)
        response = self.response_of(setup, synthetic)
        if fictional:
            produced = producers.issue_fictional(**ids)
            issued_bytes, question_bytes, binding_bytes = produced.issued_bytes, produced.question_bytes, produced.binding_bytes
            question, binding = json.loads(question_bytes), json.loads(binding_bytes)
        else:
            issued_bytes, question, binding = producers.issue_real_refusal(**ids), None, None
        issued = json.loads(issued_bytes)
        assert canon(issued) == issued_bytes                                 # the service's bytes are the canonical form the SQL compares
        parts = {"response": response, "issued": issued, "question": question, "binding": binding, "revision": revision}
        changed = []

        def flags(value):
            manifest = issued["manifest"]
            manifest["synthetic"] = value
            if isinstance(manifest.get("valuation_manifest"), dict):
                manifest["valuation_manifest"]["synthetic"] = value
            for metric in issued["metrics"]:
                if "synthetic" in metric:
                    metric["synthetic"] = value

        if synthetic is not True:
            flags(synthetic)
            changed.append("synthetic")
        if split is not None:
            (issued["manifest"].get("valuation_manifest") or issued["manifest"])["split_detection"] = split
            changed.append("split")
        if edit is not None:
            edit(parts)
            changed.append("edit")
        response, issued, question, binding = parts["response"], parts["issued"], parts["question"], parts["binding"]
        if changed:                                                           # re-derive what the service derives from the documents
            manifest_id = sha(canon(issued["manifest"]))
            issued["manifest_id"] = manifest_id
            keys = ("metrics", "clusters", "exposure_decompositions")
            if fictional and all(k in issued for k in keys):
                issued["result_digest"] = sha(canon({k: issued[k] for k in keys}))
            elif not fictional and "metrics" in issued:
                issued["result_digest"] = sha(canon(issued["metrics"]))                 # else: the shape is what the probe breaks
            issued_bytes = canon(issued)
        if edit_issued is not None:       # a change made AFTER the derivations: the issued digests are then what the probe says, and the
            edit_issued(issued)           # envelope and the binding are built to agree with them, so only the issued document itself is wrong
            issued_bytes = canon(issued)
            changed.append("late")
        manifest_id, result_digest = issued["manifest_id"], issued["result_digest"]
        response_bytes = canon(response)
        envelope = {"schema": "finweb.fictional.issued_envelope/1" if fictional else "finweb.real.issued_envelope/1", "scope": setup.scope,
                    "synthetic": synthetic, "owner_id": str(setup.owner_id), "root_id": str(setup.root_id), "operation_id": str(op),
                    "revision_id": str(revision), "ledger_pin": pin, "context_id": setup.ctx, "generation": generation, "issued_sha256": sha(issued_bytes),
                    "response_sha256": sha(response_bytes), "manifest_id": manifest_id, "result_digest": result_digest}
        if fictional:
            question_bytes = canon(question)
            if changed:                                                       # the binding names the issued documents' digests and fields
                vm, m = issued["manifest"]["valuation_manifest"], issued["manifest"]
                binding = dict(binding, question=question, question_sha256=sha(question_bytes), manifest_id=manifest_id, result_digest=result_digest,
                               issued_sha256=sha(issued_bytes), release_id=vm.get("release_id"),         # (the integration's binding states synthetic = true, always)
                               source_registry_digest=vm.get("source_registry_digest"), consumed_identity_digest=m.get("identity_digest"),
                               f8b_policy=vm.get("detection_policy"))
                parts["binding"] = binding
            if edit_binding is not None:
                edit_binding(binding)
            binding_bytes = canon(binding)
            envelope.update(question_sha256=sha(question_bytes), binding_sha256=sha(binding_bytes), question_hex=question_bytes.hex(),
                            binding_hex=binding_bytes.hex(), selector="CP5_DIVERSIFICATION", family="CP5_DIVERSIFICATION", engine_id="diversification/cp5-0.2")
        if edit_envelope is not None:
            edit_envelope(envelope)
        parts["envelope"] = envelope
        parts["service_issued_bytes"] = issued_bytes
        return Bundle(issued_bytes, response_bytes, canon(envelope), revision, pin, parts)

    def seal(self, executor, bundle, prov):
        return executor.execute(f"SELECT {self.s}.rw_seal(%s,%s,%s,%s,%s)", (bundle.parts["revision"], bundle.issued, bundle.response, bundle.envelope, prov))

    # ---- one whole create -----------------------------------------------------------------------------------------------------
    def write_all_and_bundle(self, executor, setup, op, *, synthetic=True, split=None, root_origin=None, edit=None,
                             response_for_root=None, name="invented probe root", edit_binding=None, edit_envelope=None, edit_issued=None):
        """Inside the open create transaction: portfolio, account, ledger event, root, revision; returns the bundle ready to seal."""
        self.write_portfolio(executor, setup)
        self.write_account_and_event(executor, setup)
        pin = self.pin_of(executor, setup)
        response = response_for_root or self.response_of(setup, synthetic)
        revision = self.write_root_and_revision(executor, setup, op, pin, response, root_origin=root_origin, name=name)
        bundle = self.make_bundle(setup, op, revision, pin, synthetic=synthetic, split=split, edit=edit,
                                  edit_binding=edit_binding, edit_envelope=edit_envelope, edit_issued=edit_issued)
        bundle.parts["revision"] = revision
        return bundle

    def create_and_commit(self, executor, setup, op=None, **kw):
        """The accepted path of the probe, on the executor connection: admit, write, seal, COMMIT. Returns (op, bundle)."""
        op = op or uuid.uuid4()
        try:
            self.open_create(executor, setup, op)
            bundle = self.write_all_and_bundle(executor, setup, op, **kw)
            self.seal(executor, bundle, setup.prov)
            commit(executor)
        finally:
            rollback(executor)
        return op, bundle
