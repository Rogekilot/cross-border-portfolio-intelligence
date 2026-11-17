"""`openfigi.identity`: OpenFIGI v3 mapping responses, payload format `openfigi_json_mapping/1`.
A pure translator to `IdentityAssertion`s: EVIDENCE for resolution, never identity creation.

Structure, from the first real files (2026-10-01; never committed, only synthetic files with
this structure are): a JSON list with one element per mapping job; a matched job is
`{"data": [{"figi", "name", "ticker", "exchCode", "compositeFIGI", "securityType",
"marketSector", "shareClassFIGI", "securityType2", "securityDescription"}, ...]}`, an unmatched
one is `{"warning": "No identifier found."}` and a rejected one `{"error": "..."}`.

Kept exactly as published: the ticker is not zero-padded or otherwise normalized (HK Tencent
comes back as "700", not "0700"), and `exchCode` is the source's own exchange code ("US" is the
US composite, "HK"), NOT a MIC; no MIC is inferred from it. A warning or error element yields
an issue and no assertion. FIGI strings are taken verbatim (12 characters in the examples; the
format is not validated here).
"""

from __future__ import annotations

import json
from typing import List

from marketdata.adapters.base import (
    AdapterIssue,
    AdapterOutput,
    IssueCode,
    lineage_for,
    timing_for,
)
from marketdata.contracts import IdentityAssertion, ObservationRuleError
from marketdata.manifest import DataKind, FileManifest

SOURCE_ID = "openfigi"
PAYLOAD_FORMAT = "openfigi_json_mapping/1"


class OpenFigiIdentityAdapter:
    adapter_id = "openfigi.identity"
    adapter_version = "0.1.0"
    source_id = SOURCE_ID
    data_kind = DataKind.IDENTITY
    payload_formats = (PAYLOAD_FORMAT,)

    def translate(self, manifest: FileManifest, payload: bytes) -> AdapterOutput:
        try:
            jobs = json.loads(payload.decode("utf-8"))
            if not isinstance(jobs, list):
                raise ValueError("top level must be a list")
        except (UnicodeDecodeError, ValueError) as exc:
            return AdapterOutput(issues=(AdapterIssue("file", IssueCode.UNKNOWN_FORMAT, str(exc)),))
        out: List[IdentityAssertion] = []
        issues: List[AdapterIssue] = []
        for j, job in enumerate(jobs):
            ref = f"job{j}"
            if not isinstance(job, dict):
                issues.append(AdapterIssue(ref, IssueCode.UNPARSEABLE_ROW, "job must be an object"))
                continue
            message = job.get("warning") or job.get("error")
            if message:
                issues.append(AdapterIssue(ref, IssueCode.MISSING_FIELD, str(message)[:200]))
                continue
            for i, item in enumerate(job.get("data") or []):
                iref = f"{ref}/data{i}"
                try:
                    out.append(IdentityAssertion(
                        figi=item["figi"], ticker=item["ticker"], exch_code=item["exchCode"],
                        timing=timing_for(manifest),
                        lineage=lineage_for(manifest, self, iref),
                        composite_figi=item.get("compositeFIGI"),
                        share_class_figi=item.get("shareClassFIGI"),
                        name=item.get("name"), security_type=item.get("securityType")))
                except (KeyError, TypeError, ObservationRuleError) as exc:
                    issues.append(AdapterIssue(iref, IssueCode.MISSING_FIELD, type(exc).__name__))
        return AdapterOutput(identities=tuple(out), issues=tuple(issues))
