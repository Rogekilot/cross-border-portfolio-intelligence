"""Base case of the F1 R2 registry PostgreSQL tests. Not a test module.

It sits on the R1 kit (`real_gateway_kit`): one disposable database, installs made by the PRODUCT installer (kind TEST) and, for the
install-kind cases, the kit's E11 crafted `kind="REAL"` install. Everything stored is invented; a candidate of a test scope carries
synthetic sources and no attestation; nothing here marks invented data `synthetic = false` or stores a permitting terms check.
"""
from __future__ import annotations

from collections import namedtuple
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402

import real_gateway_fixtures as fx  # noqa: E402
from persistence import real_provenance_store as provstore, real_scope  # noqa: E402
from persistence.real_proposal import Member  # noqa: E402
from persistence.real_provenance import ProvenanceError  # noqa: E402
from persistence.real_scope import resolve_scope  # noqa: E402
from real_gateway_kit import GatewayCase, begin, commit, rollback  # noqa: E402,F401
from real_provenance_fixtures import PAYLOAD, SOURCE_ID, candidate, encode, h  # noqa: E402

Live = namedtuple("Live", "cand snap ctx owner_id root_id valid")


def scope_of(name):
    return resolve_scope(name, test_switch=(name == "TEST_SWITCH"))


class ProvCase(GatewayCase):
    """A case with the loader's connection and the registry store on it."""
    INSTALL = "prov"

    def setUp(self):
        super().setUp()
        self.loader = self.conn("loader") if self.LOADER_LOGIN else None
        self.registry = (provstore.RealProvenanceStore(self.loader, self.s, loader_role=self.inst.roles["loader"])
                         if self.loader is not None else None)

    # ---- the registry --------------------------------------------------------------------------------------------------
    def scope_name(self, cand):
        return cand.context()["scope"]

    def request(self, op, cand):
        """The registration request, constructed here from the format (not by the product encoder)."""
        b = cand.bundle
        return encode(dict(schema="finweb.provenance_registration/1", scope=cand.context()["scope"], operation_id=str(op),
                           context_sha256=h(b.context_bytes), payload_sha256s=[k for k, _ in b.payloads],
                           manifest_sha256s=[k for k, _ in b.manifests], envelope_sha256s=[k for k, _ in b.envelopes],
                           witness_sha256s=[k for k, _ in b.witnesses]))

    def save(self, cand, op=None, *, registry=None, scope=None):
        """Register through the product store. Returns (operation id, result)."""
        op = op or uuid.uuid4()
        value = (registry or self.registry).register(scope or scope_of(self.scope_name(cand)), op, cand.bundle, **cand.args())
        return op, value

    def load(self, cand, *, registry=None, scope=None):
        return (registry or self.registry).load_context(scope or scope_of(self.scope_name(cand)), cand.context_sha256,
                                                        expected_members=cand.members, witnesses=cand.witnesses)

    def recover(self, op, cand, *, registry=None):
        return (registry or self.registry).reconcile(scope_of(self.scope_name(cand)), op, expected_request_sha256=h(self.request(op, cand)),
                                                     expected_context_sha256=cand.context_sha256, expected_members=cand.members,
                                                     witnesses=cand.witnesses)

    @staticmethod
    def arrays(cand):
        b = cand.bundle
        return [[raw for _, raw in values] for values in (b.payloads, b.manifests, b.envelopes, b.witnesses)]

    def put_sql(self, conn, cand, op=None, *, request=None):
        """A DIRECT call of the registry's put function (the loader can call it with any bytes)."""
        op = op or uuid.uuid4()
        request = request if request is not None else self.request(op, cand)
        return conn.execute(f"SELECT * FROM {self.s}.rwp_put_context(%s,%s,%s,%s,%s,%s,%s)", (op, request, cand.bundle.context_bytes, *self.arrays(cand))).fetchone()

    def get_sql(self, conn, context_sha=None, op=None):
        return conn.execute(f"SELECT * FROM {self.s}.rwp_get_context(%s,%s)", (context_sha, op)).fetchone()

    def rows(self, *, native=False):
        """Every row of the registry's tables (or of every OTHER table of the schema) as JSON, read by the trusted owner connection."""
        names = [r[0] for r in self.owner.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind='r' "
            "AND (left(c.relname,4)<>'rwp_')=%s ORDER BY c.relname", (self.s, native)).fetchall()]
        result = {}
        for name in names:
            result[name] = self.owner.execute(f"SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM {self.s}.{name} t").fetchone()[0]
        return result

    # ---- a snapshot for a candidate and a published, bound, leased context ---------------------------------------------
    def content_for(self, cand, label="", content=None):
        source_id = cand.context()["source_records"][0]["source_id"]
        result = fx.content(self.tag(label), sources=(source_id,))
        result["members"] = [Member(m.payload_sha256, m.manifest_sha256, source_id, None, "syn.adapter", "1") for m in cand.members]
        result.update(content or {})
        return result

    def snapshot_for(self, cand, scope_name, label="", content=None):
        """A snapshot from the PRODUCT factory whose members are the candidate's payloads and manifests."""
        return real_scope.make_snapshot(self.factory, self.s, scope_name, test_switch=(scope_name == "TEST_SWITCH"),
                                        **self.content_for(cand, label, content))

    def live(self, scope_name="TEST_SWITCH", *, valid_in=120.0, v1=False, label="", acquisitions=(1,), content=None, source_id=SOURCE_ID):
        """Publish a snapshot of the candidate's members through the product tool, register the candidate bound to the published
        context (AFTER the publish, as the loader's last use is step (4a)), and craft the root. Returns a `Live`. `content` overrides
        fields of the snapshot's content (for example the release id and the F8B policy digest the service under test will issue).
        `source_id` is the invented candidate's source (R4b: the seal probe uses the id of the service world's source, so that the
        snapshot's registry digest can equal the one the service issues)."""
        salt = self.tag(label)
        payload = PAYLOAD + salt.encode()
        unbound = candidate(payload, acquisitions, scope=scope_name, v1=v1, salt=salt, source_id=source_id)
        snap = self.snapshot_for(unbound, scope_name, label, content=content)
        source_id = unbound.context()["source_records"][0]["source_id"]
        _snap, valid, _result = self.publish(snap, valid_in=valid_in, evidence=fx.hg4_shape(self.bound(), sources=(source_id,)))
        cand = candidate(payload, acquisitions, scope=scope_name, v1=v1, salt=salt, financial_context=snap.context_id, source_id=source_id)
        _op, saved = self.save(cand)
        self.assertIsInstance(saved, provstore.CommittedRegistration)
        owner_id, root_id = self.craft_root(snap.context_id)
        return Live(cand, snap, snap.context_id, owner_id, root_id, valid)

    def guarded(self, conn, lease, live, **kw):
        return provstore.load_guarded(conn, self.s, self.inst.roles["executor"], lease, live.cand.context_sha256,
                                      expected_members=live.cand.members, witnesses=live.cand.witnesses, **kw)

    def error_of(self, fn):
        """The ProvenanceError raised by `fn()` (fails if none is)."""
        with self.assertRaises(ProvenanceError) as caught:
            fn()
        return caught.exception

    def database_code(self, fn, code=None):
        """The primary message of the RaiseException `fn()` raises (the gateway's `RW_*` code), checked against `code` when given."""
        with self.assertRaises(psycopg.errors.RaiseException) as caught:
            fn()
        primary = (caught.exception.diag.message_primary or str(caught.exception)).splitlines()[0]
        if code is not None:
            self.assertEqual(primary, code)
        return caught.exception

    @staticmethod
    def detail_codes(error):
        return (error.diag.message_detail or "").split(",")
