"""F1 R5: the six digests the design leaves to R4b (design 6.4), in a module the PRODUCT may import.

These functions were written in R4b inside `real_tools.qualification` and are MOVED here unchanged in R5, because the world builder (`real_worlds`)
must recompute them from the locked snapshot and `real_tools` is, by R4b's own rule, never imported by product code (it needs the adapters and the
ingest build, which the persistence layer must not import). `real_tools.qualification` imports these names from here, so there is ONE implementation:
the qualification run that writes a proposal and the world builder that checks a snapshot call the same functions. Nothing in the bodies changed.
Pure: no connection, no clock, no file.
"""
from __future__ import annotations

import hashlib
import json

from marketdata import profiles
from marketdata.canonical import canonical_json
from persistence import market_data_store as mds


def _sha(obj):
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def identity_digest(resolver):
    """SHA-256 of the canonical JSON of the identity registry's rows: the issuers, instruments and listings that the owner's seed step writes into
    `issuer`, `instrument` and `listing`, and the identifier rows. Recomputable from those rows, in any order (TR4B-M2): each of the four row
    lists is sorted by a TOTAL key, the canonical JSON text of the row (every field takes part, `null` for an absent one), so the digest is a
    function of the SET of rows and not of the order in which a registry happened to register them or a database happens to return them."""
    issuers, instruments, listings = resolver.snapshot()

    def ordered(rows):
        return sorted(rows, key=lambda row: canonical_json(row))

    return _sha({
        "issuers": ordered([str(i.issuer_id), i.name, i.issuer_domicile] for i in issuers),
        "instruments": ordered([str(i.instrument_id), str(i.issuer_id), i.security_type.value, i.share_class_figi] for i in instruments),
        "listings": ordered([str(x.listing_id), str(x.instrument_id), x.mic, x.exchange, x.ticker, x.trading_currency.code, x.figi, x.is_active,
                             x.composite_figi] for x in listings),
        "identifiers": ordered([str(r.listing_id), r.scheme, r.value, r.qualifier, None if r.valid_from is None else r.valid_from.isoformat(),
                                None if r.valid_to is None else r.valid_to.isoformat(), r.asserted_by] for r in resolver.identifier_rows())})


def calendar_digest(release, contents, calendars):
    """SHA-256 of the canonical JSON of the calendars of the projection document (`market_data_store.projection_obj`)."""
    return _sha(mds.projection_obj(release, contents, calendars)["calendars"])


def convention_digest(market_conventions, perf_conventions, release):
    """SHA-256 of the canonical JSON of the version ids of the rules a result cites (`ConventionSet.ids()`, `PerformanceConventionSet.ids()`)
    and the release's own convention pairs."""
    return _sha({"market": market_conventions.ids(), "performance": perf_conventions.ids(), "release": [list(p) for p in release.conventions]})


def profile_digest(source_ids):
    """SHA-256 of the canonical JSON of the profile set version and, per member source, its profile's status, role, markets and admission
    (a source with no profile is listed as such: it is not admitted until one exists)."""
    entries = []
    for source_id in sorted(set(source_ids)):
        try:
            profile = profiles.source_profile(source_id)
        except profiles.ProfileNotAdmittedError:
            entries.append([source_id, None])
        else:
            entries.append([source_id, profile.status, profile.role, sorted(profile.markets), profile.admitted])
    return _sha({"profile_set": profiles.PROFILE_SET_VERSION, "sources": entries})


def release_digest(release):
    """SHA-256 of the canonical JSON of the release document as `md_release.release_content` stores it (its content and its id)."""
    return _sha(json.loads(release.to_json()))


def projection_digest(release, contents, calendars):
    """The digest `md_release.projection_digest` holds after the loader writes this release (the write passes `stored_contents` first)."""
    return mds.projection_digest(release, mds.stored_contents(contents), calendars)
