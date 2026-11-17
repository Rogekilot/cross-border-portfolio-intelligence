"""O-7: the CLAIM RECORD (K) of a real root, and the extraction of the claim lineage from the three stored homes (the Quant's ruling of 2026-11-10; PD-0082).

WHY. The claim block of a real root (`claim_render`, design 7.4) says things the performance engine's issued document does not state: the vendor's call, the
source's name, the label status and source of the reading used, the reconciliation status, the file's retrieval time, the files of M and the V1 statement
(market-data/1.16 Ruling 3.2 item 5 is not built; `market11.UNBUILT_1_16`). Those facts exist while the create holds its lease (the market-data rows, the
snapshot, the profile). They do not exist at read time (the read admission cannot read a market-data row). So the create COPIES them into the stored
response, from the values the computation used, and the seal stores the response with the root.

THE THREE HOMES, AND ONLY THEY (the ruling, section 1). A claim field is copied from

  (I) the issued document (`archive.issued`, parsed),
  (R) the stored response (`archive.response`, parsed; its `claim_record` is (K)),
  (K) the claim record.

No field value is read from a code constant at read time, a clock, the network or a default. The preconditions compare stored values with constants of the method
(the claim list's convention set, the enum texts, the Test V4 marker); P-5 reads the engine's V4 build state, by that marker, at create and at every read, by design
(C-1 and C2 say in the present tense that no V4 record exists). The functions here compute no number, round nothing and interpret nothing:
they select a stored value, copy it, and refuse when a source is missing, malformed or ambiguous ("ambiguous" is two candidate rows, or two values where one is
required). The only text forms applied are the ruling's: an integer becomes its base-10 digits; a list is handed to the renderer, which joins it with ", "; a
file entry is three stored strings joined with single spaces; a stored decimal is copied verbatim.

THE PRECONDITIONS of the fixed claim text (the ruling's 3.4, P-1 to P-10; P-9: the holding trades in the reporting currency, both variants; P-10: the withheld
variant only when no reading values the holding) are checked in `lineage_from_documents`, before any text renders. The fixed sentences are
true only under them; if one fails, the block is refused, never softened. They are checked for the create (before the seal, so an unrenderable root is never
committed; PD-0082 Q3) and again for every read, from the same stored values.

THE TWO VARIANTS. By the NAV row's state: `AVAILABLE` and `LIMITED` fill the normal block; `INSUFFICIENT_DATA` fills the withheld variant, which needs only P-6 to
P-10 (not P-1 to P-5) and the fields it names. Any other state, or two NAV rows, refuses.

Pure: no connection, no clock, no environment, no file, no network. The market-data port and the profile table are passed in. No vendor is named here.
"""
from __future__ import annotations

import datetime
import json
import re

from marketdata import claim_render as cr
from marketdata import market11, profiles
from marketdata.canonical import canonical_json
from marketdata.contracts import LabelStatus, ReconciliationStatus
from marketdata.manifest import DataKind

SCHEMA = "finweb.claim_record/1"
#: the key of (K) in the stored response
RECORD_KEY = "claim_record"
#: P-6: the convention set the fixed text is the claim list of (market-data/1.16 Ruling 6.5 item 6)
REQUIRED_CONVENTION_SET = "market-data/1.16"
#: the V1 statement of Ruling 3.2 item 5 case 3, true by definition when no member of M is a corporate-action file (P-4; the ruling's 3.3)
V1_NONE_IN_M = "no V1 event in M"
#: the engine's open item that keeps C-1's "no V4 record exists" and C2's "unless a Test V4 record exists" true (P-5)
V4_NOT_BUILT_MARKER = "Ruling 3.3, Test V4"

_OPEN_ITEM_PREFIX = "market_data: "
_COUNT = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_VALUING_KEYS = frozenset((
    "source_id", "file_sha256", "price_session_date", "source_name", "vendor_call", "documentation_reference", "call_adjustment_status",
    "adjustment_label_source", "adjustment_label_status", "retrieval_time", "reconciliation_status"))
_MEMBER_KEYS = frozenset(("data_kind", "source_id", "payload_sha256"))
_RECORD_KEYS = frozenset(("schema", "members", "valuing"))
_SHAPE_ERRORS = (KeyError, TypeError, ValueError, AttributeError, IndexError, LookupError, PermissionError)


def _refuse(code, detail=""):
    raise cr.ClaimRenderError(code, detail)


def _text(value, what):
    if type(value) is not str or not value.strip():
        _refuse("CLAIM_RECORD_SHAPE", "%s is missing or not text" % what)
    return value


def _date_text(value, what):
    text = _text(value, what)
    try:
        if datetime.date.fromisoformat(text).isoformat() != text:
            raise ValueError(text)
    except ValueError:
        _refuse("CLAIM_RECORD_SHAPE", "%s is not an ISO date" % what)
    return text


def _pairs(value, what):
    if type(value) is not list or not all(type(p) is list and len(p) == 2 and all(type(x) is str for x in p) for p in value):
        _refuse("CLAIM_RECORD_SHAPE", "%s is a list of text pairs" % what)
    return value


def _pair_value(pairs, key, what):
    found = [p[1] for p in pairs if p[0] == key]
    if not found:
        _refuse("CLAIM_RECORD_MISSING", "%s has no %r pair" % (what, key))
    if len(found) > 1:
        _refuse("CLAIM_RECORD_AMBIGUOUS", "%s has more than one %r pair" % (what, key))
    return _text(found[0], "%s %r" % (what, key))


def _one(items, what):
    if not items:
        _refuse("CLAIM_RECORD_MISSING", "no %s" % what)
    if len(items) > 1:
        _refuse("CLAIM_RECORD_AMBIGUOUS", "more than one %s" % what)
    return items[0]


# ---- (K): built at create, from the values the computation used ----------------------------------------------------------------------------------
def build_claim_record(*, snapshot, files, port, conventions, listing_id, as_of, profile_of=None):
    """The claim record (K) of one create or reproduce: a plain JSON object of text, lists and objects (no number, no null), so it is the same bytes in the stored
    response, the seal's canonical form and a reproduce.

    `snapshot`: the locked snapshot, parsed (its `members` and `source_records`). `files`: one `(file_sha256, source_id, data_kind, manifest)` per file of the
    release (`market_data_store.read_release_files`). `port`, `conventions`, `listing_id`, `as_of`: the same lookup the valuation made for the one holding
    (`port.quote_on(listing_id, as_of, conventions)`), so (K) names the reading that valued it. `profile_of`: the profile table (default `profiles.source_profile`).

    It copies and refuses; the preconditions of the fixed text are not judged here (they depend on the NAV's state, which (K) does not know): see
    `lineage_from_documents`. A structural problem (a member with no file row, a file with no call or no retrieval time, two source records of one id, a
    retrieval time that is not the reading's) raises `ClaimRenderError`."""
    try:
        return _build(snapshot, files, port, conventions, listing_id, as_of, profile_of or profiles.source_profile)
    except cr.ClaimRenderError:
        raise
    except _SHAPE_ERRORS as error:
        raise cr.ClaimRenderError("CLAIM_RECORD_SHAPE", type(error).__name__) from error


def _build(snapshot, files, port, conventions, listing_id, as_of, profile_of):
    by_sha = {}
    for sha, source_id, kind, manifest in files:
        if sha in by_sha:
            _refuse("CLAIM_RECORD_AMBIGUOUS", "a file is listed twice")
        by_sha[sha] = (source_id, kind, manifest)
    members = []
    for member in snapshot["members"]:
        sha = _text(member["payload_sha256"], "a member's hash")
        row = by_sha.get(sha)
        if row is None or row[0] != member["source_id"]:
            _refuse("CLAIM_RECORD_MISSING", "a snapshot member has no file row of its source")
        members.append({"data_kind": _text(row[1], "a file's data kind"), "source_id": _text(member["source_id"], "a member's source"), "payload_sha256": sha})
    if not members:
        _refuse("CLAIM_RECORD_MISSING", "the snapshot has no member")
    lookup = port.quote_on(listing_id, as_of, conventions)
    selected = lookup.selected
    valuing = []
    if selected is not None:
        valuing.append(_valuing(snapshot, by_sha, lookup, selected, profile_of))
    return {"schema": SCHEMA, "members": members, "valuing": valuing}


def _valuing(snapshot, by_sha, lookup, selected, profile_of):
    observation, source_id = selected.observation, selected.source_id
    lineage = observation.lineage
    row = by_sha.get(selected.file_sha256)
    if row is None or row[0] != source_id:
        _refuse("CLAIM_RECORD_MISSING", "the valuing reading's file is not a file of the release")
    manifest = row[2]
    if type(manifest) is not dict:
        _refuse("CLAIM_RECORD_SHAPE", "a file manifest is an object")
    vendor_call = _pair_value(_pairs(manifest.get("request"), "the file manifest's request"), "function", "the file manifest's request")
    retrieval_time = _text(manifest.get("retrieval_time"), "the file manifest's retrieval_time")
    parsed = datetime.datetime.fromisoformat(retrieval_time)
    if parsed.tzinfo is None or lineage.retrieved_at != parsed:
        _refuse("CLAIM_RECORD_CROSSCHECK", "the file's retrieval time is not the reading's")
    record = _one([r for r in snapshot["source_records"] if r["source_id"] == source_id], "snapshot source record of the valuing reading's source")
    call = profile_of(source_id).call_adjustment.get(vendor_call)
    if call is None:
        _refuse("CLAIM_RECORD_MISSING", "the source's profile has no entry for the call")
    reconciliation = lookup.reconciliation
    if reconciliation is None or reconciliation.status is None:
        _refuse("CLAIM_RECORD_MISSING", "the lookup stated no reconciliation status")
    status = lineage.label_status
    if status is None:
        _refuse("CLAIM_RECORD_MISSING", "the reading has no label status")
    return {
        "source_id": _text(source_id, "the valuing source"), "file_sha256": selected.file_sha256,
        "price_session_date": observation.value_date.isoformat(), "source_name": _text(record["name"], "the source record's name"),
        "vendor_call": vendor_call, "documentation_reference": _text(call.reference, "the call's documentation reference"),
        "call_adjustment_status": _text(call.status, "the call's status"),
        "adjustment_label_source": _text(lineage.adjustment_label_source, "the reading's label source"),
        "adjustment_label_status": _text(status.value, "the reading's label status"), "retrieval_time": retrieval_time,
        "reconciliation_status": _text(reconciliation.status.value, "the reconciliation status")}


def record_bytes(record):
    """The canonical bytes of (K), the form a reproduce compares and the stored response carries."""
    return canonical_json(record).encode("utf-8")


def _checked_record(value):
    """(K) as the stored response holds it: the exact key sets and text everywhere, or a refusal."""
    if type(value) is not dict or set(value) != _RECORD_KEYS or value["schema"] != SCHEMA:
        _refuse("CLAIM_RECORD_SHAPE", "the claim record is the exact object of its schema")
    members, valuing = value["members"], value["valuing"]
    if type(members) is not list or not members or type(valuing) is not list or len(valuing) > 1:
        _refuse("CLAIM_RECORD_SHAPE", "the claim record's members and valuing lists")
    for member in members:
        if type(member) is not dict or set(member) != _MEMBER_KEYS or not all(type(v) is str and v.strip() for v in member.values()):
            _refuse("CLAIM_RECORD_SHAPE", "a member entry is three text values")
    for row in valuing:
        if type(row) is not dict or set(row) != _VALUING_KEYS or not all(type(v) is str and v.strip() for v in row.values()):
            _refuse("CLAIM_RECORD_SHAPE", "the valuing entry is its text values")
    return value


# ---- the extraction: (I), (R), (K) to the flat lineage `claim_render` reads --------------------------------------------------------------------
def lineage_of(archive):
    """The claim lineage of one stored root (`real_service.service.Archive`: only `issued`, `response` and `ledger_pin` are read). Pure; raises
    `claim_render.ClaimRenderError` and never returns a hole."""
    try:
        issued, response = json.loads(archive.issued.decode("utf-8")), json.loads(archive.response.decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError, AttributeError) as error:
        raise cr.ClaimRenderError("CLAIM_RECORD_SHAPE", "the stored documents are JSON") from error
    return lineage_from_documents(issued, response, archive.ledger_pin)


def lineage_from_documents(issued, response, ledger_pin):
    """The lineage, from the parsed issued document (I), the parsed stored response (R, with (K) under `claim_record`) and the stored ledger pin."""
    try:
        return _lineage(issued, response, ledger_pin)
    except cr.ClaimRenderError:
        raise
    except _SHAPE_ERRORS as error:
        raise cr.ClaimRenderError("CLAIM_RECORD_SHAPE", type(error).__name__) from error


def _rows(metrics, metric_id):
    return [row for row in metrics if type(row) is dict and row.get("metric_id") == metric_id and row.get("view") == "REPORTING"]


def _lineage(issued, response, ledger_pin):
    if type(issued) is not dict or type(response) is not dict or type(issued.get("manifest")) is not dict or type(issued.get("metrics")) is not list:
        _refuse("CLAIM_RECORD_SHAPE", "the stored documents are objects")
    manifest, metrics = issued["manifest"], issued["metrics"]
    # P-7 (R): a real-source root with one position and one cash balance
    origin = response.get("origin")
    if type(origin) is not dict or origin.get("market_origin") != cr.REAL_SOURCE:
        _refuse("CLAIM_PRECONDITION", "P-7: the stored origin is not a real source")
    positions = response.get("opening_positions")
    if type(positions) is not list or len(positions) != 1 or type(positions[0]) is not dict:
        _refuse("CLAIM_PRECONDITION", "P-7: exactly one opening position")
    quantity = _text(positions[0].get("quantity"), "the opening quantity")
    listing = _text(positions[0].get("listing_id"), "the opening listing")
    cash = response.get("opening_cash")
    if type(cash) is not dict:
        _refuse("CLAIM_PRECONDITION", "P-7: one opening cash balance")
    opening_cash = _text(cash.get("amount"), "the opening cash amount")
    currency = _text(response.get("reporting_currency"), "the reporting currency")
    if _text(cash.get("currency"), "the opening cash currency") != currency or _text(manifest.get("reporting_currency"), "the manifest's currency") != currency:
        _refuse("CLAIM_RECORD_CROSSCHECK", "the reporting currency, the cash currency and the manifest's currency differ")
    valuation_date = _date_text(response.get("as_of"), "the valuation date")
    if manifest.get("as_of") != valuation_date:
        _refuse("CLAIM_RECORD_CROSSCHECK", "the response's as-of is not the manifest's")
    # S4 fields: (I) and (K)
    pin = manifest.get("ledger_version")
    if type(pin) is not int or type(ledger_pin) is not int or type(response.get("ledger_version")) is not int or not (pin == ledger_pin == response["ledger_version"]):
        _refuse("CLAIM_RECORD_CROSSCHECK", "the ledger version of the manifest, the response and the pin differ")
    if pin < 0:
        _refuse("CLAIM_RECORD_SHAPE", "a ledger version is a count")
    conventions = _pairs(manifest.get("conventions"), "the manifest's conventions")
    market_set = _pair_value(conventions, "market_data.convention_set", "the manifest's conventions")
    performance_set = _pair_value(conventions, "performance.convention_set", "the manifest's conventions")
    if market_set != REQUIRED_CONVENTION_SET:                                                       # P-6
        _refuse("CLAIM_PRECONDITION", "P-6: the market-data convention set is not the claim list's")
    record = _checked_record(response.get(RECORD_KEY))
    members = record["members"]
    shas = {m["payload_sha256"] for m in members}
    refs = manifest.get("data_set_refs")
    if type(refs) is not list:
        _refuse("CLAIM_RECORD_SHAPE", "the manifest's data_set_refs is a list")
    for ref in refs:
        for entry in ref["consumed"]:
            if entry[0] not in shas:
                _refuse("CLAIM_RECORD_CROSSCHECK", "a consumed file is not a member of M")
    file_hashes = ["%s %s %s" % (m["data_kind"], m["source_id"], m["payload_sha256"]) for m in members]
    # P-9 (post-build note 5.1), both variants, before the variant is picked: the holding trades in the reporting currency, so no FX leg exists and S1 and S3
    # ("x p", "x p + cash") state no conversion truly
    native = _one([r for r in metrics if type(r) is dict and r.get("metric_id") == "holding_value" and r.get("view") == "NATIVE"], "holding_value/NATIVE row")
    if native.get("currency") != currency:
        _refuse("CLAIM_PRECONDITION", "P-9: the holding does not trade in the reporting currency")
    # the NAV row (I): its state picks the variant (P-8)
    nav = _one(_rows(metrics, "portfolio_value"), "portfolio_value/REPORTING row")
    state = nav.get("state")
    if state not in cr.NORMAL_STATES and state != cr.WITHHELD_STATE:                                # P-8
        _refuse("CLAIM_PRECONDITION", "P-8: the NAV state is not one of the three")
    freshness = nav.get("freshness")
    if type(freshness) is not dict:
        _refuse("CLAIM_RECORD_SHAPE", "the NAV row's freshness is an object")
    summary = _text(freshness.get("summary"), "the NAV row's freshness summary")
    delays = freshness.get("delays")
    if type(delays) is not list or not delays or not all(type(d) is str and d.strip() for d in delays):
        _refuse("CLAIM_RECORD_SHAPE", "the NAV row's delays are a non-empty list of text")
    common = {"valuation_date": valuation_date, "ledger_quantity": quantity, "reporting_currency": currency, "metric_state": state,
              "freshness": summary, "delay_status": list(delays), "file_hashes": file_hashes, "ledger_version": str(pin),
              "convention_ids": [market_set, performance_set]}
    if state == cr.WITHHELD_STATE:
        # P-10 (post-build note 5.1): the withheld text says no close and no reading values the holding; it is refused when (K) holds a valuing reading or any
        # holding row (either view) carries a price date used
        if record["valuing"] or any(type(row) is dict and row.get("metric_id") == "holding_value" and any(type(p) is list and p and p[0] == "price_date_used"
                                                                                                          for p in (row.get("lineage") or []))
                                    for row in metrics):
            _refuse("CLAIM_PRECONDITION", "P-10: a reading values the holding, so the withheld text does not apply")
        reason, details = nav.get("reason"), nav.get("details")
        if type(reason) is str and reason.strip():
            cause = reason
        elif type(details) is list and details and all(type(d) is str and d.strip() for d in details):
            cause = list(details)
        else:
            _refuse("CLAIM_RECORD_MISSING", "an INSUFFICIENT_DATA NAV names no cause")
        return dict(common, nav_cause=cause)
    return _normal(common, manifest, metrics, record, listing, opening_cash)


def _normal(common, manifest, metrics, record, listing, opening_cash):
    holding = _one(_rows(metrics, "holding_value"), "holding_value/REPORTING row")
    subject = _pairs(holding.get("subject"), "the holding row's subject")
    if _pair_value(subject, "listing", "the holding row's subject") != listing:
        _refuse("CLAIM_RECORD_CROSSCHECK", "the holding row is not the opening position's listing")
    lineage = _pairs(holding.get("lineage"), "the holding row's lineage")
    session = _date_text(_pair_value(lineage, "price_date_used", "the holding row's lineage"), "price_date_used")
    missed = _pair_value(lineage, "price_missed_sessions", "the holding row's lineage")
    if _COUNT.match(missed) is None:
        _refuse("CLAIM_RECORD_SHAPE", "price_missed_sessions is a count")
    entries = holding.get("freshness", {}).get("entries")
    if type(entries) is not list:
        _refuse("CLAIM_RECORD_SHAPE", "the holding row's freshness entries are a list")
    calendar = _one([e for e in entries if type(e) is dict and e.get("kind") == "EXCHANGE_CALENDAR"], "exchange-calendar freshness entry")
    mics = calendar.get("mics")
    if type(mics) is not list or len(mics) != 1:
        _refuse("CLAIM_RECORD_AMBIGUOUS", "the exchange-calendar entry governs exactly one MIC")
    mic = _text(mics[0], "the exchange MIC")
    valuing = _one(record["valuing"], "valuing reading in the claim record")
    if valuing["price_session_date"] != session:
        _refuse("CLAIM_RECORD_CROSSCHECK", "the valuing reading's session is not the price date used")
    # the preconditions of the fixed text (the ruling's 3.4)
    if valuing["adjustment_label_status"] != LabelStatus.UNVERIFIABLE.value:
        _refuse("CLAIM_PRECONDITION", "P-1: the label status is not UNVERIFIABLE")
    if valuing["call_adjustment_status"] != profiles.DECLARED or not valuing["adjustment_label_source"].endswith(":" + profiles.DECLARED):
        _refuse("CLAIM_PRECONDITION", "P-2: the label source is not a DECLARED call adjustment")
    if valuing["reconciliation_status"] != ReconciliationStatus.SINGLE_SOURCE.value:
        _refuse("CLAIM_PRECONDITION", "P-3: the reconciliation status is not SINGLE_SOURCE")
    if any(m["data_kind"] == DataKind.CORPORATE_ACTION.value for m in record["members"]):
        _refuse("CLAIM_PRECONDITION", "P-4: M holds a corporate-action file")
    # P-5 by the marker (post-build note 5.2): (i) the STORED manifest holds exactly one `market_data: ` line with the marker; (ii) the engine's present build state
    # holds exactly one line with it. A reworded line that keeps the marker still renders; a removed one (V4 built) refuses.
    open_items = manifest.get("open_items")
    stored_v4 = [] if type(open_items) is not list else [i for i in open_items if type(i) is str and i.startswith(_OPEN_ITEM_PREFIX) and V4_NOT_BUILT_MARKER in i]
    engine_v4 = [line for line in market11.UNBUILT_1_16 if V4_NOT_BUILT_MARKER in line]
    if len(stored_v4) != 1 or len(engine_v4) != 1:
        _refuse("CLAIM_PRECONDITION", "P-5: Test V4 is not stated as not built")
    return dict(common, price_session_date=session, missed_sessions=missed, source_name=valuing["source_name"],
                exchange_mic=mic, vendor_call=valuing["vendor_call"], documentation_reference=valuing["documentation_reference"],
                adjustment_label_source=valuing["adjustment_label_source"], opening_cash=opening_cash,
                reconciliation_status=valuing["reconciliation_status"], adjustment_label_status=valuing["adjustment_label_status"],
                retrieval_time=valuing["retrieval_time"], v1_statement=V1_NONE_IN_M)


def block_of(origin, issued, response, ledger_pin):
    """The claim block the create and every read render from the stored documents: `lineage_from_documents`, then `claim_render.render_claim_block`. The
    create calls it before the seal; a refusal there rolls the create back (PD-0082 Q3). It also holds the block to what the scoped contract will check on every
    response (`check_block` finds no problem, and the block re-renders from its own slots to itself), so a root that passes here cannot be refused there."""
    block = cr.render_claim_block(origin, lineage_from_documents(issued, response, ledger_pin))
    problems = cr.check_block(block, origin)
    if problems:
        _refuse("CLAIM_BLOCK_INCOMPLETE", problems[0])
    if cr.render_claim_block(origin, cr.lineage_from_slots(block["slots"])) != block:
        _refuse("CLAIM_BLOCK_ROUNDTRIP", "the block is not the rendering of its own slots")
    return block
