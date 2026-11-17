"""The risk methodology registry as DATA (`risk/1.4` Ruling 9; tech plan 17.6, 17.15, 17.17; PRD sections 16.3 and 33).

The registry is the Quant's text (`methodology/registry/RISK_1.4_REGISTRY.json`, part of the text of `risk/1.4`; one file per version, named after its id, older files kept as records); the engine carries a BYTE-IDENTICAL copy (`risk/risk_registry.json`, so the engine does not depend on the
repository's `methodology/` directory at run time) and a test (`test_risk_registry_matches_methodology`) fails if the copy and the text ever differ, if its id is not the id of the document, or if any of its numbers
disagrees with the grid it was derived from. The id is read from the file's `registry_id`, never from its name. An entry is identified by its `metric_id`; a result cites `<registry_id>#<metric_id>`; the SHA-256 of the
canonical JSON of the whole file is the `registry_digest` every manifest records (Ruling 9.2).

THE ENGINE HOLDS NO THRESHOLD. Every minimum-observation count the engine applies comes from `minimum_observations(...)` below, which reads the entry; no risk module has a count literal (a test scans for one). The UI
and the AI layer read the same entries (PRD 16.3: the UI never invents a threshold).

An entry holds the fifteen PRD section 33 fields and the seven structured fields of Ruling 9.1. A value may be a POINTER, the string `common.<name>` (a whole field value, or one item of a list field), to the shared block
`common`; `resolved(...)` expands those; a string that mentions a pointer inside prose is left as written (the loader checks that every pointer it contains names an existing `common` key, so none dangles).

Pure: the one file read is this package's own bundled data file, at import.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

from marketdata.canonical import canonical_json, sha256_hex
from product_contract.methodology_registry import REQUIRED_FIELDS, MethodologyRegistry

REGISTRY_FILE = Path(__file__).with_name("risk_registry.json")
_POINTER = re.compile(r"\bcommon\.([a-z_]+)\b")
_ADDED = ("metric_id", "judgment_class", "reference_point", "comparability_class", "presentation", "states", "wording")
FREQUENCIES = ("DAILY", "WEEKLY", "MONTHLY")


class RegistryError(ValueError):
    """The registry file is malformed: a missing field, a dangling pointer, a duplicate id."""


@dataclass(frozen=True)
class MinimumObservations:
    """`insufficient_below` and `available_from`, in observations at the stated frequency (Ruling 7.1): `n < insufficient_below` is INSUFFICIENT_DATA, `insufficient_below <= n < available_from` is LIMITED,
    `n >= available_from` has no sufficiency caveat. A window fact has `1` and `1`: no statistical minimum, one full period."""

    insufficient_below: int
    available_from: int


class RiskRegistry:
    def __init__(self, data: Mapping[str, Any]):
        self._data = data
        self.registry_id: str = str(data["registry_id"])
        self._common: Mapping[str, Any] = data["common"]
        entries = data["entries"]
        self._entries: Dict[str, Mapping[str, Any]] = {}
        for item in entries:
            metric_id = item.get("metric_id")
            if not isinstance(metric_id, str) or not metric_id:
                raise RegistryError("an entry has no metric_id")
            if metric_id in self._entries:
                raise RegistryError(f"two entries for {metric_id!r}")
            missing = [f for f in tuple(REQUIRED_FIELDS) + _ADDED + ("defined_in",) if f not in item]
            if missing:
                raise RegistryError(f"{metric_id}: missing field(s) {missing}")
            self._entries[metric_id] = item
        for name in self._references():
            if name not in self._common:
                raise RegistryError(f"a pointer names common.{name}, which does not exist")
        self.digest: str = sha256_hex(canonical_json(data).encode("utf-8"))

    # -- the shape ----------------------------------------------------------------------------------------------------------------------
    @property
    def metric_ids(self) -> FrozenSet[str]:
        return frozenset(self._entries)

    @property
    def common(self) -> Mapping[str, Any]:
        return self._common

    def entry(self, metric_id: str) -> Mapping[str, Any]:
        try:
            return self._entries[metric_id]
        except KeyError:
            raise KeyError(f"{metric_id!r} is not in the registry {self.registry_id}") from None

    def entry_key(self, metric_id: str) -> str:
        """`risk/1.3#risk_volatility`: what a result cites (Ruling 9.2)."""
        self.entry(metric_id)
        return f"{self.registry_id}#{metric_id}"

    def entries(self) -> Tuple[Mapping[str, Any], ...]:
        return tuple(self._entries[k] for k in sorted(self._entries))

    # -- pointers ------------------------------------------------------------------------------------------------------------------------
    def _references(self) -> List[str]:
        found: List[str] = []

        def walk(node: Any) -> None:
            if isinstance(node, str):
                found.extend(_POINTER.findall(node))
            elif isinstance(node, Mapping):
                for v in node.values():
                    walk(v)
            elif isinstance(node, (list, tuple)):
                for v in node:
                    walk(v)

        for item in self._entries.values():
            walk(item)
        return found

    def _resolve(self, node: Any) -> Any:
        if isinstance(node, str):
            match = _POINTER.fullmatch(node)
            return self._common[match.group(1)] if match else node
        if isinstance(node, Mapping):
            return {k: self._resolve(v) for k, v in node.items()}
        if isinstance(node, (list, tuple)):
            return [self._resolve(v) for v in node]
        return node

    def resolved(self, metric_id: str) -> Dict[str, Any]:
        """The entry with every whole-value pointer replaced by the `common` text it names (a pointer inside prose is left as written)."""
        return self._resolve(self.entry(metric_id))

    # -- what the engine reads ------------------------------------------------------------------------------------------------------------
    def minimum_observations(self, metric_id: str, frequency: str) -> MinimumObservations:
        """The thresholds of `metric_id` at `frequency`, from the entry's `minimum_observations` (a pointer to `common.minimum_observations_statistical` or `..._window_fact`). The engine has no other source."""
        if frequency not in FREQUENCIES:
            raise ValueError(f"unknown frequency {frequency!r}")
        table = self.resolved(metric_id)["minimum_observations"]
        row = table[frequency]
        return MinimumObservations(int(row["insufficient_below"]), int(row["available_from"]))

    def methodology_registry(self) -> MethodologyRegistry:
        """The entries as a `product_contract.methodology_registry.MethodologyRegistry`: each must carry the fifteen PRD section 33 fields (the constructor validates them)."""
        return MethodologyRegistry(entries=self.entries())


def load_registry(raw: Optional[bytes] = None, *, implements: Optional[str] = None) -> RiskRegistry:
    """Parse the bundled registry (or `raw`, for tests). Fails closed on a malformed file, and REFUSES a file whose `registry_id` is not the `risk` id this engine implements (Ruling 9.2 (1.2); the id is read from the
    file's content, never from its name). `implements=None` is the engine's own id; a test that wants to read an older record passes the id it expects."""
    text = (REGISTRY_FILE.read_bytes() if raw is None else raw).decode("utf-8")
    registry = RiskRegistry(json.loads(text))
    expected = IMPLEMENTED_REGISTRY_ID if implements is None else implements
    if registry.registry_id != expected:
        raise RegistryError(f"the registry file carries registry_id {registry.registry_id!r}; this engine implements {expected!r} and refuses any other")
    return registry


IMPLEMENTED_REGISTRY_ID = "risk/1.11"  # the `risk` convention id this engine implements (Ruling 9.2 (1.2)); a newer registry is a new engine version, never a silent load. risk/1.10 and risk/1.11 are label re-issues of risk/1.9 (Ruling 9.2 (1.10)); 1.11 names market-data/1.16; ids are ordered by their numeric components (1.10 follows 1.9), never as strings
REGISTRY: RiskRegistry = load_registry()
REGISTRY_ID: str = REGISTRY.registry_id
RISK_METRIC_IDS: FrozenSet[str] = REGISTRY.metric_ids
METHODOLOGY_REGISTRY: MethodologyRegistry = REGISTRY.methodology_registry()
