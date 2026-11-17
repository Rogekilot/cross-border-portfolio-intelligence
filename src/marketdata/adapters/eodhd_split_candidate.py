"""A pure, FICTIONAL-only split-row compatibility adapter (CP7-E10).

No real provider is registered or authorized here. The only positive mapping is an
invented, code-frozen fixture contract; a caller's ratio, flag or endpoint cannot
grant ordinary-SPLIT semantics. Real classification remains unbound. All fixtures
and identifiers used by this module are invented, not copied from a saved response.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
from decimal import Decimal

from domain.ledger import SplitRatio
from marketdata.adapters.base import AdapterIssue, AdapterOutput, IssueCode, lineage_for, timing_for
from marketdata.contracts import (
    AdjustmentStatus,
    CorporateActionType,
    DataDelayStatus,
    ExternalIdentifiers,
    UnresolvedCorporateAction,
    UsageScope,
)
from marketdata.manifest import DataKind, FileManifest

SOURCE_ID = "fictional.eodhd_split_candidate"
PAYLOAD_FORMAT = "fictional_eodhd_split_rows/1"
ADAPTER_ID = "fictional.eodhd_split_candidate.adapter"
ADAPTER_VERSION = "0.1.0"
REAL_CLASSIFICATION_BINDING = None
FICTIONAL_VENDOR_ID = "FICTITIOUS.SPLIT.001"
FICTIONAL_COVERAGE = (("from", "2001-01-01"), ("to", "2001-12-31"))
FICTIONAL_RETRIEVAL = datetime.datetime(2002, 1, 1, tzinfo=datetime.timezone.utc)

# These attest only the invented fixture recipe and its invented economic meaning.
# They are NOT evidence about EODHD, a real source, rights or real event coverage.
_SEMANTIC_RECIPE = b"CP7-E10 fictional split rows/1; ordinary SPLIT; date=ex-date; split=new/old"
SEMANTIC_EVIDENCE_SHA256 = hashlib.sha256(_SEMANTIC_RECIPE).hexdigest()
_FIXTURE_RECIPE = b"CP7-E10 invented fixture generator/1; no provider input; exact JSON date/split rows"
FIXTURE_RECIPE_SHA256 = hashlib.sha256(_FIXTURE_RECIPE).hexdigest()
FICTIONAL_REQUEST = (
    ("adapter_id", ADAPTER_ID),
    ("adapter_version", ADAPTER_VERSION),
    ("function", "fictional_split_rows"),
    ("input_contract", PAYLOAD_FORMAT),
    ("product", "invented_ordinary_split_fixture"),
    ("product_version", "1"),
    ("semantic_evidence_sha256", SEMANTIC_EVIDENCE_SHA256),
    ("semantic_rule", "invented_ordinary_split/1"),
)

MAX_BODY_BYTES = 65536
MAX_DEPTH = 8
MAX_TOKEN_BYTES = 4096
MAX_PRIMITIVES = 4096
MAX_ROWS = 128
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_COMPONENT = re.compile(r"(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,12})?\Z")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


class _Refusal(ValueError):
    def __init__(self, code: IssueCode, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _output_issue(ref: str, code: IssueCode, detail: str) -> AdapterOutput:
    return AdapterOutput(issues=(AdapterIssue(ref, code, detail),))


def _binding_issue(manifest: FileManifest):
    """Classification/identity checks precede even inspecting the supplied body."""
    if type(manifest) is not FileManifest:
        return IssueCode.CONTRACT_VIOLATION, "an exact FileManifest is required"
    if manifest.source_id != SOURCE_ID:
        return IssueCode.UNMAPPED_ACTION, "no classification mapping for this source"
    if manifest.usage_scope is not UsageScope.SYNTHETIC_TEST or manifest.retrieved_by != "synthetic":
        return IssueCode.CONTRACT_VIOLATION, "only the invented synthetic fixture is supported"
    if manifest.request != FICTIONAL_REQUEST:
        return IssueCode.UNMAPPED_ACTION, "the exact invented semantic mapping is absent or conflicting"
    if (
        manifest.data_kind is not DataKind.CORPORATE_ACTION
        or manifest.payload_format != PAYLOAD_FORMAT
        or manifest.source_identifiers != (FICTIONAL_VENDOR_ID,)
        or manifest.payload_filename != "fictional-split-candidate.json"
        or manifest.coverage != FICTIONAL_COVERAGE
        or manifest.retrieval_time != FICTIONAL_RETRIEVAL
        or manifest.script_name != "fictional_cp7e10_fixture"
        or manifest.script_version != "1"
        or manifest.script_sha256 != FIXTURE_RECIPE_SHA256
        or manifest.declared_adjustment is not AdjustmentStatus.RAW
        or manifest.declared_delay is not DataDelayStatus.UNKNOWN
        or manifest.market is not None
        or manifest.declared_currency is not None
        or manifest.adjustment_anchor is not None
        or manifest.libraries != ()
    ):
        return IssueCode.CONTRACT_VIOLATION, "the invented manifest/input binding does not match"
    return None


def _check_lexical_bounds(text: str) -> None:
    """Bound decoded tokens/count/depth before constructing the JSON object tree."""
    depth = 0
    count = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            try:
                value, index = json.decoder.scanstring(text, index + 1, True)
            except ValueError:
                raise _Refusal(IssueCode.UNKNOWN_FORMAT, "body contains an invalid JSON string") from None
            try:
                size = len(value.encode("utf-8", "strict"))
            except UnicodeEncodeError:
                raise _Refusal(IssueCode.CONTRACT_VIOLATION, "JSON contains a surrogate") from None
            if size > MAX_TOKEN_BYTES:
                raise _Refusal(IssueCode.CONTRACT_VIOLATION, "decoded JSON string exceeds the fixed bound")
            count += 1
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise _Refusal(IssueCode.CONTRACT_VIOLATION, "JSON nesting exceeds the fixed bound")
            index += 1
        elif char in "]}":
            depth -= 1
            index += 1
        elif char in " \r\n\t,:":
            index += 1
        else:
            end = index + 1
            while end < len(text) and text[end] not in " \r\n\t,:[{}]":
                end += 1
            token = text[index:end]
            if len(token.encode("utf-8")) > MAX_TOKEN_BYTES:
                raise _Refusal(IssueCode.CONTRACT_VIOLATION, "JSON literal exceeds the fixed bound")
            if char in "-0123456789":
                _number(token)
            elif token in ("NaN", "Infinity", "-Infinity"):
                _nonfinite(token)
            count += 1
            index = end
        if count > MAX_PRIMITIVES:
            raise _Refusal(IssueCode.CONTRACT_VIOLATION, "too many JSON strings/primitives")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _Refusal(IssueCode.CONTRACT_VIOLATION, "duplicate JSON object key")
        result[key] = value
    return result


def _number(text: str):
    if len(text.encode("utf-8")) > MAX_TOKEN_BYTES or _NUMBER.fullmatch(text) is None:
        raise _Refusal(IssueCode.CONTRACT_VIOLATION, "JSON numbers must be bounded fixed-point literals")
    return Decimal(text)


def _nonfinite(text: str):
    raise _Refusal(IssueCode.CONTRACT_VIOLATION, "nonfinite JSON literal")


def _check_tokens(doc) -> None:
    count = 0
    pending = [doc]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(value.keys())
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
        else:
            count += 1
            if count > MAX_PRIMITIVES:
                raise _Refusal(IssueCode.CONTRACT_VIOLATION, "too many JSON strings/primitives")
            if isinstance(value, str):
                try:
                    size = len(value.encode("utf-8", "strict"))
                except UnicodeEncodeError:
                    raise _Refusal(IssueCode.CONTRACT_VIOLATION, "JSON contains a surrogate") from None
                if size > MAX_TOKEN_BYTES:
                    raise _Refusal(IssueCode.CONTRACT_VIOLATION, "decoded JSON string exceeds the fixed bound")


def _parse(payload: bytes):
    try:
        text = payload.decode("utf-8", "strict")
    except UnicodeDecodeError:
        raise _Refusal(IssueCode.UNKNOWN_FORMAT, "body is not strict UTF-8") from None
    if text.startswith("\ufeff"):
        raise _Refusal(IssueCode.UNKNOWN_FORMAT, "UTF-8 BOM is not accepted")
    _check_lexical_bounds(text)
    try:
        doc = json.loads(text, object_pairs_hook=_pairs, parse_int=_number,
                         parse_float=_number, parse_constant=_nonfinite)
    except json.JSONDecodeError:
        raise _Refusal(IssueCode.UNKNOWN_FORMAT, "body is not one strict JSON value") from None
    _check_tokens(doc)
    if not isinstance(doc, list):
        raise _Refusal(IssueCode.UNKNOWN_FORMAT, "top level must be an array")
    if len(doc) > MAX_ROWS:
        raise _Refusal(IssueCode.CONTRACT_VIOLATION, "too many event rows")
    return doc


def _row(row):
    if not isinstance(row, dict):
        raise _Refusal(IssueCode.UNPARSEABLE_ROW, "event row must be an object")
    missing = {"date", "split"} - row.keys()
    if missing:
        raise _Refusal(IssueCode.MISSING_FIELD, "event row needs date and split")
    if row.keys() != {"date", "split"}:
        raise _Refusal(IssueCode.CONTRACT_VIOLATION, "event row has unknown fields")
    date_text, ratio_text = row["date"], row["split"]
    if not isinstance(date_text, str) or _DATE.fullmatch(date_text) is None:
        raise _Refusal(IssueCode.UNPARSEABLE_ROW, "date must be canonical YYYY-MM-DD")
    try:
        day = datetime.date.fromisoformat(date_text)
    except ValueError:
        raise _Refusal(IssueCode.UNPARSEABLE_ROW, "date is not a calendar date") from None
    if not (datetime.date(2001, 1, 1) <= day <= datetime.date(2001, 12, 31)):
        raise _Refusal(IssueCode.CONTRACT_VIOLATION, "date is outside the invented coverage")
    if not isinstance(ratio_text, str) or ratio_text.count("/") != 1:
        raise _Refusal(IssueCode.UNPARSEABLE_ROW, "split must be a string new/old ratio")
    new_text, old_text = ratio_text.split("/")
    if any(_COMPONENT.fullmatch(part) is None for part in (new_text, old_text)):
        raise _Refusal(IssueCode.UNPARSEABLE_ROW, "ratio components must be bounded unsigned fixed-point")
    new, old = Decimal(new_text), Decimal(old_text)
    if new <= 0 or old <= 0:
        raise _Refusal(IssueCode.NON_POSITIVE_VALUE, "ratio components must both be positive")
    return day, ratio_text, SplitRatio(new, old)


class EodhdSplitCandidateAdapter:
    """Synthetic compatibility work only; never a real provider capability."""

    __slots__ = ()
    source_id = SOURCE_ID
    adapter_id = ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    data_kind = DataKind.CORPORATE_ACTION
    payload_formats = (PAYLOAD_FORMAT,)

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        issue = _binding_issue(manifest)
        if issue is not None:
            return _output_issue("manifest", *issue)
        if type(payload) is not bytes:
            return _output_issue("file", IssueCode.CONTRACT_VIOLATION, "body must be exact bytes")
        if len(payload) > MAX_BODY_BYTES:
            return _output_issue("file", IssueCode.CONTRACT_VIOLATION, "body exceeds 64 KiB")
        if manifest.size_bytes != len(payload) or manifest.file_sha256 != hashlib.sha256(payload).hexdigest():
            return _output_issue("file", IssueCode.CONTRACT_VIOLATION, "manifest byte count/hash does not bind body")
        try:
            rows = _parse(payload)
        except _Refusal as exc:
            return _output_issue("file", exc.code, exc.detail)
        # Identify duplicated canonical dates before ratio validation so a bad ratio
        # on one duplicate cannot make another row for that date appear unique.
        date_labels = [row.get("date") for row in rows if isinstance(row, dict)
                       and isinstance(row.get("date"), str) and _DATE.fullmatch(row["date"])]
        duplicate_labels = {label for label in date_labels if date_labels.count(label) > 1}
        parsed, issues = [], []
        for index, row in enumerate(rows):
            ref = f"rows[{index}]"
            if isinstance(row, dict) and isinstance(row.get("date"), str) and row["date"] in duplicate_labels:
                issues.append(AdapterIssue(ref, IssueCode.CONTRACT_VIOLATION, "duplicate event date; every duplicate is refused"))
                continue
            try:
                parsed.append((index, _row(row)))
            except _Refusal as exc:
                issues.append(AdapterIssue(ref, exc.code, exc.detail))
        actions = []
        for index, (day, ratio_text, ratio) in parsed:
            ref = f"rows[{index}]"
            actions.append(UnresolvedCorporateAction(
                identifiers=ExternalIdentifiers(vendor_id=FICTIONAL_VENDOR_ID, source_id=SOURCE_ID),
                action_type=CorporateActionType.SPLIT,
                effective_date=day,
                timing=timing_for(manifest),
                lineage=lineage_for(manifest, self, ref, source_value_text=ratio_text),
                split_ratio=ratio,
            ))
        return AdapterOutput(actions=tuple(actions), issues=tuple(sorted(issues, key=lambda i: int(i.row_ref[5:-1]))))
