"""Ruling 6.5 item 6 (market-data/1.16): what a single-date valuation may claim and may not claim, as DATA.

The Quant's list is numbered so that a shortened rendering (an R5 output, an R7 screen, an AI explanation) can be checked item by item
(P3: plainer wording may drop precision, never a caveat that changes the conclusion). PD-0066 decision 2 and the F1 final check (finding
F-2) asked for the dividend component as an item of its own: **N-2**. This module carries the ids and the Quant's statements; it renders
nothing and decides nothing. It is deterministic data with no clock, no network and no vendor name: the vendor, the call, the session
and the label source are SLOTS that the renderer fills from the lineage (`implementation/CP7_F1_REAL_PATH_DESIGN.md` 7.4, slots S1 to S5),
so a label source is never hard-coded here (a stored result that cites market-data/1.15 or earlier says MEMORY, never DECLARED).

The statements are those of `methodology/CP2_MARKET_DATA_CONVENTIONS.md`, Ruling 6.5 item 6, "The claim limits, as one numbered list"
(1.16). They describe the HG4 single-date check and no other scope (item 7). The design's section 7.4 numbers the may-not items C1 to C7 and
joins N-1, N-2 and N-3 in its C1; the Quant's numbering here is the finer one, and R5 and R7 map the two.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import FrozenSet, Iterable, Tuple

MAY_CLAIM = "MAY_CLAIM"
MAY_NOT_CLAIM = "MAY_NOT_CLAIM"


@dataclass(frozen=True)
class ClaimLimit:
    limit_id: str
    kind: str
    statement: str  # the Quant's sentence(s); `{slot}` marks a value the renderer fills from a lineage field
    slots: Tuple[str, ...] = ()
    #: phrases that every rendering must still contain, in whatever wording and locale it uses them (P3). Canonical English tokens that carry
    #: the caveat: a status word or a field name is not translated.
    required_terms: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in (MAY_CLAIM, MAY_NOT_CLAIM):
            raise ValueError(f"unknown claim kind {self.kind!r}")
        used = tuple(sorted(set(re.findall(r"\{([a-z0-9_]+)\}", self.statement))))
        if used != tuple(sorted(self.slots)):
            raise ValueError(f"{self.limit_id}: the statement uses slots {used}, the item declares {tuple(sorted(self.slots))}")
        for term in self.required_terms:
            if not term.strip():
                raise ValueError(f"{self.limit_id}: a blank required term")


CLAIM_LIMITS: Tuple[ClaimLimit, ...] = (
    # --- may claim ---------------------------------------------------------------------------------------------------------------
    # O-7 (the Quant's ruling of 2026-11-10, section 5; PD-0082): the valuation date and the price session are two dates, so each has its own slot. The
    # reading date of the vendor's documentation is not stored as data, so the sentence cites the record that holds it (Q2 option (a)).
    ClaimLimit(
        "C-1", MAY_CLAIM,
        "The market value of the holding on {valuation_date} is {quantity} x p. Here p is the close {source} delivered for the {price_session_date} "
        "{exchange} session through {call}; {missed_sessions} sessions of that exchange lie after that close, up to {valuation_date} inclusive. "
        "p is read as as-traded (RAW) on the strength of the vendor's documentation of that call, as the owner read it ({documentation_reference}). "
        "The label source is {label_source}. That is the vendor's declaration, not a verification: no V1 event and no V4 record exists for this file.",
        ("valuation_date", "quantity", "source", "price_session_date", "exchange", "call", "missed_sessions", "documentation_reference", "label_source"),
        ("RAW", "not a verification")),
    ClaimLimit("C-2", MAY_CLAIM, "The NAV in {reporting_currency} on {valuation_date} is {quantity} x p + {cash}.",
               ("reporting_currency", "valuation_date", "quantity", "cash")),
    ClaimLimit("C-3", MAY_CLAIM, "The state is {state}, freshness {freshness}, delay {delay}.", ("state", "freshness", "delay"),
               ("freshness", "delay")),
    ClaimLimit("C-4", MAY_CLAIM, "The reconciliation status is {reconciliation}.", ("reconciliation",), ("SINGLE_SOURCE",)),
    ClaimLimit("C-5", MAY_CLAIM, "The inputs are named: the files of M with their hashes, L, and the convention ID the manifest cites.",
               (), ("hashes", "convention")),
    # The engine's lineage does not state these (market-data/1.16 Ruling 3.2 item 5 is not built; `UNBUILT_1_16`), so the sentence names the STORED
    # RECORD of the result, which does, and says what it does not give (the ruling's section 3.5).
    ClaimLimit(
        "C-6", MAY_CLAIM,
        "The stored record of this result states the label status ({label_status}) and the label source ({label_source}) of the reading used, "
        "the exposure window E({price_session_date}, {retrieval_time}), whose second argument is the file's retrieval time, and the statement of "
        "V1 events in M ({v1_statement}). The session list of that window is not stated: market-data/1.16 Ruling 3.2 item 5 is not built in the engine.",
        ("label_status", "label_source", "price_session_date", "retrieval_time", "v1_statement"), ("UNVERIFIABLE",)),
    # --- may not claim -----------------------------------------------------------------------------------------------------------
    ClaimLimit("N-1", MAY_NOT_CLAIM, "That the series' split label is verified. It is UNVERIFIABLE.", (), ("split", "UNVERIFIABLE")),
    # N-2 is an item of its own (PD-0066 decision 2; F1 final check F-2): it is not folded into N-1 or N-3.
    ClaimLimit(
        "N-2", MAY_NOT_CLAIM,
        "That the dividend component is verified. It is UNVERIFIABLE. M holds no corporate-action record either way, so nothing is known "
        "about such a dividend, and nothing is claimed about it.",
        (), ("dividend component", "UNVERIFIABLE")),
    ClaimLimit("N-3", MAY_NOT_CLAIM,
               "That the series is verified as-traded, or that the vendor's declaration has been checked against the exchange or a filing.",
               (), ("verified", "declaration")),
    ClaimLimit("N-4", MAY_NOT_CLAIM,
               "That p is the exchange's official closing-cross price as checked. It is single-source and unchecked, unless a Test V4 record exists.",
               (), ("closing-cross", "single-source")),
    ClaimLimit("N-5", MAY_NOT_CLAIM, "That the close was compared with any other source. There is none for this market.", (),
               ("compared", "other source")),
    ClaimLimit("N-6", MAY_NOT_CLAIM,
               "That the listing had no split, or that its split history is complete or verified, in any period.", (), ("split history",)),
    ClaimLimit("N-7", MAY_NOT_CLAIM,
               "That an empty split response, if one exists, shows anything beyond 'zero records at R'.", (), ("zero records",)),
    ClaimLimit("N-8", MAY_NOT_CLAIM,
               "That the quantity {quantity} is verified, or that it is the owner's holding. It is the ledger fact the project entered.",
               ("quantity",), ("ledger fact",)),
    ClaimLimit("N-9", MAY_NOT_CLAIM, "Anything about another date, a return, or any performance or risk figure.", (), ("another date",)),
)

#: The WITHHELD VARIANT (O-6; the ruling's section 6; PD-0082 Q4): the statements of the items whose normal text would say something false over a real NAV that is
#: `INSUFFICIENT_DATA` (no close values the holding, so there is no price session, no label of a reading used, no exposure window and no reconciliation status).
#: Same twelve design item ids; the Quant ids carry an `X`. The items not listed here (C-5 and N-6 to N-9) are the normal ones. S2's text has no Quant item (it is
#: the renderer's own, as in the normal block); its required term is `WITHHELD_S2_TERMS`.
WITHHELD_LIMITS: Tuple[ClaimLimit, ...] = (
    ClaimLimit("C-1X", MAY_CLAIM, "No holding value on {valuation_date} is stated: no close values the holding, and the NAV's state is {state}.",
               ("valuation_date", "state"), ("No holding value",)),
    ClaimLimit("C-2X", MAY_CLAIM,
               "No NAV in {reporting_currency} on {valuation_date} is stated. The state is {state}, cause {nav_cause}, freshness {freshness}, delay {delay}.",
               ("reporting_currency", "valuation_date", "state", "nav_cause", "freshness", "delay"), ("No NAV", "freshness", "delay")),
    ClaimLimit("C-6X", MAY_CLAIM, "No label status, exposure window or V1 statement is stated: no reading values the holding.", (), ("No label status",)),
    ClaimLimit("N-1X", MAY_NOT_CLAIM,
               "That any price series is verified as-traded, or that any of its labels, split or dividend component, is verified.",
               (), ("split", "dividend component", "verified")),
    ClaimLimit("N-4X", MAY_NOT_CLAIM, "That any close was used, or that any close is the exchange's official closing-cross price.", (), ("closing-cross",)),
    ClaimLimit("N-5X", MAY_NOT_CLAIM, "That any close was compared with any other source. There is none for this market.", (),
               ("compared", "other source")),
)
WITHHELD_S2_TERMS: Tuple[str, ...] = ("No label source",)
#: The ids of the variant's coverage set (what `check_block` requires a withheld block to cover, item by item).
WITHHELD_LIMIT_IDS: Tuple[str, ...] = ("C-1X", "C-2X", "C-5", "C-6X", "N-1X", "N-4X", "N-5X", "N-6", "N-7", "N-8", "N-9")

CLAIM_LIMIT_IDS: Tuple[str, ...] = tuple(item.limit_id for item in CLAIM_LIMITS)
DIVIDEND_COMPONENT_LIMIT_ID = "N-2"


def claim_limit(limit_id: str) -> ClaimLimit:
    for item in CLAIM_LIMITS + WITHHELD_LIMITS:
        if item.limit_id == limit_id:
            return item
    raise KeyError(limit_id)


def missing_claim_limits(present: Iterable[str], *, withheld: bool = False) -> FrozenSet[str]:
    """The ids of the list that a rendering does not carry. A rendering that leaves out any item, N-2 included, is incomplete (P3). `withheld`: the
    withheld variant's coverage set (`WITHHELD_LIMIT_IDS`)."""
    return frozenset(WITHHELD_LIMIT_IDS if withheld else CLAIM_LIMIT_IDS) - frozenset(present)


def unknown_claim_limits(present: Iterable[str], *, withheld: bool = False) -> FrozenSet[str]:
    """Ids a rendering carries that the list does not define: an item invented outside the Quant's list."""
    return frozenset(present) - frozenset(WITHHELD_LIMIT_IDS if withheld else CLAIM_LIMIT_IDS)
