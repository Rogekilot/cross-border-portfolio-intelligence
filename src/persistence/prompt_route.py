"""TR7R4-L-1: the RUNTIME check that a gated tool's password route is the real one.

Every gated tool (the launcher, the admission probe, the installer, the identity seed and the publisher tool) reaches its password through
`real_preflight.terminal_prompt` and `real_preflight.connect_with_prompt` only (PD-0077, PD-0078). The static tests pin the source of the tools; this
module is the check that runs at start, before any prompt is used: the preflight module the tool holds IS `persistence.real_preflight`, and its
`terminal_prompt` and `connect_with_prompt` ARE the objects this module saw when it was imported (so a look-alike module with its own prompt, or a
prompt function replaced after import, is found). A tool whose check fails refuses to start and writes nothing.

It reads nothing, writes nothing and opens no connection.
"""
from __future__ import annotations

from persistence import real_preflight as _genuine

_MODULE_NAME = "persistence.real_preflight"
_PROMPT = _genuine.terminal_prompt
_CONNECT = _genuine.connect_with_prompt


class PromptRouteError(Exception):
    """The tool's preflight module or its prompt route is not the genuine one. `reason` says which."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def require_genuine(module):
    """Raise `PromptRouteError` unless `module` is `persistence.real_preflight` and its prompt and connection functions are the original objects."""
    if module is not _genuine or getattr(module, "__name__", None) != _MODULE_NAME:
        raise PromptRouteError("the preflight module is not persistence.real_preflight")
    if getattr(module, "terminal_prompt", None) is not _PROMPT:
        raise PromptRouteError("terminal_prompt is not the original function of persistence.real_preflight")
    if getattr(module, "connect_with_prompt", None) is not _CONNECT:
        raise PromptRouteError("connect_with_prompt is not the original function of persistence.real_preflight")
