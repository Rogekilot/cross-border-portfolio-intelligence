# Calendar drafts: review sheet (PD-0034)

Four drafts of `finweb.marketdata.calendar/1` files, covering **2025-01-01 to 2026-12-31**,
`actual_through` 2026-09-30, version `draft-1 (unchecked)`. Each file lists every session or
fixing day explicitly: the weekdays in the coverage minus the closures below, which come from
the publisher notice named in its `evidence`. No price or rate file was used (Ruling 5.3). All
four load with the project's calendar adapter, and together they form a valid set: each MIC is
governed by exactly one calendar.

**What to check:** every row below against the notice, and the close times. If anything is
wrong, say so and the draft is regenerated. Do not hand-edit the date lists.

## NYSE_SESSIONS (XNYS, XNAS; America/New_York; close 16:00)

| Year | Weekday closures | Early close 13:00 |
|---|---|---|
| 2025 | Jan 1, **Jan 9 (unscheduled: Carter mourning day)**, Jan 20, Feb 17, Apr 18, May 26, Jun 19, Jul 4, Sep 1, Nov 27, Dec 25 | Jul 3, Nov 28, Dec 24 |
| 2026 | Jan 1, Jan 19, Feb 16, Apr 3, May 25, Jun 19, **Jul 3 (full holiday, Independence Day observed)**, Sep 7, Nov 26, Dec 25 | Nov 27, Dec 24 |

Sessions: 250 (2025), 251 (2026). Some third-party sites list 2026-07-03 as an early close.
The NYSE page's "July 3" early-close footnote is for 2028.

## CN_A_SESSIONS (XSHG, XSHE; Asia/Shanghai; close 15:00; no half days)

| Year | Weekday closures |
|---|---|
| 2025 | Jan 1; Jan 28–31, Feb 3–4 (Spring Festival); Apr 4; May 1, 2, 5; Jun 2; Oct 1–3, Oct 6–8 |
| 2026 | Jan 1–2; Feb 16–20, Feb 23 (Spring Festival); Apr 6; May 1, 4, 5; Jun 19; Sep 25; Oct 1–2, Oct 5–7 |

Sessions: 243 (2025), 242 (2026). Weekend make-up working days are not trading days. The
draft lists weekdays only, so they never appear.

## HKEX_SESSIONS (XHKG; Asia/Hong_Kong; close 16:10, half days 12:10)

| Year | Weekday closures | Half days |
|---|---|---|
| 2025 | Jan 1; Jan 29–31; Apr 4; Apr 18; Apr 21; May 1; May 5; Jul 1; Oct 1; Oct 7; Oct 29; Dec 25–26 | Jan 28, Dec 24, Dec 31 |
| 2026 | Jan 1; Feb 17–19; Apr 3; Apr 6; Apr 7; May 1; May 25; Jun 19; Jul 1; Oct 1; Oct 19; Dec 25 | Feb 16, Dec 24, Dec 31 |

Sessions: 246 (2025), 247 (2026). **Close time: 16:10 (12:10 on half days), confirmed by the
quant-analyst in `market-data/1.8`** (the latest moment the official close can exist; HKEX's
closing auction ends at a random time between 16:08 and 16:10).

## ECB (fixing 14:10, publication 16:00, Europe/Berlin)

The fixing time is 14:10 per `market-data/1.8` (the ECB's "around 14:10 CET"); it was 14:15 in
draft-1. Changed by the main session 2026-10-01; no date list changed.

| Year | TARGET closing days on weekdays |
|---|---|
| 2025 | Jan 1, Apr 18, Apr 21, May 1, Dec 25, Dec 26 |
| 2026 | Jan 1, Apr 3, Apr 6, May 1, Dec 25 (Dec 26 is a Saturday) |

Fixing days: 255 (2025), 256 (2026).

## After you have checked

1. Set `version` to a final label (e.g. `2025-2026 v1`). Set `prepared_by` to say you
   checked it, and on what date.
2. Register each file with the download tool, for example:
   `PYTHONPATH=src .venv-download/bin/python -m marketdata_tools.download register-file --path data/marketdata/calendars/drafts/NYSE_SESSIONS.json --source calendar.manual --kind CALENDAR --format finweb_calendar_json/1 --adjustment RAW --label NYSE_2025_2026 --ext json --identifiers NYSE_SESSIONS`
3. Extending past 2026-12-31, or moving `actual_through` forward, is a new version of the
   file.
