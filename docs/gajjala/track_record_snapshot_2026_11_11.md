# 📸 Track-record row snapshot — every stored 🏁 row, kept before its features expire (2026-11-11)

**Record only.** Nothing serves it: no page, no word, no gate, no push, no threshold. Two host files read Mongo
(read-only) and write files OUTSIDE the repo. Spec: rec157 WP-3 (relayed approval "Do your receommendations",
2026-11-11).

Files:
- `backend/scripts/track_record_snapshot_probe.py` — the container-side probe (read-only, the served engines).
- `backend/scripts/track_record_snapshot.py` — the host CLI + the merge (stdlib only, Python 3.9-safe).
- `backend/tests/test_track_record_snapshot_2026_11_11.py` — the merge, the store, the crash points, the probe's pure
  parts, the source guards (NEGATIVES included).

## 1. Why — what expires (measured 2026-11-12)

The rows and their grades do NOT expire: `gajjala_ledger`, `gajjala_1m_ledger`, `gajjala_alerts`, `gajjala_1m_alerts`,
`gajjala_potentials`, `luk_ledger`, `luk_alerts`, `intraday_cache` have no TTL index. What expires is the row
FEATURES:

| source | TTL | what a row loses |
|---|---|---|
| `gajjala_reads`, `gajjala_1m_reads` | 14 d (`GC.READS_TTL_DAYS`) | the reads ctx (`ctx_eod`: float, rotation, halts, reg gain, squeeze history n) |
| `gajjala_audited_overlay` | 14 d (`GC.READS_TTL_DAYS`) | the 🧪 overlay verdict (`audit` on gg5, `audit_raw` on gga) |
| `luk_reads` | 14 d (`GC.READS_TTL_DAYS`) | Luk's read of the day (`ctx_eod`: facts, tier, tile, screens rank, cap text, as-of bars, the setup's read) |
| `gajjala_daily` | 30 d (`GC.LEDGER_TTL_DAYS`) | `avg_vol_50` |
| `luk_daily` | 30 d (`GC.LEDGER_TTL_DAYS`) | Luk's daily facts (`daily`) |

The binding window is 14 days. `luk_passes` / `luk_screens` (30 d) and the GG strip / scan snapshots are SESSION-level,
not row features — not captured (HIS CALL #8 of the spec).

## 2. What one row holds, per page

- **gg5 / gg1** (`gajjala.ledger.rows_for` over the page's store): the row keys, the stored `same` / `next` grades, the
  served states and bucket, the 🔁 `dup_of` (`ledger.dedupe_trades` over `ledger.trade_facts`), the 🧠 tracker facts
  (`pot`), the claim (`alert`), `ctx_eod`, `audit` (gg5 only), `avg_vol_50` + `avg_vol_50_date`, `bars`.
- **gga**: one row per 🚩 A+ row the 🧪 🏁 lists (sessions ≥ `GC.GGA_RECORD_FROM`): `audit_cell` = the served cell
  (`audited_tab.read_span(span="all")` → `row_audits`, the ONE verdict) and `audit_raw` = the overlay doc's
  `setups[setup]` (aplus, original_aplus, failed ids, rules).
- **luk** (`luk.ledger.rows_for` / `track_row` with EVERY served cell key / `mark_dups`): the row keys, `cell`, the
  `luk_ledger` doc's `fill`, `walk`, `version`, `graded_at`, `graded_from`, raw `trigger`, `stop`, `fill_px`, `exit_px`
  (R from the fill is always recomputable), `bars`, `ctx_eod` (from `luk_reads`) and `daily` (from `luk_daily`).
- Every row: `src_present` = whether each expiring source doc exists NOW. It is never content (a source vanishing is
  not a change of the row).
- `bars` = facts from the 1-minute intraday CACHE at the ring (bars CLOSED at or before the alert time) — the only
  block that is as-of the ring. `prev_close` reads the previous MARKET day (`market_hours.reminder.is_market_day`):
  2026-11-27 reads 2026-11-25, never the closed 11-26.

**`ctx_eod` is the day's LAST write, never "known at the alert".** `upsert_read` replaces the reads doc on every pass,
so a later feature study that reads it as known at the ring looks ahead. Capturing the read at the ring = a write in
the GG / Luk pass = HIS CALL #13.

## 3. The key — page + the engine's row id

`page|<row id>`, e.g. `gg5|2026-11-11|ABCD|squeeze|aplus`, `luk|2026-11-11|IONR|opening_range_high|aplus`. The id
already holds date, symbol, setup and (on the GG pages) the kind, so a 🧠 potential and its A+ are two keys. The alert
time is kept IN the row: a re-stamped alert time is a new VERSION of the same key, never a second key (a ghost row).
This is NOT the five-part key he was told (page, date, symbol, setup, alert time) — HIS CALL #9. A row without an id, or
two rows of one page in one dump with the same id → refused (exit 2), nothing written.

## 4. The merge rule (append-only, versioned)

- No previous version → version 1.
- A TTL block that is `None` now while its source doc is gone now (`src_present` False), where the previous version
  held a value → the previous value is CARRIED (an expiry is not a change). `avg_vol_50_date` is carried with
  `avg_vol_50` (same source doc). `carried` names the block when a new version is written for another reason.
- After the carry: equal canonical content (sorted-key JSON without `src_present`) → nothing appended.
- Different → version `v + 1` with this snapshot date; the old version stays (a changed grade keeps both).
- A key in the store and not in Mongo any more → kept, untouched.
- A `None` while the source doc still exists is a real change (a new version) — never carried.

## 5. The files

`--out` (default `/Users/ajay/clinet-test/eod-audits/track-record-snapshots/`, outside the repo):
- `dumps/<snapshot date>.json.gz` — the probe JSON minus `generated_utc`, sorted keys, gzip mtime 0: the same content
  gives the same bytes. A same-date dump with other content is never overwritten → `<date>.r2.json.gz`, `.r3…`.
- `merged.jsonl` — one line per version: `{key, page, v, snapshot_date, sha (of its dump file), carried, row}`.
- `manifest.json` — `{schema, dumps: [{file, sha256, bytes, snapshot_date, generated_utc, rows: {page: {session: n}},
  nulls: {page: {block: [n_null, n_rows]}}}], merged: {lines, bytes, sha256 (of exactly those first bytes), keys,
  versions_by_page, never_captured: {page: {block: n}}}}`.

Every write is temp + `os.replace`. Order: the dated dump, then `merged.jsonl` (old bytes + new lines — the old bytes
are a byte prefix), then the manifest. A re-run with no change writes nothing.

## 6. A killed run finishes on the next run; anything else is refused

1. **Killed after the dump write** → a `dumps/` file the manifest does not list: ADOPTED when it gunzips, parses and has
   the dump shape (its sha, bytes, rows, nulls listed), and merged (idempotent) before the fresh probe. Summary:
   `recovered.dumps`.
2. **Killed after the merged write** → `merged.jsonl` longer than the manifest's `bytes`: ACCEPTED when the first
   `bytes` bytes hash to the manifest's `sha256` and the tail is whole, newline-terminated, parseable lines with
   contiguous `v` per key; the manifest is re-written, no line appended twice. Summary: `recovered.lines`.
3. No manifest at all = an empty prefix; the same two rules apply.

Refused — **exit 2**, the named reason, NOTHING written, never truncated or repaired: a prefix whose sha does not match,
a torn last line, a line that does not parse or is not the line shape, a non-contiguous `v`, a listed dump that is
missing or whose sha moved, an unlisted dump that does not gunzip / parse / have the shape, a probe dump with a `null`
or missing page, a snapshot date after the probe's session.

## 7. Null counts — named, never judged

Every run prints `nulls` (per page, per TTL block, `[n_null, n_rows]`) and `all_null` (a block `None` on EVERY row of a
page). The manifest keeps `never_captured` (keys whose every stored version held `None` for a block). There is no
threshold: an all-null block is named, nothing else is judged (the "> 50 %" warning was rejected as a new number).

## 8. `--verify`

Writes nothing. Takes a fresh probe (or `--from-json`), dry-runs the merge, and passes (exit 0) only when the store
opens clean with nothing to recover, every dump sha and the merged prefix sha match the manifest, and NO row currently
in Mongo would be appended. Prints `{covered, not_covered, kept_not_in_mongo, nulls, all_null, never_captured,
integrity}`; a recoverable store reads `"recoverable: …"` and exits 1; a corrupt one names the reason and exits 1.

## 9. The run recipe (the main session's daily scheduled task — no crontab)

After the close, a CLOSED session only, one after the other:

```
python3 backend/scripts/track_record_snapshot.py
python3 backend/scripts/track_record_snapshot.py --verify
```

Exit 0 = ok. **Exit 2 (refused) and exit 1 (verify failed / recoverable) must be SURFACED in the task's report, never
swallowed**: a refused store blocks every later run until a human reads the reason. One `docker exec` per run. The
FIRST real snapshot runs the night this lands (the 10-29 GG reads / overlay expire about now; Luk's first reads
(11-02) about 11-16).

## 10. Snapshot zero, and the WP-1 deploy

- `eod-audits/research/2026-11-11_track_record_patterns/rows.json` is the 11-11 snapshot zero of the GG rows (the
  study's dump; its block is still named `ctx`, no Luk ctx). It is NOT merged into this store.
- After the WP-1 deploy (Luk stop R from the fill), every Luk stop row filled ABOVE its trigger gets ONE new version:
  the dumped served cell's `r` / `exit_text` moved, the stored `walk` did not. Expected, not a fault.

## 11. Read-only-ness of the engines (WP-3 step 1)

- `gajjala.store.default()` / `for_variant()`, `luk.store.default()`, `audited_tab.read_span` / `_read_sides` /
  `row_audits`: construct and read only — no `ensure_indexes`, no write, no provider fetch (`_read_sides` reads
  `rows_for`, `ledger_docs`, `alert_rows`, `held_rows`, `exits_docs` — all Mongo finds).
- ONE side effect found: the stores resolve their handle through `portfolio.store._get_db`, which runs
  `portfolio_holdings.create_index(...)` on its first call. The probe pre-sets `portfolio.store._db` to its own handle
  so that `create_index` never runs. Nothing else is bypassed.
- `chart_maps.luk.ledger` imports `daytrading.data` (for `ET_RTH_OPEN`) at module level; nothing in it is called. The
  probe itself imports no `trading` / `daytrading` / broker / provider module (source guard).
- Kept exactly as the study's `dump_rows.py`: the GG pages read `rows_for` WITHOUT the ⏪ replayed line (the served
  🚩 🏁 adds it on GG5 only).

## 12. Why `avg_vol_50` is nearly always None — traced, NOT fixed (HIS CALL #13)

One read-only aggregate of `gajjala_daily` on 2026-11-12 ~12:10 ET:

| session | docs | with `avg_vol_50` |
|---|---|---|
| 2026-10-13 → 2026-11-10 (20 sessions) | 24 … 194 a day | **0** |
| 2026-11-11 | 199 | 14 |
| 2026-11-12 (in progress) | 170 | 164 |

Cause, from the code (`chart_maps/gajjala/context.py` `warm_squeeze_history`, :520-565):
1. `avg_vol_50` was born on 2026-11-11 (commit `d6c50570`, 💋 Kiss & Fly; the cron container was rebuilt 11-11 18:55Z =
   13:55 ET). No `gajjala_daily` doc written before it holds the field.
2. A cached doc is never re-read for it: when the session's doc already holds `squeeze_history`, the function serves
   the cache and `continue`s ("a doc written before the average existed … has none"). So the 185 names of 11-11 that
   were computed before 13:55 ET stay without it.
3. It is stored "ONLY when known": `momentum_burst.avg_volume_before` answers None unless `VOL_AVG_BARS` (50) finite
   closed sessions exist before the day — the 6 of 170 on 11-12 (a young listing reads None, by design).
4. `gajjala_daily` TTL 30 d: older docs leave anyway.

So the ~99 % None on the critic's 11-11 run is the field's birth date, not a defect of the reader: rows from 11-12 on
read it (164 / 170 docs), rows before 11-11 never will (`never_captured` will count them). Backfilling, dropping the
field, or re-reading cached docs = HIS CALL #13. Nothing was changed.

## 13. Live proof (read-only, after the close, into the scratch dir)

Run 2026-11-12 16:20 ET against `cheetah-market-app-api-1` (origin/main `bfa8b950`), `--out
<scratch>/rec157/snap-test` (the real default dir was NOT written). One `docker exec`, 3.6 s; `faults` empty.

| step | exit | result |
|---|---|---|
| plain run | 0 | appended gg5 1,049 · gg1 527 · gga 32 · luk 124 versions; dump 685 KB gzip, merged.jsonl 4.9 MB |
| `--verify` | 0 | integrity ok · covered = every row · not_covered 0 · kept_not_in_mongo 0 |
| second run | 0 | appended 0 on every page; the same dump file reused; no file rewritten (mtimes equal) |

Rows per page and sessions:

| page | rows | sessions | of which 2026-11-12 | 2026-11-11 |
|---|---|---|---|---|
| gg5 | 1,049 (964 🧠 + 85 A+) | 23 (10-13 → 11-12) | 17 | 59 |
| gg1 | 527 (477 🧠 + 50 A+) | 13 (10-27 → 11-12) | 20 | 42 |
| gga | 32 | 9 (11-02 → 11-12) | 3 | 7 |
| luk | 124 | 9 (11-02 → 11-12) | 18 | 21 |

Reconciliation with the spec (§1.4): gg5 1,049 − 17 rows of 11-12 = 1,032 = the critic's gg5 rows (the 1,023 ledger
docs are the GRADED rows; a row exists from its ring, its grade from the 20:15 ET nightly). gg1 527 − 20 = 507 = the
critic's. luk 124 − 18 = 106 rows (98 docs: same reason). No unexplained gap.

`nulls` ([n_null, n_rows]):

| page | ctx_eod | audit / audit_raw | audit_cell | avg_vol_50 | bars | daily |
|---|---|---|---|---|---|---|
| gg5 | 527 / 1,049 | 987 / 1,049 | — | 1,026 / 1,049 | 24 / 1,049 | — |
| gg1 | 83 / 527 | — | — | 503 / 527 | 21 / 527 | — |
| gga | — | 4 / 32 | 0 / 32 | — | — | — |
| luk | 0 / 124 | — | — | — | 29 / 124 | 25 / 124 |

`all_null`: none. Read:
- gg5 `ctx_eod` None on every row dated 10-13 → 10-28 (the 14-day TTL already took them); 10-29 is still held and is
  caught by this first snapshot. gg1: the same on 10-27 / 10-28.
- gg5 `audit` exists only where the 🧪 overlay judged the setup (from 11-02); None elsewhere is a real "no verdict".
- `avg_vol_50`: non-None on gg5 = 6 of 59 rows of 11-11 + all 17 of 11-12; gg1 = 4 of 42 + all 20 — exactly the
  field's birth (§12).
- luk `bars` None: all 18 rows of 11-12 (the intraday cache of today fills lazily) + 11 older; luk `daily` None on 25
  rows over 7 sessions, gga `audit_raw` None on 4 rows (no overlay doc for RETO, NXXT 11-11; HUHU 11-05; DTST 11-03) —
  recorded, NOT traced (not asked).
