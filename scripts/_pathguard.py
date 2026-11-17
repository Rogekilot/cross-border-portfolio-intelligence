#!/usr/bin/env python3
"""Confine a mutating script's destination to its canonical root.

Doctrine: HEA-CC-MASTER §3.13 / §28. The write-authority model reasons about
*mutation capability*, not about whether the runtime happened to name a tool
`Write`. A helper script that accepts an arbitrary destination is a write tool
wearing a different name.

## Why this is written defensively

An earlier version resolved the deepest existing ancestor and then re-attached the
not-yet-existing tail with `joinpath`, which does not normalize. A destination like

    runtime/executions/y/../../../security-policy.json

therefore compared as "inside" the root lexically (the prefix matched) while the real
filesystem path escaped it, and `mkdir(parents=True)` then realized the intermediate
directory so the write landed outside. Adversarial review overwrote the repository's
own security policy through it.

The lesson generalizes: a containment check that compares an *unnormalized* path is
not a containment check. This version therefore applies four independent defences and
requires all of them to agree.
"""
from __future__ import annotations
import os
from pathlib import Path, PurePath


class ConfinementError(ValueError):
    """A destination path escaped its permitted root."""


def confine(destination, root, project_root=None) -> Path:
    project_root = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    allowed = (project_root / root).resolve()

    raw = PurePath(str(destination))

    # 1. No `..` anywhere in the supplied path. These destinations are harness-internal
    #    and there is no legitimate reason to traverse upward. Rejecting the component
    #    outright removes the entire class rather than trying to out-normalize it.
    if any(part == ".." for part in raw.parts):
        raise ConfinementError(
            f"destination {destination!r} contains a '..' component. Upward traversal is "
            f"never required for a harness-internal destination and is refused outright "
            f"(HEA §3.13)."
        )

    candidate = Path(raw) if raw.is_absolute() else (project_root / raw)

    # 2. Normalize lexically, so any residual `.`/`..` cannot survive into the compare.
    normalized = Path(os.path.normpath(str(candidate)))

    # 3. Resolve the deepest EXISTING ancestor, so a symlink planted mid-path cannot be
    #    used to step out, then re-attach the tail and normalize again.
    probe, tail = normalized, []
    while not probe.exists():
        if probe.parent == probe:
            break
        tail.append(probe.name)
        probe = probe.parent
    resolved = Path(os.path.normpath(str(probe.resolve().joinpath(*reversed(tail)))))

    # 4. Both the lexical and the symlink-resolved forms must land inside the root.
    for check in (normalized, resolved):
        try:
            check.relative_to(allowed)
        except ValueError:
            raise ConfinementError(
                f"destination {destination!r} resolves to {check}, which is outside the "
                f"permitted root {allowed}. This script may only write under {root} "
                f"(HEA §3.13: an indirect mutation path is still a mutation path)."
            )
    return resolved


def confined_arg(destination, root, project_root=None) -> Path:
    """confine(), but exit(2) with a clear message instead of raising."""
    import sys
    try:
        return confine(destination, root, project_root)
    except ConfinementError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
