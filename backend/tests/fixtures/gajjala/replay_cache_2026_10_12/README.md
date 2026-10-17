# replay_cache_2026_10_12 — a REAL 2-name slice of the Gajjala study cache (2026-10-16 night, BUILD_SPEC11 §4 WP-D)

Used by `backend/tests/test_gajjala_replay_script.py` (the ⏪ replay script, `scripts/gajjala_replay.py`). Never
hand-edited. Nothing in here was synthesized: every file is a copy of the study cache, and the detector hits the tests
pin are what the study's own `study_symbol_day` (method v2, scope live, no pool) finds on these bars.

- **Source:** `scratchpad/gajjala/wp6/cache` (study cache layout 2, `adjusted=false`, built 2026-10-13 23:21 local),
  probed read-only in a hermetic container (`--network none`, the cache mounted `:ro`) on 2026-10-16 night.
- **Copied byte-for-byte:** `cache_layout.json`, `minutes/2026-10-08/WFF.json`, `minutes/2026-10-09/{TCRT,WFF}.json`,
  `minutes/2026-10-12/{TCRT,WFF}.json`, `minutes/2026-10-13/TCRT.json`.
- **Trimmed (values unchanged, only the two names kept):** `grouped/2026-10-08.json`, `grouped/2026-10-09.json`,
  `grouped/2026-10-12.json` — the full grouped-daily files hold ~12,600 rows each; the superset of a name reads only its
  own row and its prior-session row, so the trim changes no result (the probe re-run on this slice found the same events).

## Why these two names
The spec asked for one 2026-10-12 A+ name whose 2026-10-13 minutes ARE cached and one whose are NOT, with A's next
column graded from the cache. The study cache has five 2026-10-12 A+ names (CLWT, SKYA, TCRT, WFF, YMAT) and only ONE
of them has 10-13 minutes: **TCRT** — and its A+ rang after the close (bull_flag, pass 16:20 ET), so its same session
is 10-13 (graded from the cache, AMENDMENTS9 E1) and its next session is 10-14, which the cache does not hold. No
2026-10-12 A+ in the cache has both columns cached. So, the nearest REAL pair:

- **A = TCRT** — 10-12 A+ whose 10-13 minutes are cached: same graded on the cached 10-13 bars; next not cached.
- **B = WFF** — 10-12 A+ whose 10-13 minutes are NOT cached (reversal_squeeze, pass 20:00 ET): same and next not cached.
- **The next-graded case comes from WFF's 2026-10-09 session** (one extra grouped file, 10-08, and WFF's 10-08 minutes
  for its prior session): intraday_vcp, pass 15:00 ET — same 10-09, next 10-12, BOTH in the cache; and
  reversal_squeeze, pass 16:50 ET — same 10-12 (cached), next 10-13 (not cached). TCRT is not in the 10-09 superset
  (53,810 shares that day), so its 10-09 minutes serve only as 10-12's prior session.

The pair therefore replays the D6 run's own sessions (`--sessions 2026-10-09 2026-10-12`).

## The real hits (the probe's output, pinned by the tests)
| session | symbol | setup | entry bar (ET) | pass (ET) | trigger | stop | same day | next day |
|---|---|---|---|---|---|---|---|---|
| 2026-10-09 | WFF | intraday_vcp | 15:00 | 15:00 | 14.4 | 10.68 | 10-09 (cached) | 10-12 (cached) |
| 2026-10-09 | WFF | reversal_squeeze | 16:50 | 16:50 | 13.145 | 12.1562 | 10-12 (cached) | 10-13 (not cached) |
| 2026-10-12 | TCRT | bull_flag | 16:20 | 16:20 | 1.04 | 1.03 | 10-13 (cached) | 10-14 (not cached) |
| 2026-10-12 | WFF | reversal_squeeze | 20:00 | 20:00 | 15.17 | 14.61 | 10-13 (not cached) | 10-14 (not cached) |

Every row: entry_class aplus, no variant, no grade, inside the push window. These are replayed rows — they never rang;
nothing here is a measurement (the 2026-10-14 study read NULL).
