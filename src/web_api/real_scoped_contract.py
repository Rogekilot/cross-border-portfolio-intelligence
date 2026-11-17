"""F1 R5: the SCOPED CONTRACT of the real-data slice (design 2.4). NOT INSTALLED ANYWHERE.

It replaces E5's closed contract (`real_workspace_contract.py`, which stays exactly as it is, with its routes, its tests and its installation in
the dev app) for the slice's real routes only: create, read, reproduce on the one context, and an owner-scoped LIST route. R7 installs this
module, as reviewed at R5, in the real-mode app, and may not change a wire shape without a new review. No route table in `src/` imports it
today (a static test checks that), and a URL is never answered by both contracts in one app.

This module is a pure leaf. It imports no store, no service, no connection, no clock, no environment and no file. It defines

  * the schema versions, the route table (method, path, gateway purpose) and the refusal vocabulary;
  * the strict parser of the create intent (`parse_intent`): bounded tokens and depth BEFORE the container tree is built, exact key sets,
    no numeric JSON token (decimals are strings), no duplicate key;
  * the wire shapes of the responses: committed create, read, reproduce, list, refusal and unknown, as functions of already-computed values.

ORIGIN. Every response that describes a root carries the four stored origin fields (`real_labels.ORIGIN_FIELDS`), copied from the stored
response or root row by the caller, and the labels derived from them by `persistence.real_labels` (the caller passes the derived labels in).
This module hard-codes neither a value of the flag among them, nor a mode string, nor a market origin; its tests check the source for the strings. The request has no `mode` field: the origin is a property of the context the root is created under
and of nothing the client says.

NUMBERS. Only the committed create, the read and the reproduce carry the service result, as the stored issued document, together with the
claim-limit block (design 7.4) the caller renders from the stored origin fields. The list carries no financial number.

NOT IN THIS CONTRACT: export (a real export purpose is later work, 7.3), and any write other than create.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from decimal import Decimal
from types import MappingProxyType

from marketdata import claim_render
from persistence import real_labels

SCHEMA = "finweb.cp7.real_scoped_contract/2"
CREATE_SCHEMA = "finweb.cp7.real_scoped_create/1"
CREATE_RESULT_SCHEMA = "finweb.cp7.real_scoped_create_result/1"
READ_SCHEMA = "finweb.cp7.real_scoped_read/2"       # /2: the opened result carries `created_under_generation` (HG4 condition 2, PD-0089; TR8SR M-1)
REPRODUCE_SCHEMA = "finweb.cp7.real_scoped_reproduce/1"
LIST_SCHEMA = "finweb.cp7.real_scoped_list/2"      # /2: a readable entry carries `operation_id` (HG4 revision, PD-0087; reviewed TR8F)
ERROR_SCHEMA = "finweb.cp7.real_scoped_refusal/1"
UNKNOWN_SCHEMA = "finweb.cp7.real_scoped_unknown/1"
SCHEMAS = (SCHEMA, CREATE_SCHEMA, CREATE_RESULT_SCHEMA, READ_SCHEMA, REPRODUCE_SCHEMA, LIST_SCHEMA, ERROR_SCHEMA, UNKNOWN_SCHEMA)

MAX_HTTP_BYTES, MAX_OUTPUT_BYTES, MAX_ERROR_BYTES = 32768, 6_000_000, 4096
MAX_DEPTH, MAX_TOKEN_BYTES, MAX_ROOTS = 8, 4096, 64
HASH = re.compile(r"[0-9a-f]{64}\Z")
DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{0,5}[1-9])?\Z")

ORIGIN_FIELDS = real_labels.ORIGIN_FIELDS
LABEL_FIELDS = ("origin_kind", "origin_statement", "holding_statement")

#: (name, method, path, gateway purpose). The purposes are the gateway's own: a create is an EXECUTE_CREATE admission, a read an ARCHIVE_READ, a
#: reproduce an EXECUTE_REPRODUCE, and each LIST ENTRY an ARCHIVE_READ for that root's context (so a withdrawn or lapsed context is listed with
#: its refusal code). There is no export route and no write route besides create.
ROUTES = (
    ("create", "POST", "/api/real/v1/roots", "EXECUTE_CREATE"),
    ("list", "GET", "/api/real/v1/roots", "ARCHIVE_READ"),
    ("read", "GET", "/api/real/v1/roots/{root_id}/operations/{operation_id}", "ARCHIVE_READ"),
    ("reproduce", "POST", "/api/real/v1/roots/{root_id}/operations/{operation_id}/reproduce", "EXECUTE_REPRODUCE"),
)

#: The public refusal vocabulary: code -> (HTTP status, kind, detail). A code outside this table is reported as REAL_UNAVAILABLE and never
#: reflected. The detail strings are fixed text (no number, no attribute of the request).
ERRORS = MappingProxyType({
    "REAL_REQUEST_INVALID": (422, "REQUEST", "The request is invalid"),
    "REAL_UNAVAILABLE": (503, "CONFIGURATION", "The real-data workspace is unavailable"),
    "RW_NOT_FOUND": (404, "NOT_FOUND", "No such context, root or operation for this owner"),
    "RW_GENERATION_DIFFERS": (409, "CAPABILITY", "The context changed; repeat with the current generation"),
    "RW_LAPSED": (409, "CAPABILITY", "The context has lapsed"),
    "RW_WITHDRAWN": (409, "CAPABILITY", "The context has been withdrawn"),
    "RW_WITHDRAWAL_PENDING": (409, "CAPABILITY", "A withdrawal of the context is pending"),
    "RW_RIGHT_REFUSED": (409, "CAPABILITY", "The context does not grant this right"),
    "RW_DEADLINE": (409, "CAPABILITY", "The operation did not finish within its time bound"),
    "RW_IDEMPOTENCY_CONFLICT": (409, "CONFLICT", "The operation id was used with a different command"),
    "RW_CONTEXT_BINDING_DIFFERS": (409, "BINDING", "The requested release differs from the context's release"),
    "RW_WORLD_DIFFERS": (409, "BINDING", "The inputs differ from the context's snapshot"),
    "RW_SEAL_REFUSED": (409, "SEAL", "The result was not accepted for storage"),
    "RW_CLAIM_RECORD_REFUSED": (409, "CLAIM", "The result's claim limits could not be stated, so it was not stored"),
    "RW_MD_READ_REFUSED": (409, "CAPABILITY", "The stored market data cannot be read now"),
    "RW_RELEASE_REFUSED": (409, "BINDING", "The stored release failed its integrity checks"),
    "SYNTHETIC_MARKET_DATA_REFUSED": (409, "SERVICE", "The financial service refuses to value market data that is not from a real source"),
    "RW_LOCK_TIMEOUT": (409, "BUSY", "The operation could not take its locks in time"),
    "RW_STATEMENT_FAILED": (409, "ROLLED_BACK", "The operation failed and was rolled back"),
})

_ORIGIN_VALUE_TYPES = dict(zip(ORIGIN_FIELDS, (str, str, bool, bool)))


class ContractRefusal(Exception):
    """Only the fixed vocabulary of `ERRORS` may enter a public error."""

    def __init__(self, code):
        if code not in ERRORS:
            code = "REAL_UNAVAILABLE"
        self.status, self.kind, self.detail = ERRORS[code]
        self.code = code
        super().__init__(code)


def invalid_request():
    return ContractRefusal("REAL_REQUEST_INVALID")


# ---- the create intent --------------------------------------------------------------------------------------------------------------------
def _keys(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError("exact object required")


def _hash(value):
    if type(value) is not str or HASH.fullmatch(value) is None:
        raise ValueError("hash required")


def _identifier(value):
    if type(value) is not str or str(uuid.UUID(value)) != value:
        raise ValueError("canonical UUID required")


def _decimal(value, maximum, *, positive=False):
    if type(value) is not str or DECIMAL.fullmatch(value) is None:
        raise ValueError("canonical decimal required")
    number = Decimal(value)
    if number > maximum or (positive and number == 0):
        raise ValueError("decimal outside slice bound")


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _number(_value):
    raise ValueError("numeric JSON token is not a request field")      # decimals are strings


def _bounded_json(raw):
    """Bound tokens and depth BEFORE the container tree is built (the scan decodes at most one string token at a time)."""
    if type(raw) is not bytes or len(raw) > MAX_HTTP_BYTES or raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("bounded UTF-8 JSON required")
    text = raw.decode("utf-8")
    stack, index = [], 0
    while index < len(text):
        char = text[index]
        if char in " \t\r\n:,":
            index += 1
        elif char == '"':
            value, index = json.decoder.scanstring(text, index + 1, True)
            if len(value.encode("utf-8")) > MAX_TOKEN_BYTES:
                raise ValueError("decoded JSON token too large")
        elif char in "[{":
            stack.append(char)
            if len(stack) > MAX_DEPTH:
                raise ValueError("JSON nesting too deep")
            index += 1
        elif char in "]}":
            expected = "[" if char == "]" else "{"
            if not stack or stack.pop() != expected:
                raise ValueError("mismatched JSON container")
            index += 1
        else:
            end = index + 1
            while end < len(text) and text[end] not in " \t\r\n,:{}[]\"":
                end += 1
            if len(text[index:end].encode("utf-8")) > MAX_TOKEN_BYTES:
                raise ValueError("JSON token too large")
            index = end
    if stack:
        raise ValueError("unclosed JSON container")
    return json.loads(text, object_pairs_hook=_pairs, parse_int=_number, parse_float=_number, parse_constant=_number)


def validate_intent(value):
    """The create intent. No `mode` field: the origin is the context's. One constructed opening position and USD cash, as E5's request."""
    _keys(value, ("schema_version", "operation_id", "source_context_id", "expected_release_id", "name", "reporting_currency", "as_of",
                  "constructed_ledger_acknowledged", "opening_positions", "opening_cash"))
    if (value["schema_version"], value["reporting_currency"]) != (CREATE_SCHEMA, "USD"):
        raise ValueError("explicit request schema required")
    if value["constructed_ledger_acknowledged"] is not True:
        raise ValueError("constructed nonpersonal acknowledgement required")
    _identifier(value["operation_id"])
    _hash(value["source_context_id"])
    _hash(value["expected_release_id"])
    day = value["as_of"]
    if type(day) is not str or len(day) != 10 or dt.date.fromisoformat(day).isoformat() != day:
        raise ValueError("exact date required")
    name = value["name"]
    if (type(name) is not str or not 1 <= len(name) <= 80 or len(name.encode("utf-8")) > 320 or name.strip() != name
            or not any(not char.isspace() for char in name) or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in name)):
        raise ValueError("bounded nonblank scalar name required")
    positions = value["opening_positions"]
    if type(positions) is not list or len(positions) != 1:
        raise ValueError("one constructed opening position required")
    position = positions[0]
    _keys(position, ("listing_id", "quantity", "cost_basis", "acquired_on"))
    _identifier(position["listing_id"])
    _decimal(position["quantity"], Decimal("1000000"), positive=True)
    if position["cost_basis"] is not None or position["acquired_on"] is not None:
        raise ValueError("unknown basis and acquisition date must be explicit null")
    cash = value["opening_cash"]
    _keys(cash, ("currency", "amount"))
    if cash["currency"] != "USD":
        raise ValueError("USD cash required")
    _decimal(cash["amount"], Decimal("1000000000"))
    return value


def parse_intent(raw):
    """Raw request bytes -> the validated intent dict, or `ContractRefusal("REAL_REQUEST_INVALID")`."""
    try:
        return validate_intent(_bounded_json(raw))
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
        raise invalid_request() from None


# ---- shared wire pieces --------------------------------------------------------------------------------------------------------------------
def origin_object(origin):
    """The four stored origin fields, exactly, as given by the stored response or root row. A missing field, an extra field or a value of the
    wrong type is a defect of the caller, not something to repair: `ContractRefusal("REAL_UNAVAILABLE")`."""
    if type(origin) is not dict or set(origin) != set(ORIGIN_FIELDS) or any(type(origin[k]) is not t for k, t in _ORIGIN_VALUE_TYPES.items()):
        raise ContractRefusal("REAL_UNAVAILABLE")
    return {name: origin[name] for name in ORIGIN_FIELDS}


def label_object(labels, origin):
    """The labels, which must be exactly the ones `real_labels.root_labels` derives from THIS origin (TR5-M1): a label that belongs to another
    origin, or an origin whose fields contradict each other, is a defect of the caller and is refused, never repaired."""
    if type(labels) is not dict or any(type(labels.get(k)) is not str or not labels[k] for k in LABEL_FIELDS):
        raise ContractRefusal("REAL_UNAVAILABLE")
    try:
        derived = real_labels.root_labels(origin)
    except real_labels.LabelError:
        raise ContractRefusal("REAL_UNAVAILABLE") from None
    if any(labels[name] != derived[name] for name in LABEL_FIELDS):
        raise ContractRefusal("REAL_UNAVAILABLE")
    return {name: labels[name] for name in LABEL_FIELDS}


def digest_field(value, *, allow_none=False):
    """A SHA-256 as 64 lowercase hex characters (TR5-M1); `None` only where the caller says the digest may be absent."""
    if value is None and allow_none:
        return None
    if type(value) is not str or HASH.match(value) is None:
        raise ContractRefusal("REAL_UNAVAILABLE")
    return value


def _bounded(value, limit):
    from marketdata.canonical import canonical_json
    if len(canonical_json(value).encode("utf-8")) > limit:
        raise ContractRefusal("REAL_UNAVAILABLE")
    return value


def _claim_block(block, origin):
    """The claim-limit block, which must be THE RENDERING for THIS origin (TR5-M1, TR5-L5).

    First the completeness check (`claim_render.check_block` reports no problem): every S-slot, every C-item and each item's required terms for a
    real-source origin, the test-data mark and no item for any other. Then the equality check: the slots go back to their lineage fields
    (`claim_render.lineage_from_slots`), the block is RENDERED AGAIN from them for this origin, and the block received must equal that rendering
    byte for byte (canonical JSON). So a block with a sentence deleted (the PD-0073 seal-limit sentence among them), a sentence appended, an item
    text that disagrees with the slot values, or two slots that disagree about one lineage field is refused, whoever built it."""
    if type(block) is not dict or set(block) != claim_render.BLOCK_KEYS or type(block["items"]) is not list:
        raise ContractRefusal("REAL_UNAVAILABLE")
    try:
        problems = claim_render.check_block(block, origin)
        if problems:
            raise ContractRefusal("REAL_UNAVAILABLE")
        if origin["market_origin"] == claim_render.REAL_SOURCE:
            expected = claim_render.render_claim_block(origin, claim_render.lineage_from_slots(block["slots"]))
        else:
            expected = claim_render.render_claim_block(origin)
        from marketdata.canonical import canonical_json
        if canonical_json(block) != canonical_json(expected):
            raise ContractRefusal("REAL_UNAVAILABLE")
    except (AttributeError, KeyError, TypeError, ValueError):       # ClaimRenderError is a ValueError
        raise ContractRefusal("REAL_UNAVAILABLE") from None
    return block


# ---- responses -----------------------------------------------------------------------------------------------------------------------------
def committed_payload(*, root_id, operation_id, revision_id, ledger_pin, origin, labels, response_sha256, issued_sha256, result, claim_limits,
                      replayed=False):
    """A committed create: the identifiers, the stored origin fields and their labels, the digests of the stored bytes, the stored issued
    document (`result`, a parsed object) and the claim-limit block."""
    if type(result) is not dict or type(ledger_pin) is not int or type(replayed) is not bool:
        raise ContractRefusal("REAL_UNAVAILABLE")
    origin = origin_object(origin)
    value = dict(schema_version=CREATE_RESULT_SCHEMA, state="COMMITTED", persisted=True, replayed=replayed, root_id=str(root_id),
                 operation_id=str(operation_id), revision_id=str(revision_id), ledger_pin=ledger_pin, origin=origin,
                 labels=label_object(labels, origin), response_sha256=digest_field(response_sha256),
                 issued_sha256=digest_field(issued_sha256), result=result, claim_limits=_claim_block(claim_limits, origin))
    return _bounded(value, MAX_OUTPUT_BYTES)


def read_payload(*, root_id, operation_id, revision_id, ledger_pin, origin, labels, response_sha256, issued_sha256, result, claim_limits,
                 created_under_generation):
    """The opened result. `created_under_generation` is the generation the root was CREATED under, from the stored sealed envelope (never the
    context's current head, a lease or a constant). It is a different number from the list entry's `generation`, which is the context's CURRENT one."""
    if type(result) is not dict or type(ledger_pin) is not int:
        raise ContractRefusal("REAL_UNAVAILABLE")
    if type(created_under_generation) is not int or created_under_generation < 1:
        raise ContractRefusal("REAL_UNAVAILABLE")
    origin = origin_object(origin)
    value = dict(schema_version=READ_SCHEMA, state="COMMITTED", persisted=True, root_id=str(root_id), operation_id=str(operation_id),
                 revision_id=str(revision_id), ledger_pin=ledger_pin, created_under_generation=created_under_generation, origin=origin,
                 labels=label_object(labels, origin), response_sha256=digest_field(response_sha256), issued_sha256=digest_field(issued_sha256),
                 result=result, claim_limits=_claim_block(claim_limits, origin))
    return _bounded(value, MAX_OUTPUT_BYTES)


REPRODUCE_STATUSES = ("REPRODUCED", "RESULT_DIFFERS", "INPUT_MISMATCH", "SOURCE_REFUSED")
#: The statuses that may carry no digest (TR5-L5): the service never produced a result to digest (the source refused it, or the stored input did not
#: match). A `REPRODUCED` or `RESULT_DIFFERS` outcome compared two digests and so names one.
DIGEST_OPTIONAL_STATUSES = ("INPUT_MISMATCH", "SOURCE_REFUSED")


def reproduce_payload(*, root_id, operation_id, origin, labels, status, detail, issued_sha256):
    if status not in REPRODUCE_STATUSES:
        raise ContractRefusal("REAL_UNAVAILABLE")
    origin = origin_object(origin)
    value = dict(schema_version=REPRODUCE_SCHEMA, root_id=str(root_id), operation_id=str(operation_id), origin=origin,
                 labels=label_object(labels, origin), status=status, detail=detail if status != "REPRODUCED" else "",
                 issued_sha256=digest_field(issued_sha256, allow_none=status in DIGEST_OPTIONAL_STATUSES))
    return _bounded(value, MAX_ERROR_BYTES * 4)


def list_entry(*, root_id, context_id, generation=None, created_at=None, origin=None, status=None, operation_id=None):
    """One entry of the owner's list. A readable root: identifiers (the root id and the id of the root's one stored create operation, so a listed root can be
    reopened by the read route), the stored origin fields, the generation and the creation time, and no financial number. `generation` is the context's
    CURRENT generation (the head the entry was admitted at), NOT the generation the root was created under; that one is the read result's
    `created_under_generation`. A root whose admission was
    refused: `{root_id, context_id, status}` with the refusal code, and none of the stored fields (not the operation id either)."""
    if status is not None:
        if status not in ERRORS or origin is not None or generation is not None or created_at is not None or operation_id is not None:
            raise ContractRefusal("REAL_UNAVAILABLE")
        return dict(root_id=str(root_id), context_id=context_id, status=status)
    if type(generation) is not int or type(created_at) is not str or operation_id is None:
        raise ContractRefusal("REAL_UNAVAILABLE")
    return dict(root_id=str(root_id), operation_id=str(operation_id), context_id=context_id, generation=generation, created_at=created_at,
                origin=origin_object(origin))


def list_payload(entries):
    if type(entries) not in (list, tuple) or len(entries) > MAX_ROOTS:
        raise ContractRefusal("REAL_UNAVAILABLE")
    ordered = sorted(entries, key=lambda entry: entry["root_id"])
    return _bounded(dict(schema_version=LIST_SCHEMA, roots=ordered), MAX_OUTPUT_BYTES)


def refusal_payload(error):
    """The public error. Only the code and the fixed text of `ERRORS` are reflected."""
    code = getattr(error, "code", None)
    status, kind, detail = ERRORS.get(code, ERRORS["REAL_UNAVAILABLE"])
    code = code if code in ERRORS else "REAL_UNAVAILABLE"
    value = dict(schema_version=ERROR_SCHEMA, state="REFUSED", persisted=False, operation_recorded=False,
                 error=dict(code=code, kind=kind, detail=detail))
    return _bounded(value, MAX_ERROR_BYTES)


def unknown_payload(operation_id):
    """The outcome of a create is not known. Nothing was retried; the client repeats the IDENTICAL command to reconcile."""
    return dict(schema_version=UNKNOWN_SCHEMA, state="UNKNOWN", operation_id=str(operation_id), retried=False,
                next="repeat the identical command; do not change the operation id")
