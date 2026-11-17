"""Closed V1 contract and pure refusal: no source, store, or financial capability."""
from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

from marketdata.canonical import canonical_json

SCHEMA = "finweb.cp7.real_interface_contract/1"
REQUEST_SCHEMA = "finweb.cp7.real_workspace_create/1"
ERROR_SCHEMA = "finweb.cp7.real_interface_refusal/1"
MILESTONE = "E4_CLOSED_CONTRACT"
MODE = "LOCAL_REAL_SOURCE_TEST_ACCOUNT"
MAX_HTTP_BYTES, MAX_OUTPUT_BYTES, MAX_ERROR_BYTES = 32768, 65536, 4096
MAX_DEPTH, MAX_TOKEN_BYTES, MAX_CONTEXTS = 8, 4096, 16
HASH = re.compile(r"[0-9a-f]{64}\Z")
DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,9})(?:\.[0-9]{0,5}[1-9])?\Z")
ERRORS = MappingProxyType({
    "REAL_REQUEST_INVALID": (422, "REQUEST", "The real-workspace contract request is invalid"),
    "REAL_CONTRACT_CONFIGURATION_UNAVAILABLE": (503, "CONFIGURATION", "The closed real-workspace contract configuration is unavailable"),
    "REAL_CONTEXT_NOT_CONFIGURED": (409, "CAPABILITY", "No matching real-source context is configured"),
    "REAL_CONTEXT_BINDING_DIFFERS": (409, "BINDING", "The requested release differs from the explicit context declaration"),
    "REAL_CONTEXT_EXECUTION_WITHDRAWN": (409, "CAPABILITY", "The explicit context is withdrawn from execution"),
    "REAL_CONTEXT_NOT_QUALIFIED": (409, "CAPABILITY", "The explicit context is not qualified for real-workspace execution"),
})


class ContractRefusal(Exception):
    """Only the fixed closed-contract vocabulary may enter a public error."""
    def __init__(self, code):
        self.status, self.kind, self.detail = ERRORS[code]
        self.code = code
        super().__init__(code)


def invalid_request():
    return ContractRefusal("REAL_REQUEST_INVALID")


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
    # This request schema has no numeric JSON fields; decimals are strings.
    raise ValueError("numeric JSON token is not a request field")


def _bounded_json(raw):
    """Bound tokens/depth BEFORE constructing the JSON container tree.

    scanstring decodes at most one string token inside the already bounded body;
    it does not build a container tree. Encoding validates Unicode scalar values.
    """
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
    return json.loads(text, object_pairs_hook=_pairs, parse_int=_number,
                      parse_float=_number, parse_constant=_number)


def _validate_intent(value):
    _keys(value, ("schema_version", "operation_id", "mode", "source_context_id", "expected_release_id",
        "name", "reporting_currency", "as_of", "constructed_ledger_acknowledged", "opening_positions", "opening_cash"))
    if (value["schema_version"], value["mode"], value["reporting_currency"]) != (REQUEST_SCHEMA, MODE, "USD"):
        raise ValueError("explicit request mode required")
    if value["constructed_ledger_acknowledged"] is not True:
        raise ValueError("constructed nonpersonal acknowledgement required")
    _identifier(value["operation_id"])
    _hash(value["source_context_id"]); _hash(value["expected_release_id"])
    day = value["as_of"]
    if type(day) is not str or len(day) != 10 or dt.date.fromisoformat(day).isoformat() != day:
        raise ValueError("exact date required")
    name = value["name"]
    if (type(name) is not str or not 1 <= len(name) <= 80 or len(name.encode("utf-8")) > 320
            or name.strip() != name or not any(not char.isspace() for char in name)
            or any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in name)):
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
    try:
        return _validate_intent(_bounded_json(raw))
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
        raise invalid_request() from None


@dataclass(frozen=True)
class ClosedContext:
    context_id: str
    declared_release_id: str
    status: str


@dataclass(frozen=True)
class ClosedCatalogue:
    # No constructor validation or I/O before the authenticated route calls us.
    records: tuple = ()


def validate_catalogue(catalogue):
    try:
        if type(catalogue) is not ClosedCatalogue or type(catalogue.records) is not tuple or len(catalogue.records) > MAX_CONTEXTS:
            raise ValueError("bounded immutable catalogue required")
        previous = None
        for row in catalogue.records:
            if type(row) is not ClosedContext:
                raise ValueError("closed context required")
            _hash(row.context_id); _hash(row.declared_release_id)
            if type(row.status) is not str or row.status not in ("UNQUALIFIED", "WITHDRAWN"):
                raise ValueError("no positive status in the closed catalogue")
            if previous is not None and previous >= row.context_id:
                raise ValueError("catalogue must already be strictly ordered and unique")
            previous = row.context_id
        return catalogue.records
    except (ValueError, TypeError, AttributeError, RecursionError):
        raise ContractRefusal("REAL_CONTRACT_CONFIGURATION_UNAVAILABLE") from None


def contract_payload(catalogue):
    rows = validate_catalogue(catalogue)
    value = dict(schema_version=SCHEMA, milestone=MILESTONE, mode=MODE, state="BLOCKED",
        positive_execution="DISABLED", approved_context_count=0,
        contexts=[dict(context_id=row.context_id, declared_release_id=row.declared_release_id, status=row.status) for row in rows],
        capabilities=dict(create=False, read_saved=False, valuation=False, evidence=False, reproduce=False),
        blockers=["NO_QUALIFIED_REAL_CONTEXT", "POSITIVE_EXECUTION_PROTOCOL_NOT_CLOSED", "REAL_WORKSPACE_STORAGE_NOT_IMPLEMENTED"],
        scope=dict(markets=["US"], reporting_currencies=["USD"], personal_holdings=False),
        limits=dict(http_bytes=32768, output_bytes=65536, contexts=16, opening_positions=1),
        support=dict(data_fetch=False, source_admission=False, real_uat_verified=False, hg4_approved=False))
    if len(canonical_json(value).encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ContractRefusal("REAL_CONTRACT_CONFIGURATION_UNAVAILABLE")
    return value


def refuse_intent(catalogue, request):
    try:
        _validate_intent(request)
    except (ValueError, TypeError, OverflowError, RecursionError, UnicodeError):
        raise invalid_request() from None
    rows = validate_catalogue(catalogue)  # Whole catalogue, before matching an ID.
    matched = next((row for row in rows if row.context_id == request["source_context_id"]), None)
    if matched is None:
        raise ContractRefusal("REAL_CONTEXT_NOT_CONFIGURED")
    if matched.declared_release_id != request["expected_release_id"]:
        raise ContractRefusal("REAL_CONTEXT_BINDING_DIFFERS")
    if matched.status == "WITHDRAWN":
        raise ContractRefusal("REAL_CONTEXT_EXECUTION_WITHDRAWN")
    raise ContractRefusal("REAL_CONTEXT_NOT_QUALIFIED")


def refusal_payload(error):
    # Do not reflect attributes from a caller or an arbitrary exception object.
    _status, kind, detail = ERRORS[error.code]
    value = dict(schema_version=ERROR_SCHEMA, milestone=MILESTONE, mode=MODE, state="REFUSED",
        persisted=False, operation_recorded=False, economic_writes=0,
        error=dict(code=error.code, kind=kind, detail=detail))
    if len(canonical_json(value).encode("utf-8")) > MAX_ERROR_BYTES:
        raise RuntimeError("closed contract fixed error exceeds its output bound")
    return value
