"""F1 R7, no database: the RUNTIME check of the password route in each gated tool (technical TR7R4-L-1).

Each of the five tools (the launcher, the admission probe, the installer, the identity seed and the publisher tool) calls `prompt_route.require_genuine(pf)`
before any prompt is built or used. This module shows that a substituted preflight module, or a replaced `terminal_prompt` or `connect_with_prompt`, makes
each tool refuse: no prompt asked, no connection opened, nothing written, and the reason named. (It lives here, and not in `test_real_tools_start`, because
the static test keeps the real installer out of the other test modules.)
"""
from __future__ import annotations

import io
import sys
import types
import unittest
import uuid
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import test_real_tools_start as base  # noqa: E402
from persistence import prompt_route, real_install, real_preflight as pf, real_workspace_store  # noqa: E402
from real_tools import admission_probe, identity_seed, loader_window  # noqa: E402
from web_api import real_launcher  # noqa: E402

SOCKET, TEST_NAME, SCHEMA, EXECUTOR, ACCOUNT = base.SOCKET, base.TEST_NAME, base.SCHEMA, base.EXECUTOR, base.ACCOUNT
#: The loader's window tool (R8) takes the password from the prompt like the five; the offline `qualify_run` has no prompt and is not here.
TOOLS = ("launcher", "admission probe", "installer", "identity seed", "publisher", "loader window")


class PromptRouteTests(unittest.TestCase):
    def fake_module(self):
        """A look-alike of the preflight module: everything copied, its own `terminal_prompt` (which a mutant would make read a file)."""
        fake = types.ModuleType("persistence.prompting")
        fake.__dict__.update({k: v for k, v in vars(pf).items() if not k.startswith("__")})
        fake.terminal_prompt = lambda role: "from a file"
        return fake

    def run_tool(self, name, asked, opened, out):
        prompt = lambda role: asked.append(role) or "x"                    # noqa: E731
        connect = lambda *a, **k: opened.append(a) or mock.Mock()          # noqa: E731
        base_args = ["--socket", SOCKET, "--user", EXECUTOR]
        if name == "launcher":
            return real_launcher.main(["--socket", SOCKET, "--database", TEST_NAME, "--user", EXECUTOR, "--schema", SCHEMA, "--account-user", ACCOUNT,
                                       "--contexts-file", "/nonexistent/c.json"], connect=connect, prompt=prompt,
                                      serve=mock.Mock(side_effect=AssertionError("served")), out=out)
        if name == "admission probe":
            return admission_probe.main(["--socket", SOCKET, "--database", TEST_NAME, "--user", EXECUTOR, "--schema", SCHEMA, "--purpose", "ARCHIVE_READ",
                                         "--owner-id", str(uuid.uuid4()), "--root-id", str(uuid.uuid4()), "--context", "c" * 64, "--generation", "2"],
                                        connect=lambda a, p: opened.append(a), prompt=prompt, out=out)
        if name == "loader window":
            return loader_window.main(["load", "--socket", SOCKET, "--database", TEST_NAME, "--user", EXECUTOR, "--schema", SCHEMA, "--store-root", "/nonexistent",
                                       "--release-name", "n", "--file", "a" * 64, "--proposal", "/nonexistent/p"],
                                      connect=lambda a, p: opened.append(a), prompt=prompt, out=out)
        if name == "installer":
            return real_install.main(["check"] + base_args, prompt=prompt, out=out, connect=connect)
        if name == "identity seed":
            return identity_seed.main(base_args + ["--seed-file", "/nonexistent/s", "--proposal", "/nonexistent/p"], prompt=prompt, out=out, connect=connect)
        return real_workspace_store.main(["--socket", SOCKET, "--database", TEST_NAME, "--user", EXECUTOR, "--schema", SCHEMA, "status"],
                                         connect=lambda a: opened.append(a), out=out, prompt=prompt)

    def test_a_substituted_preflight_module_makes_each_tool_refuse(self):
        import persistence
        modules = {"launcher": real_launcher, "admission probe": admission_probe, "installer": real_install, "identity seed": identity_seed,
                   "loader window": loader_window}
        for name in TOOLS:
            with self.subTest(name):
                asked, opened, out = [], [], io.StringIO()
                fake = self.fake_module()
                if name == "publisher":
                    with mock.patch.object(persistence, "real_preflight", fake):          # the publisher imports it inside `main`
                        status = self.run_tool(name, asked, opened, out)
                else:
                    with mock.patch.object(modules[name], "pf", fake):
                        status = self.run_tool(name, asked, opened, out)
                self.assertNotEqual(status, 0, name)
                self.assertIn("PROMPT_ROUTE", out.getvalue(), name)
                self.assertIn("not persistence.real_preflight", out.getvalue(), name)
                self.assertEqual((asked, opened), ([], []), name)                          # no prompt asked, no connection opened

    def test_a_replaced_prompt_or_connection_function_makes_each_tool_refuse(self):
        for attribute in ("terminal_prompt", "connect_with_prompt"):
            for name in TOOLS:
                with self.subTest(attribute=attribute, tool=name):
                    asked, opened, out = [], [], io.StringIO()
                    with mock.patch.object(pf, attribute, lambda *a, **k: "from a file"):
                        status = self.run_tool(name, asked, opened, out)
                    self.assertNotEqual(status, 0, name)
                    self.assertIn("PROMPT_ROUTE", out.getvalue(), name)
                    self.assertIn("is not the original function", out.getvalue(), name)
                    self.assertEqual((asked, opened), ([], []), name)

    def test_the_genuine_module_passes_the_check(self):
        prompt_route.require_genuine(pf)
        self.assertIs(prompt_route._genuine, pf)
        with self.assertRaises(prompt_route.PromptRouteError):
            prompt_route.require_genuine(types.ModuleType("persistence.real_preflight"))


if __name__ == "__main__":
    unittest.main()
