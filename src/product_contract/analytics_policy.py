"""Explicit composition of the owner's immutable PD-0041 capital decision.

This is a product-wide denominator policy, not a user's investment constraint.
The historical CP5 engine still requires an explicit policy input. Applications
opt in to this approved reference rather than changing that engine's default.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from diversification.contracts import CapitalUniverseChoice

REFERENCE_FILE = Path(__file__).with_suffix(".json")
DECISION_PATH = "decisions/product/PD-0041-hg3-approved-with-conditions-and-cp6-start.md"
DECISION_FILE = Path(__file__).resolve().parents[2] / DECISION_PATH
DECISION_SHA256 = "62af1421c47b878252ef361c989151acac0db7f5aef67cec13d554c1ca1dc925"
REFERENCE_SHA256 = "c756a8328302269c2df4ed9d76471e1e04ee5ac1f2ade16680a5364e458c1157"


class ApprovedPolicyError(ValueError):
    """The approved reference or its owner evidence is missing or differs."""


def _verified_bytes(raw, path, expected, label):
    if raw is None:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ApprovedPolicyError(label + " is unavailable") from exc
    if not isinstance(raw, bytes):
        raise TypeError(label + " must be bytes")
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ApprovedPolicyError(label + " digest differs from the approved reference")
    return raw


def load_approved_capital_policy(*, reference_bytes=None, decision_bytes=None):
    """Return a frozen FULL_NAV choice after verifying reference and owner bytes.

    Optional byte inputs support offline reproduction of the same immutable
    decision. They cannot admit a different policy, scope or owner statement.
    No benchmark, source admission, personal target or risk tolerance is created.
    """
    raw = _verified_bytes(reference_bytes, REFERENCE_FILE, REFERENCE_SHA256, "analytics policy")
    _verified_bytes(decision_bytes, DECISION_FILE, DECISION_SHA256, "PD-0041 owner decision")
    reference = json.loads(raw)
    evidence = json.dumps({"policy_id": reference["policy_id"], "reference_sha256": REFERENCE_SHA256,
                           "decision": reference["decision"], "presentation": reference["presentation"]},
                          sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return CapitalUniverseChoice(reference["choice"], reference["origin"], evidence,
                                 reference["decision"]["decision_id"], reference["scope_kind"],
                                 product_id=reference["product_id"], portfolio_id=reference["portfolio_id"],
                                 account_id=reference["account_id"])
