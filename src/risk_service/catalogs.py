"""Read the committed reference catalogs (`data/marketdata/BENCHMARKS.json`, `data/marketdata/RISK_FREE.json`) and parse them with `domain.catalogs` (which holds every rule).

The files are the main session's; this module never writes one. A file that is missing, unreadable or malformed is an error (`CatalogError`): there is no default catalog, so a product with no catalog admits
no benchmark and no risk-free series rather than guessing one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from domain.catalogs import BenchmarkCatalog, CatalogError, RiskFreeCatalog, parse_benchmark_catalog, parse_risk_free_catalog

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "marketdata"
BENCHMARKS_FILE = "BENCHMARKS.json"
RISK_FREE_FILE = "RISK_FREE.json"


def _read(root: Path, name: str) -> bytes:
    path = root / name
    try:
        return path.read_bytes()
    except OSError as error:
        raise CatalogError(f"cannot read the catalog {path}: {error}") from None


def load_benchmark_catalog(root: Optional[Path] = None) -> BenchmarkCatalog:
    return parse_benchmark_catalog(_read(DEFAULT_ROOT if root is None else root, BENCHMARKS_FILE))


def load_risk_free_catalog(root: Optional[Path] = None) -> RiskFreeCatalog:
    return parse_risk_free_catalog(_read(DEFAULT_ROOT if root is None else root, RISK_FREE_FILE))
