# ⛔ SSR — the official exchange lists (2026-11-23)

Ajay, 2026-11-23, verbatim:

> "No shorting at the bid (SEC short-sale restriction)
>
> Can we check or this for other stocks too?"

This doc covers the OFFICIAL half of the ⛔ SSR tag: `backend/short_interest/ssr_lists.py` (the two exchange lists +
the ONE refresh worker) and `backend/short_interest/biff_rows.py` (the house `.xls` reader). The rule, the computed
read and every tag word live in `ssr.py` (docs/short_interest/ssr_rule_201_2026_11_24.md); the dividends and splits in
`ssr_corp.py` (docs/short_interest/ssr_corp_actions_2026_11_24.md). Display only — nothing here gates, sorts, pushes
or enters a lane. UNMEASURED.

## The two sources

| | Nasdaq | NYSE Group |
|---|---|---|
| URL | `nasdaqtrader.com/dynamic/symdir/shorthalts/shorthalts%Y%m%d.txt` | `ftp.nyse.com/NYSEGroupSSRCircuitBreakers/…_%Y/…_%Y%m/NYSEGroupSSRCircuitBreakers%Y%m%d.xls` |
| Format | CSV (CRLF). Header `Symbol,Security Name,Market Category,Trigger Time`; names can hold quoted commas → the `csv` module; last line = 14-digit ET edition stamp | OLE2 / BIFF8 `.xls`, one sheet `SSR_data`, every cell an SST string. Header `Trigger Date · Issue Symbol · Issue Name · Primary Exchange · SSR State · Trigger Time · Anticipated Deactivation Date` |
| File for D holds | the rows triggered on the PREVIOUS trading day AND D (11/20 file: 549 rows of 11/19 + 1,086 of 11/20; 261 symbols twice) | only D's triggers (11/20: 330, 11/23: 114) |
| Editions seen | 04:15 ET (only the carried prior-day rows) and 16:30 ET (+ today's) | one, published ≈ 20:06–21:18 ET |
| "No file" | HTTP 302 to `/Trader.aspx?id=http404` (`reg_sho.NO_LIST_NASDAQ_302`) | HTTP 404 |
| First read of file D | 04:20 ET on D | 20:10 ET on D |
| Edition stamp | the trailer | the file's `Last-Modified`, converted to ET (NYSE has no trailer) |
| Stored exchange | `Nasdaq` | per row: `NYSE` / `MKT` → `NYSE American` / `P` → `NYSE Arca` (an unseen code prints as itself) |

Symbols are stored through `reg_sho.norm_symbol` (`AHT PRD` → `AHT.PRD`); `rows_for` finds every house spelling
(`BRK B` = `BRK-B` = `BRK.B`). NYSE's Anticipated Deactivation Date = the 2nd trading day after the trigger on the house
calendar for every row of both captured files — the exchange's own "rest of the day and the next trading day".

## Why the 16:30 edition never completes a day [C4]

Measured on 11/20: the final 16:30 edition of file(11/20) and the next morning's file(11/23) differ by a few rows BOTH
ways — 10 rows only in the next morning's file (late 4:15 PM fund rows + 2), 4 only in the final edition (renamed
units / warrants). So Nasdaq's record of trigger day T is complete only once file(next_market_day(T)) is held (any
edition, incl. its 04:15 pre-open one), and a trigger day's rows are the UNION of file(T) and file(next T) — a row
only in the 16:30 edition still counts. `complete_for(T)`: Nasdaq via file(next T) ONLY, NYSE via file(T), every
source required. `complete_for(today)` is therefore false all day. A list doc's `final` flag (Nasdaq: the stamp is
dated the file date at/after its regular close, 13:00 on a half day; NYSE: the file exists) only stops the re-fetch
of that file.

## The stale-edition trap (measured 2026-11-23 22:10 ET)

At 22:10 ET Nasdaq's URL still served the 04:15:15 edition (three reads, a `?v=` query changed nothing) while its page
listed a 16:30:04 file. The edition is read from the TRAILER, never from the clock: a 04:15 edition read at 22:10 is
not final and stays due. An older edition never replaces a newer doc (state result `older_edition`); a newer one
replaces it and is appended to `editions`. Conditional GET (`If-None-Match`) is sent only when an ETag is held.

## The worker

ONE single-flight daemon (the `reg_sho.kick_refresh` shape), kicked from the served read, never inline:

- File dates kept fresh: `[prev_market_day(L), L]`, L = today when a market day, else the market day before.
- A (source, file date) is due when it is not final, the clock is past its first-read time, and its last attempt is
  older than `SL_RETRY_MIN` = 30 min (`SL_ERROR_RETRY_MIN` = 5 min while errors < `SL_ERROR_STRIKES` = 2). 0 outside
  list calls once both files of both sources are final.
- The state doc (`state|<src>|<date>`, result `running`) is written BEFORE the outside call.
- Its LAST job, in its OWN fenced try with a lazy import: `ssr_corp.refresh_due(coll, file_dates(now), now, http=…)`
  — a missing or raising `ssr_corp` never stops or fails the list refresh; one warning is logged.
- Throttle numbers (MINE, HIS CALL 13, none a trading threshold): timeout 6 s, round budget 45 s, kick floor 60 s,
  `retry_after_sec` 20, 2 MB / 20,000 rows / 10 skipped rows per file.

Docs (collection `ssr_rule_201`, never purged): `list|<src>|<date>` = `{kind, source, file_date, stamp, final, etag,
url, rows: [[sym, tdate, ttime, category | exchange, deactivation?]], n, skipped, fetched_at, first_fetched_at,
editions, rev}`; `state|<src>|<date>` = `{kind, source, file_date, attempt_at, result, error, errors}`. The read
decodes a list doc once per `rev` (in-process cache) and reads the other docs without their rows.

Unreadable is never empty: a wrong header, a missing or wrong-date trailer, an HTML body, more than 10 skipped rows,
a file whose every row is skipped (e.g. a Trigger Date ≠ the asked date) and any `.xls` reader error are all
`malformed` errors — the source then reads failed and `complete_for` stays false; names rest on the computed read.

Served source rows (`source_views`): `Nasdaq short sale list for 11/23 · edition 04:15 ET · 1092 rows (today's
triggers not in it yet)` · `NYSE Group short sale list for 11/23 not published yet (after 20:10 ET)` · `… could not be
read — last good list 11/20` · `… not read yet`.

## The BIFF reader and its limits

`biff_rows.read_rows(data)` — stdlib only (`xlrd`, `openpyxl`, `olefile` are not installed in the host venv or the
api container). OLE2 header → FAT → directory → the `Workbook` stream → BIFF8 records of the FIRST worksheet: `SST`
+ `CONTINUE` (a string split across a CONTINUE restarts with a flags byte; both captured files carry CONTINUE
records) and `LABELSST`. A NUMBER / RK / LABEL / FORMULA / BOOLERR cell reads None. It raises `ValueError` on: bad
magic, a DIFAT chain, a broken / looping FAT chain, a short stream, no workbook stream, a mini-stream workbook
(< 4,096 bytes), an SST index out of range, more than 200,000 cells, input over 2,000,000 bytes, truncated bytes, an
empty buffer. A layout change raises → the NYSE source reads failed. Port of the prototype
`scratchpad/ssr/probe/biff_probe.py`; its grids are identical on both captured files.

## Known limit — preferred share classes (review 2026-11-23, NOT fixed)

The lists spell a preferred `AHT PRD`, stored as `AHT.PRD` (served also as `AHT-PRD`). The snapshot keys the same
issue `AHTPD`. No alias joins the two spellings, so `rows_for("AHTPD")` finds no official row. Effect: a computed
tag on a preferred is never confirmed. Once the lists for that day are complete it is dropped as `computed_only`.
Preferreds are not on Gajjala cards today. No alias rule was added: it would be a new symbol rule, and choosing one
is HIS CALL. The limit is pinned in
`test_NEGATIVE_KNOWN_LIMIT_a_preferred_asked_without_its_separator_finds_no_official_row`, and a fix moves that pin on
purpose.

## Not read

- **Cboe BZX** — an HTML page only (703 KB, no file link found), every row seen a leveraged fund / ETN (HIS CALL 7).

## UNMEASURED

- **Nasdaq intraday editions.** Step 0 of the package (the trailer stamp read twice ≥ 30 minutes apart in RTH) was
  NOT run: the package was built 2026-11-23 ≈ 23:15 ET, outside regular hours. Owed to the main session. The code
  assumes nothing either way: any edition is read from its trailer, and only file(next T) completes T.
- The exact publish time of each Nasdaq edition beyond the 04:15:15 and 16:30:12–16:30:31 stamps seen.

## Tests

`backend/tests/test_ssr_lists_2026_11_24.py`, `backend/tests/test_biff_rows_2026_11_24.py`; fixtures
`backend/tests/fixtures/ssr/` (the 11/20 final and 11/23 pre-open Nasdaq files, the 11/20 and 11/23 NYSE files —
byte-for-byte copies of the 2026-11-23 captures).
