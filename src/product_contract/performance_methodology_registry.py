"""Read-only CP3 methodology appendix, without changing historical manifests.

The bundled JSON is byte-identical to the Quant's performance/1.12 appendix,
issue `performance-registry/1.2` (`methodology/registry/PERFORMANCE_1.12_REGISTRY_APPENDIX_1.2.json`).
Its `registry_id` is still `performance/1.12`: 1.1 and 1.2 re-issue the appendix so that
`common.implementation_version` names `market-data/1.15` and `market-data/1.16` respectively, the label the code runs,
and no performance ruling changes. Two appendix texts therefore share one
`registry_id` and differ in `appendix_id` and digest; the digest is what a result
pins. The 1.0 text (`PERFORMANCE_1.12_REGISTRY.json`) stays as a record and is refused here.
This consumer exposes accepted definitions; numerical methods still belong to
the existing performance engine. Returned objects are detached copies.
"""
from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from product_contract.methodology_registry import MethodologyRegistry, validate_entry

REGISTRY_FILE = Path(__file__).with_name("performance_methodology_registry.json")
REGISTRY_BYTES = REGISTRY_FILE.read_bytes()
_BUNDLED_IDS = frozenset(row["metric_id"] for row in json.loads(REGISTRY_BYTES)["entries"])
_POINTER = re.compile(r"\bcommon\.[a-z_]+(?:\.[a-z_]+)*\b")


class RegistryError(ValueError):
    pass


def _lookup(data, pointer):
    value = data
    for part in pointer.split("."):
        if not isinstance(value, dict) or part not in value:
            raise RegistryError("dangling methodology pointer: " + pointer)
        value = value[part]
    return value


def _resolve(data, value, seen=()):
    if isinstance(value, str):
        if _POINTER.fullmatch(value):
            if value in seen:
                raise RegistryError("circular methodology pointer: " + value)
            return _resolve(data, _lookup(data, value), seen + (value,))
        for pointer in _POINTER.findall(value):
            _lookup(data, pointer)
        return value
    if isinstance(value, dict):
        return {key: _resolve(data, item, seen) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(data, item, seen) for item in value]
    return value


@dataclass(frozen=True)
class PerformanceMethodologyRegistry:
    _json: str

    @property
    def registry_id(self):
        return self.to_obj()["registry_id"]

    @property
    def appendix_id(self):
        return self.to_obj()["appendix_id"]

    @property
    def digest(self):
        return hashlib.sha256(self._json.encode("utf-8")).hexdigest()

    @property
    def metric_ids(self):
        return frozenset(row["metric_id"] for row in self.to_obj()["entries"])

    def to_obj(self):
        return json.loads(self._json)

    def entries(self):
        return tuple(sorted(self.to_obj()["entries"], key=lambda row: row["metric_id"]))

    def entry(self, metric_id):
        for row in self.entries():
            if row["metric_id"] == metric_id:
                return row
        raise KeyError(metric_id)

    def resolved(self, metric_id):
        return _resolve(self.to_obj(), self.entry(metric_id))

    def entry_key(self, metric_id):
        self.entry(metric_id)
        return self.registry_id + "#" + metric_id


def load_registry(raw=None):
    data = json.loads(REGISTRY_BYTES if raw is None else raw)
    if data.get("registry_id") != "performance/1.12" or data.get("appendix_id") != "performance-registry/1.2":
        raise RegistryError("unsupported performance methodology appendix")
    ids = []
    for entry in data["entries"]:
        validate_entry(entry)
        ids.append(entry.get("metric_id"))
    if len(ids) != 24 or len(ids) != len(set(ids)) or set(ids) != _BUNDLED_IDS:
        raise RegistryError("appendix ids differ from the performance engine registry")
    _resolve(data, data["entries"])
    return PerformanceMethodologyRegistry(json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


REGISTRY = load_registry()
REGISTRY_ID = REGISTRY.registry_id
REGISTRY_DIGEST = REGISTRY.digest
METHODOLOGY_REGISTRY = MethodologyRegistry(entries=REGISTRY.entries())
