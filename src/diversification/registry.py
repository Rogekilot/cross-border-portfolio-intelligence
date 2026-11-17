"""Bundled byte-identical Quant registry; thresholds are read, never invented."""
import json
from pathlib import Path

from diversification.contracts import digest
from product_contract.methodology_registry import REQUIRED_FIELDS

REGISTRY_BYTES = Path(__file__).with_name("diversification_registry.json").read_bytes()
REGISTRY = json.loads(REGISTRY_BYTES)
REGISTRY_ID = REGISTRY["registry_id"]
REGISTRY_DIGEST = digest(REGISTRY)
METRIC_IDS = frozenset(row["metric_id"] for row in REGISTRY["entries"])
if len(METRIC_IDS) != len(REGISTRY["entries"]) or any(set(REQUIRED_FIELDS) - set(row) for row in REGISTRY["entries"]):
    raise ValueError("invalid diversification registry")


def thresholds(frequency):
    row = REGISTRY["common"]["statistical_thresholds"][frequency]
    return row["insufficient_below"], row["available_from"]


def annualization(frequency):
    # Existing CP4 frequency constants, shared with its statistics.
    from risk.single import PERIODS_PER_YEAR
    return PERIODS_PER_YEAR[frequency]
