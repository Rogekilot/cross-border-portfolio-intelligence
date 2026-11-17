"""F1 R5: the PURE RENDER of the claim limits of the single-date valuation (design 7.4; Ruling 6.5 items 5 and 6 of market-data/1.16).

`marketdata.claim_limits` carries the Quant's items as data (C-1 to C-6 may claim; N-1 to N-9 may not) and renders nothing. This module renders
them into the block an R5 output carries and the R7 screen shows, under the design's numbering (7.4):

  may say, slots   S1 the holding value `quantity x p` (the vendor's call, the price session, the missed sessions, as-traded RAW)  <- C-1
                   S2 the label source, as the stored record states it                                                  <- C-1 (its last sentences)
                   S3 the NAV on the valuation date, the state / freshness / delay and the reconciliation status        <- C-2, C-3, C-4
                   S4 the named inputs: the files of M with their hashes, L, the convention sets                        <- C-5
                   S5 the stored record's label status and source, the exposure window and the V1 statement             <- C-6
  may NOT claim    C1 the series is verified as-traded: its split label AND its dividend component are UNVERIFIABLE <- N-1, N-2, N-3
                   C2 that p is the official closing-cross price as checked                                        <- N-4
                   C3 a comparison with any other source                                                           <- N-5
                   C4 that the listing had no split, or that split history is complete or verified                 <- N-6
                   C5 anything about a SPLITS response                                                             <- N-7
                   C6 that the quantity is verified, or that it is the owner's holding                             <- N-8
                   C7 anything about another date, a return, or any performance or risk figure                     <- N-9

THE RULE OF ORIGIN. The real-source sentences (the vendor, the call, the session, the owner's reading) are produced ONLY when the stored
`market_origin` is `REAL_SOURCE`, and only from the lineage fields. Over any other origin the same block carries the invented-data mark and every
slot holds that mark; no real-source sentence is produced and no C-item is stated about a series that does not exist (design 4.3). The origin is
read from the stored fields passed in, never assumed. The block is built from nothing but its inputs: no connection, no clock, no network, no
vendor name (the vendor is a slot), no price, no market number.

A SLOT IS FILLED FROM ITS LINEAGE FIELD (`SLOT_FIELDS`) and from nothing else. THE LINEAGE of a real root is the flat mapping that
`marketdata.claim_record.lineage_of` copies from the root's THREE STORED HOMES and from nothing else (the Quant's ruling of 2026-11-10, section 1): (I) the
issued document, (R) the stored response, and (K) the claim record that the create wrote into that response from the values the computation used. The
preconditions that the fixed text depends on (the label status, the label source's status, the reconciliation status, the V1 statement, the open items)
are checked there, before any text renders. A lineage that lacks a field, or holds an empty or non-text value, is refused (`ClaimRenderError`) rather than
rendered with a hole: a caveat that cannot be filled is not softened. The label source is whatever the record states (a stored result that cites
market-data/1.15 or earlier says MEMORY, never DECLARED); it is not hard-coded here.

TWO VARIANTS, ONE SET OF TWELVE IDS (the ruling's section 6; PD-0082 Q4). The state of the lineage (`metric_state`) picks the variant: `AVAILABLE` and
`LIMITED` give the normal block (the valuation date and the price session are separate slots, so a stale close is true in the same sentence);
`INSUFFICIENT_DATA` gives the WITHHELD variant (`WITHHELD_SLOT_FIELDS`), which says that no close values the holding and states no price, label, window or
reconciliation status. Any other state is refused.

COMPLETENESS (`missing_items`, `check_block`): a rendering is complete only if every S-slot S1 to S5 is present with every one of its lineage
fields filled, every C-item C1 to C7 is present, each item's text carries the required terms of the Quant items it renders (P3: a status word or a
field name is not translated), and the Quant's list is covered item by item. Removing any one item makes the check fail.
"""
from __future__ import annotations

from marketdata import claim_limits as cl

REAL_SOURCE = "REAL_SOURCE"            # the one stored market origin that may produce a real-source sentence (compared, never hard-wired into text)
INVENTED_DATA_MARK = "Invented test data; no claim about any real source."
#: What the storage seal does and does not check (PD-0073; R3 disposition 5.2; TR5-L2). Said in S4, next to the ledger it names. It checks the
#: ledger by its pin, and says it does NOT verify the instrument identity facts the computation asked of its resolver (disposition 5.2) or the origin
#: in the engine's manifest. It says nothing about the context: for a real-source result the seal does bind the result to its context's snapshot
#: (`rw_check_real`), and the fictional context's unverified `context_id` (disposition 5.5) is a test-only limit that never renders here.
SEAL_LIMIT = ("The seal that stores the result checks the ledger by its pin (the ledger version), not by its content; the staging and the "
              "reproduce of the result are what catch a different ledger. The seal does not verify the instrument identity facts the computation "
              "used (trading currency, exchange and security type), and it does not verify the origin recorded in the engine's manifest.")
#: The key set of a rendered block (`render_claim_block`'s return value). The scoped contract takes it from here, so the shape lives in one place.
BLOCK_KEYS = frozenset(("items", "slots", "invented_data_mark"))

#: slot -> the lineage field that fills it (S-slot name -> {slot: lineage field}), the NORMAL variant. A label source is read from
#: `adjustment_label_source` (marketdata/contracts.py), never hard-coded. The valuation date and the price session are two fields (the ruling, section 4).
SLOT_FIELDS = {
    "S1": {"valuation_date": "valuation_date", "price_session_date": "price_session_date", "missed_sessions": "missed_sessions",
           "quantity": "ledger_quantity", "source": "source_name", "exchange": "exchange_mic", "call": "vendor_call",
           "documentation_reference": "documentation_reference", "label_source": "adjustment_label_source"},
    "S2": {"label_source": "adjustment_label_source"},
    "S3": {"reporting_currency": "reporting_currency", "valuation_date": "valuation_date", "quantity": "ledger_quantity", "cash": "opening_cash",
           "state": "metric_state", "freshness": "freshness", "delay": "delay_status", "reconciliation": "reconciliation_status"},
    "S4": {"file_hashes": "file_hashes", "ledger_version": "ledger_version", "convention_ids": "convention_ids"},
    "S5": {"label_status": "adjustment_label_status", "label_source": "adjustment_label_source", "price_session_date": "price_session_date",
           "retrieval_time": "retrieval_time", "v1_statement": "v1_statement"},
}
#: The WITHHELD variant (a real NAV in state `INSUFFICIENT_DATA`; the ruling's section 6): the same five groups, and S2 and S5 hold no slot because their
#: sentences say that nothing is stated. `quantity` sits in S1 (the C6 item names it) and is not used by S1's own sentence.
WITHHELD_SLOT_FIELDS = {
    "S1": {"valuation_date": "valuation_date", "quantity": "ledger_quantity", "state": "metric_state"},
    "S2": {},
    "S3": {"reporting_currency": "reporting_currency", "valuation_date": "valuation_date", "state": "metric_state", "nav_cause": "nav_cause",
           "freshness": "freshness", "delay": "delay_status"},
    "S4": SLOT_FIELDS["S4"],
    "S5": {},
}
S_SLOTS = tuple(SLOT_FIELDS)
#: the NAV states that pick a variant. Nothing else renders.
NORMAL_STATES = ("AVAILABLE", "LIMITED")
WITHHELD_STATE = "INSUFFICIENT_DATA"
#: design item -> the Quant items it renders (7.4 and the module docstring)
S_ITEMS = {"S1": ("C-1",), "S2": ("C-1",), "S3": ("C-2", "C-3", "C-4"), "S4": ("C-5",), "S5": ("C-6",)}
C_ITEMS = {"C1": ("N-1", "N-2", "N-3"), "C2": ("N-4",), "C3": ("N-5",), "C4": ("N-6",), "C5": ("N-7",), "C6": ("N-8",), "C7": ("N-9",)}
WITHHELD_S_ITEMS = {"S1": ("C-1X",), "S2": (), "S3": ("C-2X",), "S4": ("C-5",), "S5": ("C-6X",)}
WITHHELD_C_ITEMS = {"C1": ("N-1X",), "C2": ("N-4X",), "C3": ("N-5X",), "C4": ("N-6",), "C5": ("N-7",), "C6": ("N-8",), "C7": ("N-9",)}
C_IDS = tuple(C_ITEMS)
ALL_ITEM_IDS = S_SLOTS + C_IDS
#: S2's own sentence in the withheld variant (it has no Quant item; its required terms are `claim_limits.WITHHELD_S2_TERMS`)
WITHHELD_S2_TEXT = "No label source is stated: no reading values the holding."


class ClaimRenderError(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__("%s: %s" % (code, detail) if detail else code)


def _fill(lineage, mapping):
    if type(lineage) is not dict:
        raise ClaimRenderError("CLAIM_LINEAGE_SHAPE", "the lineage is an object")
    values = {}
    for slot, field in mapping.items():
        value = lineage.get(field)
        if isinstance(value, (list, tuple)) and value and all(type(v) is str and v for v in value):
            value = ", ".join(value)
        if type(value) is not str or not value.strip():
            raise ClaimRenderError("CLAIM_LINEAGE_FIELD", "the lineage field %r (slot %s) is missing or empty" % (field, slot))
        values[slot] = value
    return values


def _statement(limit_id, values):
    item = cl.claim_limit(limit_id)
    return item.statement.format(**{name: values[name] for name in item.slots})


def _s_texts(values_by_slot, withheld=False):
    s1, s2, s3, s4, s5 = (values_by_slot[name] for name in S_SLOTS)
    inputs = ("The inputs are named: the files of M with their hashes (%s), L (the ledger version %s) and the convention sets %s. %s"
              % (s4["file_hashes"], s4["ledger_version"], s4["convention_ids"], SEAL_LIMIT))
    if withheld:
        return {"S1": _statement("C-1X", s1), "S2": WITHHELD_S2_TEXT, "S3": _statement("C-2X", s3), "S4": inputs, "S5": _statement("C-6X", s5)}
    return {
        "S1": _statement("C-1", s1),
        "S2": "The label source is %s. The series is read as as-traded (RAW) on the vendor's declaration of it, which is not a verification "
              "(V1 and V4 have not checked it)." % s2["label_source"],
        "S3": " ".join((_statement("C-2", s3), _statement("C-3", s3), _statement("C-4", s3))),
        "S4": inputs,
        "S5": _statement("C-6", s5),
    }


def _c_texts(quantity, withheld=False):
    items = WITHHELD_C_ITEMS if withheld else C_ITEMS
    return {item_id: " ".join(_statement(q, {"quantity": quantity}) for q in quant_ids) for item_id, quant_ids in items.items()}


def variant_of_lineage(lineage):
    """`"NORMAL"` or `"WITHHELD"` by the lineage's `metric_state` (the NAV row's state). Any other state, or a lineage that has none, is refused: there is
    no block for a state this module does not know (P8, and no fallback)."""
    if type(lineage) is not dict:
        raise ClaimRenderError("CLAIM_LINEAGE_SHAPE", "the lineage is an object")
    state = lineage.get("metric_state")
    if state in NORMAL_STATES:
        return "NORMAL"
    if state == WITHHELD_STATE:
        return "WITHHELD"
    raise ClaimRenderError("CLAIM_STATE_UNKNOWN", "the NAV state names no claim block")


def _variant_of_slots(slots):
    """The variant a rendered block's `slots` are shaped for: the withheld variant is the one whose S3 group has the cause of the withheld NAV."""
    return "WITHHELD" if type(slots) is dict and type(slots.get("S3")) is dict and "nav_cause" in slots["S3"] else "NORMAL"


def _mappings(variant):
    return WITHHELD_SLOT_FIELDS if variant == "WITHHELD" else SLOT_FIELDS


def render_claim_block(origin, lineage=None):
    """The claim-limit block for one stored root. `origin` is the stored four-field origin (read from the stored response or root row);
    `lineage` is the flat mapping of `SLOT_FIELDS` (or of `WITHHELD_SLOT_FIELDS`, by its `metric_state`) and is read ONLY for a `REAL_SOURCE` origin.
    Returns `{"items": [...], "slots": {...}, "invented_data_mark": str | None}`."""
    if type(origin) is not dict or "market_origin" not in origin:
        raise ClaimRenderError("CLAIM_ORIGIN_MISSING", "the stored origin fields are required")
    if origin["market_origin"] != REAL_SOURCE:
        # Any other origin: the mark, and no sentence about a real source. The lineage is not read (a test scope has none worth a claim).
        return {"items": [], "slots": {name: INVENTED_DATA_MARK for name in S_SLOTS}, "invented_data_mark": INVENTED_DATA_MARK}
    withheld = variant_of_lineage(lineage) == "WITHHELD"
    values = {name: _fill(lineage, mapping) for name, mapping in _mappings("WITHHELD" if withheld else "NORMAL").items()}
    texts = _s_texts(values, withheld)
    texts.update(_c_texts(values["S1"]["quantity"], withheld))
    s_items, c_items = (WITHHELD_S_ITEMS, WITHHELD_C_ITEMS) if withheld else (S_ITEMS, C_ITEMS)
    items = [{"id": item_id, "kind": cl.MAY_CLAIM if item_id in S_SLOTS else cl.MAY_NOT_CLAIM,
              "quant_ids": list((s_items if item_id in S_SLOTS else c_items)[item_id]), "text": texts[item_id]} for item_id in ALL_ITEM_IDS]
    return {"items": items, "slots": values, "invented_data_mark": None}


def lineage_from_slots(slots):
    """The flat lineage a rendered block's `slots` were filled from (TR5-L5): each slot value goes back to its lineage field through `SLOT_FIELDS` (or
    `WITHHELD_SLOT_FIELDS` for a block shaped as the withheld variant). A lineage field that fills more than one slot (the label source, the valuation
    date, the quantity, the state) must hold ONE value across them; slots that disagree, a missing or extra slot, or a missing or extra slot value is
    refused (`ClaimRenderError`), never repaired. Pure."""
    if type(slots) is not dict or set(slots) != set(SLOT_FIELDS):
        raise ClaimRenderError("CLAIM_SLOTS_SHAPE", "the slot groups are exactly S1 to S5")
    lineage = {}
    for slot, mapping in _mappings(_variant_of_slots(slots)).items():
        group = slots[slot]
        if type(group) is not dict or set(group) != set(mapping):
            raise ClaimRenderError("CLAIM_SLOTS_SHAPE", "slot %s holds exactly its own values" % slot)
        for slot_name, field in mapping.items():
            value = group[slot_name]
            if type(value) is not str or not value.strip():
                raise ClaimRenderError("CLAIM_LINEAGE_FIELD", "slot %s value %r is missing or empty" % (slot, slot_name))
            if lineage.setdefault(field, value) != value:
                raise ClaimRenderError("CLAIM_SLOTS_DISAGREE", "the lineage field %r is filled with two different values" % field)
    return lineage


def missing_items(block, origin):
    """The design item ids a rendering lacks (empty for a complete one). For a non-`REAL_SOURCE` origin the block is complete when it carries
    the mark in every S-slot and no item at all."""
    if origin.get("market_origin") != REAL_SOURCE:
        ok = (block.get("invented_data_mark") == INVENTED_DATA_MARK and not block.get("items")
              and all(block.get("slots", {}).get(name) == INVENTED_DATA_MARK for name in S_SLOTS))
        return frozenset() if ok else frozenset(ALL_ITEM_IDS)
    present = {item.get("id") for item in block.get("items", ())}
    missing = set(ALL_ITEM_IDS) - present
    for name, mapping in _mappings(_variant_of_slots(block.get("slots"))).items():
        group = block.get("slots", {}).get(name)
        if type(group) is not dict or any(type(group.get(slot)) is not str or not group[slot].strip() for slot in mapping):
            missing.add(name)
    return frozenset(missing)


def check_block(block, origin):
    """Problems of a rendering, as strings (empty for a sound one): the missing items, any item the list does not define, a Quant item that no
    design item covers, and a required term (P3) that the item's text lacks."""
    problems = ["missing %s" % item_id for item_id in sorted(missing_items(block, origin))]
    if origin.get("market_origin") != REAL_SOURCE:
        return problems
    withheld = _variant_of_slots(block.get("slots")) == "WITHHELD"
    by_id = {item.get("id"): item for item in block.get("items", ())}
    for item_id in sorted(set(by_id) - set(ALL_ITEM_IDS)):
        problems.append("unknown item %s" % item_id)
    covered = set()
    for item_id, item in by_id.items():
        for quant_id in item.get("quant_ids", ()):
            covered.add(quant_id)
            try:
                limit = cl.claim_limit(quant_id)
            except KeyError:
                problems.append("unknown Quant item %s in %s" % (quant_id, item_id))
                continue
            for term in limit.required_terms:
                if term not in item.get("text", ""):
                    problems.append("%s lacks the required term %r of %s" % (item_id, term, quant_id))
    if withheld:       # S2's withheld sentence is the renderer's own and has no Quant item: its terms are checked here
        for term in cl.WITHHELD_S2_TERMS:
            if term not in by_id.get("S2", {}).get("text", ""):
                problems.append("S2 lacks the required term %r" % term)
    problems += ["Quant item %s is not in this block's list" % q for q in sorted(cl.unknown_claim_limits(covered, withheld=withheld))]
    problems += ["Quant item %s is not covered" % q for q in sorted(cl.missing_claim_limits(covered, withheld=withheld))]
    return problems
