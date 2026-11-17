"""E1 metadata declarations only: never payload verification or financial readiness."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from marketdata.canonical import canonical_json
from marketdata.manifest import FileManifest, MarketDataRelease, SourceRegistry

SCHEMA = "finweb.cp7.real_source/1"
MODE = "LOCAL_REAL_SOURCE_TEST_ACCOUNT"
MAX_CONTEXTS, MAX_FILES, MAX_FILE_BYTES = 16, 8, 65536
MAX_METADATA_BYTES, MAX_OUTPUT_BYTES = 1048576, 65536
HASH = re.compile(r"[0-9a-f]{64}\Z")
SOURCE = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,63}\Z")
ROLES = frozenset(("SOURCE_REGISTRY", "RELEASE_DECLARATION", "FILE_MANIFEST"))


class RealSourceError(Exception):
    def __init__(self, status, code, detail, kind="CONFIGURATION"):
        self.status, self.code, self.detail, self.kind = status, code, detail, kind


def invalid_configuration():
    return RealSourceError(503, "REAL_SOURCE_CONFIGURATION_UNAVAILABLE",
        "Explicit real-source metadata configuration is unavailable or invalid")


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def constant(_value):
        raise ValueError("non-finite JSON constant")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def _keys(value, required, optional=()):
    if type(value) is not dict or not set(required) <= set(value) or set(value) - set(required) - set(optional):
        raise ValueError("metadata field set")


def _text(value, *, blank=False):
    if type(value) is not str or not blank and not value.strip():
        raise ValueError("metadata text")


def _hash(value):
    if type(value) is not str or HASH.fullmatch(value) is None:
        raise ValueError("metadata hash")


def _strings(value, *, nonempty=False, pattern=None, ordered=False):
    if type(value) is not list or nonempty and not value:
        raise ValueError("metadata string array")
    for item in value:
        _text(item)
        if pattern is not None and pattern.fullmatch(item) is None:
            raise ValueError("metadata string format")
    if ordered and value != sorted(set(value)):
        raise ValueError("metadata order")


def _pairs(value, *, ordered=False):
    if type(value) is not list or any(type(row) is not list or len(row) != 2 or
            any(type(item) is not str for item in row) for row in value):
        raise ValueError("metadata pairs")
    if ordered and value != [list(row) for row in sorted(set(map(tuple, value)))]:
        raise ValueError("metadata pair order")


def _date(value):
    if type(value) is not str or len(value) != 10 or dt.date.fromisoformat(value).isoformat() != value:
        raise ValueError("metadata date")


def _relative(value):
    _text(value)
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value or any(part in (".", "..") for part in path.parts) or \
            "\\" in value or any(ord(char) < 32 for char in value):
        raise ValueError("metadata path")
    return path


@dataclass(frozen=True)
class MetadataFile:
    relative_path: str
    expected_sha256: str
    role: str

    def to_obj(self):
        return dict(relative_path=self.relative_path, expected_sha256=self.expected_sha256, role=self.role)


@dataclass(frozen=True)
class ConfiguredSourceDescriptor:
    context_id: str
    declared_release_id: str
    declared_source_ids: tuple
    metadata_files: tuple

    def to_obj(self):
        return dict(context_id=self.context_id, declared_release_id=self.declared_release_id,
            declared_source_ids=list(self.declared_source_ids), metadata_files=[row.to_obj() for row in self.metadata_files])


def validate_descriptor(value):
    if isinstance(value, ConfiguredSourceDescriptor):
        value = value.to_obj()
    _keys(value, ("context_id", "declared_release_id", "declared_source_ids", "metadata_files"))
    _hash(value["context_id"]); _hash(value["declared_release_id"])
    sources = value["declared_source_ids"]
    _strings(sources, nonempty=True, pattern=SOURCE, ordered=True)
    if len(sources) > 6 or type(value["metadata_files"]) is not list or not 3 <= len(value["metadata_files"]) <= MAX_FILES:
        raise ValueError("descriptor capacity")
    files = []
    for row in value["metadata_files"]:
        _keys(row, ("relative_path", "expected_sha256", "role"))
        _relative(row["relative_path"]); _hash(row["expected_sha256"])
        if type(row["role"]) is not str or row["role"] not in ROLES:
            raise ValueError("metadata role")
        files.append(MetadataFile(**row))
    if len({row.relative_path for row in files}) != len(files) or \
            sum(row.role == "SOURCE_REGISTRY" for row in files) != 1 or \
            sum(row.role == "RELEASE_DECLARATION" for row in files) != 1 or \
            not 1 <= sum(row.role == "FILE_MANIFEST" for row in files) <= 6:
        raise ValueError("metadata cardinality")
    return ConfiguredSourceDescriptor(value["context_id"], value["declared_release_id"], tuple(sources), tuple(files))


def _registry(obj):
    _keys(obj, ("sources",))
    if type(obj["sources"]) is not list or not obj["sources"]:
        raise ValueError("empty registry")
    fields = ("source_id", "name", "upstream_provider", "independence_group", "terms_url", "synthetic", "terms_check")
    for row in obj["sources"]:
        _keys(row, fields, ("source_priority",))
        for key in ("source_id", "name", "upstream_provider", "independence_group"):
            _text(row[key])
        if SOURCE.fullmatch(row["source_id"]) is None or type(row["synthetic"]) is not bool:
            raise ValueError("source identity")
        if row["terms_url"] is not None:
            _text(row["terms_url"], blank=True)
        if "source_priority" in row and (type(row["source_priority"]) is not int or row["source_priority"] <= 0):
            raise ValueError("source priority")
        check = row["terms_check"]
        if check is not None:
            _keys(check, ("checked_by", "checked_on", "permits_internal_development_use", "notes"))
            _text(check["checked_by"]); _date(check["checked_on"]); _text(check["notes"], blank=True)
            if type(check["permits_internal_development_use"]) is not bool:
                raise ValueError("attestation type")
    return SourceRegistry.from_json(canonical_json(obj))


def _release(obj):
    _keys(obj, ("schema", "name", "files", "source_precedence", "conventions", "created_for", "convention_set_id", "release_id"))
    _text(obj["name"]); _text(obj["created_for"], blank=True); _text(obj["convention_set_id"]); _hash(obj["release_id"])
    _strings(obj["files"], nonempty=True, ordered=True)
    for value in obj["files"]:
        _hash(value)
    _strings(obj["source_precedence"], nonempty=True, pattern=SOURCE)
    if len(set(obj["source_precedence"])) != len(obj["source_precedence"]):
        raise ValueError("source precedence")
    _pairs(obj["conventions"], ordered=True)
    if obj["schema"] != "finweb.marketdata.release/1":
        raise ValueError("release schema")
    return MarketDataRelease.from_json(canonical_json(obj))


def _manifest(obj):
    fields = ("schema", "file_sha256", "size_bytes", "payload_filename", "payload_format", "source_id", "data_kind", "market",
        "retrieval_time", "retrieved_by", "request", "declared_adjustment", "adjustment_anchor", "declared_currency",
        "declared_delay", "source_identifiers", "script", "libraries", "usage_scope", "coverage")
    _keys(obj, fields); _hash(obj["file_sha256"])
    if type(obj["size_bytes"]) is not int or obj["size_bytes"] < 0:
        raise ValueError("manifest size")
    for key in ("payload_filename", "payload_format", "source_id", "retrieval_time", "retrieved_by",
                "data_kind", "declared_adjustment", "declared_delay", "usage_scope"):
        _text(obj[key])
    name = obj["payload_filename"]
    if _relative(name).name != name:
        raise ValueError("payload basename")
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", obj["retrieval_time"]) is None:
        raise ValueError("retrieval time")
    for key in ("market", "adjustment_anchor", "declared_currency"):
        if obj[key] is not None:
            _text(obj[key], blank=True)
    if obj["declared_currency"] is not None and re.fullmatch(r"[A-Z]{3}", obj["declared_currency"]) is None:
        raise ValueError("manifest currency")
    _pairs(obj["request"]); _pairs(obj["libraries"]); _pairs(obj["coverage"])
    _strings(obj["source_identifiers"])
    script = obj["script"]
    _keys(script, ("name", "version", "script_sha256"))
    for key in ("name", "version"):
        if script[key] is not None:
            _text(script[key], blank=True)
    if script["script_sha256"] is not None:
        _hash(script["script_sha256"])
    if obj["retrieved_by"] != "human" or obj["usage_scope"] != "INTERNAL_DEVELOPMENT_ONLY" or \
            obj["data_kind"] not in ("QUOTE", "CALENDAR") or \
            obj["data_kind"] == "QUOTE" and (obj["market"], obj["declared_currency"]) != ("US", "USD") or \
            obj["data_kind"] == "CALENDAR" and (obj["market"] not in (None, "US") or obj["declared_currency"] not in (None, "USD")):
        raise ValueError("E1 metadata scope")
    return FileManifest.from_json(canonical_json(obj))


def _read_metadata(root, entry, allowed, remaining):
    if entry not in allowed:
        raise ValueError("metadata not allowlisted")
    relative = _relative(entry.relative_path)
    root = Path(root).resolve(strict=True)
    (root / entry.relative_path).resolve(strict=True).relative_to(root)
    # Walk directory descriptors without following any symlink, including races.
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in relative.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor); descriptor = child
        file_descriptor = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        try:
            if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
                raise ValueError("metadata is not regular")
            with os.fdopen(file_descriptor, "rb", closefd=False) as stream:
                raw = stream.read(min(MAX_FILE_BYTES, remaining) + 1)
        finally:
            os.close(file_descriptor)
    finally:
        os.close(descriptor)
    if len(raw) > MAX_FILE_BYTES or len(raw) > remaining or hashlib.sha256(raw).hexdigest() != entry.expected_sha256:
        raise ValueError("metadata bytes differ")
    return raw


def inspect_configured_metadata(root, descriptor, allowed_metadata_files, *, remaining=MAX_METADATA_BYTES):
    descriptor = validate_descriptor(descriptor)
    if type(allowed_metadata_files) is not tuple or not all(type(row) is MetadataFile for row in allowed_metadata_files):
        raise ValueError("metadata allowlist")
    registry = release = None
    manifests, used = [], 0
    for entry in descriptor.metadata_files:
        raw = _read_metadata(root, entry, allowed_metadata_files, remaining - used)
        used += len(raw)
        value = strict_json(raw)
        if entry.role == "SOURCE_REGISTRY":
            registry = _registry(value)
        elif entry.role == "RELEASE_DECLARATION":
            release = _release(value)
        else:
            manifests.append(_manifest(value))
    sources = set(descriptor.declared_source_ids)
    if release.release_id != descriptor.declared_release_id or set(release.source_precedence) != sources or \
            {row.source_id for row in manifests} != sources or \
            sorted(row.file_sha256 for row in manifests) != list(release.files):
        raise ValueError("metadata cross-reference")
    for source_id in sources:
        record = registry.get(source_id)
        if record.synthetic or record.terms_check is None or not record.terms_check.permits_internal_development_use:
            raise ValueError("source attestation unavailable")
    return dict(context_id=descriptor.context_id,
        configuration_digest=hashlib.sha256(canonical_json(descriptor.to_obj()).encode()).hexdigest(),
        declared_release_id=descriptor.declared_release_id, declared_source_ids=list(descriptor.declared_source_ids),
        status="CONFIGURED_NOT_VERIFIED", readiness_stage="METADATA_ONLY",
        metadata_integrity="EXPECTED_METADATA_BYTES_MATCHED", payload_integrity="NOT_VERIFIED", financially_qualified=False), used


class MetadataProvider:
    def __init__(self, root=None, descriptors=(), allowed_metadata_files=()):
        # No validation/file access before the authenticated route calls us.
        self.root, self.descriptors, self.allowed = root, descriptors, allowed_metadata_files

    def _raw(self):
        if type(self.descriptors) is not tuple or len(self.descriptors) > MAX_CONTEXTS:
            raise ValueError("context capacity")
        return self.descriptors

    def contexts(self):
        try:
            descriptors = [validate_descriptor(row) for row in self._raw()]
            if len({row.context_id for row in descriptors}) != len(descriptors):
                raise ValueError("duplicate context")
            result, used = [], 0
            for descriptor in sorted(descriptors, key=lambda row: row.context_id):
                value, count = inspect_configured_metadata(self.root, descriptor, self.allowed, remaining=MAX_METADATA_BYTES-used)
                result.append(value); used += count
            return result
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise invalid_configuration() from None

    def refuse(self, request):
        try:
            matches = [row for row in self._raw() if (row.context_id if isinstance(row, ConfiguredSourceDescriptor)
                else row.get("context_id") if type(row) is dict else None) == request["source_context_id"]]
            if not matches:
                raise RealSourceError(409, "REAL_SOURCE_NOT_CONFIGURED", "No matching real-source context is configured", "CAPABILITY")
            if len(matches) != 1:
                raise ValueError("duplicate context")
            value, _count = inspect_configured_metadata(self.root, matches[0], self.allowed)
            if (request["expected_configuration_digest"], request["release_id"]) != (value["configuration_digest"], value["declared_release_id"]):
                raise RealSourceError(409, "REAL_SOURCE_CONFIGURATION_DIFFERS", "The explicit context declaration differs", "CONFIGURATION")
        except RealSourceError:
            raise
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError):
            raise invalid_configuration() from None
        raise RealSourceError(409, "REAL_PORTFOLIO_CREATION_DISABLED",
            "This metadata-only milestone cannot create or save real-source portfolios", "CAPABILITY")


def real_capabilities(provider):
    contexts = provider.contexts()
    result = dict(schema_version=SCHEMA, milestone="E1_GATE_ONLY", mode=MODE, state="BLOCKED", readiness_stage="METADATA_ONLY",
        provenance=dict(ledger_origin="PROJECT_CONSTRUCTED_NONPERSONAL_UAT_REQUESTED",
            market_origin="REAL_SOURCE_REQUESTED_NOT_QUALIFIED", personal_holdings=False),
        capabilities=dict(source_metadata=True, payload_verification=False, source_qualification=False, create=False, saved=False,
            workspace=False, analytics=False, imports=False, exports=False, evidence=False), approved_context_count=0, contexts=contexts,
        blockers=["NO_APPROVED_REAL_SOURCE_CONTEXT", "REAL_PORTFOLIO_STORAGE_NOT_IMPLEMENTED", "REAL_ANALYTICS_NOT_IMPLEMENTED"],
        limits=dict(http_bytes=32768, output_bytes=MAX_OUTPUT_BYTES), scope=dict(markets=["US"], reporting_currencies=["USD"]),
        support=dict(data_action="EXISTING_REGISTERED_PROJECT_METADATA_ONLY", download_or_admission=False, real_uat_verified=False, hg4_approved=False))
    if len(canonical_json(result).encode()) > MAX_OUTPUT_BYTES:
        raise invalid_configuration()
    return result
