# PD-0050 — once-only known-event EODHD demo evaluation

Status: APPROVED_WITH_CONDITIONS. Received from owner interactively.
Recorded UTC: 2026-10-19T12:05:24.213534+00:00

## Exact question and answer

Question: 目标日期已核实，测试和独立复核已完成。是否批准《CP7_E8_DATA_ACTION_PACKET》推荐 A：只用已冻结工具，向 EODHD 公开 demo 发起最多1次 AAPL.US 拆股请求，日期固定为2020-08-31当天；原文仅私有本地保存／解析，与已核实的4比1预期作精确数值比较，模型只看匹配枚举等元数据；20秒监督预算＋最多0.5秒回收宽限，接受应用body≤64KiB、超限检测最多多读1字节；不开户、不用私人key、不付费、不重试／跳转或日期回退、不准入来源或通过HG4、不恢复夜间任务？任何结果都结束本次请求。PD-0049仅覆盖已消耗的2026-09-30一次请求，本轮新日期及本地比较需要单独授权；未答不执行。

Owner answer verbatim: “批准 A：按授权包执行一次请求（推荐）”

Authority is this explicit answer. Preparation, tests, previous PD-0049 or silence
do not grant this new acquisition.

## Concrete grant and stop boundary

Reviewed packet: reviews/CP7_E8_DATA_ACTION_PACKET.md, SHA
04ede6634945db64505d510d30f3ec55fa36cd0bf5e339980130b32fa207b4de.
Frozen tool: reviews/CP7_E8_EVIDENCE/author/eodhd_event_requester.py, SHA
36c2733a5f471e92078745e55f5c6d15da911d4925dc42d6214dcededcee67de. Request/expectation SHA 688de39f86c55ec832d2f3b8f4bb1b9248af78b621125592ea36613dc8671f1c.
Preparation seal:612d80c984a86b8f130dd8af489e87aff638dc816e736a21e9655de2a6c79edb.

Only HTTPS GET eodhd.com:443 /api/splits/AAPL.US, from=to=2020-08-31,
fmt=json, api_token=demo; one first resolved address, at most one attempt.
No redirects, retries, alternate dates, securities, hosts or fetcher fallback.
20-second monotonic worker supervision includes preflight/DNS/TLS/headers/body/
parse, with pre-fork remaining-budget gate and <=0.5-second reap grace. Accepted
HTTP-framed application body<=65,536 bytes; detector<=65,537 bytes; identity
encoding only. Frozen strict JSON/record/token/depth/row/decimal limits remain.

New exclusive local leaf:.local/cp7e8-eodhd-aapl-split-20200831,0700directory/
0600files, no-follow/exclusive; pre-network ATTEMPT marker consumes this allowance
even if failed or UNKNOWN. Distinct0600 receipt binds tool, request, decision
path, leaf and max_attempts1; no old receipt/artifact reuse.

Complete valid200 arrays may be privately saved and parsed by frozen local code
only. No cat/preview/browser/model/connector/upload/cloud read or hash of
response.json by PM/reviewer. Model sees bounded metadata/enums only. Local exact
integer/decimal-scale comparison: exactly1 valid fixed-day row with new/old4
=>expected_event_checkPASS; empty=>NOT_EXERCISED; valid mismatch/multiple=>FAIL;
noncandidate/UNKNOWN/save or finalization failure=>NOT_EXERCISED. Equivalent8/2
representations may match. Structural record_check stays separate; exit0 can
contain expectedFAIL/NOT_EXERCISED. Every outcome ends the attempt.

Actual bytes/date/ratio/error body/headers never reach the model. PASS means only
agreement of this sample with the public known-event expectation. No profile,
coverage, classification, historical identity/MIC/USD/RAW or independent-chain
qualification follows; no ongoing UI/export/cloud rights are granted.

Parent filesystem/OS/kernel stalls/external termination can exceed the worker
budget; body cap is not total wire/TLS/kernel bytes and false-small framing may
hide trailing wire bytes. Platform CA defaults may use SSL_CERT_*. Receipt and
Python controls assume trusted operator, not OS/native or hostile-same-user
isolation. All practical limits in the reviewed packet remain applicable.

No account, private key, payment, real holdings/files, source admission, market
store/release/context mutation, positive finance/UAT or HG4 approval. D3 remains
NOT_QUALIFIED and F1 NOT_CLOSED. No new dependencies, provider contact, commits/
push/merge, deployment/publication, night automation or caffeinate restoration.
Prior SEC/OpenFIGI/E7 allowances are not reopened.

PM may execute the frozen CLI once under necessary network permission, preserve
metadata and get independent metadata-only audit. No rerun after any outcome.
