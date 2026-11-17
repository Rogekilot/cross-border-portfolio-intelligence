"""Read the independently issued CP6 method; its bytes participate in identity."""
import json
from pathlib import Path

from marketdata.canonical import sha256_hex

_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_BYTES = (_ROOT / "methodology/registry/INSIGHTS_1.0_REGISTRY.json").read_bytes()
REGISTRY = json.loads(REGISTRY_BYTES)
METHOD_ID = REGISTRY["registry_id"]
REGISTRY_DIGEST = sha256_hex(REGISTRY_BYTES)
METHOD_DIGEST = sha256_hex((_ROOT / "methodology/CP6_INSIGHT_CONVENTIONS.md").read_bytes())
RULES = {row["rule_id"]: row for row in REGISTRY["entries"]}
POLICY_SELECTORS = RULES["user_limit"]["metric_selectors"]
