"""F1 R1: the proposal format `finweb.real_proposal/1`, its pure writer and verifier (design 2.3 item 2; T01, FF1-C03, FF1-C05 digests).

Pure tests. R4b's qualification run must produce proposals that pass this verifier; the PG tests publish from these bytes.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

import real_gateway_fixtures as fx  # noqa: E402
from marketdata.canonical import canonical_json  # noqa: E402
from persistence import real_proposal as rp  # noqa: E402
from persistence.real_scope import SCOPES, ResolvedScope, ScopeError, resolve_scope  # noqa: E402


def _proposal(tag="p", scope="SYNTHETIC_TEST", **overrides):
    content = fx.content(tag)
    content.update(overrides)
    return rp.write_proposal(resolve_scope(scope, test_switch=(scope == "TEST_SWITCH")), **content)


def _rewrite(data, mutate, *, refresh_context=False):
    """Edit a proposal as a person with a text editor would, then re-serialise it canonically. With `refresh_context`, the editor
    also recomputes the context id (a self-consistent but different proposal)."""
    document = json.loads(data)
    mutate(document)
    if refresh_context:
        document["context_id"] = hashlib.sha256(canonical_json(document["snapshot"]).encode("utf-8")).hexdigest()
    return canonical_json(document).encode("utf-8")


class WriterTests(unittest.TestCase):
    def test_writer_is_deterministic_and_the_context_is_the_content_hash(self):
        first, second = _proposal("det"), _proposal("det")
        self.assertEqual(first, second)
        document = json.loads(first)
        snapshot_bytes = canonical_json(document["snapshot"]).encode("utf-8")
        self.assertEqual(document["context_id"], hashlib.sha256(snapshot_bytes).hexdigest())
        self.assertEqual(first, canonical_json(document).encode("utf-8"))

    def test_a_proposal_carries_no_rights_expiry_or_decision(self):
        # A proposal file can never carry a lease, so editing one cannot make a publisher publish one.
        data = _proposal("norights")
        self.assertEqual(set(json.loads(data)), {"context_id", "schema", "snapshot"})
        text = data.decode("utf-8")
        for word in ("valid_until", "rights", "expiry", "pd_id", "git_commit", "issuer", "ARCHIVE_READ", "EXECUTE_CREATE"):
            self.assertNotIn(word, text, word)

    def test_every_digest_that_defines_the_context_changes_the_context(self):
        base = json.loads(_proposal("sens"))["context_id"]
        changes = {}
        for key in ("release_id", "release_digest", "projection_digest", "identity_digest", "calendar_digest", "convention_digest",
                    "profile_digest", "f8b_policy_digest"):
            changes[key] = json.loads(_proposal("sens", **{key: fx.sha("other-" + key)}))["context_id"]
        members = fx.content("sens")["members"]
        changes["member"] = json.loads(_proposal("sens", members=members[:2]))["context_id"]
        changes["scope"] = json.loads(_proposal("sens", scope="TEST_SWITCH"))["context_id"]
        for key, value in changes.items():
            self.assertNotEqual(value, base, key)
        self.assertEqual(len(set(changes.values())), len(changes))

    def test_full_registry_and_used_source_digests_differ_when_a_source_is_unused(self):
        used_only = json.loads(_proposal("reg"))["snapshot"]["registry"]
        self.assertEqual(used_only["full_registry_digest"], used_only["used_source_digest"])
        content = fx.content("reg", unused_sources=("syn.unused",))
        both = json.loads(rp.write_proposal(resolve_scope("SYNTHETIC_TEST"), **content))["snapshot"]["registry"]
        self.assertNotEqual(both["full_registry_digest"], both["used_source_digest"])

    def test_writer_derives_the_digests_and_takes_none_as_input(self):
        with self.assertRaises(TypeError):
            rp.write_proposal(resolve_scope("SYNTHETIC_TEST"), full_registry_digest=fx.sha("x"), **fx.content("derive"))

    def test_writer_refuses_malformed_members_and_records(self):
        content = fx.content("bad")
        members = content["members"]
        cases = {
            "duplicate payload": dict(members=[members[0], members[0]]),
            "no members": dict(members=[]),
            "member without a record": dict(source_records=content["source_records"][:2]),
            "duplicate record": dict(source_records=content["source_records"] + content["source_records"][:1]),
            "short hash": dict(release_id="abc"),
            "upper-case hash": dict(projection_digest="A" * 64),
        }
        for name, override in cases.items():
            with self.assertRaises(rp.ProposalError, msg=name) as caught:
                _proposal("bad", **override)
            self.assertEqual(caught.exception.code, "RW_PROPOSAL_SHAPE", name)

    def test_the_builder_and_the_writer_are_not_a_second_door_to_test_switch(self):
        """Technical review R1, M-1: `SCOPES["TEST_SWITCH"]` is a table entry, not a way in. The builder and the writer take a
        `ResolvedScope`, which only `resolve_scope` makes, so a TEST_SWITCH snapshot needs `test_switch=True` at its source. Every
        bare form of the scope is refused with the unresolved-scope code, whatever its flags say."""
        content = fx.content("door")
        definition = SCOPES["TEST_SWITCH"]
        forms = {"the table entry": definition, "its name": "TEST_SWITCH", "a copy with the flag cleared": dataclasses.replace(definition, requires_switch=False),
                 "an ordinary scope's name": "SYNTHETIC_TEST", "an ordinary scope's entry": SCOPES["SYNTHETIC_TEST"], "the REAL entry": SCOPES["REAL"],
                 "a dict": {"name": "TEST_SWITCH"}, "nothing": None}
        for label, form in forms.items():
            for function in (rp.build_snapshot, rp.write_proposal):
                with self.assertRaises(ScopeError, msg="%s via %s" % (label, function.__name__)) as caught:
                    function(form, **content)
                self.assertEqual(caught.exception.code, "RW_SCOPE_UNRESOLVED", label)
        # A resolved scope cannot be made or edited by hand.
        for args in ((definition,), (definition, object()), (definition, None), ("TEST_SWITCH", object())):
            with self.assertRaises(ScopeError, msg=repr(args)) as caught:
                ResolvedScope(*args)
            self.assertEqual(caught.exception.code, "RW_SCOPE_UNRESOLVED")
        resolved = resolve_scope("SYNTHETIC_TEST")
        for attribute in ("definition", "name", "requires_switch"):
            with self.assertRaises(AttributeError, msg=attribute):
                setattr(resolved, attribute, definition if attribute == "definition" else True)
        self.assertIs(resolved.definition, SCOPES["SYNTHETIC_TEST"])
        with self.assertRaises(TypeError):                              # the table itself is read-only
            SCOPES["TEST_SWITCH"] = dataclasses.replace(definition, requires_switch=False)
        # Through the switch it works; the bytes verify; the verified scope (data) cannot be handed back to a builder.
        data = rp.write_proposal(resolve_scope("TEST_SWITCH", test_switch=True), **content)
        verified = rp.verify_proposal(data)
        self.assertEqual(verified.scope.name, "TEST_SWITCH")
        with self.assertRaises(ScopeError) as caught:
            rp.build_snapshot(verified.scope, **content)
        self.assertEqual(caught.exception.code, "RW_SCOPE_UNRESOLVED")

    def test_test_scopes_store_no_terms_check_and_no_real_origin_string(self):
        # Design 4.2: an invented permitting terms check is an invented human attestation; it is never written in a test scope.
        records = fx.content("terms")["source_records"]
        for scope in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            with self.assertRaises(rp.ProposalError) as caught:
                _proposal("terms", scope=scope, source_records=[rp.SourceRecord(r.source_id, r.name, r.upstream_provider,
                          r.independence_group, r.terms_url, {"permits": True}) for r in records])
            self.assertEqual(caught.exception.code, "RW_ORIGIN_MIXED", scope)
            with self.assertRaises(rp.ProposalError) as caught:
                _proposal("marker", scope=scope, source_records=[rp.SourceRecord(r.source_id, "REAL_SOURCE " + r.name, r.upstream_provider,
                          r.independence_group, r.terms_url, None) for r in records])
            self.assertEqual(caught.exception.code, "RW_ORIGIN_MIXED", scope)


class VerifierTests(unittest.TestCase):
    def test_writer_output_verifies_for_every_scope(self):
        for scope in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            data = _proposal("ok-" + scope, scope=scope)
            verified = rp.verify_proposal(data)
            self.assertEqual(verified.scope.name, scope)
            self.assertEqual(verified.member_sources, tuple(sorted(fx.SOURCES)))
            self.assertEqual(verified.snapshot.data, canonical_json(json.loads(data)["snapshot"]).encode("utf-8"))
        # No invented content is ever written or verified under the REAL scope's own labels (PD-0066 decision 8, design 4.2): the
        # REAL branch of the writer and verifier is exercised first by R4b on real inputs. What R1 shows about the REAL scope is
        # the refusal below: a snapshot whose scope field ALONE is REAL (synthetic sources, synthetic labels, no real-origin string)
        # does not verify, because a REAL snapshot must carry the REAL labels.
        for scope in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            data = _proposal("scope-field-" + scope, scope=scope)
            relabelled = _rewrite(data, lambda d: d["snapshot"].update(scope="REAL"), refresh_context=True)
            self.assertNotIn(b"REAL_SOURCE", relabelled)
            with self.assertRaises(rp.ProposalError, msg=scope) as caught:
                rp.verify_proposal(relabelled)
            self.assertEqual(caught.exception.code, "RW_ORIGIN_MISMATCH", scope)

    def test_a_non_canonical_encoding_is_refused(self):
        data = _proposal("canon")
        for name, edited in (("pretty", json.dumps(json.loads(data), indent=2).encode()),
                             ("spaced", json.dumps(json.loads(data)).encode()),
                             ("unsorted", json.dumps(json.loads(data), sort_keys=False, separators=(",", ":")).encode()
                              if list(json.loads(data)) != sorted(json.loads(data)) else None)):
            if edited is None or edited == data:
                continue
            with self.assertRaises(rp.ProposalError, msg=name) as caught:
                rp.verify_proposal(edited)
            self.assertEqual(caught.exception.code, "RW_PROPOSAL_NOT_CANONICAL", name)

    def test_duplicate_keys_floats_and_junk_are_refused(self):
        data = _proposal("junk")
        text = data.decode("utf-8")
        duplicate = text[:-1] + ',"schema":"finweb.real_proposal/1"}'
        with self.assertRaises(rp.ProposalError) as caught:
            rp.verify_proposal(duplicate.encode())
        self.assertEqual(caught.exception.code, "RW_PROPOSAL_NOT_CANONICAL")
        with self.assertRaises(rp.ProposalError) as caught:
            rp.verify_proposal(text.replace('"personal_holdings":false', '"personal_holdings":0.5').encode())
        self.assertEqual(caught.exception.code, "RW_PROPOSAL_SHAPE")
        for junk in (b"", b"{}", b"[]", b"not json", b"\xff\xfe", "x".encode() * 3_000_000, None, "text"):
            with self.assertRaises(rp.ProposalError, msg=repr(junk)[:30]):
                rp.verify_proposal(junk)

    def test_wrong_keys_and_unknown_scope_are_refused(self):
        data = _proposal("keys")
        for name, mutate in (("extra top key", lambda d: d.update(valid_until="2099-01-01")),
                             ("extra snapshot key", lambda d: d["snapshot"].update(rights={})),
                             ("missing snapshot key", lambda d: d["snapshot"].pop("profile_digest")),
                             ("extra member key", lambda d: d["snapshot"]["members"][0].update(note="x")),
                             ("extra record key", lambda d: d["snapshot"]["source_records"][0].update(note="x")),
                             ("wrong schema", lambda d: d.update(schema="finweb.real_proposal/2")),
                             ("unknown scope", lambda d: d["snapshot"].update(scope="TEST_SWITCH2"))):
            with self.assertRaises(rp.ProposalError, msg=name) as caught:
                rp.verify_proposal(_rewrite(data, mutate, refresh_context=True))
            self.assertEqual(caught.exception.code, "RW_PROPOSAL_SHAPE", name)

    def test_origin_labels_must_match_the_scope(self):
        # The verifier compares ALL FOUR origin fields with the scope's own. The probes put other values in, none of them a real
        # label: no document in this test is invented data carrying `synthetic: false` or a real-origin string (decision 8). That
        # the real labels themselves never match a test scope is a truth-table fact about the definitions
        # (`test_real_scope.py`, `labels_match_scope`), not a document.
        data = _proposal("labels", scope="TEST_SWITCH")
        for name, mutate in (("synthetic not true", lambda d: d["snapshot"]["origin"].update(synthetic=0)),
                             ("other market origin", lambda d: d["snapshot"]["origin"].update(market_origin="OTHER_ORIGIN")),
                             ("other ledger origin", lambda d: d["snapshot"]["origin"].update(ledger_origin="OTHER_LEDGER")),
                             ("personal holdings", lambda d: d["snapshot"]["origin"].update(personal_holdings=True)),
                             ("extra label", lambda d: d["snapshot"]["origin"].update(note="x")),
                             ("missing label", lambda d: d["snapshot"]["origin"].pop("synthetic")),
                             ("scope relabelled", lambda d: d["snapshot"].update(scope="REAL"))):
            with self.assertRaises(rp.ProposalError, msg=name) as caught:
                rp.verify_proposal(_rewrite(data, mutate, refresh_context=True))
            self.assertEqual(caught.exception.code, "RW_ORIGIN_MISMATCH", name)

    def test_swapped_registry_digests_are_refused(self):
        content = fx.content("swap", unused_sources=("syn.unused",))
        data = rp.write_proposal(resolve_scope("SYNTHETIC_TEST"), **content)

        def swap(document):
            registry = document["snapshot"]["registry"]
            registry["full_registry_digest"], registry["used_source_digest"] = registry["used_source_digest"], registry["full_registry_digest"]
        with self.assertRaises(rp.ProposalError) as caught:
            rp.verify_proposal(_rewrite(data, swap, refresh_context=True))
        self.assertEqual(caught.exception.code, "RW_PROPOSAL_REGISTRY_DIGEST")

    def test_an_edited_record_with_the_old_digests_is_refused(self):
        data = _proposal("record")
        with self.assertRaises(rp.ProposalError) as caught:
            rp.verify_proposal(_rewrite(data, lambda d: d["snapshot"]["source_records"][0].update(name="Edited"), refresh_context=True))
        self.assertEqual(caught.exception.code, "RW_PROPOSAL_REGISTRY_DIGEST")

    def test_the_context_id_must_be_the_content_hash(self):
        # T01 / FF1-C03: editing the file cannot change what a context id names. Without the id refreshed, the edit is refused;
        # with it refreshed, the edit is a DIFFERENT context, never the old one.
        data = _proposal("hash")
        old = json.loads(data)["context_id"]

        def edit(document):
            document["snapshot"]["members"][0]["payload_sha256"] = fx.sha("edited")
        with self.assertRaises(rp.ProposalError) as caught:
            rp.verify_proposal(_rewrite(data, edit))
        self.assertEqual(caught.exception.code, "RW_PROPOSAL_CONTEXT_DIFFERS")
        refreshed = rp.verify_proposal(_rewrite(data, edit, refresh_context=True))
        self.assertNotEqual(refreshed.snapshot.context_id, old)
        with self.assertRaises(rp.ProposalError) as caught:
            rp.verify_proposal(_rewrite(data, lambda d: d.update(context_id="0" * 64)))
        self.assertEqual(caught.exception.code, "RW_PROPOSAL_CONTEXT_DIFFERS")
        with self.assertRaises(rp.ProposalError) as caught:
            rp.verify_proposal(_rewrite(data, lambda d: d.update(context_id="ABC")))
        self.assertIn(caught.exception.code, ("RW_PROPOSAL_SHAPE", "RW_PROPOSAL_CONTEXT_DIFFERS"))

    def test_verifier_reads_nothing_but_its_argument(self):
        # A proposal is bytes in, a verdict out: no file, environment, clock or registry is consulted (T01).
        source = (Path(rp.__file__)).read_text("utf8")
        for token in ("open(", "Path(", "os.environ", "getenv", "datetime", "time.time", "FileStore", "SOURCES.json", "load_registry", "psycopg"):
            self.assertNotIn(token, source, token)


if __name__ == "__main__":
    unittest.main()
