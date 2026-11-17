"""F1 R4b, PostgreSQL: the qualification run's load, candidates and publish on a disposable TEST install (design 7.1, R4b row).

All data is invented (`TEST_SWITCH`, synthetic sources, no network). The chain is the one R8 will run on real files, on an invented release:

  qualify (reads a store, writes a proposal)  ->  the LOADER role projects the release (`real_loader.load_release`, `count_rows=False`)
  ->  the loader registers the UNBOUND candidate  ->  the publisher publishes the proposal bytes  ->  the loader registers the BOUND candidate.

What the tests prove against the database, with expected values read FROM the database rather than from the run's own output:
  * the snapshot's `projection_digest` is the one `md_release` holds, and its `release_digest` is the digest of the stored `release_content`;
  * the snapshot's members are exactly `md_release_file` joined to `md_file` (file hash, source id): the seal's `RW_REAL_MEMBERS_DIFFER` comparison,
    run here with the gateway's own SQL expression on the PUBLISHED snapshot row;
  * `registry.used_source_digest` equals the engine's `registry_digest_of` the port that `read_release` builds from those rows (the value a
    service puts in `manifest.source_registry_digest`, the seal's `RW_REAL_REGISTRY_DIFFERS` comparison);
  * a proposal edit changes nothing in the database or the store.

An install is shared by the tests of a class, and a release is written once, so each class holds ONE test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import marketdata_exit_kit as x  # noqa: E402
import pg_market_kit as pk  # noqa: E402
import real_gateway_fixtures as fx  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from performance.engine import registry_digest_of  # noqa: E402
from persistence import market_data_store as mds, real_proposal as rp, real_provenance_store as provstore  # noqa: E402
from persistence.real_scope import resolve_scope  # noqa: E402
from real_gateway_kit import KIT, setUpModule, tearDownModule  # noqa: E402,F401
from real_tools import candidates as cand, qualification as q  # noqa: E402
from test_postgres_real_loader import MD_TABLES, LoaderCase  # noqa: E402
from test_real_qualification import run, sha, tree_state  # noqa: E402

TEST_SWITCH = resolve_scope("TEST_SWITCH", test_switch=True)
MEMBERS_SQL = ("SELECT (SELECT COALESCE(jsonb_agg(jsonb_build_array(f.file_sha256,f.source_id) ORDER BY f.file_sha256,f.source_id),'[]'::jsonb) "
               "FROM {s}.md_release_file rf JOIN {s}.md_file f ON f.file_sha256=rf.file_sha256 WHERE rf.release_id={release}) "
               "IS NOT DISTINCT FROM "
               "(SELECT COALESCE(jsonb_agg(jsonb_build_array(x.value->>'payload_sha256',x.value->>'source_id') ORDER BY x.value->>'payload_sha256',x.value->>'source_id'),'[]'::jsonb) "
               "FROM jsonb_array_elements(snap->'members') x) "
               "FROM (SELECT convert_from(snapshot,'UTF8')::jsonb AS snap FROM {s}.rw_snapshot WHERE context_id=%s) s")   # the text of the seal's comparison


class QualifiedChainCase(LoaderCase):
    """An install of its own per subclass (the tests write a release). The loader's connection sets its own search path. The identity rows the
    observation tables reference are seeded by the OWNER role, once per install (E11; the real seed step is an owner-run step of R6's plan)."""

    def setUp(self):
        super().setUp()
        if self.count("listing") == 0:
            pk.insert_identity(self.owner, x.identity())
        self.loader_session = self.conn("loader")
        self.loader_session.execute(f'SET search_path TO "{self.s}", pg_temp')
        self.world = x.build_world("mock")
        self.addCleanup(self.world.close)
        self.ident = x.identity()                                  # the ids the owner seeded above (deterministic)
        self.store = FileStore(self.world.root)
        self.result = run(self.world, resolver=self.ident)
        self.snapshot = json.loads(self.result.proposal)["snapshot"]
        self.release_id = self.snapshot["release"]["release_id"]
        self.member_sources = sorted({m["source_id"] for m in self.snapshot["members"]})

    def load(self):
        return q.load_qualified(self.loader_session, self.result, exchange_of=self.ident.exchange_mic)

    def provenance(self):
        return provstore.RealProvenanceStore(self.conn("loader"), self.s, loader_role=self.inst.roles["loader"])

    def register(self, financial_context=None):
        built = cand.build_candidate(TEST_SWITCH, self.store, self.result, financial_context=financial_context)
        saved = cand.register_candidate(self.provenance(), TEST_SWITCH, built)
        self.assertIsInstance(saved, provstore.CommittedRegistration)
        return built, saved

    def publish_proposal(self, data=None):
        # `valid_until` and the evidence are computed ONCE per test (they come from `db_now()` truncated to the second) and reused, so that a second publish of the same
        # bytes sends identical input even when the two calls straddle a second boundary; `rw_publish` returns the original only for identical rights, bound and basis.
        if getattr(self, "_publish_inputs", None) is None:
            self._publish_inputs = (self.bound(120), fx.hg4_shape(self.bound(), sources=tuple(self.member_sources)))
        valid_until, evidence = self._publish_inputs
        return self.tool().publish(data or self.result.proposal, rights=fx.ALL_RIGHTS, valid_until=valid_until, actor=fx.ACTOR, ref=fx.REF, evidence=evidence)

    def members_comparison(self, release=None):
        sql = MEMBERS_SQL.format(s=self.s, release="snap->'release'->>'release_id'" if release is None else "'%s'" % release)
        return self.owner.execute(sql, (self.result.context_id,)).fetchone()[0]


class LoadAgainstTheDatabaseTests(QualifiedChainCase):
    INSTALL = "qualload"

    def test_the_loader_projects_the_qualified_release_and_the_database_agrees_with_the_proposal(self):
        self.assertEqual({t: self.count(t) for t in MD_TABLES}, {t: 0 for t in MD_TABLES})
        self.assertEqual({t: self.count(t) for t in ("rw_snapshot", "rw_history", "rw_head")}, {"rw_snapshot": 0, "rw_history": 0, "rw_head": 0})  # qualifying wrote nothing
        loaded = self.load()
        self.assertTrue(loaded.created)
        self.assertEqual(loaded.row_counts, ())                                                  # count_rows=False: the loader reads nothing back
        # the projection digest and the release document
        (stored_digest, content), = self.owner.execute(f"SELECT projection_digest,release_content FROM {self.s}.md_release WHERE release_id=%s",
                                                       (self.release_id,)).fetchall()
        self.assertEqual(stored_digest, self.snapshot["projection_digest"])                      # RW_REAL_PROJECTION_DIFFERS would pass
        self.assertEqual(loaded.projection_digest, stored_digest)
        self.assertEqual(sha(canonical_json(content).encode("utf-8")), self.snapshot["release"]["release_digest"])
        self.assertEqual(content["release_id"], self.release_id)
        # the members are the release's files, read from the database (every data kind, calendars and FX included)
        pairs = [tuple(r) for r in self.owner.execute(
            f"SELECT f.file_sha256,f.source_id FROM {self.s}.md_release_file rf JOIN {self.s}.md_file f ON f.file_sha256=rf.file_sha256 "
            "WHERE rf.release_id=%s ORDER BY 1,2", (self.release_id,)).fetchall()]
        self.assertEqual(pairs, sorted((m["payload_sha256"], m["source_id"]) for m in self.snapshot["members"]))
        self.assertEqual(len(pairs), len(self.world.release.files))
        # the used-source digest is the engine's digest of the port built from those rows
        owner = self.conn("owner")
        owner.execute(f'SET search_path TO "{self.s}", pg_temp')
        port = mds.read_release(owner, self.release_id, self.ident.exchange_mic, registry=self.store.load_registry())
        self.assertEqual(registry_digest_of(port), self.snapshot["registry"]["used_source_digest"])    # what a service puts in manifest.source_registry_digest
        self.assertEqual(port.projection_digest(), self.snapshot["projection_digest"])
        # loading again is idempotent
        counts = {t: self.count(t) for t in MD_TABLES}
        again = self.load()
        self.assertFalse(again.created)
        self.assertEqual({t: self.count(t) for t in MD_TABLES}, counts)


class ChainTests(QualifiedChainCase):
    INSTALL = "qualchain"

    def test_the_chain_loads_registers_publishes_and_binds(self):
        self.load()
        unbound, saved = self.register()
        again = cand.register_candidate(self.provenance(), TEST_SWITCH, unbound)               # the same operation id: reconciles, never duplicates
        self.assertIsInstance(again, provstore.CommittedRegistration)
        self.assertEqual(again.response_bytes, saved.response_bytes)
        published = self.publish_proposal()
        self.assertEqual((published.status, published.outcome), (0, "PUBLISHED"), published.text)
        self.assertEqual(published.data["context_id"], self.result.context_id)
        stored, = self.owner.execute(f"SELECT snapshot FROM {self.s}.rw_snapshot WHERE context_id=%s", (self.result.context_id,)).fetchone()
        self.assertEqual(bytes(stored), canonical_json(self.snapshot).encode("utf-8"))
        self.assertEqual(rp.verify_proposal(self.result.proposal).snapshot.data, bytes(stored))     # the verified bytes are what the database holds
        # the seal's members comparison, on the published row: passes; control: against a release the database does not hold it differs
        self.assertTrue(self.members_comparison())
        self.assertFalse(self.members_comparison("0" * 64))
        # the bound candidate is registered after the publish, and reads back with the published context
        bound, _saved = self.register(financial_context=self.result.context_id)
        loaded = self.provenance().load_context(TEST_SWITCH, bound.context_sha256, expected_members=bound.members, witnesses=bound.witnesses)
        self.assertEqual(loaded.financial_context_sha256, self.result.context_id)
        self.assertEqual(sorted(k for k, _ in loaded.bundle.payloads), sorted(self.world.release.files))
        # publishing the same bytes again is the same publish
        self.assertEqual(self.publish_proposal().outcome, "ALREADY_PUBLISHED")
        self.assertEqual(self.count("rw_snapshot", "context_id=%s", (self.result.context_id,)), 1)
        # the test scope needed no sidecar: O5 is bypassed and no member holds the digest of one
        self.assertTrue(self.result.o5_bypassed)
        self.assertTrue(all(m["acquisition_record_sha256"] is None for m in self.snapshot["members"]))


class ProposalEditTests(QualifiedChainCase):
    INSTALL = "qualedit"

    def test_an_edited_proposal_changes_nothing_in_the_database_and_the_store_is_untouched(self):
        self.load()
        self.register()
        document = json.loads(self.result.proposal)
        document["snapshot"]["registry"]["used_source_digest"] = "0" * 64
        tables = ("rw_snapshot", "rw_history", "rw_head", "rw_lease", "rwp_context", "rwp_registration")
        before = {t: self.count(t) for t in tables + MD_TABLES}
        files_before = tree_state(self.world.root)
        outcome = self.publish_proposal(canonical_json(document).encode("utf-8"))
        self.assertEqual(outcome.status, 2)
        self.assertEqual(outcome.data["code"], "RW_PROPOSAL_REGISTRY_DIGEST")
        self.assertEqual({t: self.count(t) for t in tables + MD_TABLES}, before)
        self.assertEqual(tree_state(self.world.root), files_before)


class LoaderGateTests(QualifiedChainCase):
    INSTALL = "qualgate"

    def test_the_loader_entry_refuses_without_the_identitys_lookup_and_writes_nothing(self):
        """`real_loader.load_release` requires the identity's exchange lookup, so a load never skips the listing-level admission gate; without
        it nothing is sent and the tables stay empty. (The refusal of a US-labelled CN reading is pinned in test_postgres_real_loader.)"""
        from persistence import real_loader
        with self.assertRaises(real_loader.RealLoaderError):
            q.load_qualified(self.loader_session, self.result, exchange_of=None)
        self.assertEqual({t: self.count(t) for t in MD_TABLES}, {t: 0 for t in MD_TABLES})


if __name__ == "__main__":
    import unittest
    unittest.main()
