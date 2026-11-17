"""F1 R1: the scope core (design 4.2): scopes, origin labels, the reviewed test switch, the install-kind guard, the factory.

Pure tests: the factory's database read is answered by a scripted connection, so no PostgreSQL is needed. The same factory and
guard are exercised against a real database in `test_postgres_real_gateway_core.py`.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE))

import real_gateway_fixtures as fx  # noqa: E402
from persistence import real_proposal, real_scope  # noqa: E402
from persistence.real_scope import (SCOPES, ResolvedScope, ScopeError, check_install_kind, labels_match_scope, make_snapshot,  # noqa: E402
                                    require_resolved, resolve_scope, scope_by_snapshot_field)

SRC = HERE.parents[1] / "src"


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


class _KindConnection:
    """Answers `SELECT * FROM <schema>.rw_install_info()` with a scripted row and counts every statement it receives."""

    def __init__(self, row):
        self.row, self.statements = row, []

    def execute(self, query, params=()):
        self.statements.append(query.as_string())
        return _Cursor([self.row] if self.row is not None else [])


class ScopeDefinitionTests(unittest.TestCase):
    def test_three_scopes_pair_a_branch_with_an_origin_axis(self):
        self.assertEqual({k: (s.branch, s.origin_axis, s.install_kind) for k, s in SCOPES.items()},
                         {"SYNTHETIC_TEST": ("FICTIONAL", "SYNTHETIC", "TEST"), "TEST_SWITCH": ("REAL", "SYNTHETIC", "TEST"),
                          "REAL": ("REAL", "REAL", "REAL")})

    def test_labels_follow_the_axis_not_the_branch(self):
        # I1, I3 (design 4.2): TEST_SWITCH runs the real branch and carries synthetic labels throughout.
        for name in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            fields = SCOPES[name].origin_fields()
            self.assertEqual(fields, {"market_origin": "SYNTHETIC_TEST", "ledger_origin": "INVENTED_TEST_LEDGER",
                                      "personal_holdings": False, "synthetic": True}, name)
            self.assertNotIn("REAL_SOURCE", str(fields), name)
        self.assertEqual(SCOPES["REAL"].origin_fields()["market_origin"], "REAL_SOURCE")
        self.assertIs(SCOPES["REAL"].origin_fields()["synthetic"], False)
        self.assertIs(SCOPES["REAL"].origin_fields()["personal_holdings"], False)

    def test_invented_data_is_never_marked_synthetic_false(self):
        # Design 4.2 rule: the first `synthetic = false` record is reserved for the real run.
        for name in ("SYNTHETIC_TEST", "TEST_SWITCH"):
            self.assertIs(SCOPES[name].synthetic, True)
            self.assertIs(SCOPES[name].origin_fields()["synthetic"], True)

    def test_label_check_requires_exactly_the_scope_labels(self):
        test_scope = SCOPES["TEST_SWITCH"]
        self.assertTrue(labels_match_scope(test_scope, test_scope.origin_fields()))
        self.assertFalse(labels_match_scope(test_scope, SCOPES["REAL"].origin_fields()))
        self.assertFalse(labels_match_scope(test_scope, dict(test_scope.origin_fields(), synthetic=False)))
        self.assertFalse(labels_match_scope(test_scope, None))

    def test_scope_by_snapshot_field_never_grants_the_switch(self):
        self.assertIs(scope_by_snapshot_field("TEST_SWITCH"), SCOPES["TEST_SWITCH"])
        for bad in ("test_switch", "", None, 3):
            with self.assertRaises(ScopeError) as caught:
                scope_by_snapshot_field(bad)
            self.assertEqual(caught.exception.code, "RW_SCOPE_UNKNOWN")


class TestSwitchTests(unittest.TestCase):
    """THE TEST SWITCH is a separate review item (real_scope.py, section 'THE TEST SWITCH')."""

    def test_the_switch_is_the_only_door_to_test_switch(self):
        with self.assertRaises(ScopeError) as caught:
            resolve_scope("TEST_SWITCH")
        self.assertEqual(caught.exception.code, "RW_SWITCH_REQUIRED")
        with self.assertRaises(ScopeError) as caught:
            resolve_scope("TEST_SWITCH", test_switch=False)
        self.assertEqual(caught.exception.code, "RW_SWITCH_REQUIRED")
        resolved = resolve_scope("TEST_SWITCH", test_switch=True)
        self.assertIs(type(resolved), ResolvedScope)
        self.assertIs(resolved.definition, SCOPES["TEST_SWITCH"])
        self.assertIs(require_resolved(resolved), SCOPES["TEST_SWITCH"])

    def test_the_switch_is_not_a_general_relaxation(self):
        for name in ("SYNTHETIC_TEST", "REAL"):
            with self.assertRaises(ScopeError) as caught:
                resolve_scope(name, test_switch=True)
            self.assertEqual(caught.exception.code, "RW_SWITCH_NOT_APPLICABLE", name)
            self.assertIs(resolve_scope(name).definition, SCOPES[name])

    def test_the_switch_is_a_plain_bool_and_keyword_only(self):
        for bad in (1, 0, "True", "1", None, [], object()):
            with self.assertRaises(ScopeError) as caught:
                resolve_scope("TEST_SWITCH", test_switch=bad)
            self.assertEqual(caught.exception.code, "RW_SHAPE", repr(bad))
        with self.assertRaises(TypeError):
            resolve_scope("TEST_SWITCH", True)

    def test_unknown_scope_names_are_refused(self):
        for bad in ("test_switch", "REAL ", "", None, 5):
            with self.assertRaises(ScopeError) as caught:
                resolve_scope(bad)
            self.assertEqual(caught.exception.code, "RW_SCOPE_UNKNOWN", repr(bad))

    def test_no_environment_command_line_or_request_reaches_the_switch(self):
        module = (SRC / "persistence" / "real_scope.py").read_text("utf8")
        code = "\n".join(line for line in module.splitlines() if not line.lstrip().startswith("#"))
        tree = ast.parse(module)
        imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
        imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        self.assertFalse(imported & {"os", "sys", "argparse", "environ", "http", "flask", "fastapi", "starlette", "web_api"}, imported)
        for token in ("os.environ", "getenv", "sys.argv", "argparse", "import os", "import sys"):
            self.assertNotIn(token, code, token)

    def test_no_product_code_outside_the_scope_module_passes_the_switch(self):
        # R7 extends this to the launcher module; today nothing in src/ may pass the keyword at a call site.
        offenders = []
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text("utf8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                for keyword in node.keywords:
                    if keyword.arg != "test_switch":
                        continue
                    # The scope module forwards its own caller's argument (a name); nobody writes the literal or sets it.
                    forwards = path.name == "real_scope.py" and isinstance(keyword.value, ast.Name) and keyword.value.id == "test_switch"
                    if not forwards:
                        offenders.append("%s:%d" % (path.relative_to(SRC), node.lineno))
        self.assertEqual(offenders, [])
        mentions = sorted(str(p.relative_to(SRC)) for p in SRC.rglob("*.py") if "test_switch" in p.read_text("utf8"))
        self.assertEqual(mentions, ["persistence/real_scope.py"])

    def test_the_switch_section_is_delimited_and_small(self):
        lines = (SRC / "persistence" / "real_scope.py").read_text("utf8").splitlines()
        start = next(i for i, line in enumerate(lines) if "THE TEST SWITCH" in line and line.startswith("# THE"))
        end = next(i for i, line in enumerate(lines) if line.startswith("# End of the test switch"))
        self.assertLess(end - start, 60)
        section = "\n".join(lines[start:end])
        self.assertEqual(re.findall(r"^def (\w+)", section, flags=re.M), ["resolve_scope"])         # one function: the switch
        self.assertEqual(re.findall(r"^class (\w+)", section, flags=re.M), ["ResolvedScope"])      # and the one value it mints


def _parse_sources():
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text("utf8"))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        yield str(path.relative_to(SRC)), tree, parents


def _enclosing(node, parents):
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return node.name
    return "<module>"


def _uses(name, *, calls=False, only=""):
    """(file, enclosing function) of every LOAD of `name` (or every CALL of it) in src/, whether spelled `name` or `x.name`.
    `only` limits the files to a path prefix, for names that other packages also use (`Snapshot`, `build_snapshot`)."""
    found = []
    for relative, tree, parents in _parse_sources():
        if not relative.startswith(only):
            continue
        for node in ast.walk(tree):
            if calls:
                if isinstance(node, ast.Call) and ((isinstance(node.func, ast.Name) and node.func.id == name)
                                                   or (isinstance(node.func, ast.Attribute) and node.func.attr == name)):
                    found.append((relative, _enclosing(node, parents)))
            elif (isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, ast.Load)) \
                    or (isinstance(node, ast.Attribute) and node.attr == name):
                found.append((relative, _enclosing(node, parents)))
    return sorted(found)


class SecondDoorTests(unittest.TestCase):
    """Technical review R1, M-1. The switch is the ONLY way to a TEST_SWITCH snapshot (design 4.2, PD-0066 decision 8). The check
    does not look for the spelling of the keyword. It looks at every place in src/ that can yield a scope, and at what every function
    that takes a scope does with a TEST_SWITCH scope offered in every bare form."""

    R = "persistence/real_scope.py"
    P = "persistence/real_proposal.py"
    PV = "persistence/real_provenance.py"
    PS = "persistence/real_provenance_store.py"

    def test_scopes_are_looked_up_in_two_functions_only(self):
        # The table is read by `resolve_scope` (the switch) and by `scope_by_snapshot_field` (the scope field of BYTES, which is data).
        self.assertEqual(_uses("SCOPES"), [(self.R, "resolve_scope"), (self.R, "scope_by_snapshot_field")])
        # R2 adds two readers of data that is already stored, and no third: the registry's read-back validator and the guarded load, which
        # take the scope from the lease's snapshot field and from the candidate's own bytes. Reading a candidate back cannot create one, so
        # neither grants the switch; `validate_loaded_bundle` also refuses a scope that is not the table's own entry (a test checks).
        # R5 adds two more readers of stored data, in the executor-side service: the create (`_stage_create`) and the reproduce (the `body` it runs
        # in the read tail). Each takes the scope from the `scope` field of the snapshot the gateway LOCKED with the lease (`lease.snapshot`), never
        # from an argument, a mode or a keyword, so neither can name TEST_SWITCH. Only the CREATE then runs `check_install_kind` on the result (it
        # writes); the reproduce does not call it, and relies on the SQL admission's install-kind guard. The create-only Python check is R5's own
        # defence in depth: design 4.2 states the install-kind guard at publish and at admit (SQL), and design 1 item 1 calls it "a second barrier";
        # neither text names a Python check on the create (R5 review note, corrected in R6). TR5-L3: a test removes the create's check and fails
        # (`DefenceInDepthGuardTests`).
        self.assertEqual(_uses("scope_by_snapshot_field", calls=True),
                         [(self.P, "verify_proposal"), (self.PV, "validate_loaded_bundle"), (self.PS, "load_guarded"),
                          ("real_service/service.py", "_stage_create"), ("real_service/service.py", "body")])

    def test_a_resolved_scope_is_made_by_the_switch_alone(self):
        self.assertEqual(_uses("ResolvedScope", calls=True), [(self.R, "resolve_scope")])
        self.assertEqual(_uses("_MINT"), [(self.R, "__init__"), (self.R, "resolve_scope")])
        self.assertEqual(_uses("ScopeDef", calls=True), [(self.R, "<module>")] * 3)               # the three table entries
        literal = []
        for relative, tree, _parents in _parse_sources():
            literal += [relative for node in ast.walk(tree) if isinstance(node, ast.Constant) and node.value == "TEST_SWITCH"]
        self.assertEqual(sorted(set(literal)), [self.R])

    def test_snapshots_are_built_from_resolved_scopes_or_from_bytes_only(self):
        # R2: the registration path validates a candidate of a ResolvedScope, the way a snapshot is built, so a candidate of the switch's
        # scope needs the switch too. Its read-back path takes data (`validate_loaded_bundle`, above).
        # R4b adds two callers, both TAKING a scope and both refusing a bare name, a `ScopeDef` or a copy exactly as `build_snapshot` does: the
        # qualification run and the candidate builder (`real_tools`, human-run tools that no product code imports). Neither can mint a scope.
        self.assertEqual(_uses("require_resolved", calls=True), [(self.P, "build_snapshot"), (self.PV, "validate_bundle"),
                                                                 ("real_tools/candidates.py", "build_candidate"), ("real_tools/qualification.py", "qualify")])
        self.assertEqual(_uses("_build_snapshot", calls=True), [(self.P, "build_snapshot"), (self.P, "verify_proposal")])
        self.assertEqual(_uses("Snapshot", calls=True, only="persistence/real_"), [(self.P, "_build_snapshot")])
        self.assertEqual(_uses("build_snapshot", calls=True, only="persistence/real_"), [(self.P, "write_proposal"), (self.R, "make_snapshot")])

    def test_every_public_function_that_takes_a_scope_is_one_this_review_knows(self):
        found = set()
        for module in (real_scope, real_proposal):
            for name, function in inspect.getmembers(module, inspect.isfunction):
                if function.__module__ == module.__name__ and not name.startswith("_") \
                        and {"scope", "scope_name"} & set(inspect.signature(function).parameters):
                    found.add("%s.%s" % (module.__name__.rsplit(".", 1)[1], name))
        # Of these, only `make_snapshot`, `build_snapshot` and `write_proposal` yield a snapshot; the others read a scope.
        self.assertEqual(found, {"real_scope.check_install_kind", "real_scope.labels_match_scope", "real_scope.make_snapshot",
                                 "real_scope.require_resolved", "real_proposal.build_snapshot", "real_proposal.write_proposal"})

    def test_every_function_that_builds_refuses_a_test_switch_scope_in_every_bare_form(self):
        definition = SCOPES["TEST_SWITCH"]
        bare = {"the table entry": definition, "its name": "TEST_SWITCH", "a copy with the flag cleared": dataclasses.replace(definition, requires_switch=False)}
        conn = _KindConnection(("TEST", 4))
        for label, form in bare.items():
            for function in (real_proposal.build_snapshot, real_proposal.write_proposal):
                with self.assertRaises(ScopeError, msg="%s via %s" % (label, function.__name__)) as caught:
                    function(form, **fx.content("door"))
                self.assertEqual(caught.exception.code, "RW_SCOPE_UNRESOLVED", label)
            # The factory takes a NAME and the switch; it never takes a scope value. "TEST_SWITCH" without the switch is refused.
            with self.assertRaises(ScopeError, msg="factory: " + label) as caught:
                make_snapshot(conn, "rw_x", form, **fx.content("door"))
            self.assertIn(caught.exception.code, ("RW_SCOPE_UNKNOWN", "RW_SWITCH_REQUIRED"), label)
        self.assertEqual(conn.statements, [])                                    # refused before any database read


class InstallKindGuardTests(unittest.TestCase):
    def test_guard_in_both_directions(self):
        for name, kind, ok in (("SYNTHETIC_TEST", "TEST", True), ("TEST_SWITCH", "TEST", True), ("REAL", "TEST", False),
                               ("SYNTHETIC_TEST", "REAL", False), ("TEST_SWITCH", "REAL", False), ("REAL", "REAL", True)):
            scope = SCOPES[name]
            if ok:
                self.assertIs(check_install_kind(scope, kind), scope, (name, kind))
            else:
                with self.assertRaises(ScopeError) as caught:
                    check_install_kind(scope, kind)
                self.assertEqual(caught.exception.code, "RW_INSTALL_KIND", (name, kind))

    def test_an_install_without_a_kind_admits_no_scope(self):
        for kind in (None, "", "test", "PROD", 1):
            with self.assertRaises(ScopeError) as caught:
                check_install_kind(SCOPES["SYNTHETIC_TEST"], kind)
            self.assertEqual(caught.exception.code, "RW_INSTALL_MISSING", repr(kind))


class FactoryTests(unittest.TestCase):
    """`make_snapshot` is the only way a test obtains a snapshot of a test scope (PD-0066 decision 8)."""

    def test_factory_builds_both_test_scopes_in_a_test_install(self):
        conn = _KindConnection(("TEST", 4))
        plain = make_snapshot(conn, "rw_x", "SYNTHETIC_TEST", **fx.content("factory"))
        switched = make_snapshot(conn, "rw_x", "TEST_SWITCH", test_switch=True, **fx.content("factory"))
        self.assertEqual((plain.scope, switched.scope), ("SYNTHETIC_TEST", "TEST_SWITCH"))
        self.assertNotEqual(plain.context_id, switched.context_id)
        for snap in (plain, switched):
            self.assertEqual(snap.content["origin"], SCOPES[snap.scope].origin_fields())
            self.assertNotIn(b"REAL_SOURCE", snap.data)
            self.assertIs(snap.content["origin"]["synthetic"], True)
        self.assertEqual(len(conn.statements), 2)
        self.assertTrue(all("rw_install_info" in s for s in conn.statements))

    def test_factory_labels_come_from_the_scope_not_the_caller(self):
        conn = _KindConnection(("TEST", 4))
        with self.assertRaises(TypeError):
            make_snapshot(conn, "rw_x", "SYNTHETIC_TEST", origin={"synthetic": False}, **fx.content("labels"))

    def test_switch_misuse_is_refused_before_any_database_read(self):
        conn = _KindConnection(("TEST", 4))
        with self.assertRaises(ScopeError) as caught:
            make_snapshot(conn, "rw_x", "TEST_SWITCH", **fx.content("a"))
        self.assertEqual(caught.exception.code, "RW_SWITCH_REQUIRED")
        with self.assertRaises(ScopeError) as caught:
            make_snapshot(conn, "rw_x", "SYNTHETIC_TEST", test_switch=True, **fx.content("a"))
        self.assertEqual(caught.exception.code, "RW_SWITCH_NOT_APPLICABLE")
        self.assertEqual(conn.statements, [])

    def test_factory_raises_outside_a_test_install(self):
        real_install = _KindConnection(("REAL", 600))
        for name, switch in (("SYNTHETIC_TEST", False), ("TEST_SWITCH", True)):
            with self.assertRaises(ScopeError) as caught:
                make_snapshot(real_install, "rw_x", name, test_switch=switch, **fx.content("real-install"))
            self.assertEqual(caught.exception.code, "RW_INSTALL_KIND", name)
        with self.assertRaises(ScopeError) as caught:
            make_snapshot(_KindConnection(("TEST", 4)), "rw_x", "REAL", **fx.content("real-in-test"))
        self.assertEqual(caught.exception.code, "RW_INSTALL_KIND")

    def test_factory_raises_where_the_install_reports_nothing(self):
        with self.assertRaises(ScopeError) as caught:
            make_snapshot(_KindConnection(None), "rw_x", "SYNTHETIC_TEST", **fx.content("none"))
        self.assertEqual(caught.exception.code, "RW_INSTALL_MISSING")

    def test_factory_output_passes_the_proposal_verifier(self):
        snap = make_snapshot(_KindConnection(("TEST", 4)), "rw_x", "TEST_SWITCH", test_switch=True, **fx.content("verify"))
        verified = real_proposal.verify_proposal(real_proposal.proposal_bytes(snap))
        self.assertEqual((verified.scope.name, verified.snapshot.context_id), ("TEST_SWITCH", snap.context_id))


if __name__ == "__main__":
    unittest.main()
