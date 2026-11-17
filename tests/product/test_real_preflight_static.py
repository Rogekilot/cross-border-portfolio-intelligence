"""F1 R6, no database: the STATIC NO-BYPASS test over the tools that exist at R6 (design 1.2 rule 5.2 "Tests", technical TR3-L2, rule 7).

The tools: the real installer (`real_install.py`), the publisher tool (`real_workspace_store.py`, whose `main` carries the gate) and the owner-run identity
seed (`real_tools/identity_seed.py`). R7 extends this test to the launcher and the admission probe when it builds them (technical TR3R-L3: an R6 test
cannot list the options of a tool that does not exist yet).

It fails on:
  * any option that is a credential option (a password, a password file, a passfile, a DSN or URL) or a switch of the preflight, the kind, the clock
    or the test scope: every tool's option set is pinned to an allow-list of target and command inputs;
  * any environment read (`os.environ`, `getenv`) in a tool, and any in `real_preflight.py` outside the one function that copies the caller's
    environment so that Pass S can look for stored credentials;
  * a credential route other than the terminal prompt: `input`, `getpass`, `sys.stdin` anywhere but `terminal_prompt`;
  * the real installer naming the TEST-only part's file or function, a SQL file name of any kind, a grant of its own, or a file list or grant list taken
    from anything but the functions R3 tests (`real_roles.sql_files`, `real_roles.grant_statements` via `_install_gateway_body`);
  * an install kind other than `REAL` written by the installer, or a kind parameter on any of its functions.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
import re
import sys
import unittest

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from persistence import real_install, real_preflight as pf, real_roles, real_tool_gate, real_workspace_store as store  # noqa: E402
from real_tools import admission_probe, identity_seed, loader_window, qualify_run, r8_files  # noqa: E402
from web_api import real_launcher  # noqa: E402

#: Every tool: a command-line program that opens its own connection to the real gateway's database (R6: installer, publisher tool, identity seed;
#: R7: the real-mode launcher and the admission probe). The test DISCOVERS command-line programs in the real-tool paths (`DiscoveryTests`) and fails
#: for one that is not listed here (technical TR6C-3), so a later tool (the loader's window tools of R8) is covered the day it exists.
TOOLS = {"installer": SRC / "persistence" / "real_install.py", "publisher": SRC / "persistence" / "real_workspace_store.py",
         "identity seed": SRC / "real_tools" / "identity_seed.py", "launcher": SRC / "web_api" / "real_launcher.py",
         "admission probe": SRC / "real_tools" / "admission_probe.py",
         # R8: the loader's window tool (takes the loader's password from the prompt) and the offline qualify command (takes none and opens no connection)
         "loader window": SRC / "real_tools" / "loader_window.py", "qualify run": SRC / "real_tools" / "qualify_run.py",
         # R8 round 2: the offline writers of the publish evidence file and the launcher's contexts file (no connection, no password)
         "r8 files": SRC / "real_tools" / "r8_files.py"}
#: Code the tools share and that must meet the same environment, file and credential rules, though it is not a program of its own.
SHARED = {"start gate": SRC / "persistence" / "real_tool_gate.py",
          # R8: where the two new tools read their files and build the qualification; held to the same environment, spelling and credential rules
          "real inputs": SRC / "real_tools" / "real_inputs.py"}
PREFLIGHT = SRC / "persistence" / "real_preflight.py"
CHECKED = {**TOOLS, **SHARED}
#: Where a real tool may live. Any module in these places that is a command-line program must be a key of TOOLS.
TOOL_PLACES = (("real_tools", "*.py"), ("persistence", "real_*.py"), ("web_api", "real_*.py"), ("web_api", "*launcher*.py"))

#: The options each tool may have: target and command inputs only. A new option is a reviewed change to this table.
ALLOWED_OPTIONS = {
    "installer": {"--socket", "--user", "--loader-login"},
    "publisher": {"--socket", "--database", "--user", "--schema", "--lock-timeout-ms", "--proposal", "--sidecar", "--valid-until", "--evidence-file",
                  "--rights-json", "--context", "--generation", "--names-mark", "--actor", "--pd", "--commit", "--sha"},
    "identity seed": {"--socket", "--user", "--seed-file", "--proposal"},
    "launcher": {"--socket", "--database", "--user", "--schema", "--account-user", "--contexts-file", "--port"},
    "admission probe": {"--socket", "--database", "--user", "--schema", "--purpose", "--owner-id", "--root-id", "--context", "--generation"},
    "loader window": {"--socket", "--database", "--user", "--schema", "--store-root", "--release-name", "--file", "--sidecar", "--registered-check", "--proposal",
                      "--lock-timeout-ms", "--candidate"},
    "qualify run": {"--store-root", "--release-name", "--file", "--sidecar", "--registered-check", "--proposal-out", "--seed-out"},
    "r8 files": {"--alphavantage-pd", "--alphavantage-commit", "--alphavantage-sha", "--openfigi-pd", "--openfigi-commit", "--openfigi-sha",
                 "--calendar-pd", "--calendar-commit", "--calendar-sha", "--out", "--store-root", "--release-name", "--file", "--sidecar", "--registered-check", "--proposal", "--generation"},
}
#: R8's GUIDED RUNNER is a command-line program in the real-tool places but not a TOOL in the sense of this test: it opens no connection, asks for no password and has
#: no credential route, yet it must read the environment (to strip it), start child programs and write its own state, which every rule for TOOLS forbids. It is
#: therefore listed here and not in TOOLS, and `OrchestratorTests` holds it to its own rules (what it may import, where it may launch a child, write or read the
#: environment, which strings it may carry) and pins its whole source. A change to it is a reviewed change to `ORCHESTRATOR_PINS`.
ORCHESTRATORS = {"r8 guide": SRC / "real_tools" / "r8_guide.py",
                 # The supplementary-run runner (PD-0087, plan `implementation/CP7_F1_R8_SUPPLEMENT_PLAN.md` revision 2): a `Guide` subclass held to the same rules,
                 # with the one reviewed relaxation in `orchestrator_problems(allow_runner_import=True)` (it may import `real_tools.r8_guide`, and only that).
                 "r8 supplement": SRC / "real_tools" / "r8_supplement.py"}
#: The supplementary run's LOOPBACK TOOL. It opens no database connection and takes no database password, so it is not a `TOOLS` entry (those rules say a password goes
#: into a connection string only); it takes a WEB-ACCOUNT password at the same reviewed prompt and sends it to the loopback launcher. `HttpToolTests` holds it to its own rules.
HTTP_TOOLS = {"r8 http check": SRC / "real_tools" / "r8_http_check.py"}
HTTP_ALLOWED_OPTIONS = {"--phase", "--resume", "--operation-id", "--context", "--release", "--listing", "--root", "--root-operation", "--user-a", "--user-b", "--replay-name",
                        "--first-response-sha", "--first-issued-sha", "--y-response-sha", "--y-issued-sha", "--acknowledged"}
PARSERS = {"installer": real_install._build_parser, "publisher": store._build_parser, "identity seed": identity_seed._build_parser,
           "launcher": real_launcher._build_parser, "admission probe": admission_probe._build_parser, "loader window": loader_window._build_parser,
           "qualify run": qualify_run._build_parser, "r8 files": r8_files._build_parser}
FORBIDDEN_OPTION = re.compile(r"pass|pwd|secret|token|cred|auth|service|dsn|conninfo|url|env|kind|mode|switch|test|skip|force|bypass|relax|insecure|trust|"
                              r"preflight|check-off|no-check|clock|now|role|database-kind|override", re.I)

def tree(path):
    return ast.parse(path.read_text("utf8"))


def strings(node, skip_docstrings=True):
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.append(n.value)
    if skip_docstrings:
        for n in ast.walk(node):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(n, clean=False)
                if doc is not None and doc in out:
                    out.remove(doc)
    return out


def parser_options(parser):
    options, stack = set(), [parser]
    while stack:
        current = stack.pop()
        for action in current._actions:
            options.update(o for o in action.option_strings if o not in ("-h", "--help"))
            if isinstance(getattr(action, "choices", None), dict):
                stack.extend(action.choices.values())
    return options


class OptionTests(unittest.TestCase):
    def test_each_tool_has_exactly_its_target_and_command_options_and_no_credential_or_switch_option(self):
        self.assertEqual(set(PARSERS), set(TOOLS))
        self.assertEqual(set(ALLOWED_OPTIONS), set(TOOLS))
        for name, build in PARSERS.items():
            options = parser_options(build())
            self.assertEqual(options, ALLOWED_OPTIONS[name], name)
            for option in options:
                self.assertIsNone(FORBIDDEN_OPTION.search(option.lstrip("-")), (name, option))

    def test_the_probe_has_three_purposes_and_none_of_them_creates(self):
        """E27: no option selects `EXECUTE_CREATE`, whose admission can register a root; the probe has no `new_root` input either."""
        self.assertEqual(admission_probe.PURPOSES, ("ARCHIVE_READ", "ARCHIVE_EXPORT", "EXECUTE_REPRODUCE"))
        purpose = next(a for a in admission_probe._build_parser()._actions if "--purpose" in a.option_strings)
        self.assertEqual(tuple(purpose.choices), admission_probe.PURPOSES)
        module = tree(TOOLS["admission probe"])
        self.assertNotIn("EXECUTE_CREATE", "\n".join(strings(module)))
        used = ({k.arg for n in ast.walk(module) if isinstance(n, ast.Call) for k in n.keywords} | {n.id for n in ast.walk(module) if isinstance(n, ast.Name)}
                | {n.attr for n in ast.walk(module) if isinstance(n, ast.Attribute)})
        self.assertNotIn("new_root", used)

    def test_the_launcher_and_the_probe_decide_their_target_through_the_one_start_gate_keyed_to_their_command(self):
        """The decision is `real_tool_gate.start_gate(conn, <constant command>, database=args.database, schema=args.schema, socket=args.socket)`: the
        database NAME and the rows READ (inside the gate), a command that is a module constant, and no other input. Nothing else in either module
        names `decide_target`, `command_plan` or `run_runtime_gate`."""
        self.assertEqual(list(inspect.signature(real_tool_gate.start_gate).parameters), ["conn", "command", "database", "schema", "socket"])
        self.assertEqual(list(inspect.signature(real_tool_gate._run_gate).parameters), ["conn", "database", "socket"])
        self.assertEqual(real_tool_gate.START_COMMANDS, ("serve", "admit"))
        for name, command, constant in (("launcher", "serve", "COMMAND"), ("admission probe", "admit", "COMMAND")):
            module = tree(TOOLS[name])
            assigned = [n for n in module.body if isinstance(n, ast.Assign) and [ast.unparse(t) for t in n.targets] == [constant]]
            self.assertEqual([ast.unparse(n.value) for n in assigned], [repr(command)], name)
            calls = [n for n in ast.walk(module) if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("start_gate")]
            self.assertEqual(len(calls), 1, name)
            self.assertEqual([ast.unparse(a) for a in calls[0].args], ["conn", constant], name)
            self.assertEqual({k.arg: ast.unparse(k.value) for k in calls[0].keywords},
                             {"database": "args.database", "schema": "args.schema", "socket": "args.socket"}, name)
            names = {n.id for n in ast.walk(module) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(module) if isinstance(n, ast.Attribute)}
            self.assertFalse(names & {"decide_target", "command_plan", "run_runtime_gate", "run_gate", "_run_gate", "gather_facts", "decide"}, name)
        gate = tree(SHARED["start gate"])
        decisions = [n for n in ast.walk(gate) if isinstance(n, ast.Call) and ast.unparse(n.func) == "pf.decide_target"]
        self.assertEqual([[ast.unparse(a) for a in c.args] for c in decisions], [["database", "read_install_kinds(conn, schema)"]])
        plans = [n for n in ast.walk(gate) if isinstance(n, ast.Call) and ast.unparse(n.func) == "pf.command_plan"]
        self.assertEqual([[ast.unparse(a) for a in c.args] for c in plans], [["command", "target"]])

    GATE_BODIES = {
        "read_install_kinds": "def read_install_kinds(conn, schema):\n    import psycopg\n    try:\n        with conn.transaction():\n            return tuple((r[0] for r in query_all(conn, identifier(schema), 'rw_install_info', ())))\n    except (psycopg.Error, RealWorkspaceError):\n        return None",
        "_run_gate": 'def _run_gate(conn, database, socket):\n    return pf.run_runtime_gate(conn, database=database, socket=socket)',
        "start_gate": "def start_gate(conn, command, *, database, schema, socket):\n    if command not in START_COMMANDS:\n        raise ValueError('the start gate serves the launcher and the admission probe only')\n    target = pf.decide_target(database, read_install_kinds(conn, schema))\n    plan = pf.command_plan(command, target)\n    if not plan.proceed:\n        return StartDecision(False, '', plan.code, ('REFUSED %s: %s' % (plan.code, plan.detail),))\n    if plan.preflight_before:\n        decision = _run_gate(conn, database, socket)\n        if not decision.ok:\n            return StartDecision(False, '', 'PF_PREFLIGHT_REFUSED', tuple(decision.lines) + ('REFUSED PF_PREFLIGHT_REFUSED: ' + ', '.join(decision.codes()),))\n        return StartDecision(True, 'REAL', '', tuple(decision.lines))\n    return StartDecision(True, 'TEST', '', ())",
    }

    @staticmethod
    def gate_function_text(module, name):
        """The function `name` of a parsed gate module as normalized source with the docstring dropped (comments and layout do not matter)."""
        node = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == name)
        node.body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
        return ast.unparse(node)

    def test_the_shared_gates_function_bodies_are_pinned_exactly(self):
        """TR7-L-2: the arguments and the parameter lists were pinned, not the bodies. Two relaxations survived: `_run_gate` passing `environ={}, home=...`
        (the stored-credential scan of Pass S silently skipped) and a socket-path word that skips the preflight. The three functions are now pinned as
        normalized source; any change is a reviewed change to this table. Nothing else in the module may be a function that reaches the gate."""
        module = tree(SHARED["start gate"])
        for name, expected in self.GATE_BODIES.items():
            self.assertEqual(self.gate_function_text(module, name), expected, name)
        self.assertEqual(sorted(n.name for n in module.body if isinstance(n, ast.FunctionDef)), sorted(self.GATE_BODIES))

    def test_the_pin_sees_the_two_mutants_the_reviewer_found(self):
        original = SHARED["start gate"].read_text("utf8")
        mutants = {
            "G1 the credential scan skipped (environ={} and a home that does not exist)": original.replace(
                "pf.run_runtime_gate(conn, database=database, socket=socket)", 'pf.run_runtime_gate(conn, database=database, socket=socket, environ={}, home="/nonexistent")'),
            "G3 a socket-path word skips the preflight": original.replace("if plan.preflight_before:", 'if plan.preflight_before and "/nogate/" not in socket:'),
        }
        for label, text in mutants.items():
            self.assertNotEqual(text, original, label)                                  # the mutation applied
            mutated = ast.parse(text)
            differing = [name for name, expected in self.GATE_BODIES.items() if self.gate_function_text(mutated, name) != expected]
            self.assertEqual(len(differing), 1, label)

    def test_neither_the_launcher_nor_the_probe_has_a_path_to_the_test_switch_or_a_scope(self):
        """Design 1.2 rule 5.2 and `real_scope`: no code path passes `test_switch`, resolves a scope or builds a snapshot."""
        for name in ("launcher", "admission probe"):
            module = tree(TOOLS[name])
            text = TOOLS[name].read_text("utf8")
            self.assertNotIn("test_switch", text, name)
            for banned in ("resolve_scope", "make_snapshot", "build_snapshot", "real_scope", "real_proposal", "ResolvedScope", "TEST_SWITCH", "SCOPES"):
                self.assertNotIn(banned, text, "%s names %s" % (name, banned))
            for node in ast.walk(module):
                if isinstance(node, (ast.ImportFrom, ast.Import)):
                    names = [getattr(node, "module", None) or ""] + [a.name for a in node.names]
                    self.assertFalse(any(n.split(".")[-1] in ("real_scope", "real_proposal") for n in names), (name, names))

    def test_the_options_do_not_reach_the_target_decision_or_the_preflights_arguments(self):
        self.assertEqual(list(inspect.signature(pf.decide_target).parameters), ["database", "kind_rows"])
        self.assertEqual(list(inspect.signature(pf.command_plan).parameters), ["command", "target"])
        self.assertEqual(list(inspect.signature(pf.run_runtime_gate).parameters), ["conn", "database", "socket", "environ", "home", "prober", "sysconfdir"])
        self.assertEqual(list(inspect.signature(store._run_gate).parameters), ["conn", "args"])
        # the target decision of the publisher tool is computed from the database NAME and the rows READ, in one expression
        main = next(n for n in ast.walk(tree(TOOLS["publisher"])) if isinstance(n, ast.FunctionDef) and n.name == "main")
        decisions = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "decide_target"]
        self.assertEqual(len(decisions), 1)
        self.assertEqual([ast.unparse(a) for a in decisions[0].args], ["args.database", "_read_kind_rows(conn, args.schema)"])
        self.assertEqual(decisions[0].keywords, [])
        plans = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "command_plan"]
        self.assertEqual([ast.unparse(a) for a in plans[0].args], ["args.command", "pf.decide_target(args.database, _read_kind_rows(conn, args.schema))"])

    def test_the_gate_commands_are_keyed_to_the_command_alone(self):
        self.assertEqual(pf.GATED_COMMANDS, ("publish", "renew", "serve", "admit"))          # R7 added the launcher's start and the probe's
        self.assertEqual(pf.NEVER_GATED_COMMANDS, ("withdraw",))
        self.assertEqual(set(pf.GATED_COMMANDS) & set(pf.NEVER_GATED_COMMANDS), set())


class EnvironmentAndCredentialTests(unittest.TestCase):
    def test_no_tool_reads_the_environment(self):
        for name, path in CHECKED.items():
            text = path.read_text("utf8")
            for token in ("os.environ", "getenv", "environ["):
                # the installer and the tools pass an `environ=` KEYWORD to the preflight's seams; they never read a variable
                self.assertNotIn(token, text, "%s: %s" % (name, token))
            module = tree(path)
            forwarded = {id(k.value) for n in ast.walk(module) if isinstance(n, ast.Call) for k in n.keywords if k.arg == "environ"}
            for node in ast.walk(module):
                if isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv"):
                    self.fail("%s reads the environment" % name)
                # a parameter named `environ`, forwarded as the keyword `environ=environ` to the preflight's seam, is not a read
                if isinstance(node, ast.Name) and node.id in ("environ", "getenv") and id(node) not in forwarded:
                    self.fail("%s reads the environment" % name)

    def test_no_tool_imports_os_or_anything_that_reaches_the_environment_under_any_spelling(self):
        """TR6B-M-2 (S3, S3i, S3s): `from os import environ as _E` has no `os.environ` text and no attribute, so the checks above do not see it. None of
        the three tools needs `os` at all, so ANY import of `os`, `posix`, `nt` or `importlib`, in any form, and any `__import__`, fails."""
        for name, path in CHECKED.items():
            for node in ast.walk(tree(path)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name.split(".")[0], ("os", "posix", "nt", "importlib"), "%s: import %s" % (name, alias.name))
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or "").split(".")[0], ("os", "posix", "nt", "importlib"),
                                     "%s: from %s import %s" % (name, node.module, ", ".join(a.name for a in node.names)))
                    self.assertNotIn("environ", [a.name for a in node.names], name)
                if isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "__import__", name)
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, ("expanduser", "environb", "getenvb", "putenv"), "%s: .%s" % (name, node.attr))

    def test_the_preflights_only_environment_read_is_one_function_that_copies_it_to_refuse(self):
        module = tree(PREFLIGHT)
        reads = []
        for function in [n for n in ast.walk(module) if isinstance(n, ast.FunctionDef)]:
            for node in ast.walk(function):
                if isinstance(node, ast.Attribute) and node.attr in ("environ", "getenv") and isinstance(node.value, ast.Name) and node.value.id == "os":
                    reads.append(function.name)
        self.assertEqual(sorted(set(reads)), ["process_environment"])
        top_level = [n for n in module.body if isinstance(n, ast.Assign) and "environ" in ast.unparse(n) and "os." in ast.unparse(n)]
        self.assertEqual(top_level, [])
        accesses = [n for n in ast.walk(module) if isinstance(n, ast.Attribute) and n.attr == "environ" and isinstance(n.value, ast.Name) and n.value.id == "os"]
        self.assertEqual(len(accesses), 1)

    def test_the_prompt_is_the_only_credential_route(self):
        for name, path in list(CHECKED.items()) + [("preflight", PREFLIGHT)]:
            module = tree(path)
            for function in [n for n in ast.walk(module) if isinstance(n, ast.FunctionDef)]:
                if function.name == "terminal_prompt":
                    continue
                for node in ast.walk(function):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("input", "raw_input"):
                        self.fail("%s.%s reads input()" % (name, function.name))
                    if isinstance(node, ast.Attribute) and node.attr in ("getpass", "stdin"):
                        self.fail("%s.%s reads %s" % (name, function.name, node.attr))
            for node in ast.walk(module):
                if isinstance(node, ast.Import) and any(a.name == "getpass" for a in node.names) and name != "preflight":
                    self.fail("%s imports getpass" % name)

    def test_no_tool_writes_or_reads_a_password_file_or_names_a_credential_store_to_use(self):
        for name, path in CHECKED.items():
            for text in strings(tree(path)):
                self.assertNotRegex(text, r"\.pgpass|pg_service|PGPASS|PGSERVICE|PGSYSCONF", "%s names a credential store: %r" % (name, text))
        # the preflight names them only to SCAN them (Pass S) and sets the connection's passfile to /dev/null
        for text in strings(tree(PREFLIGHT)):
            self.assertNotIn("password=%", text)

    def test_the_password_goes_into_a_connection_string_only_and_never_into_a_log_or_a_print(self):
        source = PREFLIGHT.read_text("utf8")
        function = next(n for n in ast.walk(tree(PREFLIGHT)) if isinstance(n, ast.FunctionDef) and n.name == "connect_with_prompt")
        code = "\n".join(ast.unparse(s) for s in function.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)))
        self.assertEqual(code.count("'password': password"), 1)
        self.assertEqual(len([n for n in ast.walk(function) if isinstance(n, ast.Call) and ast.unparse(n.func) == "prompt"]), 1)
        self.assertNotRegex(code, r"print\(|log|write|\.format\(|%s")
        self.assertEqual(source.count("def connect_with_prompt"), 1)


class InstallerListTests(unittest.TestCase):
    def test_the_installer_never_names_the_test_only_part(self):
        banned = set(real_roles.TEST_ONLY_SQL_FILES) | {name for name, _a in real_roles.TEST_ONLY_FUNCTIONS} | {"real_workspace_fictional"}
        banned |= {f.replace(".sql", "") for f in real_roles.TEST_ONLY_SQL_FILES}
        self.assertEqual(banned, {"real_workspace_fictional_v1.sql", "real_workspace_fictional_v1", "real_workspace_fictional", "rw_check_fictional"})
        for name, path in TOOLS.items():
            source = path.read_text("utf8")
            for token in banned:
                self.assertNotIn(token, source, "%s names %s" % (name, token))
            self.assertNotIn("TEST_ONLY", source, name)
        for text in strings(tree(TOOLS["installer"])):
            self.assertNotRegex(text, r"fictional|rw_check", text)

    def test_the_installer_has_no_sql_file_name_and_no_grant_of_its_own(self):
        installer = tree(TOOLS["installer"])
        for text in strings(installer):
            self.assertNotRegex(text, r"\.sql\b", "a file name: %r" % text)
            self.assertNotRegex(text, r"GRANT\s+(EXECUTE|SELECT|INSERT|UPDATE|DELETE|TRUNCATE|USAGE|ALL)\b", "a grant of its own: %r" % text)
            self.assertNotRegex(text, r"ON\s+(ALL\s+)?(TABLES|FUNCTIONS|ROUTINES|SEQUENCES)|ON\s+(TABLE|FUNCTION|SEQUENCE)\b", "an object grant: %r" % text)
            self.assertNotRegex(text, r"CREATE\s+(OR\s+REPLACE\s+)?(FUNCTION|TRIGGER|TABLE|POLICY)", "gateway DDL: %r" % text)
        # the only GRANT is the database-level CONNECT barrier (1 item 2)
        grants = [t for t in strings(installer) if re.search(r"\bGRANT\b", t)]
        self.assertEqual(len(grants), 1)
        self.assertIn("GRANT CONNECT ON DATABASE", grants[0])

    def test_the_file_list_and_the_grant_lists_come_from_the_shared_installer_functions_alone(self):
        installer_source = TOOLS["installer"].read_text("utf8")
        calls = [n for n in ast.walk(tree(TOOLS["installer"])) if isinstance(n, ast.Call)]
        gateway = [c for c in calls if isinstance(c.func, ast.Name) and c.func.id == "_install_gateway_body"]
        self.assertEqual(len(gateway), 1)
        kinds = [k for k in gateway[0].keywords if k.arg == "kind"]
        self.assertEqual([ast.unparse(k.value) for k in kinds], ["'REAL'"])
        # the body takes the lists from `real_roles.sql_files(kind)` and `real_roles.grant_statements(kind, ...)`: pinned in R3's tests and here
        body = inspect.getsource(store._install_gateway_body)
        self.assertIn("real_roles.sql_files(kind)", body)
        self.assertIn("real_roles.apply_role_grants(conn, schema, executor_role, loader_role, publisher_role, kind, account_role)", body)
        self.assertNotIn("Path(", installer_source.replace("Path(__file__)", ""))
        for call in calls:
            if isinstance(call.func, ast.Attribute) and call.func.attr == "sql_files":
                self.assertEqual([ast.unparse(a) for a in call.args], ["'REAL'"])
        # and the REAL list is the core alone
        self.assertEqual(real_roles.sql_files("REAL"), real_roles.CORE_SQL_FILES)
        self.assertFalse(set(real_roles.sql_files("REAL")) & set(real_roles.TEST_ONLY_SQL_FILES))

    STATEMENT_SOURCES = {"role_statements", "database_statements", "schema_statements"}

    def test_every_statement_the_installer_executes_is_a_literal_or_comes_from_its_own_statement_functions(self):
        """TR6B-M-2 (S6, S6b): statements from a text or JSON file, or from any other source, fail. A statement is (a) a string literal, (b) a literal
        with `%` values (the schema and role names, validated by `identifier`), or (c) the loop variable of a `for` over the three statement
        functions of this module (directly, or through a name assigned from them)."""
        module = tree(TOOLS["installer"])
        executes = []
        for function in [n for n in ast.walk(module) if isinstance(n, ast.FunctionDef)]:
            assigned = {}
            for node in ast.walk(function):
                if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    assigned[node.targets[0].id] = node.value
            loops = {}
            for node in ast.walk(function):
                if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
                    loops.setdefault(node.target.id, []).append(node.iter)
            for node in ast.walk(function):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("execute", "executemany", "executescript"):
                    executes.append((function.name, node, assigned, loops))
        self.assertGreaterEqual(len(executes), 7)

        def called(expr, assigned, seen=()):
            """The sources of a statement list: the functions it is built from (their ARGUMENTS are names, validated by `identifier`, not statements)."""
            if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name):
                return {expr.func.id}
            if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
                return called(expr.left, assigned, seen) | called(expr.right, assigned, seen)
            if isinstance(expr, ast.Name) and expr.id in assigned and expr.id not in seen:
                return called(assigned[expr.id], assigned, seen + (expr.id,))
            return {"<other: %s>" % ast.unparse(expr)[:40]}

        for function_name, call, assigned, loops in executes:
            first = call.args[0]
            text = "%s: %s" % (function_name, ast.unparse(call)[:90])
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                continue
            if isinstance(first, ast.BinOp) and isinstance(first.op, ast.Mod) and isinstance(first.left, ast.Constant) and isinstance(first.left.value, str):
                continue
            self.assertIsInstance(first, ast.Name, text)
            self.assertIn(first.id, loops, text)
            for source in loops[first.id]:
                self.assertTrue(called(source, assigned), text)
                self.assertTrue(called(source, assigned) <= self.STATEMENT_SOURCES, "%s iterates %s" % (text, sorted(called(source, assigned))))

    def test_the_installer_reads_no_file_and_opens_no_connection_but_through_its_seams(self):
        source = TOOLS["installer"].read_text("utf8")
        self.assertEqual(file_reads(TOOLS["installer"]), [])
        for token in ("subprocess", "urllib", "socket.", "requests", "pickle", "marshal", "shelve", "sqlite3"):
            self.assertNotIn(token, source, token)

    def test_the_installer_writes_the_kind_real_and_no_other_and_has_no_kind_parameter(self):
        source = TOOLS["installer"].read_text("utf8")
        self.assertEqual(re.findall(r"VALUES\(true,\\?'(\w+)\\?'", source), ["REAL"])
        for name, function in inspect.getmembers(real_install, inspect.isfunction):
            if function.__module__ != real_install.__name__:
                continue
            self.assertNotIn("kind", inspect.signature(function).parameters, name)
        for text in strings(tree(TOOLS["installer"])):
            self.assertNotRegex(text, r"'TEST'|\"TEST\"", text)
        self.assertNotIn('"TEST"', source)
        self.assertNotIn("'TEST'", source)
        # no TEST mode: the choices of the loader option are the only choices any option has
        parser = real_install._build_parser()
        for action in parser._actions[-1].choices.values():
            for a in action._actions:
                if a.choices and a.option_strings:
                    self.assertEqual(set(a.choices), {"login", "nologin"})

    def test_no_statement_of_the_installer_carries_a_password(self):
        names = real_install.REAL_NAMES
        statements = (real_install.role_statements(names, "login") + real_install.role_statements(names, "nologin") +
                      real_install.database_statements(names, ["postgres", "template1", "other"]) + real_install.schema_statements(names))
        for statement in statements:
            self.assertNotRegex(statement, r"(?i)password|encrypted|\bsecret\b", statement)
        for text in strings(tree(TOOLS["installer"])):
            if re.match(r"\s*(CREATE|ALTER)\s+ROLE", text):
                self.assertNotRegex(text, r"(?i)password", text)
        self.assertEqual(real_install.REAL_NAMES.database, pf.REAL_DATABASE)
        self.assertTrue(real_install.REAL_NAMES.database.startswith("finweb_real"))

    def test_the_installer_is_not_imported_by_any_runtime_module(self):
        for path in sorted(SRC.rglob("*.py")):
            if path.name in ("real_install.py",) or path in ORCHESTRATORS.values():       # the runner names the installer as a child program; `OrchestratorTests` forbids an import
                continue
            text = path.read_text("utf8")
            self.assertNotRegex(text, r"(from|import)\s+persistence(\.|\s+import\s+.*)\s*real_install\b|persistence\.real_install", str(path))

    def test_the_test_provisioner_and_the_test_kits_do_not_import_the_real_installer(self):
        for path in sorted(HERE.glob("*.py")):
            if path.name.startswith("test_real_preflight") or path.name.startswith("test_postgres_real_preflight") or path.name.startswith("test_preflight") \
                    or path.name == "test_r8_guide.py":        # the runner's test types out the runbook's command lines, which name the installer's module
                continue
            self.assertNotRegex(path.read_text("utf8"), r"persistence\.real_install|import real_install|persistence import [^\n]*\breal_install\b", path.name)


#: The file reads each tool may make, by (tool, enclosing function): the INPUTS named on the command line, and R3's own gateway-file read. Nothing else
#: may read a file (TR6B-M-2: S4 a password from a dotfile, S6 / S6b statements from a text or JSON file).
ALLOWED_FILE_READS = {
    "installer": set(),
    "publisher": {"_read_input", "_install_gateway_body"},
    "identity seed": {"main"},
    "launcher": {"_read_contexts_file"},         # R7: the contexts file named on the command line
    "admission probe": set(),
    "loader window": set(),         # R8: every file it reads (proposal, sidecars, the store) is read in `real_tools.real_inputs`, which `main` calls
    "qualify run": set(),           # R8: likewise; its two outputs are created there and by `qualification.save_proposal`
    "r8 files": set(),              # R8 round 2: likewise (its one output is created in `real_inputs.write_new_file`)
    "start gate": set(),
    "real inputs": {"cut_release", "read_bytes_files", "write_new_file"},     # the store's manifests, the sidecar and proposal files named on the command line, the seed output
}
READ_ATTRIBUTES = ("read_text", "read_bytes", "open", "readlines", "readline", "read", "load", "loads", "fromfile", "loadtxt")


def file_reads(path):
    """[(enclosing function, call text)] for every call that could read a file: `open(...)`, `<x>.read_text()`, `.read_bytes()`, `.open()`, `.read()`,
    `json.load(...)` and the like. `json.loads` of a string is no read, but it is listed; the allow-list is by function."""
    module = tree(path)
    found = []

    def walk(node, function):
        for child in ast.iter_child_nodes(node):
            inside = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else function
            if isinstance(child, ast.Call):
                func = child.func
                if (isinstance(func, ast.Name) and func.id in ("open", "input", "exec", "eval", "compile")) or \
                        (isinstance(func, ast.Attribute) and func.attr in READ_ATTRIBUTES and func.attr not in ("loads",)):
                    found.append((function, ast.unparse(child)[:80]))
            walk(child, inside)
    walk(module, "<module>")
    return found


class FileReadTests(unittest.TestCase):
    def test_no_tool_reads_a_file_except_its_named_inputs(self):
        for name, path in CHECKED.items():
            for function, call in file_reads(path):
                self.assertIn(function, ALLOWED_FILE_READS[name], "%s reads a file in %s: %s" % (name, function, call))

    def test_the_allowed_reads_are_the_command_line_inputs_and_r3s_gateway_file_only(self):
        publisher = tree(TOOLS["publisher"])
        calls = [n for n in ast.walk(publisher) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("_read_input", "_read_evidence")]
        self.assertEqual(sorted((c.func.id, ast.unparse(c.args[0])) for c in calls),
                         [("_read_evidence", "args.evidence_file"), ("_read_evidence", "args.evidence_file"), ("_read_input", "args.proposal"),
                          ("_read_input", "path"), ("_read_input", "path")])
        sidecars = [n for n in ast.walk(publisher) if isinstance(n, ast.comprehension) and ast.unparse(n.iter) == "args.sidecar"]
        self.assertEqual(len(sidecars), 1)
        seed_opens = [n for n in ast.walk(tree(TOOLS["identity seed"])) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"]
        self.assertEqual(sorted(ast.unparse(c.args[0]) for c in seed_opens), ["args.proposal", "args.seed_file"])
        gateway = next(n for n in ast.walk(publisher) if isinstance(n, ast.FunctionDef) and n.name == "_install_gateway_body")
        reads = [ast.unparse(n) for n in ast.walk(gateway) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "read_text"]
        self.assertEqual(reads, ["Path(__file__).with_name(filename).read_text('utf8')"])

    def test_the_checker_sees_the_reviewers_spellings(self):
        for source in ('Path("~/.finweb_publisher").expanduser().read_text()', 'open("grants.json")', 'json.load(fh)',
                       'Path(__file__).with_name("installer_extra.txt").read_text()', 'p.read_bytes()'):
            with self.subTest(source):
                import tempfile
                with tempfile.TemporaryDirectory() as tmp:
                    probe = Path(tmp, "probe.py")
                    probe.write_text("def f():\n    return %s\n" % source)
                    self.assertTrue(file_reads(probe), source)


#: --- TR6B-R-1: the spellings the R6 re-review found passing -------------------------------------------------------------------------------------
DANGEROUS_NAMES = {"environ", "environb", "getenv", "getenvb", "putenv", "execute", "executemany", "executescript", "read_text", "read_bytes", "open",
                   "readlines", "readline", "read", "expanduser", "modules", "__dict__", "__globals__", "__builtins__"}
#: TR7-L-3 added `methodcaller` and `attrgetter` (a statement executed through `operator.methodcaller("execute", s)(conn)`) to the banned calls, and
#: `subprocess`, `operator`, `pty`, `shlex`, `pexpect` and the other ways to run a program (`printenv`) or to name a method by a string to the banned modules.
DANGEROUS_NAMES |= {"methodcaller", "attrgetter"}
BANNED_CALLS = {"setattr", "delattr", "vars", "globals", "locals", "eval", "exec", "compile", "__import__", "breakpoint", "methodcaller", "attrgetter"}
BANNED_MODULES = {"os", "posix", "nt", "importlib", "netrc", "linecache", "fileinput", "ctypes", "runpy", "imp", "pkgutil", "shelve", "pickle", "marshal",
                  "subprocess", "operator", "pty", "shlex", "pexpect", "commands", "popen2", "pipes", "getpass", "keyring"}
EXECUTE_NAMES = ("execute", "executemany", "executescript")


def spelling_violations(module):
    """What the R6 re-review found passing, and the family around it, as strings (empty for a clean module). An AST walk of one parsed module:
      * a reference to `.execute` (or `executemany`/`executescript`) that is not directly CALLED: `run = conn.execute`, `map(conn.execute, ...)`;
      * `sys.modules` in any form; `__dict__`, `__globals__`, `__builtins__`;
      * `getattr` whose name argument is not a string literal, or is a literal naming one of the dangerous attributes;
      * `setattr`, `delattr`, `vars`, `globals`, `locals`, `eval`, `exec`, `compile`, `__import__`;
      * an import of `netrc`, `linecache`, `fileinput`, or of any module in the existing `os`/`importlib` family."""
    found = []
    called = {id(n.func) for n in ast.walk(module) if isinstance(n, ast.Call)}
    for node in ast.walk(module):
        if isinstance(node, ast.Attribute):
            if node.attr in EXECUTE_NAMES and id(node) not in called:
                found.append("line %d: a reference to .%s that is not a direct call" % (node.lineno, node.attr))
            if node.attr in ("modules", "__dict__", "__globals__", "__builtins__"):
                found.append("line %d: .%s" % (node.lineno, node.attr))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_CALLS:
                found.append("line %d: %s()" % (node.lineno, func.id))
            if isinstance(func, ast.Attribute) and func.attr in ("methodcaller", "attrgetter"):
                found.append("line %d: .%s()" % (node.lineno, func.attr))
            if isinstance(func, ast.Name) and func.id == "getattr":
                name = node.args[1] if len(node.args) > 1 else None
                if not (isinstance(name, ast.Constant) and isinstance(name.value, str)) or name.value in DANGEROUS_NAMES:
                    found.append("line %d: getattr with a name that is not a safe literal" % node.lineno)
        elif isinstance(node, ast.Import):
            found += ["line %d: import %s" % (node.lineno, a.name) for a in node.names if a.name.split(".")[0] in BANNED_MODULES]
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in BANNED_MODULES or any(a.name in BANNED_MODULES | set(DANGEROUS_NAMES) for a in node.names):
                found.append("line %d: from %s import %s" % (node.lineno, node.module, ", ".join(a.name for a in node.names)))
        elif isinstance(node, ast.Name) and node.id in EXECUTE_NAMES:
            found.append("line %d: the name %s" % (node.lineno, node.id))
    return found


#: TR7R-L-3. `real_preflight` is held to the same rules as the tools. It legitimately needs five things, each allowed by NAME and by the one function (or
#: the module level) that needs it, and nothing else: the `os` import (path functions; `os.environ` only in `process_environment`), the `subprocess` import
#: (two child runs), the `getpass` import (the prompt), and one `getattr` over a constant tuple in a dataclass. `connect_with_prompt`, the password route of
#: every gated tool, is in none of the lists, so `subprocess`, `os.popen` or any other way to run a program there is a violation.
PREFLIGHT_ALLOWED = {
    ("import os", "<module>"), ("import subprocess", "<module>"), ("import getpass", "terminal_prompt"),
    ("getattr with a name that is not a safe literal", "RoleFact"),
}
#: (module name, attribute) -> the only top-level functions that may use it.
PREFLIGHT_ATTRIBUTE_USE = {
    ("getpass", "getpass"): {"terminal_prompt"},
    ("os", "environ"): {"process_environment"},
    ("os", "path"): {"_same_directory", "_split_socket", "_under", "forbidden_roots"},
    ("os", "sep"): {"_under"},
    ("subprocess", "run"): {"_spawn_child", "installation_sysconfdir"},
    ("subprocess", "SubprocessError"): {"installation_sysconfdir"},
    ("subprocess", "TimeoutExpired"): {"_spawn_child"},
}


#: TR7R4-L-1 (3): the spelling-checked set is every module a gated tool imports from `persistence/`, not only `real_*.py`. Two of them need `os` and get
#: exactly that, by name and function, as `real_preflight` does: `connection` (`os.path.split` in `build_conninfo`) and `migrator` (`os.listdir` in
#: `load_migrations`, the installer's read of the gateway's migration directory).
RESTRICTED_MODULES = {
    "connection": ({("import os", "<module>")}, {("os", "path"): {"build_conninfo"}}),
    "migrator": ({("import os", "<module>")}, {("os", "listdir"): {"load_migrations"}}),
}


def preflight_violations(module, allowed_findings=None, attribute_use=None):
    """What `real_preflight` may not contain: every `spelling_violations` finding that is not in `PREFLIGHT_ALLOWED` for its top-level function, and any
    use of an attribute of `os`, `subprocess`, `getpass`, `sys` (`executable` in `_spawn_child` only) or `operator`/`pty`/`shlex` outside the table.
    The two optional arguments give the same rule to another module with its own allowances (`RESTRICTED_MODULES`)."""
    allowed_findings = PREFLIGHT_ALLOWED if allowed_findings is None else allowed_findings
    attribute_use = PREFLIGHT_ATTRIBUTE_USE if attribute_use is None else attribute_use
    found = []
    for top in module.body:
        name = getattr(top, "name", "<module>")
        for finding in spelling_violations(ast.Module(body=[top], type_ignores=[])):
            text = finding.split(": ", 1)[1]
            if (text, name) not in allowed_findings:
                found.append("%s: %s" % (name, finding))
        for node in ast.walk(top):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in ("os", "subprocess", "getpass", "sys"):
                key = (node.value.id, node.attr)
                if key == ("sys", "executable"):
                    allowed = {"_spawn_child"}
                else:
                    allowed = attribute_use.get(key, set())
                if name not in allowed:
                    found.append("%s: %s.%s outside %s" % (name, key[0], key[1], sorted(allowed)))
            if isinstance(node, ast.Name) and node.id in ("subprocess", "getpass", "os") and not isinstance(node.ctx, ast.Load):
                found.append("%s: the name %s is rebound" % (name, node.id))
    return found


def percent_violations(module):
    """TR6B-R-1 N3c: a statement `'...%s...' % x` that is executed may substitute only an attribute of the validated names (`n.schema`) or an
    `identifier(...)` call (or a tuple of those). A literal with `%` values from anywhere else is not accepted."""
    def valid(operand):
        if isinstance(operand, ast.Tuple):
            return all(valid(e) for e in operand.elts)
        if isinstance(operand, ast.Attribute):
            return isinstance(operand.value, ast.Name) and operand.value.id in ("n", "names")
        return isinstance(operand, ast.Call) and isinstance(operand.func, ast.Name) and operand.func.id == "identifier"
    found = []
    for node in ast.walk(module):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in EXECUTE_NAMES and node.args:
            first = node.args[0]
            if isinstance(first, ast.BinOp) and isinstance(first.op, ast.Mod) and not valid(first.right):
                found.append("line %d: %s" % (node.lineno, ast.unparse(first)[:70]))
    return found


class SpellingTests(unittest.TestCase):
    #: Each source is one spelling that passed the R6 static test (TECH_REVIEW "R6 re-review", N-ids) or a neighbour of one. The checker must flag it.
    MUTANTS = {
        "N4 list(map(conn.execute, ...))": "def f(conn, extra):\n    return list(map(conn.execute, extra))\n",
        "N5c run = conn.execute": "def f(conn, extra):\n    run = conn.execute\n    run(extra)\n",
        "N1 getattr(sys.modules[...])": "import sys\ndef f():\n    return getattr(sys.modules['o' + 's'], 'env' + 'iron')\n",
        "sys.modules['os'].environ": "import sys\ndef f():\n    return sys.modules['os'].environ\n",
        "N9 netrc": "import netrc\ndef f():\n    return netrc.netrc().authenticators('finweb')[2]\n",
        "N9b from netrc import": "from netrc import netrc\n",
        "N10 linecache": "import linecache\ndef f():\n    return linecache.getline('x', 1)\n",
        "N11 getattr(path, 'read_'+'text')": "def f(path):\n    return getattr(path, 'read_' + 'text')()\n",
        "N11b getattr literal read_text": "def f(path):\n    return getattr(path, 'read_text')()\n",
        "N12 fileinput": "import fileinput\ndef f():\n    return list(fileinput.input('x'))\n",
        "getattr(conn, 'execute')": "def f(conn, s):\n    getattr(conn, 'execute')(s)\n",
        "getattr with a variable name": "def f(conn, name):\n    return getattr(conn, name)\n",
        "vars()": "def f(o):\n    return vars(o)\n",
        "exec": "def f(s):\n    exec(s)\n",
        "__import__": "def f():\n    return __import__('o' + 's')\n",
        "from os import environ": "from os import environ as E\n",
        "an alias of execute passed on": "def f(conn):\n    return [conn.execute][0]\n",
        # TR7-L-3: the reviewer's G6 and R1, and their neighbours
        "G6 subprocess.check_output printenv": "import subprocess\ndef f():\n    return subprocess.check_output(['printenv', 'FINWEB_REAL_PW'], text=True).strip()\n",
        "from subprocess import run": "from subprocess import run\n",
        "R1 operator.methodcaller": "import operator\ndef f(conn, extra):\n    operator.methodcaller('execute', extra)(conn)\n",
        "from operator import methodcaller": "from operator import methodcaller\ndef f(conn, extra):\n    methodcaller('execute', extra)(conn)\n",
        "attrgetter with a dotted name": "from operator import attrgetter\ndef f(c):\n    return attrgetter('execute')(c)\n",
        "a bare methodcaller call": "def f(m, conn, extra):\n    m.methodcaller('execute', extra)(conn)\n",
        "pty": "import pty\n", "shlex": "import shlex\n", "pexpect": "import pexpect\n", "getpass": "import getpass\n",
    }

    def test_the_checker_flags_every_spelling_the_re_review_found_and_the_ones_around_them(self):
        for label, source in self.MUTANTS.items():
            with self.subTest(label):
                self.assertTrue(spelling_violations(ast.parse(source)), label)

    def test_the_checker_passes_the_plain_forms_the_tools_use(self):
        plain = ("def f(conn, error):\n    conn.execute('SELECT 1')\n    x = getattr(error, 'code', type(error).__name__)\n"
                 "    conn.execute('SET ROLE \"%s\"' % identifier(x))\n    return conn.execute('SELECT 2', (1,)).fetchone()\n")
        self.assertEqual(spelling_violations(ast.parse(plain)), [])

    def test_no_tool_and_no_shared_module_uses_any_of_them(self):
        for name, path in CHECKED.items():
            self.assertEqual(spelling_violations(tree(path)), [], name)

    #: Persistence modules a tool imports that are NOT held to the spelling rules, with the reason. The two provenance modules use getattr only with a
    #: name from a constant tuple. `real_preflight` is NOT excluded any more (TR7R-L-3): it is held to the rules by `preflight_violations`, with the few
    #: things it legitimately needs allowed by name and by function.
    SPELLING_EXCLUDED = {"real_provenance": "getattr over the constant MEMBER_KEYS / WITNESS_KEYS", "real_sidecar": "getattr of a member by a constant key",
                         "real_scope": "a __getattr__ proxy to the scope definition (reached through the closure of imports)"}

    @staticmethod
    def imported_persistence_modules():
        """TR7R4-L-1 (3): EVERY module of `persistence/` that a checked module imports, and those that module imports in turn (the closure), not only `real_*`."""
        found, pending = set(), list(CHECKED.values())
        while pending:
            path = pending.pop()
            for node in ast.walk(tree(path)):
                names = ([node.module or ""] + [a.name for a in node.names]) if isinstance(node, ast.ImportFrom) else (
                    [a.name for a in node.names] if isinstance(node, ast.Import) else [])
                for name in names:
                    for piece in name.split("."):
                        module_path = SRC / "persistence" / (piece + ".py")
                        if module_path.exists() and piece not in found:
                            found.add(piece)
                            pending.append(module_path)
        return found

    def test_the_persistence_modules_a_tool_imports_meet_the_spelling_rules_too(self):
        """TR7-L-3: `CHECKED` named only the tools and the shared gate, so a statement or a credential read placed in a module they import passed. Every
        `persistence/real_*.py` a checked module imports is held to the same spelling rules, apart from the three documented exclusions."""
        modules = self.imported_persistence_modules()
        self.assertTrue(set(self.SPELLING_EXCLUDED) <= modules, "a stale exclusion")
        self.assertIn("real_preflight", modules)
        self.assertTrue({"real_roles", "real_tails", "real_catalog_audit"} <= modules)
        self.assertIn("connection", modules)
        self.assertIn("prompt_route", modules)
        self.assertTrue(set(RESTRICTED_MODULES) <= modules, "a stale restricted module")
        for module in sorted(modules - set(self.SPELLING_EXCLUDED)):
            parsed = tree(SRC / "persistence" / (module + ".py"))
            if module == "real_preflight":
                found = preflight_violations(parsed)
            elif module in RESTRICTED_MODULES:
                found = preflight_violations(parsed, *RESTRICTED_MODULES[module])
            else:
                found = spelling_violations(parsed)
            self.assertEqual(found, [], module)

    def test_real_preflight_meets_the_rules_apart_from_what_it_is_allowed_by_name(self):
        """TR7R-L-3: the module that owns `connect_with_prompt` is no longer excluded."""
        self.assertEqual(preflight_violations(tree(PREFLIGHT)), [])
        self.assertNotIn("real_preflight", self.SPELLING_EXCLUDED)
        source = PREFLIGHT.read_text("utf8")
        for allowed_import, function in (("import getpass", "terminal_prompt"),):
            self.assertIn(allowed_import, source)                    # an allowance that names nothing would be stale
        self.assertEqual({name for (_text, name) in PREFLIGHT_ALLOWED} - {"<module>"}, {"terminal_prompt", "RoleFact"})

    def test_the_reviewers_printenv_mutant_and_the_neighbours_in_real_preflight_fail(self):
        """The mutants are applied to the source TEXT in memory; nothing is written. P1 is the reviewer's: `subprocess.run(["printenv", ...])` in place of the
        prompt in `connect_with_prompt`. The others are the same route by another door, and `subprocess` imported anywhere but where it already is."""
        original = PREFLIGHT.read_text("utf8")
        line = "    password = prompt(user)\n"
        self.assertEqual(original.count(line), 1)
        mutants = {
            "P1 subprocess printenv": line.replace("prompt(user)", 'subprocess.run(["printenv", "FINWEB_REAL_PW"], capture_output=True, text=True).stdout.strip() or prompt(user)'),
            "P2 os.environ": line.replace("prompt(user)", 'os.environ.get("FINWEB_REAL_PW") or prompt(user)'),
            "P3 os.popen": line.replace("prompt(user)", 'os.popen("printenv FINWEB_REAL_PW").read().strip() or prompt(user)'),
            "P4 os.system": line.replace("prompt(user)", "os.system('true') or prompt(user)"),
            "P5 a subprocess import inside connect_with_prompt": "    import subprocess as sp\n" + line.replace("prompt(user)", 'sp.check_output(["printenv", "X"]).decode() or prompt(user)'),
            "P6 from subprocess import": "    from subprocess import check_output\n" + line.replace("prompt(user)", 'check_output(["printenv", "X"]).decode() or prompt(user)'),
            "P7 operator.methodcaller": "    import operator\n" + line.replace("prompt(user)", 'operator.methodcaller("strip")(prompt(user))'),
            "P8 getpass outside the prompt": line.replace("prompt(user)", 'getpass.getpass() or prompt(user)'),
        }
        self.assertEqual(preflight_violations(ast.parse(original)), [])
        for label, replacement in mutants.items():
            with self.subTest(label):
                mutated = original.replace(line, replacement)
                self.assertNotEqual(mutated, original, label)
                self.assertTrue(preflight_violations(ast.parse(mutated)), label)
        # a subprocess import in another function, and a use in a function that does not run a child
        extra = original + "\n\ndef elsewhere():\n    import subprocess\n    return subprocess.run(['true'])\n"
        self.assertTrue(preflight_violations(ast.parse(extra)))
        extra_use = original + "\n\ndef elsewhere():\n    return subprocess.run(['true'])\n"
        self.assertTrue(preflight_violations(ast.parse(extra_use)))

    def test_a_new_helper_module_with_the_reviewers_statement_would_fail_this_test(self):
        helper = "import operator\nfrom persistence.real_extra import EXTRA_STATEMENTS\ndef run(conn):\n    for s in EXTRA_STATEMENTS:\n        operator.methodcaller('execute', s)(conn)\n"
        self.assertTrue(spelling_violations(ast.parse(helper)))

    def test_an_executed_percent_statement_substitutes_only_validated_names(self):
        for label, source in {"N3c a name from outside": "def f(conn, extra):\n    for e in extra:\n        conn.execute('%s' % e)\n",
                              "a call": "def f(conn):\n    conn.execute('X %s' % read())\n",
                              "a tuple with an outside name": "def f(conn, n, e):\n    conn.execute('X %s %s' % (n.schema, e))\n"}.items():
            with self.subTest(label):
                self.assertTrue(percent_violations(ast.parse(source)), label)
        good = "def f(conn, n):\n    conn.execute('X %s %s' % (n.schema, n.owner))\n    conn.execute('Y \"%s\"' % identifier(n.schema))\n"
        self.assertEqual(percent_violations(ast.parse(good)), [])
        self.assertEqual(percent_violations(tree(TOOLS["installer"])), [])


def is_program(path):
    """True for a module that is a command-line program: it builds an `ArgumentParser`, reads `sys.argv`, has a `__main__` guard or defines `main`."""
    for node in ast.walk(ast.parse(path.read_text("utf8"))):
        if isinstance(node, ast.Call) and ast.unparse(node.func).split(".")[-1] == "ArgumentParser":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "argv" and isinstance(node.value, ast.Name) and node.value.id == "sys":
            return True
        if isinstance(node, ast.Compare) and ast.unparse(node.left) == "__name__" and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in node.comparators):
            return True
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return True
    return False


GATEWAY_MODULES = ("real_mode_routes", "real_launcher", "real_workspace_store", "real_tool_gate", "real_preflight", "real_install", "real_roles",
                   "real_workspace_context", "real_tails", "real_service", "real_catalog_audit")


def is_launcher(path, parsed=None):
    """TR7-L-1: a module that serves or starts something without being a command-line program by the forms of `is_program`: it imports `uvicorn`, or it
    defines a module-level `app` (how `web_api.dev`, `account_dev` and `guarded_dev` are served: `uvicorn web_api.account_dev:app`)."""
    parsed = parsed if parsed is not None else ast.parse(path.read_text("utf8"))
    for node in parsed.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "app" for t in node.targets):
            return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "app":
            return True
    for node in ast.walk(parsed):
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "uvicorn" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "uvicorn":
            return True
    return False


#: TR7R-L-2. The modules that SERVE or START the real-mode app or decide its start. A module that imports one of them is a candidate whatever its shape: the
#: import is the decisive signal, the shape is not (a `uvicorn --factory web_api.real_factory:build` builder has no `app`, no parser and no `main`; an ASGI
#: object named `application` has no `app`). The two importers today are the launcher and the admission probe, both listed in `TOOLS`.
LAUNCH_MODULES = ("real_mode_routes", "real_launcher", "real_tool_gate")


def imports_launch_modules(parsed):
    for node in ast.walk(parsed):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""] + [a.name for a in node.names]
        if any(piece in LAUNCH_MODULES for name in names for piece in name.split(".")):
            return True
    return False


def is_real_related(path, src_root, parsed=None):
    """TR7-L-1: a module is a REAL tool candidate by where it is or what it touches: a path component or a file name that says `real`, `loader` or
    `launcher`, or an import of one of the real gateway's modules (`GATEWAY_MODULES`; `performance_tools.real_slice`, about historical files, is not one)."""
    parts = path.relative_to(src_root).with_suffix("").parts
    if any(re.search(r"real|loader|launcher|window", part) for part in parts):
        return True
    parsed = parsed if parsed is not None else ast.parse(path.read_text("utf8"))
    for node in ast.walk(parsed):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""] + [a.name for a in node.names]
        if any(piece in GATEWAY_MODULES for name in names for piece in name.split(".")):
            return True
    return False


def discover(src_root):
    """Every command-line program or launcher that is a candidate real tool, anywhere under `src` (subpackages included): a program by `is_program` or
    a launcher by `is_launcher`, which is also real-related by `is_real_related` (TR7-L-1; it was four named places, without recursion, and missed a
    module-level `app` launcher, `real_tools/loader/__main__.py` and `marketdata/real_window_loader.py`). A later tool is found the day it exists."""
    found = set()
    for path in src_root.rglob("*.py"):
        parsed = ast.parse(path.read_text("utf8"))
        if (is_program(path) or is_launcher(path, parsed) or imports_launch_modules(parsed)) and is_real_related(path, src_root, parsed):
            found.add(path)
    return found


class DiscoveryTests(unittest.TestCase):
    """TR6C-3: the static test covers every real tool by DISCOVERY, not by a list someone has to remember. R6's install plan says a future loader tool
    "is refused by the same static test"; this is what makes that true."""

    def test_every_command_line_program_in_the_real_tool_places_is_a_tool_of_this_test(self):
        unlisted = sorted(str(p.relative_to(SRC)) for p in discover(SRC) - set(TOOLS.values()) - set(ORCHESTRATORS.values()) - set(HTTP_TOOLS.values()))
        self.assertEqual(unlisted, [], "a new command-line program must be added to TOOLS, ALLOWED_OPTIONS and PARSERS (and then meets every check here)")

    def test_every_listed_tool_is_found_by_the_discovery(self):
        self.assertEqual(set(TOOLS.values()) - discover(SRC), set(), "a stale entry in TOOLS")
        self.assertEqual(set(ORCHESTRATORS.values()) - discover(SRC), set(), "a stale entry in ORCHESTRATORS")
        self.assertEqual(set(HTTP_TOOLS.values()) - discover(SRC), set(), "a stale entry in HTTP_TOOLS")
        self.assertEqual(set(TOOLS.values()) & set(ORCHESTRATORS.values()), set())
        self.assertEqual((set(TOOLS.values()) | set(ORCHESTRATORS.values())) & set(HTTP_TOOLS.values()), set())

    def test_a_new_tool_in_the_places_is_found_and_would_fail_until_it_is_listed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for sub, name, source in (("real_tools", "loader_window.py", "import argparse\nparser = argparse.ArgumentParser()\n"),
                                      ("persistence", "real_other_tool.py", "import sys\nPASSWORD = sys.argv[1]\n"),
                                      ("web_api", "real_second_launcher.py", "def main():\n    pass\n"),
                                      ("web_api", "dev_launcher.py", "if __name__ == '__main__':\n    pass\n"),
                                      # TR7-L-1: the reviewer's G4 (a module-level `app` served by uvicorn, no parser and no main), G5 (a subpackage's
                                      # __main__) and G6 (a program in another directory whose name says real), and two more spellings of G4.
                                      ("web_api", "real_dev.py", "import os\nfrom web_api.real_mode_routes import create_real_mode_app\n"
                                                                 "PW = os.environ['FINWEB_REAL_PASSWORD']\napp = create_real_mode_app(PW)\n"),
                                      ("web_api", "serve_it.py", "from web_api.real_mode_routes import make\napp = make()\n"),
                                      ("web_api", "any_name.py", "import uvicorn\nfrom persistence import real_workspace_store\nuvicorn.run('x:y')\n"),
                                      ("web_api", "fictional_dev.py", "import uvicorn\nuvicorn.run('x:y')\n"),     # the fictional app's dev servers: no tie to the real gateway
                                      ("real_tools/loader", "__main__.py", "import argparse\nargparse.ArgumentParser().parse_args()\n"),
                                      ("marketdata", "real_window_loader.py", "import argparse\nargparse.ArgumentParser().parse_args()\n"),
                                      # TR7R-L-2: the reviewer's two files (a `uvicorn --factory` builder and an ASGI object named `application`), a builder
                                      # whose name says nothing about real, and a module that only imports the start gate
                                      ("web_api", "real_factory.py", "import os\nfrom web_api.real_mode_routes import create_real_mode_app\n"
                                                                     "def build():\n    return create_real_mode_app(os.environ['FINWEB_REAL_PW'])\n"),
                                      ("web_api", "real_asgi.py", "from web_api.real_mode_routes import create_real_mode_app\napplication = create_real_mode_app(None)\n"),
                                      ("web_api", "any_factory.py", "from web_api import real_launcher\ndef build():\n    return real_launcher\n"),
                                      ("real_tools", "gate_user.py", "from persistence import real_tool_gate\nVALUE = real_tool_gate\n"),
                                      ("web_api", "plain_factory.py", "def build():\n    return object()\n"),
                                      ("real_tools", "library.py", "def helper():\n    return 1\n"),
                                      ("marketdata", "plain_tool.py", "import argparse\nargparse.ArgumentParser().parse_args()\n"),
                                      ("web_api", "plain_app.py", "app = object()\n")):
                (root / sub).mkdir(parents=True, exist_ok=True)
                (root / sub / name).write_text(source)
            found = {str(p.relative_to(root)) for p in discover(root)}
            self.assertEqual(found, {"real_tools/loader_window.py", "persistence/real_other_tool.py", "web_api/real_second_launcher.py",
                                     "web_api/dev_launcher.py", "web_api/real_dev.py", "web_api/serve_it.py", "web_api/any_name.py",
                                     "real_tools/loader/__main__.py", "marketdata/real_window_loader.py", "web_api/real_factory.py", "web_api/real_asgi.py",
                                     "web_api/any_factory.py", "real_tools/gate_user.py"})
            self.assertTrue(discover(root) - set(TOOLS.values()))        # none of them is listed, so the first test above would fail for each


#: TR7R2-L-1. The attribute allow-list says WHICH functions may use `os.environ` or `subprocess`, not which functions CALL which, so a call to
#: `process_environment()`, `_read(...)` or `_spawn_child(...)` added to `connect_with_prompt` after the prompt line passed. The functions that turn the
#: prompt's answer into a connection are therefore pinned as normalized source (docstrings dropped; comments and layout do not matter): the prompt, the
#: connection, the two wrappers that remember an answer, and the string builder the password goes through. Any change is a reviewed change to this table.
PASSWORD_PATH = {
    ("persistence/real_preflight.py", "terminal_prompt"):
        "def terminal_prompt(role):\n    import getpass\n    return getpass.getpass('Password for role %s: ' % role)",
    ("persistence/real_preflight.py", "connect_with_prompt"):
        "def connect_with_prompt(socket, database, user, *, require_auth, prompt, autocommit=False):\n    import psycopg\n    password = prompt(user)\n    params = {'password': password, 'passfile': '/dev/null', 'sslmode': 'disable', 'gssencmode': 'disable', 'connect_timeout': '10', 'application_name': 'finweb_real_tool'}\n    if require_auth:\n        params['require_auth'] = require_auth\n    return psycopg.connect(conninfo_with(build_conninfo(socket=socket, dbname=database, user=user), **params), autocommit=autocommit)",
    ("web_api/real_launcher.py", "remembered"):
        "def remembered(prompt):\n    answers = {}\n\n    def ask(role):\n        if role not in answers:\n            answers[role] = prompt(role)\n        return answers[role]\n    return ask",
    ("persistence/real_install.py", "_remembered"):
        "def _remembered(prompt):\n    cache = {}\n\n    def ask(role):\n        if role not in cache:\n            cache[role] = prompt(role)\n        return cache[role]\n    return ask",
    ("persistence/connection.py", "conninfo_with"):
        "def conninfo_with(base: str, **params: str) -> str:\n    return base + ''.join((f' {k}={_quote(str(v))}' for k, v in params.items()))",
    # TR7R3-L-1: `_quote` sees every value, the password included (a logging mutant wrote it to a file); `build_conninfo` chooses the server (a mutant
    # took the socket directory from the environment, so the REAL gate would judge another cluster); `is_reserved_real_name` and the two constants
    # decide REAL from the NAME and what a socket path means. `build_conninfo`'s only callees are `_quote`, `os.path.split` and `_SOCKET_NAME.match`.
    ("persistence/connection.py", "_quote"):
        'def _quote(value: str) -> str:\n    return "\'" + value.replace(\'\\\\\', \'\\\\\\\\\').replace("\'", "\\\\\'") + "\'"',
    ("persistence/connection.py", "build_conninfo"):
        "def build_conninfo(*, dbname: str, user: str, socket: Optional[str]=None, host: Optional[str]=None, port: Optional[str]=None) -> str:\n    if socket:\n        directory, base = os.path.split(socket)\n        match = _SOCKET_NAME.match(base)\n        if not directory or match is None:\n            raise ValueError(f'socket path must look like <dir>/.s.PGSQL.<port>, got {socket!r}')\n        host, port = (directory, match.group(1))\n    if not host or not port:\n        raise ValueError('either socket, or both host and port, must be given')\n    parts: List[Tuple[str, str]] = [('host', host), ('port', str(port)), ('dbname', dbname), ('user', user)]\n    return ' '.join((f'{k}={_quote(v)}' for k, v in parts))",
    ("persistence/connection.py", "is_reserved_real_name"):
        "def is_reserved_real_name(name: object) -> bool:\n    return isinstance(name, str) and name.startswith(RESERVED_REAL_PREFIX)",
}
#: Module-level statements of `connection.py` on the same path (the constants those functions read).
CONNECTION_CONSTANTS = {"RESERVED_REAL_PREFIX": "RESERVED_REAL_PREFIX = 'finweb_real'",
                        "_SOCKET_NAME": "_SOCKET_NAME = re.compile('^\\\\.s\\\\.PGSQL\\\\.(\\\\d+)$')"}

#: TR7R3-L-1. HOW each gated tool chooses its prompt. Every statement (and every function signature or test) of the tool that names `prompt`, `ask`,
#: `remembered`, `terminal_prompt` or `connect_with_prompt`, per top-level function, pinned as normalized source. The reviewer's mutant replaced the
#: selection expression in `real_launcher.main` with a reader of a file beside the contexts file; no file reader, environment read or other source can
#: now stand in for `pf.terminal_prompt` without changing a pinned statement. A new statement that touches the prompt is a reviewed change to this table.
PROMPT_STATEMENTS = {
    "web_api/real_launcher.py": [
        ('remembered', 'def remembered(prompt)'), ('ask', 'answers[role] = prompt(role)'), ('remembered', 'return ask'),
        ('default_connect', 'def default_connect(args, user, prompt, autocommit)'),
        ('default_connect', 'conn = pf.connect_with_prompt(args.socket, args.database, user, require_auth=pf.GATED_REQUIRE_AUTH, prompt=prompt, autocommit=autocommit)'),
        ('make_account_store', 'def make_account_store(args, connect, prompt)'),
        ('make_account_store', 'return WebAccountStore(None, args.schema, opener=lambda: connect(args, args.account_user, prompt, True))'),
        ('build', 'def build(args, connect, prompt, pins, account_store)'), ('build', 'executor = lambda: connect(args, args.user, prompt, True)'),
        ('main', 'def main(argv=None, *, connect=None, prompt=None, serve=None, out=None)'), ('main', 'prompt = remembered(prompt or pf.terminal_prompt)'),
        ('main', 'conn = connect(args, args.user, prompt, True)'), ('main', 'account_store = make_account_store(args, connect, prompt)'),
        ('main', 'app = build(args, connect, prompt, pins, account_store)')],
    "real_tools/admission_probe.py": [
        ('_default_connect', 'def _default_connect(args, prompt)'),
        ('_default_connect', 'conn = pf.connect_with_prompt(args.socket, args.database, args.user, require_auth=pf.GATED_REQUIRE_AUTH, prompt=prompt, autocommit=True)'),
        ('main', 'def main(argv=None, *, connect=None, out=None, prompt=None)'), ('main', 'conn = connect(args, prompt or pf.terminal_prompt)')],
    "real_tools/loader_window.py": [
        ('_default_connect', 'def _default_connect(args, prompt)'),
        ('_default_connect', 'conn = pf.connect_with_prompt(args.socket, args.database, args.user, require_auth=pf.GATED_REQUIRE_AUTH, prompt=prompt, autocommit=True)'),
        ('main', 'def main(argv=None, *, connect=None, out=None, prompt=None, build=None)'), ('main', 'conn = connect(args, prompt or pf.terminal_prompt)')],
    "persistence/real_install.py": [
        ('_remembered', 'def _remembered(prompt)'), ('ask', 'cache[role] = prompt(role)'), ('_remembered', 'return ask'),
        ('main', 'def main(argv=None, *, prompt=None, out=None, connect=None)'), ('main', 'ask = _remembered(prompt or pf.terminal_prompt)'),
        ('connect', 'return pf.connect_with_prompt(socket, database, user, require_auth=pf.GATED_REQUIRE_AUTH, prompt=ask, autocommit=True)')],
    "real_tools/identity_seed.py": [
        ('main', 'def main(argv=None, *, prompt=None, out=None, connect=None)'),
        ('main', 'conn = pf.connect_with_prompt(args.socket, pf.REAL_DATABASE, args.user, require_auth=pf.GATED_REQUIRE_AUTH, prompt=prompt or pf.terminal_prompt, autocommit=True)')],
    "persistence/real_workspace_store.py": [
        ('_default_connect', 'def _default_connect(prompt)'),
        ('connect', 'return pf.connect_with_prompt(a.socket, a.database, a.user, require_auth=require, prompt=prompt)'),
        ('main', 'def main(argv=None, *, connect=None, out=None, prompt=None)'), ('main', 'connect = _default_connect(prompt or pf.terminal_prompt)')],
}
PROMPT_NAMES = {"prompt", "ask", "remembered", "_remembered", "terminal_prompt", "connect_with_prompt"}
_COMPOUND = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.If, ast.For, ast.While, ast.Try, ast.With)


def prompt_statements(module):
    """(top-level function, normalized text) of every statement that names a prompt name, every signature that takes one and every `if`/`while` test."""
    def mentions(node):
        return any((isinstance(n, ast.Name) and n.id in PROMPT_NAMES) or (isinstance(n, ast.Attribute) and n.attr in PROMPT_NAMES)
                   or (isinstance(n, ast.arg) and n.arg in PROMPT_NAMES) for n in ast.walk(node))
    out = []

    def visit(node, scope):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(a.arg in PROMPT_NAMES for a in child.args.args + child.args.kwonlyargs):
                    out.append((child.name, "def %s(%s)" % (child.name, ast.unparse(child.args))))
                visit(child, child.name)
            elif isinstance(child, (ast.If, ast.While)):
                if mentions(child.test):
                    out.append((scope, "test: " + ast.unparse(child.test)))
                visit(child, scope)
            elif isinstance(child, _COMPOUND):
                visit(child, scope)
            elif isinstance(child, ast.stmt):
                if mentions(child) and not (isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant)):
                    out.append((scope, ast.unparse(child)))
    visit(module, "<module>")
    return out
#: Functions of `real_preflight` that read the environment, a file or a child process. A tool, or the shared gate, may not name them: it would be a way to
#: ask for a stored credential through a function that is itself allowed to touch the environment.
#: (`installation_sysconfdir` is not listed: the installer passes it to the preflight as a directory name; it runs `pg_config` and returns a path.)
PREFLIGHT_PRIVATE_READERS = {"process_environment", "process_home", "_spawn_child", "_read", "scan_stored_credentials", "Prober"}


#: TR7R4-L-1 (2). Each gated tool's `main` IN FULL, every tool-module function on the path from `main` to the connection (the connect defaults and what builds
#: or remembers the prompt), and the module's import statements, pinned as the SHA-256 (first 20 hex digits) of their normalized source (docstrings
#: dropped; comments and layout do not matter). A swapped import (a look-alike preflight module) or a wrapped `connect`/`prompt` in `main` changes a pin.
#: The same is done for `prompt_route`, `real_preflight`, `connection` and the shared gate (imports only for the last three: their functions are pinned
#: above). WHEN A PINNED FUNCTION CHANGES LEGITIMATELY LATER, THE PIN MUST BE UPDATED DELIBERATELY, in the same change and with the reviewer told:
#: `FullPinTests.digests(relative)` returns the new values (print them from a scratch script; do not copy a value from a failing assertion unread).
FULL_PINS = {
    'web_api/real_launcher.py': ('350a627406a391d9eea6', {'main': '48e883b4d9d0c4195695', 'default_connect': '0c53bce56af0c5662b69', 'remembered': 'e31dfc3fd79ba8de1619', 'make_account_store': '1982f5da01bb33e5f3de', 'build': '580610a9aba60708bc13'}),
    'real_tools/admission_probe.py': ('1a4468dd6d14a8ca8e98', {'main': 'eea8757bb15e3f1508e2', '_default_connect': '25ff582b882e537838cc'}),
    'persistence/real_install.py': ('5f75131174e4c7ec8846', {'main': '944c737738b2c51bb88c', '_remembered': '2ff0c0a65f50c8633241'}),
    'real_tools/identity_seed.py': ('3195f96adc8cb1352a7f', {'main': 'd45547a0a7671b0f4004'}),
    'real_tools/loader_window.py': ('0d8f580fab9553a91037', {'main': '45d8d86d7550b5c2cc0d', '_default_connect': 'adcc132b0b9f54f68a32'}),
    'real_tools/qualify_run.py': ('9a31a6c11f00203f0c45', {'main': 'd78df1977c7d6d119502'}),
    'real_tools/r8_files.py': ('29f347959f854225b567', {'main': 'd39816691160e0f3aa3a'}),
    'persistence/real_workspace_store.py': ('2ec0e29f12994e4e9461', {'main': 'ec02612721802b76bae0', '_default_connect': 'e8a1790d70cdf9010458'}),
    'persistence/prompt_route.py': ('3777af2391df46008b95', {'require_genuine': 'da0a9204aee2b680eec1'}),
    'persistence/real_preflight.py': ('cd6eab08071f1bd57fc4', {}),
    'persistence/connection.py': ('9da7b1051cfdd1a77b7a', {}),
    'persistence/real_tool_gate.py': ('cab5a5f230e6075d3e0f', {}),
}
#: Calls that could read a file in the persistence modules the tools import (directly or through the closure): by module, the functions that may.
#: Anything else (a look-alike prompt module that opens a dotfile) is a violation. `web_account_store.get_portfolio` is a `.read(` on a workspace store.
PERSISTENCE_FILE_READS = {
    "migrator": {"load_migrations", "read_manifest"}, "real_catalog_audit": {"_declared_functions", "_declared_definitions", "migration_guard_definitions"},
    "real_preflight": {"_read"}, "real_workspace_store": {"_install_gateway_body", "_read_input"}, "web_account_store": {"get_portfolio"},
}


def import_text(module):
    """Every import statement of a parsed module, in walk order, as normalized source (function-level imports included)."""
    return "\n".join(ast.unparse(n) for n in ast.walk(module) if isinstance(n, (ast.Import, ast.ImportFrom)))


def digest(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:20]


def pinned_text(module, name):
    node = next(n for n in ast.walk(module) if isinstance(n, ast.FunctionDef) and n.name == name)
    node.body = [b for b in node.body if not (isinstance(b, ast.Expr) and isinstance(b.value, ast.Constant))]
    return ast.unparse(node)


class PasswordPathTests(unittest.TestCase):
    def test_the_functions_that_turn_the_prompts_answer_into_a_connection_are_pinned(self):
        for (relative, name), expected in PASSWORD_PATH.items():
            self.assertEqual(pinned_text(tree(SRC / relative), name), expected, "%s: %s" % (relative, name))

    def test_no_tool_and_not_the_gate_names_a_function_that_reads_the_environment_a_file_or_a_child(self):
        for name, path in CHECKED.items():
            for node in ast.walk(tree(path)):
                used = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
                if used is None and isinstance(node, ast.ImportFrom):
                    used = next((a.name for a in node.names if a.name in PREFLIGHT_PRIVATE_READERS), None)
                self.assertNotIn(used, PREFLIGHT_PRIVATE_READERS, "%s names %s" % (name, used))

    def test_how_each_tool_chooses_its_prompt_is_pinned(self):
        for relative, expected in PROMPT_STATEMENTS.items():
            self.assertEqual(prompt_statements(tree(SRC / relative)), expected, relative)
        # a tool that touches a prompt name and is not in the table would be new and unpinned
        pinned = {SRC / relative for relative in PROMPT_STATEMENTS}
        for name, path in TOOLS.items():
            if prompt_statements(tree(path)):
                self.assertIn(path, pinned, "%s names a prompt and is not pinned" % name)
        for name, expected in CONNECTION_CONSTANTS.items():
            node = next(n for n in tree(SRC / "persistence" / "connection.py").body
                        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == name for t in n.targets))
            self.assertEqual(ast.unparse(node), expected, name)

    def test_the_reviewers_tr7r3_mutants_and_one_per_new_link_fail(self):
        """Each mutant is applied to the source TEXT in memory; the pin of the link it touches must then differ. Nothing is written."""
        def changed_prompt(relative, old, new):
            text = (SRC / relative).read_text("utf8")
            self.assertEqual(text.count(old), 1, (relative, old))
            return prompt_statements(ast.parse(text.replace(old, new))) != PROMPT_STATEMENTS[relative]

        def changed_function(relative, name, old, new):
            text = (SRC / relative).read_text("utf8")
            self.assertEqual(text.count(old), 1, (relative, old))
            return pinned_text(ast.parse(text.replace(old, new)), name) != PASSWORD_PATH[(relative, name)]

        reader = "(lambda role: open(args.contexts_file + '.pw').read().strip())"
        # the reviewer's three
        self.assertTrue(changed_prompt("web_api/real_launcher.py", "remembered(prompt or pf.terminal_prompt)", "remembered(prompt or %s)" % reader))
        self.assertTrue(changed_function("persistence/connection.py", "_quote", '    return "\'" + value.replace', "    open('/tmp/x', 'a').write(value)\n    return \"'\" + value.replace"))
        self.assertTrue(changed_function("persistence/connection.py", "build_conninfo", "        directory, base = os.path.split(socket)\n",
                                         "        directory, base = os.path.split(socket)\n        directory = os.environ.get('FINWEB_SOCKET_DIR', directory)\n"))
        # one per newly pinned link
        self.assertTrue(changed_prompt("real_tools/admission_probe.py", "connect(args, prompt or pf.terminal_prompt)", "connect(args, prompt or %s)" % reader))
        self.assertTrue(changed_prompt("persistence/real_install.py", "_remembered(prompt or pf.terminal_prompt)", "_remembered(prompt or %s)" % reader))
        self.assertTrue(changed_prompt("real_tools/identity_seed.py", "prompt=prompt or pf.terminal_prompt", "prompt=prompt or %s" % reader))
        self.assertTrue(changed_prompt("persistence/real_workspace_store.py", "_default_connect(prompt or pf.terminal_prompt)", "_default_connect(prompt or %s)" % reader))
        self.assertTrue(changed_prompt("web_api/real_launcher.py", "answers[role] = prompt(role)", "answers[role] = prompt(role) or open('x').read()"))
        self.assertTrue(changed_prompt("web_api/real_launcher.py", "    prompt = remembered(prompt or pf.terminal_prompt)\n",
                                       "    prompt = remembered(prompt or pf.terminal_prompt)\n    prompt = (lambda inner: (lambda role: inner(role) or open('x').read()))(prompt)\n"))
        self.assertTrue(changed_function("persistence/connection.py", "is_reserved_real_name", "name.startswith(RESERVED_REAL_PREFIX)", "name.startswith(RESERVED_REAL_PREFIX) and False"))
        text = (SRC / "persistence" / "connection.py").read_text("utf8")
        self.assertNotEqual(ast.unparse(next(n for n in ast.parse(text.replace('RESERVED_REAL_PREFIX = "finweb_real"', 'RESERVED_REAL_PREFIX = "finweb_x"')).body
                                             if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "RESERVED_REAL_PREFIX")), CONNECTION_CONSTANTS["RESERVED_REAL_PREFIX"])

    def test_the_reviewers_three_additions_after_the_prompt_line_and_the_neighbours_fail(self):
        """Applied to the source text in memory, IN ADDITION to the prompt line, which stays. Nothing is written."""
        original = PREFLIGHT.read_text("utf8")
        anchor = "    password = prompt(user)\n"
        self.assertEqual(original.count(anchor), 1)
        key = ("persistence/real_preflight.py", "connect_with_prompt")
        mutants = {
            "R1 process_environment().get": anchor + '    password = process_environment().get("FINWEB_REAL_PW") or password\n',
            "R2 _read(Path(process_home()) / ...)": anchor + '    password = _read(Path(process_home()) / ".finweb_real_pw") or password\n',
            "R3 _spawn_child(...)": anchor + '    password = _spawn_child("x", {}, 1) or password\n',
            "R4 an assignment before the prompt": '    seed = process_environment()\n' + anchor,
            "R5 a changed parameter": anchor + '    params = None\n',
        }
        self.assertEqual(pinned_text(ast.parse(original), key[1]), PASSWORD_PATH[key])
        for label, replacement in mutants.items():
            with self.subTest(label):
                mutated = original.replace(anchor, replacement)
                self.assertNotEqual(mutated, original, label)
                self.assertNotEqual(pinned_text(ast.parse(mutated), key[1]), PASSWORD_PATH[key], label)
        for label, old, new in (("the prompt itself", "    return getpass.getpass(", "    return process_environment().get('X') or getpass.getpass("),
                                ("the prompt's import", "    import getpass\n    return getpass.getpass(", "    import getpass\n    import subprocess\n    return getpass.getpass(")):
            with self.subTest(label):
                mutated = original.replace(old, new, 1)
                self.assertNotEqual(mutated, original, label)
                self.assertNotEqual(pinned_text(ast.parse(mutated), "terminal_prompt"), PASSWORD_PATH[("persistence/real_preflight.py", "terminal_prompt")], label)


class FullPinTests(unittest.TestCase):
    @staticmethod
    def digests(relative, text=None):
        """(imports digest, {function: digest}) of the module at `relative` (or of `text` in its place), as `FULL_PINS` stores them."""
        module = ast.parse(text if text is not None else (SRC / relative).read_text("utf8"))
        return digest(import_text(module)), {name: digest(pinned_text(ast.parse(ast.unparse(module)), name)) for name in FULL_PINS[relative][1]}

    def test_each_gated_tools_main_the_connect_path_and_the_imports_are_pinned_in_full(self):
        for relative, expected in FULL_PINS.items():
            self.assertEqual(self.digests(relative), expected, relative)
        self.assertEqual({SRC / r for r in FULL_PINS} >= set(TOOLS.values()), True)       # every gated or owner tool is in the table

    def test_y1_a_look_alike_preflight_module_and_y2_a_wrapped_connect_fail(self):
        """The reviewer's two mutants, on the source text in memory. Y1: the launcher imports a look-alike module instead of `real_preflight`, every pinned
        statement unchanged. Y2: `connect = connect or default_connect` replaced by a wrapper that gives `default_connect` a file-reading prompt."""
        relative = "web_api/real_launcher.py"
        original = (SRC / relative).read_text("utf8")
        y1 = original.replace("from persistence import real_preflight as pf", "from persistence import prompting as pf")
        y2 = original.replace("    connect = connect or default_connect\n",
                              "    connect = connect or (lambda a, u, p, c: default_connect(a, u, lambda role: open(args.contexts_file + '.pw').read().strip(), c))\n")
        for label, mutated in (("Y1", y1), ("Y2", y2)):
            self.assertNotEqual(mutated, original, label)
            self.assertNotEqual(self.digests(relative, mutated), FULL_PINS[relative], label)
        self.assertNotEqual(self.digests(relative, y1)[0], FULL_PINS[relative][0])        # Y1 changes the import pin
        self.assertNotEqual(self.digests(relative, y2)[1]["main"], FULL_PINS[relative][1]["main"])     # Y2 changes the main pin
        # the prompt statements of Y1 are unchanged: the older pin alone did not see it
        self.assertEqual(prompt_statements(ast.parse(y1)), PROMPT_STATEMENTS[relative])

    def test_one_mutant_per_added_defence_changes_its_pin(self):
        def changes(relative, old, new, *, function=None, imports=False):
            text = (SRC / relative).read_text("utf8")
            self.assertEqual(text.count(old), 1, (relative, old))
            now = self.digests(relative, text.replace(old, new))
            if imports:
                return now[0] != FULL_PINS[relative][0]
            return now[1][function] != FULL_PINS[relative][1][function]
        reader = "lambda role: open('x').read()"
        # each gated tool's main: a wrapped connect or prompt
        self.assertTrue(changes("real_tools/admission_probe.py", "    connect = connect or _default_connect\n",
                                "    connect = connect or (lambda a, p: _default_connect(a, %s))\n" % reader, function="main"))
        self.assertTrue(changes("persistence/real_install.py", "    ask = _remembered(prompt or pf.terminal_prompt)\n",
                                "    ask = _remembered(prompt or pf.terminal_prompt)\n    ask = (lambda inner: (lambda role: open('x').read() or inner(role)))(ask)\n", function="main"))
        self.assertTrue(changes("real_tools/identity_seed.py", "            conn = connect(args.socket, pf.REAL_DATABASE, args.user)\n",
                                "            conn = connect(args.socket, pf.REAL_DATABASE, args.user)\n            open('x').read()\n", function="main"))
        self.assertTrue(changes("persistence/real_workspace_store.py", "        connect = _default_connect(prompt or pf.terminal_prompt)\n",
                                "        connect = _default_connect(prompt or pf.terminal_prompt)\n        connect = (lambda inner: (lambda a: inner(a)))(connect)\n", function="main"))
        # the connect defaults and the prompt builders on the path
        self.assertTrue(changes("web_api/real_launcher.py", "prompt=prompt, autocommit=autocommit)", "prompt=(lambda role: open('x').read()), autocommit=autocommit)", function="default_connect"))
        self.assertTrue(changes("real_tools/admission_probe.py", "prompt=prompt, autocommit=True)", "prompt=(lambda role: open('x').read()), autocommit=True)", function="_default_connect"))
        self.assertTrue(changes("persistence/real_workspace_store.py", "require_auth=require, prompt=prompt)", "require_auth=require, prompt=(lambda role: open('x').read()))", function="_default_connect"))
        # the imports of the modules the password passes through, and of the runtime check itself
        self.assertTrue(changes("persistence/real_preflight.py", "import psycopg\n    password = prompt(user)", "import psycopg as psycopg\n    from persistence import prompting as _x\n    password = prompt(user)", imports=True))
        self.assertTrue(changes("persistence/prompt_route.py", "from persistence import real_preflight as _genuine", "from persistence import prompting as _genuine", imports=True))
        self.assertTrue(changes("persistence/prompt_route.py", "    if module is not _genuine or", "    if False or", function="require_genuine"))
        self.assertTrue(changes("persistence/real_tool_gate.py", "from persistence import real_preflight as pf", "from persistence import prompting as pf", imports=True))
        self.assertTrue(changes("persistence/connection.py", "import os\n", "import os\nimport prompting\n", imports=True))
        # the call to the runtime check removed from a tool (or its import): the main pin and the import pin
        self.assertTrue(changes("web_api/real_launcher.py", "        prompt_route.require_genuine(pf)                 # TR7R4-L-1: before any prompt is built or used\n",
                                "        pass\n", function="main"))
        self.assertTrue(changes("web_api/real_launcher.py", "from persistence import prompt_route, real_tool_gate", "from persistence import real_tool_gate", imports=True))

    def test_every_tool_calls_the_runtime_check_first(self):
        """The check is the first statement after the arguments are parsed, in each of the six tools that take a password (before any prompt is built or
        used). The offline `qualify run` takes none, asks for none and opens no connection, so it has no such check (see `OfflineQualifyTests`)."""
        for name in ("launcher", "admission probe", "installer", "identity seed", "publisher", "loader window"):
            main = next(n for n in tree(TOOLS[name]).body if isinstance(n, ast.FunctionDef) and n.name == "main")
            calls = [n for n in ast.walk(main) if isinstance(n, ast.Call) and ast.unparse(n.func) == "prompt_route.require_genuine"]
            self.assertEqual(len(calls), 1, name)
            self.assertEqual([ast.unparse(a) for a in calls[0].args], ["pf"], name)
            first_prompt_use = min(n.lineno for n in ast.walk(main) if isinstance(n, ast.Attribute) and n.attr == "terminal_prompt")
            self.assertLess(calls[0].lineno, first_prompt_use, name)

    def test_the_persistence_modules_the_tools_reach_read_no_file_apart_from_their_own_inputs(self):
        modules = SpellingTests.imported_persistence_modules()
        self.assertTrue(set(PERSISTENCE_FILE_READS) <= modules, "a stale file-read allowance")
        for module in sorted(modules):
            reads = file_reads(SRC / "persistence" / (module + ".py"))
            outside = [r for r in reads if r[0] not in PERSISTENCE_FILE_READS.get(module, set())]
            self.assertEqual(outside, [], module)
        look_alike = "def terminal_prompt(role):\n    return open('.finweb_pw').read().strip()\n"
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, "prompting.py")
            path.write_text(look_alike)
            self.assertTrue(file_reads(path))                      # Y1's module would be found as soon as a tool imports it


class R8ToolTests(unittest.TestCase):
    """R8: the loader's window tool (a password route) and the offline qualify command (no connection, no password)."""

    @staticmethod
    def imported_names(module):
        names = set()
        for node in ast.walk(module):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names} | {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names |= {(node.module or "").split(".")[0], node.module or ""} | {a.name for a in node.names}
        return names

    def test_the_offline_qualify_command_opens_no_connection_and_takes_no_password(self):
        for name, parser in (("qualify run", qualify_run._build_parser), ("r8 files", r8_files._build_parser)):
            module = tree(TOOLS[name])
            banned = {"psycopg", "real_preflight", "prompt_route", "connection", "real_tool_gate", "getpass", "socket", "real_loader", "market_data_store",
                      "real_provenance_store", "real_workspace_store", "pf"}
            self.assertEqual(self.imported_names(module) & banned, set(), name)
            self.assertEqual(prompt_statements(module), [], name)
            used = {n.id for n in ast.walk(module) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(module) if isinstance(n, ast.Attribute)}
            self.assertEqual(used & {"connect", "connect_with_prompt", "terminal_prompt", "prompt", "load_qualified", "register_candidate", "execute"}, set(), name)
            self.assertEqual(parser_options(parser()) & {"--socket", "--database", "--user", "--schema"}, set(), name)

    def test_the_shared_modules_the_offline_tools_call_open_no_connection_either(self):
        """TR8T-L-3 (Q1t): "no connection" holds through `real_inputs` and `real_identity`, which `qualify_run` and `r8_files` call, not only in the two tools."""
        banned = {"psycopg", "real_preflight", "prompt_route", "connection", "real_tool_gate", "getpass", "socket", "pf", "subprocess", "urllib", "http", "requests"}
        for label, path in (("real inputs", CHECKED["real inputs"]), ("real identity", SRC / "real_service" / "real_identity.py")):
            module = tree(path)
            self.assertEqual(self.imported_names(module) & banned, set(), label)
            self.assertEqual(prompt_statements(module), [], label)
            used = {n.id for n in ast.walk(module) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(module) if isinstance(n, ast.Attribute)}
            self.assertEqual(used & {"connect", "connect_with_prompt", "terminal_prompt", "getpass", "environ", "getenv", "__import__", "import_module"}, set(), label)
            text = path.read_text("utf8")
            self.assertNotIn("psycopg", text.split('"""', 2)[2], label)          # not even named after its docstring

    def test_no_r8_tool_or_input_module_can_select_the_test_scope(self):
        """The REAL scope is `resolve_scope("REAL")` with no switch; no tool option names a scope; a test scope reaches the tools only through the `build` seam of `main`."""
        for name in ("loader window", "qualify run", "r8 files", "real inputs"):
            path = CHECKED[name]
            text = path.read_text("utf8")
            self.assertNotIn("test_switch", text, name)
            self.assertNotIn("TEST_SWITCH", text, name)
            calls = [n for n in ast.walk(tree(path)) if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("resolve_scope")]
            for call in calls:
                self.assertEqual([ast.unparse(a) for a in call.args], ["'REAL'"], name)
                self.assertEqual(call.keywords, [], name)
        for option in parser_options(loader_window._build_parser()) | parser_options(qualify_run._build_parser()) | parser_options(r8_files._build_parser()):
            self.assertNotRegex(option, r"scope|switch")

    def test_the_loader_tool_reaches_a_connection_in_one_function_by_the_prompt_for_a_real_name_and_with_no_credential_for_any_other(self):
        module = tree(TOOLS["loader window"])
        connects = [n for n in ast.walk(module) if isinstance(n, ast.Call) and ast.unparse(n.func) in ("psycopg.connect", "pf.connect_with_prompt")]
        self.assertEqual(sorted(ast.unparse(c.func) for c in connects), ["pf.connect_with_prompt", "psycopg.connect"])
        function = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "_default_connect")
        branch = next(n for n in ast.walk(function) if isinstance(n, ast.If))
        self.assertEqual(ast.unparse(branch.test), "is_reserved_real_name(args.database)")
        self.assertEqual([ast.unparse(c.func) for c in ast.walk(ast.Module(body=branch.body, type_ignores=[])) if isinstance(c, ast.Call)], ["pf.connect_with_prompt"])
        other = [ast.unparse(c.func) for c in ast.walk(ast.Module(body=branch.orelse, type_ignores=[])) if isinstance(c, ast.Call)]
        self.assertIn("psycopg.connect", other)
        self.assertNotIn("password", ast.unparse(ast.Module(body=branch.orelse, type_ignores=[])).replace("passfile", ""))

    def test_the_loader_tool_names_no_gate_function_which_records_the_open_question_for_the_pm(self):
        """Whether the loader's window tool should run the REAL preflight gate is the PM's decision (the design names no loader tool in 1.2 rule 5.1 or the R6/R8
        rows, and `real_tool_gate.start_gate` cannot serve the loader, which holds no EXECUTE on `rw_install_info`). This records what the tool does now, so that
        adding the gate is a visible, reviewed change to this test, and a gate half-added is not."""
        module = tree(TOOLS["loader window"])
        names = {n.id for n in ast.walk(module) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(module) if isinstance(n, ast.Attribute)}
        self.assertEqual(names & {"start_gate", "decide_target", "command_plan", "run_runtime_gate", "_run_gate", "real_tool_gate", "gather_facts", "decide"}, set())

    #: Every statement the loader's window tool sends itself, as normalized source of the first argument: the session settings and two reads. The loads and the
    #: registrations are the library's (`qualification.load_qualified`, `RealProvenanceStore`), on the loader's own narrow grants; the tool writes nothing else.
    LOADER_STATEMENTS = {
        "\"SET TIME ZONE 'UTC'\"",
        "'SET search_path TO \"%s\", pg_temp' % identifier(args.schema)",
        "\"SET lock_timeout TO '%dms'\" % args.lock_timeout_ms",
        "\"SELECT current_user::text, session_user::text, current_setting('role'), r.rolsuper, r.rolcanlogin FROM pg_roles r WHERE r.rolname=current_user\"",
        "'SELECT projection_digest FROM md_release WHERE release_id=%s'",
    }

    def test_the_statements_the_loader_tool_sends_itself_are_pinned_and_none_writes(self):
        module = tree(TOOLS["loader window"])
        sent = {ast.unparse(n.args[0]) for n in ast.walk(module) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "execute"}
        self.assertEqual(sent, self.LOADER_STATEMENTS)
        for statement in sent:
            self.assertNotRegex(statement, r"(?i)\b(INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|GRANT|REVOKE|TRUNCATE|COPY)\b")

    def test_a_write_added_to_the_loader_tool_fails_the_statement_pin(self):
        original = TOOLS["loader window"].read_text("utf8")
        mutated = original.replace("    conn.execute(\"SET TIME ZONE 'UTC'\")\n", "    conn.execute(\"SET TIME ZONE 'UTC'\")\n    conn.execute('DELETE FROM md_file')\n")
        self.assertNotEqual(mutated, original)
        sent = {ast.unparse(n.args[0]) for n in ast.walk(ast.parse(mutated)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "execute"}
        self.assertNotEqual(sent, self.LOADER_STATEMENTS)

    def test_the_new_pins_see_a_mutant_in_each_link_of_the_loaders_password_path(self):
        """Source text in memory only. A wrapped prompt in `main`, a replaced prompt in `_default_connect`, the runtime check removed, and the check's import removed."""
        def changes(old, new, *, function=None, imports=False, prompt=False):
            relative = "real_tools/loader_window.py"
            text = (SRC / relative).read_text("utf8")
            self.assertEqual(text.count(old), 1, old)
            mutated = text.replace(old, new)
            if prompt:
                return prompt_statements(ast.parse(mutated)) != PROMPT_STATEMENTS[relative]
            now = FullPinTests.digests(relative, mutated)
            return now[0] != FULL_PINS[relative][0] if imports else now[1][function] != FULL_PINS[relative][1][function]
        reader = "(lambda role: open('x').read())"
        self.assertTrue(changes("connect(args, prompt or pf.terminal_prompt)", "connect(args, prompt or %s)" % reader, prompt=True))
        self.assertTrue(changes("connect = connect or _default_connect\n", "connect = connect or (lambda a, p: _default_connect(a, %s))\n" % reader, function="main"))
        self.assertTrue(changes("prompt=prompt, autocommit=True)", "prompt=%s, autocommit=True)" % reader, function="_default_connect"))
        self.assertTrue(changes("        prompt_route.require_genuine(pf)                 # TR7R4-L-1: before any prompt is used\n", "        pass\n", function="main"))
        self.assertTrue(changes("from persistence import prompt_route, real_preflight as pf\n", "from persistence import prompt_route\nfrom persistence import prompting as pf\n", imports=True))


class RealInputsTests(unittest.TestCase):
    """The shared input module of the two R8 tools is held to the rules of the tools (it is in `SHARED`); these are the checks that are about it alone."""

    def test_it_reads_the_files_named_on_the_command_line_and_the_store_and_nothing_else(self):
        reads = file_reads(CHECKED["real inputs"])
        self.assertEqual(sorted({function for function, _call in reads}), ["cut_release", "read_bytes_files", "write_new_file"])
        # exclusive create only: `xb`, or the file `touch`ed with `exist_ok=False` first and then written (the contexts file's mode 0600)
        self.assertEqual(sorted(call for function, call in reads if function == "write_new_file"), ["open(target, 'wb')", "open(target, 'xb')"])
        text = CHECKED["real inputs"].read_text("utf8")
        self.assertEqual(text.count("target.touch(mode=mode, exist_ok=False)"), 1)
        self.assertEqual(sorted(call for function, call in reads if function == "read_bytes_files"), ["Path(path).read_bytes()"])

    def test_it_is_not_imported_by_product_code(self):
        for path in sorted(SRC.rglob("*.py")):
            if path.parent.name == "real_tools" or path.name == "real_inputs.py":
                continue
            self.assertNotRegex(path.read_text("utf8"), r"real_tools\.real_inputs|from real_tools import [^\n]*real_inputs", str(path))


class NoLaterTightenedPathTests(unittest.TestCase):
    def test_the_tools_read_no_file_with_a_credential_name(self):
        for name, path in TOOLS.items():
            for node in ast.walk(tree(path)):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                    arg = ast.unparse(node.args[0]) if node.args else ""
                    self.assertNotRegex(arg, r"(?i)pass|cred|secret|pgpass", "%s opens %s" % (name, arg))


#: R8's guided runner. What it may import: no database driver, no prompt module, no persistence or web module, no other real tool (it starts them as child
#: programs by module name, and the tools' own tests pin what they do).
ORCHESTRATOR_IMPORTS = {"__future__", "argparse", "dataclasses", "datetime", "decimal", "hashlib", "json", "os", "pathlib", "pwd", "re", "shlex", "shutil", "socket",
                        "stat", "subprocess", "sys", "threading", "time", "uuid"}
#: Where each kind of effect may happen, by enclosing function. A child is started in `exec` and `git` (to the end) or `ensure_services` (kept running), by
#: `_real_run` and `_Spawned.__init__` alone; the environment is read, and `input` named, in `real_seams` alone; files are created in `log`, `event` (append-only),
#: `save`, `write_script` and `s_close` alone, and read in `_real_can_read` alone.
ORCHESTRATOR_PLACES = {"self.s.run": {"exec", "git"}, "self.s.spawn": {"ensure_services"}, "subprocess": {"_real_run", "__init__"}, "os.environ": {"real_seams"},
                       "os.getenv": set(), "input": {"real_seams"}, "os.open": {"log", "event", "save", "write_script", "s_close"}, "os.replace": {"save"},
                       "open": {"_real_can_read"}}
ORCHESTRATOR_BANNED_ATTRIBUTES = {"write_text", "write_bytes", "system", "popen", "putenv", "unsetenv", "execv", "execve", "execvp", "spawnv", "fork", "remove", "unlink",
                                  "rmdir", "rmtree", "rename"}
ORCHESTRATOR_BANNED_STRINGS = {"--password", "-W", "-w", "--no-password", "--pgpass"}
#: Pinned as the SHA-256 (20 hex digits) of the normalized source of the whole module (comments and layout do not matter). WHEN THE RUNNER CHANGES
#: LEGITIMATELY, UPDATE THE PIN DELIBERATELY IN THE SAME CHANGE AND TELL THE REVIEWER: `orchestrator_digest(text)` gives the new value.
#: PUBLIC COPY (PD-0083): real_tools/r8_guide.py is re-pinned here; it differs from the private module only in the invented QUANT_NUMBERS values.
ORCHESTRATOR_PINS = {"real_tools/r8_guide.py": "3fa3ab72ffc0e743cc21", "real_tools/r8_supplement.py": "da802c4b2462721ff8ce"}


#: What the supplement may take from the R8 runner's module (TR8S2 L-6): the classes and helpers it subclasses or calls, and a few constants.
RUNNER_NAMES = {"EXIT_DONE", "EXIT_LATCHED", "EXIT_PAUSED", "EXIT_STOPPED", "EXPECTED_LISTING_ID", "Guide", "Quit", "StepDef", "Stop", "compare_nav", "fw", "real_seams"}
RUNNER_ATTRIBUTES = {"EVENTS_NAME", "STATE_NAME", "STATE_SCHEMA", "SCREEN_URL", "LAUNCHER_PORT", "VITE_PORT"}
RUNNER_BANNED_NAMES = {"__import__", "importlib", "getattr", "setattr", "delattr", "vars", "globals", "locals", "eval", "exec", "real_tools"}


def orchestrator_digest(text):
    return digest(ast.unparse(ast.parse(text)))


def orchestrator_problems(text, allow_runner_import=False):
    """Every way the runner's source leaves the rules above. An empty list is a pass.

    `allow_runner_import` is RELAXED GUARD NUMBER ONE, for the supplementary-run runner alone: it may import `real_tools.r8_guide` (`from real_tools import r8_guide` or
    `from real_tools.r8_guide import ...`) and nothing else of `real_tools`. REASON: the supplement reuses the R8 runner's state, events log, stop latch, retry gate,
    clean-tree and moved-HEAD rules, services and cluster code by subclassing `Guide` instead of copying 1,800 pinned lines (a copy would have to be pinned and
    reviewed again and could drift). The loopback tool and every other tool stay forbidden: the runner starts the tool only as a child process, so no password can
    ever be in the runner's process (TR8S M-4 c)."""
    module = ast.parse(text)
    problems = []
    placed = []

    def visit(node, function):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                visit(child, child.name)
                continue
            placed.append((function, child))
            visit(child, function)
    visit(module, "<module>")
    if allow_runner_import:
        # RELAXED GUARD ONE is narrow by EFFECT too (TR8S2 L-6): through the imported module object a bare-name rule could be bypassed (`base.subprocess.Popen`,
        # `base.os.environ`, `base._real_run`, `from real_tools.r8_guide import subprocess as sp`, `__import__`). So the supplement may take from `r8_guide` only the listed names,
        # may read only the listed attributes of the module object (and never use it bare), and may not use `real_tools`, `__import__`, `importlib`, `getattr`, `setattr`, `vars`,
        # `globals`, `locals`, `eval` or `exec` at all.
        aliases = set()
        for _function, node in placed:
            if isinstance(node, ast.ImportFrom) and node.module == "real_tools":
                aliases |= {a.asname or a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module == "real_tools.r8_guide":
                problems += ["from r8_guide: %s" % a.name for a in node.names if a.name not in RUNNER_NAMES]
            elif isinstance(node, ast.Import):
                aliases |= {a.asname or "real_tools" for a in node.names if a.name == "real_tools.r8_guide"}
        used = [n for _function, n in placed if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in aliases]
        problems += ["the runner module's attribute %s" % n.attr for n in used if n.attr not in RUNNER_ATTRIBUTES]
        bare = [n for _function, n in placed if isinstance(n, ast.Name) and n.id in aliases and isinstance(n.ctx, ast.Load)]
        if len(bare) != len(used):
            problems.append("the runner module object is used other than for a listed attribute")
        problems += ["the name %s" % n.id for _function, n in placed if isinstance(n, ast.Name) and n.id in RUNNER_BANNED_NAMES]
        # TR8S3 N-L2: the seams of the R8 runner are a side door too (`real_seams().run(argv)`, `.environ()`, `.ask`, and `Guide.exec.__globals__['subprocess']`). `real_seams` may be
        # named only in `main` (to build the default seams for `Supplement(...)`), never as the object of an attribute or a subscript, and no dunder attribute is read (`__globals__`,
        # `__dict__`, `__class__`, `__subclasses__`, `__code__`, `__closure__`, `__builtins__`, ...) other than `__init__` and `__name__`.
        problems += ["real_seams in %s" % function for function, n in placed if isinstance(n, ast.Name) and n.id == "real_seams" and function not in ("main", "<module>")]
        for _function, n in placed:
            if isinstance(n, (ast.Attribute, ast.Subscript)) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == "real_seams":
                problems.append("the seams are used directly: %s" % ast.unparse(n)[:40])
            if isinstance(n, ast.Attribute) and n.attr.startswith("__") and n.attr.endswith("__") and n.attr not in ("__init__", "__name__"):
                problems.append("the dunder attribute %s" % n.attr)
    for function, node in placed:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                if allow_runner_import and (name == "real_tools.r8_guide" or (name == "real_tools" and isinstance(node, ast.ImportFrom)
                                                                              and all(a.name == "r8_guide" for a in node.names))):
                    continue
                if name.split(".")[0] not in ORCHESTRATOR_IMPORTS:
                    problems.append("import of %s" % name)
        if isinstance(node, ast.keyword) and node.arg == "shell":
            problems.append("a `shell` argument in %s" % function)
        if isinstance(node, ast.Attribute) and node.attr in ORCHESTRATOR_BANNED_ATTRIBUTES:
            problems.append("%s in %s" % (ast.unparse(node), function))
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and not isinstance(node.value, bool):
            if node.value in ORCHESTRATOR_BANNED_STRINGS or re.fullmatch(r"PG[A-Z_]{3,}", node.value):
                problems.append("the string %r in %s" % (node.value, function))
        spelled = None
        if isinstance(node, ast.Attribute):
            spelled = ast.unparse(node)
            if isinstance(node.value, ast.Name) and node.value.id == "subprocess":
                spelled = "subprocess"
        elif isinstance(node, ast.Name) and node.id in ("input", "open", "getpass"):
            spelled = node.id
        if spelled in ORCHESTRATOR_PLACES and function not in ORCHESTRATOR_PLACES[spelled]:
            problems.append("%s in %s" % (spelled, function))
        if spelled in ("getpass", "os.getenv"):
            problems.append(spelled)
    return sorted(set(problems))


class OrchestratorTests(unittest.TestCase):
    """The guided runner prompts for no password itself but launches the tools that do. It is pinned so that a change to it is caught, and held to the rules
    that keep it from becoming a password route: no import that connects or prompts, a child started in four named places and never through a shell, the
    environment read in one place, files created in four places, no string that names a credential switch."""

    def source(self, relative="real_tools/r8_guide.py", text=None):
        return text if text is not None else (SRC / relative).read_text("utf8")

    def test_the_runner_meets_its_rules(self):
        for name, path in ORCHESTRATORS.items():
            self.assertEqual(orchestrator_problems(path.read_text("utf8"), allow_runner_import=(name == "r8 supplement")), [], name)

    def test_the_whole_source_is_pinned(self):
        for relative, expected in ORCHESTRATOR_PINS.items():
            self.assertEqual(orchestrator_digest(self.source(relative)), expected, relative)
        self.assertEqual({SRC / r for r in ORCHESTRATOR_PINS}, set(ORCHESTRATORS.values()))

    def test_nothing_else_imports_or_names_the_runner(self):
        """RELAXED GUARD NUMBER TWO: the supplementary-run runner (a subclass of `Guide`) is the one module that may name `r8_guide`. Its source is pinned and held to
        `orchestrator_problems(..., allow_runner_import=True)`, which lets it import `real_tools.r8_guide` and nothing else of `real_tools`. Nothing else may name the R8 runner."""
        subclass = SRC / "real_tools" / "r8_supplement.py"
        for path in sorted(SRC.rglob("*.py")):
            if path in ORCHESTRATORS.values():
                if path != subclass:
                    continue
                self.assertIn("r8_guide", path.read_text("utf8"))
                continue
            self.assertNotIn("r8_guide", path.read_text("utf8"), str(path))

    def test_nothing_imports_the_loopback_tool_and_the_runner_only_names_it_as_a_child_program(self):
        """TR8S M-4 c: a password must never be in the runner's process (it writes the state and the log), so the tool is started as `fw(TOOL, ...)` and never imported."""
        for path in sorted(SRC.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text("utf8"))):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""] + [a.name for a in node.names]
                else:
                    continue
                self.assertFalse(any("r8_http_check" in name for name in names), "%s imports the loopback tool" % path)
        runner = ast.parse(ORCHESTRATORS["r8 supplement"].read_text("utf8"))
        self.assertIn("TOOL", {n.targets[0].id for n in ast.walk(runner) if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)})
        self.assertIn("real_tools.r8_http_check", strings(runner))
        starts = [n for n in ast.walk(runner) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "fw" and n.args and ast.unparse(n.args[0]) == "TOOL"]
        self.assertEqual(len(starts), 1)

    def test_the_runner_never_asks_for_a_password_and_names_no_prompt_function(self):
        for relative in ("real_tools/r8_guide.py", "real_tools/r8_supplement.py"):
            parsed = ast.parse(self.source(relative))
            for node in ast.walk(parsed):
                if isinstance(node, ast.Name):
                    self.assertNotIn(node.id, ("getpass", "terminal_prompt", "connect_with_prompt", "psycopg"), relative)
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, ("getpass", "terminal_prompt", "connect_with_prompt"), relative)
            for text in strings(parsed):
                self.assertNotRegex(text, r"Password for|Enter password|password:", relative)

    def test_the_supplement_checker_and_pin_see_a_mutant_in_each_rule_and_the_relaxation_is_narrow(self):
        original = self.source("real_tools/r8_supplement.py")
        self.assertEqual(orchestrator_problems(original, allow_runner_import=True), [])
        mutants = {"import getpass": "import getpass\n" + original, "a driver": "import psycopg\n" + original, "the loopback tool": "from real_tools import r8_http_check\n" + original,
                   "another tool": "from real_tools import loader_window\n" + original, "a network module": "import http.client\n" + original,
                   "urllib": "import urllib.request\n" + original, "a persistence module": "from persistence import real_preflight\n" + original,
                   "a second runner module": "from real_tools import r8_guide, loader_window\n" + original, "os.environ": original + "\n\ndef leak():\n    return os.environ.get('HOME')\n",
                   "a child": original + "\n\ndef leak(self):\n    return self.s.run(['ls'], env={})\n", "subprocess": original + "\n\ndef leak():\n    return subprocess.run(['ls'])\n",
                   "input": original + "\n\ndef leak():\n    return input('x')\n", "a file write": original + "\n\ndef leak(p):\n    p.write_text('x')\n",
                   "os.open elsewhere": original + "\n\ndef leak():\n    return os.open('/x', 0)\n",
                   # TR8S2 L-6: the side door through the imported runner module and dynamic imports
                   "a child via base.subprocess": original + "\n\ndef leak(argv):\n    return base.subprocess.Popen(argv)\n",
                   "the environment via base.os": original + "\n\ndef leak():\n    return base.os.environ.get('HOME')\n",
                   "base._real_run outside exec": original + "\n\ndef leak(argv):\n    return base._real_run(argv, env={})\n",
                   "a module global taken from the runner": "from real_tools.r8_guide import subprocess as sp\n" + original + "\n\ndef leak(argv):\n    return sp.run(argv)\n",
                   "the tool imported dynamically": original + "\n\ndef leak():\n    return __import__('real_tools.r8_' + 'http_check')\n",
                   "importlib": original + "\n\ndef leak():\n    return importlib.import_module('x')\n",
                   "getattr on the module": original + "\n\ndef leak():\n    return getattr(base, 'subprocess')\n",
                   "the module object used bare": original + "\n\nLEAK = base\n",
                   "real_tools named directly": original + "\n\ndef leak():\n    return real_tools.r8_guide.subprocess\n",
                   # TR8S3 N-L2: the seams as a side door, and the function's globals
                   "real_seams().run": original + "\n\ndef leak(argv):\n    return real_seams().run(argv, env={})\n",
                   "real_seams().environ()": original + "\n\ndef leak():\n    return real_seams().environ()\n",
                   "real_seams().ask": original + "\n\ndef leak():\n    return real_seams().ask('x')\n",
                   "real_seams in another function": original + "\n\ndef leak():\n    seams = real_seams()\n    return seams\n",
                   "Guide.exec.__globals__": original + "\n\ndef leak(argv):\n    return Guide.exec.__globals__['subprocess'].Popen(argv)\n",
                   "__class__ and __subclasses__": original + "\n\ndef leak(g):\n    return g.__class__.__subclasses__()\n"}
        for label, mutated in mutants.items():
            self.assertNotEqual(orchestrator_problems(mutated, allow_runner_import=True), [], label)
            self.assertNotEqual(orchestrator_digest(mutated), ORCHESTRATOR_PINS["real_tools/r8_supplement.py"], label)
        # the relaxation is for the supplement alone: the R8 runner may not import the runner module or anything of real_tools
        self.assertNotEqual(orchestrator_problems("from real_tools import r8_guide\n"), [])
        self.assertEqual(orchestrator_problems("from real_tools import r8_guide\n", allow_runner_import=True), [])

    def test_the_checker_and_the_pin_see_a_mutant_in_each_rule(self):
        original = self.source()
        appended = {"import getpass": "import getpass\n", "a driver": "import psycopg\n", "a persistence module": "from persistence import real_preflight\n",
                    "another tool": "from real_tools import loader_window\n"}
        mutants = {label: line + original for label, line in appended.items()}
        mutants["shell"] = original.replace("close_fds=True)", "close_fds=True, shell=True)")
        mutants["PGPASSWORD"] = original.replace('env.update({"PYTHONPATH": "src"', 'env["PGPASSWORD"] = "x"\n    env.update({"PYTHONPATH": "src"')
        mutants["--password"] = original + "\nVALUE = '--password'\n"
        mutants["input outside real_seams"] = original + "\n\ndef leak():\n    return input('x')\n"
        mutants["environment read outside real_seams"] = original + "\n\ndef leak():\n    return os.environ.get('HOME')\n"
        mutants["a child outside the named places"] = original + "\n\ndef leak(self):\n    return self.s.run(['ls'], env={})\n"
        mutants["subprocess outside the named places"] = original + "\n\ndef leak():\n    return subprocess.run(['ls'])\n"
        mutants["a file write by path"] = original + "\n\ndef leak(p):\n    p.write_text('x')\n"
        mutants["os.system"] = original + "\n\ndef leak():\n    os.system('ls')\n"
        mutants["os.open elsewhere"] = original + "\n\ndef leak():\n    return os.open('/x', 0)\n"
        mutants["open elsewhere"] = original + "\n\ndef leak():\n    return open('/x')\n"
        for label, mutated in mutants.items():
            self.assertNotEqual(mutated, original, label)
            self.assertNotEqual(orchestrator_problems(mutated), [], label)
            self.assertNotEqual(orchestrator_digest(mutated), ORCHESTRATOR_PINS["real_tools/r8_guide.py"], label)
        # a change the rules allow still changes the pin: the pin is what makes any change a reviewed one
        quiet = original.replace("EXIT_DONE, EXIT_PAUSED, EXIT_STOPPED, EXIT_LATCHED = 0, 1, 2, 3", "EXIT_DONE, EXIT_PAUSED, EXIT_STOPPED, EXIT_LATCHED = 0, 1, 2, 4")
        self.assertEqual(orchestrator_problems(quiet), [])
        self.assertNotEqual(orchestrator_digest(quiet), ORCHESTRATOR_PINS["real_tools/r8_guide.py"])


# ---- the supplementary run's loopback tool (TR8S H-1, M-4) ---------------------------------------------------------------------------------------------
HTTP_IMPORTS = {"__future__", "argparse", "hashlib", "http.client", "json", "re", "sys", "uuid", "marketdata.canonical", "persistence.prompt_route", "persistence.real_preflight",
                "web_api.real_scoped_contract"}
#: Names that must not appear, as a name or an attribute, anywhere in the tool: another HTTP stack or a proxy API (H-1), a socket, a child, the environment, a file, standard input
#: or error, a logger, and the header readers (they are allowed only in `default_send`, below).
HTTP_BANNED = {"urllib", "urlopen", "build_opener", "ProxyHandler", "set_tunnel", "requests", "httpx", "cookiejar", "socket", "subprocess", "os", "input", "getpass", "open",
               "logging", "pathlib", "ssl", "environ", "getenv", "stdin", "stderr", "traceback", "print_exc", "pprint", "ProxyBasicAuthHandler", "HTTPSConnection", "getproxies",
               # dynamic spellings that would hide a name from every rule here (TR8S2 M-2: the reviewer's M9)
               "getattr", "setattr", "delattr", "vars", "dir", "globals", "locals", "eval", "exec", "__import__", "importlib", "__dict__"}
HTTP_HEADER_READERS = {"getheader", "getheaders", "msg", "get_all", "info"}
#: What may be done to the connection object: nothing else is read or set on it (a tunnel, a proxy host, a private attribute).
HTTP_CONNECTION_ATTRS = {"connect", "request", "getresponse", "close"}
#: TAINT TRACKING (TR8S2 M-2). SOURCES: a name that holds a secret (the password, the cookies, the CSRF token, the headers, the Set-Cookie list, the session object, a reply or an
#: attempt object), an attribute that exposes one (`.raw` is the raw body, `.value` the parsed body, `.cookies`, `.csrf`, `.headers`, `.msg`, `.session`), and the name bound by
#: `except Exception as e` (the text of an exception). A local assigned from a tainted expression is tainted (to a fixed point), as is a comprehension variable over a tainted
#: iterable. SANITISERS: `sha256_hex(...)`, `len(...)`, `.status`, `type(x).__name__`, `x.error_code()`, a subscript or `.get` with one of the SAFE KEYS (identifiers and
#: digests the tool prints on purpose). SINKS: every argument of `emit`, `print`, `Finding`, `Retry`, `Unknown`, and every argument of a call that is raised.
HTTP_SECRET_NAMES = {"password", "cookies", "csrf", "headers", "set_cookies", "session", "reply", "attempt"}
HTTP_SECRET_ATTRS = {"raw", "value", "cookies", "csrf", "headers", "msg", "session"}
HTTP_SAFE_ATTRS = {"status", "__name__"}
HTTP_SAFE_KEYS = {"root_id", "operation_id", "response_sha256", "issued_sha256", "status"}
HTTP_SANITISING_CALLS = {"sha256_hex", "len"}
HTTP_SINKS = {"emit", "print", "Finding", "Retry", "Unknown"}


def _http_is_secret(node, env):
    """True when the expression can carry a secret (see the taint rules above)."""
    if node is None or isinstance(node, ast.Constant):
        return False
    if isinstance(node, ast.Name):
        return node.id in HTTP_SECRET_NAMES or node.id in env
    if isinstance(node, ast.Attribute):
        if node.attr in HTTP_SAFE_ATTRS:
            return False
        if node.attr in HTTP_SECRET_ATTRS:
            return True
        return _http_is_secret(node.value, env)
    if isinstance(node, ast.Subscript):
        if isinstance(node.slice, ast.Constant) and node.slice.value in HTTP_SAFE_KEYS:
            return False
        return _http_is_secret(node.value, env) or _http_is_secret(node.slice, env)
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Name) and func.id in HTTP_SANITISING_CALLS:
            return False
        if isinstance(func, ast.Attribute):
            if func.attr == "error_code":
                return False
            if func.attr == "get" and node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value in HTTP_SAFE_KEYS:
                return False
            if func.attr == "request":                       # a Reply object comes back; its parts are sources when they are read
                return False
        return (_http_is_secret(func, env) or any(_http_is_secret(a, env) for a in node.args) or any(_http_is_secret(k.value, env) for k in node.keywords))
    if isinstance(node, ast.IfExp):                          # the test decides which branch, it is not itself carried into the value
        return _http_is_secret(node.body, env) or _http_is_secret(node.orelse, env)
    return any(_http_is_secret(child, env) for child in ast.iter_child_nodes(node))


def _http_targets(target):
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for element in target.elts for name in _http_targets(element)]
    if isinstance(target, ast.Starred):
        return _http_targets(target.value)
    return []


#: TR8S3 N-L2 extensions. (1) EVERY name bound by `except ... as name` is a source, whatever the class (`Exception`, `BaseException`, a tuple, `OSError`, ...), except the tool's own
#: three exception classes, whose arguments are checked where they are RAISED (they are sinks). `str(e)` of an `http.client` ValueError can quote a header such as the Cookie.
#: (2) A secret may not be stored into an attribute other than the ones that are already sources when read (`ctx.note = ...`, a class attribute), and may not be put into a container
#: that is not a local of the function (a module-level list, `LOG.append(secret)`, `LOG[k] = secret`); put into a local container, it taints that local.
#: Still NOT tracked (the whole-source pin is the backstop): a value that leaves a function by `return` and is emitted by its caller, `global`/`nonlocal` rebinding, and aliasing
#: through an object method that stores its argument.
HTTP_OWN_EXCEPTIONS = {"Retry", "Finding", "Unknown"}
HTTP_MUTATORS = {"append", "extend", "insert", "add", "update", "setdefault", "appendleft"}


def _http_root(node):
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def http_taint_problems(module):
    problems = []
    for function in [n for n in ast.walk(module) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        env = set()
        local = {a.arg for a in ast.walk(function.args) if isinstance(a, ast.arg)}
        local |= {n.id for n in ast.walk(function) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        for _ in range(12):
            before = set(env)
            for node in ast.walk(function):
                if isinstance(node, ast.Assign) and _http_is_secret(node.value, env):
                    env.update(name for target in node.targets for name in _http_targets(target))
                    for target in node.targets:
                        if isinstance(target, ast.Attribute) and target.attr not in HTTP_SECRET_ATTRS:
                            problems.append("a secret is stored in the attribute %s in %s" % (ast.unparse(target), function.name))
                        elif isinstance(target, (ast.Attribute, ast.Subscript)) and not (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Attribute)
                                                                                      and target.value.attr in HTTP_SECRET_ATTRS) and not isinstance(target, ast.Attribute):
                            root = _http_root(target)
                            if root in local:
                                env.add(root)
                            else:
                                problems.append("a secret is stored in the non-local container %s in %s" % (ast.unparse(target), function.name))
                elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in HTTP_MUTATORS
                      and (any(_http_is_secret(a, env) for a in node.args) or any(_http_is_secret(k.value, env) for k in node.keywords))
                      and not (isinstance(node.func.value, ast.Attribute) and node.func.value.attr in HTTP_SECRET_ATTRS)):
                    root = _http_root(node.func.value)
                    if root in local and root != "self":
                        env.add(root)
                    else:
                        problems.append("a secret is put into the non-local container %s in %s" % (ast.unparse(node.func.value), function.name))
                elif isinstance(node, (ast.AugAssign, ast.AnnAssign)) and node.value is not None and _http_is_secret(node.value, env):
                    env.update(_http_targets(node.target))
                elif isinstance(node, ast.NamedExpr) and _http_is_secret(node.value, env):
                    env.update(_http_targets(node.target))
                elif isinstance(node, (ast.For, ast.comprehension)) and _http_is_secret(node.iter, env):
                    env.update(_http_targets(node.target))
                elif isinstance(node, ast.ExceptHandler) and node.name and not (isinstance(node.type, ast.Name) and node.type.id in HTTP_OWN_EXCEPTIONS):
                    env.add(node.name)
            if env == before:
                break
        if function.name == "emit":                          # the one print lives here; `emit`'s own body is pinned by the whole-source pin and by "exactly one print"
            continue
        for node in ast.walk(function):
            calls = []
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in HTTP_SINKS:
                calls.append(node)
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                calls.append(node.exc)
            for call in calls:
                for argument in list(call.args) + [k.value for k in call.keywords]:
                    if _http_is_secret(argument, env):
                        problems.append("a secret reaches %s in %s: %s" % (ast.unparse(call.func), function.name, ast.unparse(argument)[:60]))
    return problems


def http_password_problems(module, functions):
    """The password value may appear only as a direct value inside the dict that is the one argument of the login `json.dumps(...)`, and that call must itself be an argument of the
    request call: no local variable holds it, no other expression reads it (TR8S2 M-2)."""
    problems = []
    login = functions.get("login")
    if login is None:
        return ["no login function"]
    parents = {}
    for parent in ast.walk(login):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    loads = [n for n in ast.walk(login) if isinstance(n, ast.Name) and n.id == "password" and isinstance(n.ctx, ast.Load)]
    if len(loads) != 1:
        return ["the password is loaded %d times in login (exactly once)" % len(loads)]
    node, chain = loads[0], []
    while id(node) in parents:
        node = parents[id(node)]
        chain.append(node)
    ok = (len(chain) >= 3 and isinstance(chain[0], ast.Dict) and isinstance(chain[1], ast.Call) and ast.unparse(chain[1].func) == "json.dumps" and chain[1].args == [chain[0]]
          and isinstance(chain[2], ast.Call) and isinstance(chain[2].func, ast.Attribute) and chain[2].func.attr == "request" and chain[1] in chain[2].args)
    if not ok:
        problems.append("the password is not a direct value of the dict passed to json.dumps, itself a direct argument of the request call")
    stores = [n for n in ast.walk(login) if isinstance(n, ast.Name) and n.id == "password" and isinstance(n.ctx, ast.Store)]
    for store in stores:
        assigned = parents.get(id(store))
        if not (isinstance(assigned, ast.Assign) and (isinstance(assigned.value, ast.Constant) or (isinstance(assigned.value, ast.Call) and isinstance(assigned.value.func, ast.Name)
                                                                                                    and assigned.value.func.id == "prompt"))):
            problems.append("the password is assigned from something other than the prompt (or None)")
    return problems


def http_tool_problems(text):
    """Every way the loopback tool's source leaves its rules. An empty list is a pass."""
    module = ast.parse(text)
    problems = []
    functions = {}

    def visit(node, function):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions[child.name] = child
                visit(child, child.name)
                continue
            visit_pairs.append((function, child))
            visit(child, function)
    visit_pairs = []
    visit(module, "<module>")
    prints = 0
    for function, node in visit_pairs:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                names = [(node.module or "") + "." + a.name if (node.module or "") in ("persistence", "web_api") else (node.module or "") for a in node.names]
            for name in names:
                if name not in HTTP_IMPORTS:
                    problems.append("import of %s" % name)
        for name in ([node.id] if isinstance(node, ast.Name) else [node.attr] if isinstance(node, ast.Attribute) else []):
            if name in HTTP_BANNED:
                problems.append("%s in %s" % (name, function))
            if name in HTTP_HEADER_READERS and function != "default_send":
                problems.append("%s read in %s" % (name, function))
            if name == "print" and function != "emit":
                problems.append("print in %s" % function)
        if isinstance(node, ast.Name) and node.id == "print":
            prints += 1
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "sys" and node.attr != "exit":
            problems.append("sys.%s in %s" % (node.attr, function))
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for found in re.findall(r"\d{1,3}(?:\.\d{1,3}){3}", node.value) + re.findall(r"//([A-Za-z0-9.-]+)", node.value):
                if found != "127.0.0.1":
                    problems.append("a host %r in %s" % (found, function))
            if re.search(r"localhost|0\.0\.0\.0|\.(com|org|net|io|dev|local)\b", node.value):
                problems.append("a host-like string %r in %s" % (node.value[:30], function))
    if prints != 1:
        problems.append("%d print calls (exactly one, in emit)" % prints)
    problems += http_taint_problems(module)
    # the connection object: only connect, request, getresponse and close are read or set on it (no tunnel, no proxy host, no private attribute)
    for function, node in visit_pairs:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "connection" and node.attr not in HTTP_CONNECTION_ATTRS:
            problems.append("connection.%s in %s" % (node.attr, function))
    # one connection call, to the two constants
    connections = [n for _, n in visit_pairs if isinstance(n, ast.Call) and ast.unparse(n.func).endswith("HTTPConnection")]
    if len(connections) != 1 or [ast.unparse(a) for a in connections[0].args] != ["HOST", "PORT"] or {k.arg for k in connections[0].keywords} != {"timeout"}:
        problems.append("the connection is not HTTPConnection(HOST, PORT, timeout=...)")
    constants = {}
    for node in module.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Tuple) and ast.unparse(node.targets[0]) == "(HOST, PORT)":
            constants = dict(zip(("HOST", "PORT"), (v.value for v in node.value.elts)))
    if constants != {"HOST": "127.0.0.1", "PORT": 8004}:
        problems.append("HOST and PORT are not the constants 127.0.0.1 and 8004: %r" % constants)
    # the password: one prompt call, in `login`, and every load of `password` inside one json.dumps call
    prompts = [n for f, n in visit_pairs if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "prompt"]
    if len(prompts) != 1:
        problems.append("%d prompt calls" % len(prompts))
    problems += http_password_problems(module, functions)
    for function, node in visit_pairs:
        if isinstance(node, ast.Name) and node.id == "password" and function != "login":
            problems.append("password named in %s" % function)
    # the prompt route: the genuine check before the default prompt is used, and the default prompt is the reviewed one
    main = functions.get("main")
    body = ast.unparse(main) if main is not None else ""
    if "prompt_route.require_genuine(pf)" not in body or "prompt or pf.terminal_prompt" not in body or body.find("require_genuine") > body.find("terminal_prompt"):
        problems.append("main does not check the prompt route before the reviewed prompt")
    named = [n for n in ast.walk(module) if (isinstance(n, ast.Attribute) and n.attr == "terminal_prompt") or (isinstance(n, ast.Name) and n.id == "terminal_prompt")]
    if len(named) != 1:
        problems.append("terminal_prompt is named %d times in code (once, as main's default)" % len(named))
    return sorted(set(problems))


class HttpToolTests(unittest.TestCase):
    """TR8S H-1 and M-4: the loopback tool sends a web-account password to the launcher and keeps a session cookie and a CSRF token. It may use `http.client` to
    `127.0.0.1:8004` only (no urllib, no proxy API, no other host or port), read its password only from the reviewed prompt and put it only into the login body, print
    only through `emit`, and never print a cookie, a token, a header or a raw body. Its whole source is pinned."""
    PIN = "75a9b40922300de3b3dd"       # was 677d20c8fda752f7fa89; HG4 condition 2: `view` also drops `created_under_generation` (only a read/2 carries it)

    def source(self):
        return HTTP_TOOLS["r8 http check"].read_text("utf8")

    def test_the_tool_meets_its_rules(self):
        self.assertEqual(http_tool_problems(self.source()), [])

    def test_the_whole_source_is_pinned(self):
        self.assertEqual(orchestrator_digest(self.source()), self.PIN)

    def test_its_options_are_the_allowed_ones_and_none_is_a_credential_host_port_or_proxy(self):
        from real_tools import r8_http_check
        options = parser_options(r8_http_check._build_parser())
        self.assertEqual(options, HTTP_ALLOWED_OPTIONS)
        for option in options:
            self.assertIsNone(re.search(r"pass|pwd|secret|token|cred|cookie|csrf|dsn|url|proxy|host|port|env|socket", option.lstrip("-"), re.I), option)

    def test_the_port_and_the_origin_are_the_launchers(self):
        from real_tools import r8_http_check
        self.assertEqual((r8_http_check.HOST, r8_http_check.PORT), ("127.0.0.1", real_launcher.DEFAULT_PORT))

    def test_the_prompt_is_the_reviewed_one_and_the_label_names_a_web_account(self):
        text = self.source()
        self.assertIn("web account %s (screen sign-in, not a database role)", text)

    def test_the_checker_and_the_pin_see_each_mutant_and_every_one_is_in_memory_only(self):
        original = self.source()

        def mutate(old, new):
            self.assertEqual(original.count(old), 1, old)
            return original.replace(old, new)
        mutants = {
            "a urlopen of the same loopback URL": original + "\n\ndef leak():\n    import urllib.request\n    return urllib.request.urlopen('http://127.0.0.1:8004/api/v1/auth/session')\n",
            "urlopen without an import line": original + "\n\ndef leak(urllib):\n    return urllib.request.urlopen('http://127.0.0.1:8004/')\n",
            "a proxy handler": original + "\n\ndef leak(h):\n    return h.ProxyHandler({})\n",
            "a second host": mutate('HOST, PORT = "127.0.0.1", 8004', 'HOST, PORT = "192.168.1.5", 8004'),
            "another port": mutate('HOST, PORT = "127.0.0.1", 8004', 'HOST, PORT = "127.0.0.1", 8005'),
            "a host literal elsewhere": original + "\n\nDEST = 'http://example.com/x'\n",
            "a connection to another target": mutate("http.client.HTTPConnection(HOST, PORT, timeout=60)", "http.client.HTTPConnection('127.0.0.1', 5175, timeout=60)"),
            "a tunnel": mutate("            connection.connect()\n", "            connection.set_tunnel('proxy')\n            connection.connect()\n"),
            "a printed header list": original + "\n\ndef leak(resp):\n    print(resp.getheaders())\n",
            "a header read outside default_send": original + "\n\ndef leak(resp):\n    return resp.getheader('Set-Cookie')\n",
            "a printed cookie": original + "\n\ndef leak(ctx):\n    emit('x', note=str(ctx.session.cookies))\n",
            "a printed token": original + "\n\ndef leak(ctx):\n    emit('x', note=ctx.session.csrf)\n",
            "a printed password": mutate('    password = prompt("web account', '    print(password)\n    password = prompt("web account'),
            "a password in an emit call": original + "\n\ndef leak(password):\n    emit('x', note=password)\n",
            "a raw body printed": original + "\n\ndef leak(reply):\n    emit('x', note=reply.raw.decode())\n",
            "an emit of an unsafe key": original + "\n\ndef leak(reply):\n    emit('x', note=reply.value['csrf_token'])\n",
            "an input": original + "\n\ndef leak():\n    return input('x')\n",
            "a different prompt": mutate("prompt or pf.terminal_prompt", "prompt or getpass_like"),
            "a prompt not checked first": mutate("        prompt_route.require_genuine(pf)               # before any prompt is built or used\n", "        pass\n"),
            "a file write": original + "\n\ndef leak():\n    return open('/x', 'w')\n",
            "the environment": original + "\n\ndef leak():\n    return os.environ\n",
            "the password named in another function": original + "\n\ndef leak():\n    password = 'x'\n    return password\n",
            "a second prompt": original + "\n\ndef leak(prompt):\n    return prompt('x')\n",
            "a logger": "import logging\n" + original,
            "requests": "import requests\n" + original,
            "httpx": "import httpx\n" + original,
            "sys.stderr": original + "\n\ndef leak():\n    sys.stderr.write('x')\n",
        }
        for label, mutated in mutants.items():
            self.assertNotEqual(mutated, original, label)
            self.assertNotEqual(http_tool_problems(mutated), [], label)
            self.assertNotEqual(orchestrator_digest(mutated), self.PIN, label)
        # a change the rules allow still changes the pin
        quiet = original.replace('QUANTITY, CONFLICT_QUANTITY, CASH, AS_OF = "10", "11"', 'QUANTITY, CONFLICT_QUANTITY, CASH, AS_OF = "10", "12"')
        self.assertNotEqual(quiet, original)
        self.assertEqual(http_tool_problems(quiet), [])
        self.assertNotEqual(orchestrator_digest(quiet), self.PIN)

    def test_the_reviewers_ten_leak_mutants_each_fail_the_rules_and_not_only_the_pin(self):
        """TR8S2 M-2: each of these passed the first version of the rules (a local variable carried the secret to `emit`, to a raised code or to `Retry`). All ten must now fail the
        RULES (taint tracking, the hard rule on the password, the ban on dynamic names and on connection attributes), and each changes the pin as well."""
        original = self.source()

        def rep(old, new):
            self.assertEqual(original.count(old), 1, old)
            return original.replace(old, new)
        login_call = '    reply = session.request("POST", "/api/v1/auth/login", json.dumps({"username": username, "password": password}), mutation=True)\n'
        mutants = {
            "M1 the password via a local, then emitted": rep(login_call, '    body = json.dumps({"username": username, "password": password})\n'
                                                                        '    reply = session.request("POST", "/api/v1/auth/login", body, mutation=True)\n    emit("login_sent", note=body)\n'),
            "M2 the raw login body via a local": rep('    emit("login", status=reply.status, code=code, body_sha256=sha256_hex(reply.raw), body_bytes=len(reply.raw))\n',
                                                      '    text = reply.raw.decode("utf-8", "replace")\n    emit("login", status=reply.status, code=code, note=text)\n'),
            "M3 the raw body in a Finding code": rep('    raise Finding("LOGIN_UNEXPECTED")', '    raise Finding("LOGIN_UNEXPECTED " + reply.raw.decode())'),
            "M4 the session's __dict__ emitted": rep('        emit("login", status=200, verdict="SIGNED_IN")', '        emit("login", status=200, verdict="SIGNED_IN", note=repr(vars(session)))'),
            "M5 the exception text emitted": rep('emit("uncaught", code=type(error).__name__, verdict="STOP")', 'emit("uncaught", code=type(error).__name__, note=str(error), verdict="STOP")'),
            "M6 the Cookie header via a local": rep('            headers["Cookie"] = "; ".join("%s=%s" % (k, v) for k, v in sorted(self.cookies.items()))\n',
                                                     '            headers["Cookie"] = "; ".join("%s=%s" % (k, v) for k, v in sorted(self.cookies.items()))\n'
                                                     '            jar = headers["Cookie"]\n            emit("cookie", note=jar)\n'),
            "M7 the Set-Cookie list via a local": rep('        self._absorb(set_cookies)\n', '        self._absorb(set_cookies)\n        seen = ";".join(set_cookies)\n        emit("sc", note=seen)\n'),
            "M8 a private attribute of the connection": rep('connection = http.client.HTTPConnection(HOST, PORT, timeout=60)',
                                                             'connection = http.client.HTTPConnection(HOST, PORT, timeout=60)\n    connection._tunnel_host = None'),
            "M9 HTTPConnection through getattr and argv": rep('    connection = http.client.HTTPConnection(HOST, PORT, timeout=60)\n',
                                                              '    Conn = getattr(http.client, "HTTP" + "Connection")\n    connection = Conn(sys.argv[-1], PORT, timeout=60)\n'
                                                              '    connection = http.client.HTTPConnection(HOST, PORT, timeout=60)\n'),
            "M10 a retry code taken from the body": rep('        raise Retry("LOGIN_REFUSED", True)', '        raise Retry(reply.raw.decode()[:60], True)'),
        }
        for label, mutated in mutants.items():
            self.assertNotEqual(http_tool_problems(mutated), [], label)
            self.assertNotEqual(orchestrator_digest(mutated), self.PIN, label)
        # TR8S3 N-L2: five more leaks that crossed a function boundary or a container, and a local container
        more = {
            "N1 a raw body on ctx, emitted elsewhere": original + "\n\ndef leak(ctx, reply):\n    ctx.note = reply.raw\n",
            "N2 a cookie in a module-level list": original + "\n\nLOG = []\n\n\ndef leak(session):\n    LOG.append(session.cookies)\n",
            "N3 str(e) of a ValueError": original + "\n\ndef leak(send):\n    try:\n        send()\n    except ValueError as problem:\n        emit('x', note=str(problem))\n",
            "N4 a token on a class attribute": original + "\n\ndef leak(reply):\n    Session.token = reply.csrf\n",
            "N5 str(e) of a BaseException": original + "\n\ndef leak(send):\n    try:\n        send()\n    except BaseException as error:\n        emit('x', note=str(error))\n",
            "N6 str(e) of an OSError tuple": original + "\n\ndef leak(send):\n    try:\n        send()\n    except (OSError, KeyError) as error:\n        emit('x', note=repr(error))\n",
            "N7 a local container, then emitted": original + "\n\ndef leak(reply):\n    parts = []\n    parts.append(reply.raw)\n    emit('x', note=parts)\n",
            "N8 a module-level dict": original + "\n\nSEEN = {}\n\n\ndef leak(session):\n    SEEN['c'] = session.cookies\n",
        }
        for label, mutated in more.items():
            self.assertNotEqual(http_taint_problems(ast.parse(mutated)), [], label)         # the taint rule itself, not an unrelated rule
            self.assertNotEqual(http_tool_problems(mutated), [], label)
            self.assertNotEqual(orchestrator_digest(mutated), self.PIN, label)
        # the password rule alone (without the taint rules) already rejects M1: the password is a direct value in the login call or nowhere
        self.assertTrue(any("password" in problem for problem in http_password_problems(ast.parse(mutants["M1 the password via a local, then emitted"]),
                                                                                         {n.name: n for n in ast.walk(ast.parse(mutants["M1 the password via a local, then emitted"]))
                                                                                          if isinstance(n, ast.FunctionDef)})))

    def test_it_is_discovered_listed_and_no_other_module_imports_it_or_the_prompt_route_it_uses_for_http(self):
        self.assertIn(HTTP_TOOLS["r8 http check"], discover(SRC))
        for path in sorted(SRC.rglob("*.py")):
            if path == HTTP_TOOLS["r8 http check"]:
                continue
            for node in ast.walk(ast.parse(path.read_text("utf8"))):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    self.assertNotIn("r8_http_check", ast.unparse(node), str(path))


if __name__ == "__main__":
    unittest.main()
