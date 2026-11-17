"""The Risk Manifest (`finweb.risk_manifest/1`; `risk/1.2` Ruling 9.4; tech plan 17.7.5, 17.16) and `reproduce_risk`.

An immutable record of the QUESTION a risk result answers. It EMBEDS the Computation Manifest of the portfolio leg (`performance.manifest.ComputationManifest`: ledger version and digest, the market-data release and
the quote and FX files read, the conventions, the suppressions, the source registry digest, the request and the grid, all in its `manifest_id`) and adds what only the risk layer knows:

- the risk engine id, the `registry_id` and the `registry_digest` of the registry file the metrics were computed under (Ruling 9.2: both are recorded);
- the request (rule, months, `B`, `E`), the frequency, the grid rule and the metrics asked for;
- the risk-free block: the currency, the series id, the files read, the catalog id and digest, and a digest of every period's `(f_k, m_k, state)` (Ruling 9.4);
- the benchmark block: the selection PIN (portfolio, version, state, the row in force: UAT-03), the catalog id and digest, the entry's digest, the files read, the currency treatment;
- the identities that were run (RD-1, RD-3, RQ-1 and the series' I-10, I-11).

`manifest_id` is the sha256 of its canonical JSON. The ANSWER is identified separately by `result_digest` (sha256 of the canonical metrics): the manifest names the question, the digest the answer. The calculation
timestamp is NOT recorded (metadata, never part of a digest). `reproduce_risk` re-asks the question against supplied inputs and says, as a typed status, which input differs; the files the re-run reads are compared
with the manifest's in BOTH directions, per kind (a hidden input is a status, not a pass).
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Dict, Optional, Tuple

from marketdata.canonical import canonical_json, sha256_hex
from marketdata.manifest import FileRef
from performance.manifest import ComputationManifest
from risk.results import RiskMetric, risk_digest

RISK_MANIFEST_SCHEMA = "finweb.risk_manifest/1"


def file_obj(f: FileRef) -> list:
    return [f.file_sha256, f.adapter_id, f.adapter_version]


@dataclass(frozen=True)
class RiskFreeBlock:
    """Ruling 9.4: the risk-free series, the files read, and for each period `f_k` and `m_k` (as a digest; the per-period values are in lineage)."""

    currency: str
    series_id: Optional[str]
    consumed: Tuple[FileRef, ...]
    catalog_id: str
    catalog_digest: str
    periods_digest: str
    synthetic: bool

    def to_obj(self) -> Dict[str, Any]:
        return {"currency": self.currency, "series_id": self.series_id, "consumed": [file_obj(f) for f in self.consumed], "catalog_id": self.catalog_id, "catalog_digest": self.catalog_digest,
                "periods_digest": self.periods_digest, "synthetic": self.synthetic}


@dataclass(frozen=True)
class BenchmarkBlock:
    """Ruling 5.6 / 9.4: the selection pin and everything the benchmark leg read. `pin` is `SelectionPin.to_obj()`."""

    pin: Dict[str, Any]
    benchmark_id: Optional[str]
    catalog_id: Optional[str]
    catalog_digest: Optional[str]
    entry_digest: Optional[str]
    consumed: Tuple[FileRef, ...]
    currency_treatment: Optional[str]
    synthetic: bool
    #: Ruling 5.8 item 6 (Current mode): for `g_n`, the calculation day of the benchmark and the ECB fixing date actually used (None in historical mode, and when no level was read)
    level_date_gn: Optional[datetime.date] = None
    fixing_date_gn: Optional[datetime.date] = None

    def to_obj(self) -> Dict[str, Any]:
        out = {"pin": self.pin, "benchmark_id": self.benchmark_id, "catalog_id": self.catalog_id, "catalog_digest": self.catalog_digest, "entry_digest": self.entry_digest,
               "consumed": [file_obj(f) for f in self.consumed], "currency_treatment": self.currency_treatment, "synthetic": self.synthetic}
        if self.level_date_gn is not None or self.fixing_date_gn is not None:  # present only in Current mode: every historical manifest id is unchanged
            out["level_date_gn"], out["fixing_date_gn"] = self.level_date_gn, self.fixing_date_gn
        return out


@dataclass(frozen=True)
class CurrentBlock:
    """Ruling 5.8 item 6 and `performance` Ruling 1.7: a Current-mode result records the mode, the instant `t`, the as-of date `D_c(t)` the engine chose (and the causes if it could not), `M` (the release the caller
    named) and the hashes of the files `M_t` leaves out. `end` of the manifest is `D_c(t)`."""

    valuation_mode: str
    instant: datetime.datetime
    as_of_rule: str
    as_of: Optional[datetime.date]
    as_of_causes: Tuple[str, ...]
    parent_release_id: str
    excluded_files: Tuple[str, ...]

    def to_obj(self) -> Dict[str, Any]:
        return {"valuation_mode": self.valuation_mode, "instant": self.instant, "as_of_rule": self.as_of_rule, "as_of": self.as_of, "as_of_causes": list(self.as_of_causes),
                "parent_release_id": self.parent_release_id, "excluded_files": list(self.excluded_files)}


@dataclass(frozen=True)
class RiskManifest:
    risk_engine_id: str
    registry_id: str
    registry_digest: str
    metrics: Tuple[str, ...]                         # the metric ids asked for, sorted
    frequency: str
    request_rule: str                                # TRAILING_MONTHS, YTD, SINCE_INCEPTION, CUSTOM or MAX_AVAILABLE
    request_months: Optional[int]
    request_base: Optional[datetime.date]            # the caller's `B` for CUSTOM
    end: datetime.date
    boundary_rule_id: str
    series: ComputationManifest                      # the portfolio leg's question (ledger, release, conventions, window, grid)
    series_digest: str
    risk_free: Optional[RiskFreeBlock]
    benchmark: Optional[BenchmarkBlock]
    identities: Tuple[Tuple[str, str], ...]
    verify_identities: bool
    numerics: Tuple[Tuple[str, str], ...]
    synthetic: bool
    schema: str = RISK_MANIFEST_SCHEMA
    state_kind: str = "ACTUAL"
    current: Optional[CurrentBlock] = None           # Ruling 5.8 item 6: Current mode only

    def to_obj(self) -> Dict[str, Any]:
        out = self._base_obj()
        if self.current is not None:  # present only in Current mode: every historical manifest id is unchanged
            out["current"] = self.current.to_obj()
        return out

    def _base_obj(self) -> Dict[str, Any]:
        return {
            "schema": self.schema, "risk_engine_id": self.risk_engine_id, "registry_id": self.registry_id, "registry_digest": self.registry_digest, "metrics": list(self.metrics),
            "frequency": self.frequency, "request_rule": self.request_rule, "request_months": self.request_months, "request_base": self.request_base, "end": self.end,
            "boundary_rule_id": self.boundary_rule_id, "series_manifest_id": self.series.manifest_id, "series_manifest": self.series.to_obj(), "series_digest": self.series_digest,
            "risk_free": None if self.risk_free is None else self.risk_free.to_obj(), "benchmark": None if self.benchmark is None else self.benchmark.to_obj(),
            "identities": [list(p) for p in self.identities], "verify_identities": self.verify_identities, "numerics": [list(p) for p in self.numerics], "synthetic": self.synthetic,
            "state_kind": self.state_kind,
        }

    @property
    def manifest_id(self) -> str:
        return sha256_hex(canonical_json(self.to_obj()).encode("utf-8"))

    def consumed_files(self, kind: str = "ALL") -> Tuple[FileRef, ...]:
        """The files the question read. `kind`: `SERIES` (quotes, FX and calendars of the portfolio leg), `RISK_FREE`, `BENCHMARK` or `ALL` (their union)."""
        series = {f for r in self.series.data_set_refs for f in r.consumed}
        rf = set() if self.risk_free is None else set(self.risk_free.consumed)
        bm = set() if self.benchmark is None else set(self.benchmark.consumed)
        pick = {"SERIES": series, "RISK_FREE": rf, "BENCHMARK": bm, "ALL": series | rf | bm}[kind]
        return tuple(sorted(pick))


@dataclass(frozen=True)
class RiskResult:
    manifest: RiskManifest
    metrics: Tuple[RiskMetric, ...]
    result_digest: str

    def to_canonical_dict(self) -> Dict[str, Any]:
        return {"manifest_id": self.manifest.manifest_id, "manifest": self.manifest.to_obj(), "result_digest": self.result_digest, "metrics": [m.to_canonical_dict() for m in self.metrics]}

    def canonical_json(self) -> str:
        return canonical_json(self.to_canonical_dict())

    def metric(self, metric_id: str) -> RiskMetric:
        (found,) = [m for m in self.metrics if m.metric_id == metric_id]
        return found


def seal(manifest: RiskManifest, metrics: Tuple[RiskMetric, ...]) -> RiskResult:
    """Stamp every metric with the manifest id and compute the result digest."""
    mid = manifest.manifest_id
    stamped = tuple(m.with_manifest(mid) for m in sorted(metrics, key=lambda m: m.metric_id))
    return RiskResult(manifest, stamped, risk_digest(stamped))


@unique
class RiskReproductionStatus(Enum):
    REPRODUCED = "REPRODUCED"
    RESULT_NOT_COMPARED = "RESULT_NOT_COMPARED"            # the question re-ran and its inputs agree, but no expected digest was given: nothing was compared, so it is NOT "reproduced"
    LEDGER_DIGEST_MISMATCH = "LEDGER_DIGEST_MISMATCH"
    RELEASE_MISMATCH = "RELEASE_MISMATCH"
    CONVENTION_MISMATCH = "CONVENTION_MISMATCH"
    SUPPRESSIONS_MISMATCH = "SUPPRESSIONS_MISMATCH"
    SOURCE_REGISTRY_MISMATCH = "SOURCE_REGISTRY_MISMATCH"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    REGISTRY_MISMATCH = "REGISTRY_MISMATCH"                # the registry id or digest differs (Ruling 9.2)
    CATALOG_MISMATCH = "CATALOG_MISMATCH"                  # a catalog's id or digest differs
    SELECTION_MISMATCH = "SELECTION_MISMATCH"              # the selection log, at the manifest's version, gives another pin
    FILE_NOT_CITED = "FILE_NOT_CITED"                      # the re-run read a portfolio-leg file the manifest does not cite: a hidden input
    FILE_NOT_READ = "FILE_NOT_READ"
    RISK_FREE_FILE_NOT_CITED = "RISK_FREE_FILE_NOT_CITED"
    RISK_FREE_FILE_NOT_READ = "RISK_FREE_FILE_NOT_READ"
    BENCHMARK_FILE_NOT_CITED = "BENCHMARK_FILE_NOT_CITED"
    BENCHMARK_FILE_NOT_READ = "BENCHMARK_FILE_NOT_READ"
    MANIFEST_DIFFERS = "MANIFEST_DIFFERS"
    RESULT_DIFFERS = "RESULT_DIFFERS"


@dataclass(frozen=True)
class RiskReproductionReport:
    status: RiskReproductionStatus
    detail: str = ""
    rerun: Optional[RiskResult] = None

    @property
    def reproduced(self) -> bool:
        return self.status is RiskReproductionStatus.REPRODUCED
