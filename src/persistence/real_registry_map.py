"""F1 R4b: the one mapping from a proposal's source record to the engine's `SourceRecord`, and the registry digests built on it.

Disposition note 5.3, obligation 1: `registry.used_source_digest` of a snapshot is the ENGINE's `source_registry_digest` over the engine's
`SourceRecord`s of the sources with a file in the release, because that is what the seal compares with `manifest.source_registry_digest`
(the performance engine computes it with the same function over the port's records). The proposal format keeps its own record dicts
(`real_proposal.SourceRecord`); this module is the only place that turns one into an engine record, so the writer, the verifier and R5's
world builder cannot disagree about it.

A proposal record has no `synthetic` and no `source_priority` key:
  * `synthetic` is the scope's origin, passed in: a test scope's sources are all synthetic, and the REAL scope's none is (O1);
  * a source priority is not representable: the registry file has none, and `source_registry_digest` adds the key only when it is set, so
    a record without one digests as every record did before the field existed.

Pure: no file, clock, environment or connection. (The date parse below is a parse of text, not a read of the clock.)
"""
from __future__ import annotations

import datetime as dt

from marketdata.manifest import ManifestError, SourceRecord as EngineSourceRecord, TermsCheck, source_registry_digest

TERMS_CHECK_KEYS = frozenset(("checked_by", "checked_on", "permits_internal_development_use", "notes"))


class RegistryMapError(ValueError):
    """The record is not one the engine would accept. Callers re-raise it under their own code."""


def engine_source_record(record, *, synthetic):
    """The engine's `SourceRecord` that a proposal record dict stands for. `terms_check` is None or exactly the engine's four fields, and
    `checked_on` is the engine's own ISO form (so a record has one canonical text). Anything the engine's constructors refuse is
    `RegistryMapError`."""
    try:
        terms = record["terms_check"]
        check = None
        if terms is not None:
            if type(terms) is not dict or set(terms) != TERMS_CHECK_KEYS or type(terms["checked_on"]) is not str or type(terms["notes"]) is not str:
                raise ValueError("terms_check is the engine's four fields")
            day = dt.date.fromisoformat(terms["checked_on"])
            if day.isoformat() != terms["checked_on"]:
                raise ValueError("checked_on is an ISO date")
            check = TermsCheck(terms["checked_by"], day, terms["permits_internal_development_use"], terms["notes"])
        terms_url = record["terms_url"]
        if terms_url is not None and type(terms_url) is not str:
            raise ValueError("terms_url is text or null")
        return EngineSourceRecord(record["source_id"], record["name"], record["upstream_provider"], record["independence_group"],
                                  terms_url, check, synthetic)
    except (ManifestError, ValueError, TypeError, KeyError) as error:
        raise RegistryMapError("a source record the engine would refuse: %s" % error) from error


def registry_digests(record_dicts, member_sources, *, synthetic):
    """(full-registry digest, used-source digest): the engine's `source_registry_digest` over the records of the registry, and over the
    records of the members' sources. The two differ whenever a source has no member."""
    engine = [engine_source_record(r, synthetic=synthetic) for r in sorted(record_dicts, key=lambda r: r["source_id"])]
    used = [r for r in engine if r.source_id in frozenset(member_sources)]
    return source_registry_digest(engine), source_registry_digest(used)
