# PD-0048 — approved SEC S1-A candidate evidence only

2026-10-19, Asia/Shanghai. This is an interactive owner decision after E1
acceptance, not resumption or extension of the ended night task.

## Owner decision

> 批准 S1-A：按上述限制补证（推荐）

The owner answered the structured question naming the exact limits in
[CP7_E_NEXT_SOURCE_DECISION_PACKET](../../reviews/CP7_E_NEXT_SOURCE_DECISION_PACKET.md).
Packet SHA at approval:
`7f6ed064eda5756bf4073c65b485e15e91c16ee787a1e505e91fd8ad55e9aff8`.

The owner also explicitly supplied an approved public project contact for the
SEC User-Agent. Its literal is intentionally omitted from this record and all
committable evidence, rather than misrepresented as a missing answer. The sender
identifier is `FinWebResearch`; the supplied contact may be sent only as part of
the approved SEC request header. No private-file inference or new contact lookup.
No API key, account or credential has been supplied or authorized.

## Authorized acquisition

At most three actual HTTP attempts, zero fees, no retries/redirects/fallbacks,
at least one second apart, entire S1 wall clock at most60 seconds. Per connection
and read timeout at most20 seconds; standard TLS verification, no auth/cookies or
environment proxy. Count an attempted request before sending it. Failures stop
all dependent requests; an unused attempt is not permission for another source.

1. Whole cross-issuer `https://www.sec.gov/files/company_tickers_exchange.json`,
   at most2MiB. Derive one unambiguous AAPL CIK from actual validated fields.
2. Only that issuer's `https://data.sec.gov/submissions/CIK<10 digits>.json`,
   at most4MiB, including its recent filing index. Check issuer/ticker consistency.
3. Only the unique latest exact10-Q/10-K by filingDate at or before2026-09-30,
   not report-period end, under the fixed `https://www.sec.gov/Archives/edgar/data/`
   CIK/accession/safe-primary-basename template, at most4MiB.

Total at most10MiB, encoded and decoded body budgets both bounded. Request identity
encoding and stop on unexpected compression. Bound error reads too, saving at
most64KiB of an error prefix. No extra HEAD/probe/pagination/attachments/amendments/
companyfacts or linked resources. Invalid/ambiguous/missing/oversized evidence
stops, with actual attempt/outcome recorded. Strict numeric CIK/accession, safe
basename and two permitted HTTPS hosts; no index-supplied arbitrary URL.

Parse JSON/HTML as inert data with no scripts, external entities or resources.
Save bounded original responses and their timestamps/hashes in a new evidence
directory, preserving failures. Do not persist the contact literal, request
header dump or a digest of the contact. If a response echoes the contact, stop
without persisting that body and record the scoped privacy stop. Technical
evidence omission is then explicit, not a fabricated raw-response preservation.

## Conditions retained

This is candidate material acquisition and independent verification only. No SEC
source registration/admission, old file/manifest/registry replacement or financial
release. Identity, MIC/USD/history, rights, upstream feed/filing independence,
action completeness and existing service gates still require actual evidence.
No real financial calculation, UAT or HG4 approval follows automatically.

No Alpha Vantage key/action calls or price/rate/benchmark history, personal
holdings, purchases, new dependencies/models, commit/push/deploy/publication,
formal CP8/9 or OCR work. E1's220 sealed artifacts and its historical scope finding
remain untouched. No old payload is reread for hashing or investigation. No
automation or caffeinate is restored; the old night deadline does not constrain
this separately authorized interactive action.

## Execution disposition (PM record, not a new owner decision)

S1-A completed on2026-10-19 at15:23 Shanghai: one reviewed final-tool run,
threeHTTP200 responses,8.625122seconds,1705944 returned HTTP-body bytes.
No retry/redirect/fallback or fourth request. All three authorized attempts are
spent. The contact literal/common-encoding private check passed before adoption;
no owner-contact literal/digest is in project evidence. Independent actual
acquisition and narrow source-report reviews passed; D3 remains NOT_QUALIFIED.
No source admission, release, financial service/UAT, HG4 or night-task restart.
See [actual result](../../reviews/CP7_E2_SEC_RESULT.md) and
[next readiness order](../../reviews/CP7_E3_DATA_READINESS_NEXT_STEPS.md).
