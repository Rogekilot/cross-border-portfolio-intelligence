"""The Computation Manifest (`finweb.computation_manifest/1`; tech plan 16.2, extending 6.2) and `reproduce`.

An immutable record of the QUESTION: which ledger version (and a digest of the live events at it), which market-data release
and files, which conventions (ledger replay, market data, performance), which calendar files, which suppressions, which
as-of date and window. `manifest_id` is the sha256 of its canonical JSON. The ANSWER is identified separately by
`result_digest` (sha256 of the canonical metrics), so the manifest names the question and the digest the answer.

`reproduce(...)` re-runs a manifest against supplied inputs and reports, as a typed status, whether the ledger, the release,
the conventions and the consumed file set (in BOTH directions: a file the re-run reads that the manifest does not cite is a
hidden input) and the result digest all agree.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from marketdata.canonical import canonical_json, sha256_hex
from marketdata.manifest import DataSetRef, FileRef
from performance.results import ComputedMetric, WindowUsed, metrics_digest

MANIFEST_SCHEMA = "finweb.computation_manifest/1"
ENGINE_ID = "performance/cp4-0.16"  # bumped on ANY change to a computation (like an adapter version); `ENGINE_PINS` in test_performance_boundaries pins the engine source hashes so a change cannot be silent
CALENDAR_ADAPTER_SUFFIX = ".calendar"


class ManifestBuildError(ValueError):
    pass


def calendar_files(refs: Iterable[FileRef]) -> Tuple[FileRef, ...]:
    """The calendar files among the consumed files (the calendar adapter's id ends in `.calendar`)."""
    return tuple(sorted({r for r in refs if r.adapter_id.endswith(CALENDAR_ADAPTER_SUFFIX)}))


@dataclass(frozen=True)
class ComputationManifest:
    portfolio_id: Optional[str]
    reporting_currency: str
    ledger_version: int
    ledger_digest: str
    as_of: datetime.date
    window: WindowUsed
    valuation_mode: str
    conventions: Tuple[Tuple[str, str], ...]  # sorted pairs, e.g. ("market_data.fx", "...")
    conformant: bool
    open_items: Tuple[str, ...]
    release_id: Optional[str]
    data_set_refs: Tuple[DataSetRef, ...]
    calendar_file_refs: Tuple[FileRef, ...]
    split_suppressions_digest: str
    methodology: Tuple[str, ...]  # registry entry ids; empty while the registry is empty (PRD 33)
    numerics: Tuple[Tuple[str, str], ...]
    synthetic: bool
    engine_id: str = ENGINE_ID
    schema: str = MANIFEST_SCHEMA
    state_kind: str = "ACTUAL"
    scope: str = "PORTFOLIO"  # "PORTFOLIO" or "ACCOUNT:<id>" (Ruling 4.5)
    as_of_rule: str = "CALLER"  # "CALLER" (the caller names D) or "D_c(t)" (Ruling 1.7, Current mode)
    instant: Optional[datetime.datetime] = None  # Current mode: the instant t (the engine never reads a clock)
    as_of_causes: Tuple[str, ...] = ()  # why no D_c(t) could be chosen, if so
    identity_digest: str = ""  # CP3-6: the identity facts (trading currency, MIC, security type) the computation asked the resolver for
    split_detection: str = "CALLER_SUPPLIED"  # CP3-4: where the suppressions came from ("F8B_DRY_RUN": detection ran; "CALLER_SUPPLIED": the caller said)
    parent_release_id: Optional[str] = None  # Current mode: the release `M` that `M_t` is derived from (`release_id` is `M_t`)
    excluded_files: Tuple[str, ...] = ()  # Current mode: hashes of the files of `M` retrieved after `t` (performance/1.2 Ruling 1.7)
    identities_run: Tuple[str, ...] = ()  # Ruling 11.1 (performance/1.2 Q5): which runtime identities this call was asked to run (the lineage records each outcome)
    source_registry_digest: str = ""  # performance/1.12 Ruling 1.7 item 4: SHA-256 of the full source records of the sources with a file in the M read (M_t in Current mode); "" where the port carries none
    detection_policy: Tuple[Tuple[str, str], ...] = ()  # CP3-11: the F8 confirmation policy detection ran under: ("digest", sha256), ("feed", "a,b"), ("filing", "c"); empty when the caller supplied the suppressions

    def to_obj(self) -> Dict[str, Any]:
        return {
            "detection_policy": [list(p) for p in self.detection_policy],
            "identities_run": list(self.identities_run),
            "identity_digest": self.identity_digest, "source_registry_digest": self.source_registry_digest, "split_detection": self.split_detection, "parent_release_id": self.parent_release_id,
            "excluded_files": list(self.excluded_files),
            "scope": self.scope, "as_of_rule": self.as_of_rule, "instant": self.instant, "as_of_causes": list(self.as_of_causes),
            "schema": self.schema, "engine_id": self.engine_id, "state_kind": self.state_kind,
            "portfolio_id": self.portfolio_id, "reporting_currency": self.reporting_currency,
            "ledger_version": self.ledger_version, "ledger_digest": self.ledger_digest, "as_of": self.as_of,
            "window": self.window.to_obj(), "valuation_mode": self.valuation_mode,
            "conventions": [list(p) for p in self.conventions], "conformant": self.conformant,
            "open_items": list(self.open_items), "release_id": self.release_id,
            "data_set_refs": [r.to_obj() for r in self.data_set_refs],
            "calendar_files": [[f.file_sha256, f.adapter_id, f.adapter_version] for f in self.calendar_file_refs],
            "split_suppressions_digest": self.split_suppressions_digest, "methodology": list(self.methodology),
            "numerics": [list(p) for p in self.numerics], "synthetic": self.synthetic,
        }

    @property
    def manifest_id(self) -> str:
        return sha256_hex(canonical_json(self.to_obj()).encode("utf-8"))

    def consumed_files(self) -> Tuple[FileRef, ...]:
        return tuple(sorted({f for r in self.data_set_refs for f in r.consumed}))


@dataclass(frozen=True)
class ComputationResult:
    manifest: ComputationManifest
    metrics: Tuple[ComputedMetric, ...]
    result_digest: str

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {"manifest_id": self.manifest.manifest_id, "manifest": self.manifest.to_obj(),
                "result_digest": self.result_digest, "metrics": [m.to_canonical_dict() for m in self.metrics]}

    def canonical_json(self) -> str:
        return canonical_json(self.to_canonical_dict())


def seal(manifest: ComputationManifest, metrics: Sequence[ComputedMetric]) -> ComputationResult:
    """Stamp every metric with the manifest id and compute the result digest."""
    mid = manifest.manifest_id
    stamped = tuple(m.with_manifest(mid) for m in metrics)
    return ComputationResult(manifest, stamped, metrics_digest(stamped))


@unique
class ReproductionStatus(Enum):
    REPRODUCED = "REPRODUCED"
    RESULT_NOT_COMPARED = "RESULT_NOT_COMPARED"  # CP3-6: the question re-ran and its inputs agree, but no expected result digest was given: nothing was compared, so it is NOT "reproduced"
    LEDGER_DIGEST_MISMATCH = "LEDGER_DIGEST_MISMATCH"
    RELEASE_MISMATCH = "RELEASE_MISMATCH"
    CONVENTION_MISMATCH = "CONVENTION_MISMATCH"
    SUPPRESSIONS_MISMATCH = "SUPPRESSIONS_MISMATCH"
    SOURCE_REGISTRY_MISMATCH = "SOURCE_REGISTRY_MISMATCH"  # the source registry records the re-run used differ from the manifest's (performance/1.12 Ruling 1.7 item 4)
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"  # the identity registry facts the re-run used differ from the manifest's (CP3-6)
    FILE_NOT_CITED = "FILE_NOT_CITED"  # the re-run read a file the manifest does not cite: a hidden input
    FILE_NOT_READ = "FILE_NOT_READ"  # the manifest cites a file the re-run did not read
    MANIFEST_DIFFERS = "MANIFEST_DIFFERS"
    RESULT_DIFFERS = "RESULT_DIFFERS"


@dataclass(frozen=True)
class ReproductionReport:
    status: ReproductionStatus
    detail: str = ""
    rerun: Optional[ComputationResult] = None

    @property
    def reproduced(self) -> bool:
        return self.status is ReproductionStatus.REPRODUCED
