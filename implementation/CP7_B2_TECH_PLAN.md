# CP7-B remaining workspace workflows

Authority: PD-0044; login/storage acceptance remains the base. No new dependency,
data admission, production deployment or scheduler is introduced.

The immutable `web_portfolio_revision` migration0018 records each confirmed command,
its parent, exact request digest, global ledger pin, canonical benchmark selection
pin/version, explicit UserLimit records and complete reproducible snapshot. The
original `web_saved_sandbox` is unchanged; its revision UUID is the portfolio UUID.
Current means greatest revision sequence, assigned under a per-portfolio lock.
Every mutation verifies owner first, then locks, checks idempotency before expected
head, validates domain rules and appends everything atomically. Same operation and
content replays its saved response; changed content409; stale head409. Runtime
grants extend only SELECT/INSERT and sequence usage; ledger and revision mutation
remain forbidden. No financial engine/method/fixture changes.

HTTP contracts, all cookie/CSRF protected and owner scoped:

- GET `/api/v1/portfolios/{id}/workspace[?revision_id=UUID]`: revision history,
  accounts visible at that revision, full canonical event facts with audit links,
  existing domain field rules, and canonical native state from `reconstruct`.
- POST `.../ledger-commands/preview`: exactly LedgerCommand below; actual append
  validation and financial replay inside a transaction that always rolls back.
  No command/revision is reserved; PostgreSQL sequences can have gaps. Preview
  digests/pins are transient and cannot be used as a committed Proof Packet.
- POST `.../ledger-commands`: same input, commit ledger and new revision together.
- POST `.../preferences`: explicit full policy replacement and benchmark KEEP,
  CLEAR or admitted SELECT, with no implied threshold, benchmark or risk profile.
- Existing snapshot, packet and reproduction URLs accept `?revision_id=UUID`.
  Reproduction passes the selected revision's actual UserLimit objects to CP6.

LedgerCommand: operation_id UUID, expected_revision_id UUID, explicit as_of date,
operation APPEND/CORRECT/REVERSE/ADD_ACCOUNT, events array, target_event_ids array,
optional account_name. ADD_ACCOUNT takes name and no facts; APPEND takes one or
more domain EventInput objects; CORRECT pairs targets and replacements; REVERSE
takes targets only. Reversals and correction links are server-created, using the
existing validator and atomic append_batch. Internal transfer pairs require both
matching legs. Event amounts/quantities are positive exact strings; basis permits
zero. EventInput preserves all existing optional dates, conversion bought amount,
split ratio, external transfer basis and acquired_on; no opening-quantity rewrite.

PreferencesCommand: operation_id, expected_revision_id, as_of, policies_confirmed
true, explicit policies array and benchmark `{action,benchmark_id?,selected_on?}`.
Each policy has UUID policy_id, source_kind, metric_id, semantic_key, scope_kind,
account_id/null, subject, direction, exact decimal/fraction limit, effective_from,
effective_until/null and visible user evidence. Only current offered semantic
targets are accepted; versions are the operation UUID. Empty array explicitly
clears; no preference history initially means NOT_STATED. No thresholds default.
Current source offers CP5 portfolio scopes only; unavailable CP4/account scopes
are not silently rebound. Historical revisions preserve every prior policy.

Benchmark uses the existing canonical selection log and committed catalog admission.
The synthetic API edge owns catalog-file loading and injects its catalog-provider
callable; persistence never imports the risk-service edge or opens a catalog file.
The provider runs only after owner resolution. A missing/malformed catalog or
non-catalog provider result is503 BENCHMARK_CATALOG_UNAVAILABLE, distinct from a
valid empty catalog, which remains an honest unavailable selection branch.
Existing saved snapshot/proof replay reads its pinned selection without requiring
today's catalog file to be available.
Transport NOT_STATED/NONE/SELECTED maps canonical NONE/CLEARED/IN_FORCE. KEEP writes
no selection; CLEAR is explicit and dated; SELECT requires an admitted entry and
records USER_CHOSEN origin/catalog version. Committed entries remain empty, so
positive selection is gated until separate source/catalog admission. Test-only
catalog injection verifies the mechanism without modifying committed data. A
selection never fabricates historical market data or a relative-return value.

The fictional source/calendar still covers only 2026-01-02. Commands explicitly
choose valuation as_of; after-opening activity is not hidden behind a fixed date.
Native positions/cash still replay exactly on later dates while unsupported
market valuations suppress numbers. Existing opening-date guards are untouched.
The original opening inputs remain labelled separately from current replayed facts.

Local bounds: at most32 events/policies per command,16 account containers and1000
workspace revisions. These are resource limits, never personal financial limits.
