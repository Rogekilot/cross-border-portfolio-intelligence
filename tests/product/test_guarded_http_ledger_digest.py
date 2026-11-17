"""The ledger-digest check on the archived-projection read path, and the way it is injected (no PostgreSQL).

`persistence` may not import the engine (`test_performance_boundaries`), so `web_api.guarded_dev` injects
`performance.ledger_view.ledger_digest` into the profile. These tests pin: the refusal and its public outcome, what the
injected callable receives, that the real engine function is what is accepted, and that the launcher wires exactly it.
"""
import dataclasses
import functools
import hashlib
import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from types import MethodType, SimpleNamespace

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from marketdata.canonical import canonical_json  # noqa: E402
from performance.ledger_view import ledger_digest  # noqa: E402
from persistence import guarded_http_store as store_module  # noqa: E402
from persistence.guarded_http_store import (ArchivedWorkspaceProjection, FictionalProfile, build_fictional_profile,  # noqa: E402
    sha)
from persistence.guarded_workspace_context import GuardedWorkspaceError  # noqa: E402
from persistence.web_account_store import AccountStoreError  # noqa: E402
from web_api import guarded_dev  # noqa: E402

KEY = b"F3_digest_test_only_32_byte_key__"
PIN = 3
OWNER, ROOT, OP, REV = (uuid.UUID("00000000-0000-4000-8000-00000000000%d" % i) for i in (1, 2, 3, 4))
CONTEXT = "c" * 64


class Events(tuple):
    """A distinct empty tuple, so identity (not equality) of what the callable receives is observable."""


def profile(digest=ledger_digest):
    return build_fictional_profile(SimpleNamespace(schema="f3_digest"), preview_key=KEY, ledger_digest=digest)


def projection(manifest_digest, events, prof=None, digest_spy=None):
    """An ArchivedWorkspaceProjection whose database reads are stubs that satisfy every earlier binding check."""
    prof = profile() if prof is None else prof
    if digest_spy is not None:
        prof = SimpleNamespace(store=prof.store, world=prof.world, ledger_digest=digest_spy)
    world = prof.world
    snapshot = {"diversification": {"metrics": []}}
    snapshot_json = canonical_json(snapshot)
    issued = json.dumps({"manifest": {"valuation_manifest": {"ledger_digest": manifest_digest}}, "metrics": []}).encode()
    response = json.dumps(snapshot).encode()
    envelope = json.dumps(dict(owner_id=str(OWNER), root_id=str(ROOT), revision_id=str(REV), context_id=CONTEXT,
        issued_sha256=sha(issued), response_sha256=sha(response))).encode()
    facade = SimpleNamespace(profile=prof, _meta=lambda conn, owner, root, rev=None: (OP, REV, None, "CREATE"),
        _snapshot=lambda raw, kind: raw)
    core = SimpleNamespace(_archive=lambda conn, owner, op: (issued, response, envelope, REV, PIN))
    scope = SimpleNamespace(assert_current=lambda conn: None, root_id=ROOT, owner_id=OWNER, context_id=CONTEXT)
    view = ArchivedWorkspaceProjection(facade, core, scope, OWNER)
    reads = []
    def read(conn, ident, pin):
        reads.append((ident, pin))
        return events
    view._events = read
    record = dict(revision_id=REV, ledger_version=PIN, snapshot_json=snapshot_json,
        snapshot_sha256=sha(snapshot_json.encode()), policies=[],
        request=dict(source_sha256=world.input_sha256, calendar_sha256=world.calendar_sha256, as_of=world.as_of.isoformat()))
    return view, record, reads


class ArchivedProjectionDigestTests(unittest.TestCase):
    def test_empty_ledger_digest_is_pinned_so_semantics_drift_fails_here(self):
        self.assertEqual(ledger_digest(Events(), PIN), hashlib.sha256(b"[]").hexdigest())

    def test_a_matching_native_digest_is_accepted(self):
        events = Events()
        view, record, reads = projection(ledger_digest(events, PIN), events)
        item, got = view._item(None, ROOT, record)
        self.assertIs(got, events)
        self.assertEqual(item.snapshot_json, record["snapshot_json"])
        self.assertEqual(reads, [(ROOT, PIN)])

    def test_a_mismatched_native_digest_is_refused_as_503_projection_differs(self):
        for wrong in ("0" * 64, ledger_digest(Events(), PIN + 1) + "x", None, 7):
            events = Events()
            view, record, _ = projection(wrong, events)
            with self.assertRaises(AccountStoreError, msg=repr(wrong)) as ctx:
                view._item(None, ROOT, record)
            self.assertEqual((ctx.exception.status, ctx.exception.code), (503, "F3_ARCHIVE_PROJECTION_DIFFERS"))

    def test_the_mismatch_is_the_digest_check_and_not_an_earlier_binding(self):
        # The same stubs with the matching digest are accepted (test above), so only the digest differs here.
        seen = []
        events = Events()
        view, record, _ = projection("0" * 64, events, digest_spy=lambda e, p: seen.append((e, p)) or "1" * 64)
        with self.assertRaises(AccountStoreError):
            view._item(None, ROOT, record)
        self.assertEqual(len(seen), 1)

    def test_the_injected_callable_receives_the_events_read_for_the_root_then_the_archived_pin(self):
        events, calls = Events(), []
        def spy(*args, **kwargs):
            calls.append((args, kwargs))
            return ledger_digest(*args, **kwargs)
        view, record, reads = projection(ledger_digest(events, PIN), events, digest_spy=spy)
        view._item(None, ROOT, record)
        self.assertEqual(reads, [(ROOT, PIN)])
        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual(kwargs, {})
        self.assertEqual(len(args), 2)
        self.assertIs(args[0], events)
        self.assertEqual(args[1], PIN)


class LedgerDigestInjectionIsFailClosedTests(unittest.TestCase):
    def refused(self, build):
        with self.assertRaises(GuardedWorkspaceError) as ctx:
            build()
        self.assertEqual(ctx.exception.code, "F3_LEDGER_DIGEST_REQUIRED")

    def parts(self):
        p = profile()
        return [getattr(p, f.name) for f in dataclasses.fields(p) if f.name != "ledger_digest"]

    def test_the_real_engine_function_is_accepted_by_every_path(self):
        p = profile()
        self.assertIs(p.ledger_digest, ledger_digest)
        self.assertIs(FictionalProfile(*self.parts(), ledger_digest).ledger_digest, ledger_digest)
        self.assertIs(dataclasses.replace(p, preview_key=KEY + b"x").ledger_digest, ledger_digest)

    def test_missing_none_and_non_callables_are_refused(self):
        self.refused(lambda: build_fictional_profile(SimpleNamespace(schema="f3_digest"), preview_key=KEY))
        for bad in (None, "sha256", 7, b"x", object(), {}):
            self.refused(lambda bad=bad: profile(bad))

    def test_lambda_wrapper_partial_and_method_are_refused(self):
        def wrapper(events, version):
            return ledger_digest(events, version)
        for bad in (lambda events, version: ledger_digest(events, version), wrapper,
                functools.partial(ledger_digest), MethodType(ledger_digest, object()), profile, print):
            self.refused(lambda bad=bad: profile(bad))

    def test_a_forged_name_on_a_foreign_function_is_refused(self):
        def forged(events, version):
            return "0" * 64
        forged.__module__, forged.__qualname__ = "performance.ledger_view", "ledger_digest"
        self.refused(lambda: profile(forged))

    def test_an_equal_to_anything_object_is_refused(self):
        class Anything:
            __module__ = "performance.ledger_view"
            __qualname__ = "ledger_digest"
            def __eq__(self, other):
                return True
            def __hash__(self):
                return 0
            def __call__(self, events, version):
                return "0" * 64
        self.refused(lambda: profile(Anything()))

    def test_direct_construction_and_dataclasses_replace_are_refused(self):
        p = profile()
        self.refused(lambda: FictionalProfile(*self.parts()))
        self.refused(lambda: FictionalProfile(*self.parts(), None))
        self.refused(lambda: FictionalProfile(*self.parts(), lambda events, version: "0" * 64))
        self.refused(lambda: dataclasses.replace(p, ledger_digest=None))
        self.refused(lambda: dataclasses.replace(p, ledger_digest=lambda events, version: "0" * 64))

    def test_persistence_does_not_import_the_engine(self):
        self.assertFalse(hasattr(store_module, "ledger_digest"))


class LauncherWiringTests(unittest.TestCase):
    def test_guarded_dev_injects_exactly_the_engine_function(self):
        self.assertIs(guarded_dev.ledger_digest, ledger_digest)
        context = profile().context_id
        built = guarded_dev.build_profile(SimpleNamespace(schema="f3_digest"), context)
        self.assertIs(built.ledger_digest, ledger_digest)
        self.assertEqual(built.context_id, context)

    def test_build_profile_refuses_a_context_that_differs_from_the_profile_snapshot(self):
        context = profile().context_id
        for wrong in ("0" * 64, "f" * 64, context[:-1] + ("0" if context[-1] != "0" else "1"), ""):
            with self.subTest(context_id=wrong):
                self.assertNotEqual(wrong, context)
                with self.assertRaises(GuardedWorkspaceError) as ctx:
                    guarded_dev.build_profile(SimpleNamespace(schema="f3_digest"), wrong)
                self.assertEqual(ctx.exception.code, "F3_CONTEXT_DIFFERS")
        # The matching context builds, and the profile carries exactly that context.
        built = guarded_dev.build_profile(SimpleNamespace(schema="f3_digest"), context)
        self.assertEqual(built.context_id, context)

    def test_the_launcher_builds_its_profile_only_through_build_profile(self):
        seen = {}
        def fake_build(store, context_id):
            seen["args"] = (store, context_id)
            return "PROFILE"
        config = dict(socket="s", database="d", product_schema="schema", executor_role="r", context_id="c" * 64)
        created = {}
        from unittest.mock import patch
        # create_local_app scrubs PG*/proxy variables from os.environ; restore them so other tests are unaffected.
        with patch.dict(os.environ), patch.object(guarded_dev, "load_config", lambda: config), patch.object(guarded_dev, "executor_dsn", lambda c: "dsn"), \
                patch.object(guarded_dev, "WebAccountStore", lambda dsn, schema: SimpleNamespace(dsn=dsn, schema=schema)), \
                patch.object(guarded_dev, "require_report_installed", lambda store: None), \
                patch.object(guarded_dev, "build_profile", fake_build), \
                patch.object(guarded_dev, "create_app", lambda **kw: created.update(kw) or "APP"):
            self.assertEqual(guarded_dev.create_local_app(), "APP")
        self.assertEqual(seen["args"][1], "c" * 64)
        self.assertEqual(created["guarded_profile"], "PROFILE")

    def test_a_wrong_function_in_the_launcher_is_refused_at_profile_build(self):
        from unittest.mock import patch
        with patch.object(guarded_dev, "ledger_digest", lambda events, version: "0" * 64):
            with self.assertRaises(GuardedWorkspaceError) as ctx:
                guarded_dev.build_profile(SimpleNamespace(schema="f3_digest"), None)
        self.assertEqual(ctx.exception.code, "F3_LEDGER_DIGEST_REQUIRED")


if __name__ == "__main__":
    unittest.main()
