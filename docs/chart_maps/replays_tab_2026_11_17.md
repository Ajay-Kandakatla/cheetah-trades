# 🎬 Replays tab — backend (2026-11-17)

Ajay 2026-11-17 ~22:30 ET, verbatim: **"Can you store the videos in to the app please"**.
Standing rule 2026-11-16: "Remove all the videos that are not till 8pm I only wanna see ones from 4 AM to 8 pm please".

**Owner-only, read-only, UNMEASURED.** A replay is for his eyes, not a signal. No rule, gate, threshold, push or trade
changes. Spec: the replaytab spec §3.1 / §4 WP-BE. Frontend: `replays_tab_frontend_2026_11_17.md`; mount + compose:
`replays_storage_2026_11_17.md`.

## Files
- `backend/chart_maps/replays/constants.py` — every served word; setup words from `chart_maps.gajjala.constants.SUBS`,
  page words from `chart_maps.gajjala_watch.constants.FRAME_WORDS` (never retyped — a source-guard test pins it).
- `backend/chart_maps/replays/store.py` — the disk engine (no Mongo, no network, no write).
- `backend/chart_maps/replays/api.py` — two routes, mounted in `backend/main.py` after 👀 Watch.
- `backend/scripts/replays_probe.py` — prints the same `store.payload` the route serves.
- Tests: `backend/tests/test_replays_store_2026_11_17.py` (56), `backend/tests/test_replays_api_2026_11_17.py` (41).

## Routes (both `Depends(require_primary_admin)` — the ONE owner gate)
| Route | Answer |
|---|---|
| `GET /chart-maps/replays[?date=YYYY-MM-DD]` | the listing, `Cache-Control: no-store`; malformed `date` → 404 |
| `GET\|HEAD /chart-maps/replays/video/{day}/{name}` | the bytes of a LISTED mp4 via Starlette `FileResponse` |

Anyone else → the stealth 404 on both routes, resolved before the path is looked at (a traversal probe and a real file
answer the same). No header → 401 (`auth.current_user_email`, the house shape).

## Accept rule (per `.json` in `videos/<date>/`)
Body is a dict · `window == "04:00-20:00 ET"` (`FULL_DAY_WINDOW`, his 11-16 rule; else `skipped_window`) · `file` is a
str matching `FILE_RE`, equal to the json's stem + `.mp4`, and that `.mp4` is in the same folder listing (a render in
flight is still `<name>.part.mp4` while its sidecar exists → not listed until run.sh's `mv`). Else `skipped_bad`. Every
`.mp4` with no ACCEPTED sidecar counts as `no_sidecar`, except the mp4 paired by stem with a window-skipped sidecar
(see the 2026-11-17 refix below). Each card is built
inside `try … except CARD_ERRORS` — one malformed sidecar (`why: []`, `speed: null`, `minutes: "x"`,
`ring_id: null`) drops only its own card (`skipped_bad`), never the listing. `jobs.json`, `run_log.tsv`, `.sent`,
the root reels and non-date folders are never listed.

**2026-11-17 refix — `counts.no_sidecar` no longer counts window-skipped reels.** On the real 11-13 folder it read
10 while 9 of those mp4s had a sidecar skipped for its 16:00 window; only 1 truly lacked one. `_parse_day` now records
the `file` of each window-skipped sidecar when it equals that json's own stem + `.mp4`, and leaves those mp4s out of
`no_sidecar` (they stay counted once, as `skipped_window`). A window-skipped sidecar naming a DIFFERENT mp4 excuses
nothing, and a bad (`skipped_bad`) sidecar's mp4 still counts as `no_sidecar`. Informational only: the FE never
prints `counts`; the §5.6 probe reads it. Listing, groups and `resolve_video` are unchanged.

## Groups (`group_of`, in this order; empty groups are omitted)
1. `plan_word == "🎾 Reversal Squeeze potential"` or an `rs` list → **🎾 Reversal Squeeze potentials** (ordered by
   `potential.first_stored_et`, then symbol).
2. `why[0]` starts with `"biggest mover of"` → **biggest mover**. This is the pipeline's own sentence
   (`replay_video.py:1199`, outside the repo) — the only marker it writes (HIS CALL #4). If that sentence ever changes,
   the mover silently becomes `other`; the probe's group counts show it.
3. ring day (`ring_id` before the first `|`) ≠ folder day → **other (carried after-close rings)** — HIS CALL #3: one
   deletable line if he says "grade decides". `carried` + `ring_day` are served either way.
4. `ring_id` ends `|aplus`: grade `W…` → **🏁 A+ winners**, `L…` → **A+ losers**, else other.
5. else **other** (👀 Watch / 🧠 / post-market reels — HIS CALL #9).

Inside every non-🎾 group: `move_pct` desc (unknown last), then symbol, then page (HIS CALL #5).

## Payload keys
`state` ∈ `ready | empty | no_folder`; `title`, `tab`, `date`, `dates` (desc, only folders with ≥ 1 listed video),
`window`, `window_note`, `text` (empty / no_folder), `groups[{key,label,videos}]`,
`counts{videos, skipped_window, no_sidecar, skipped_bad[, ledger_error]}`, `rs{title, note, columns, rows, text}`.
A well-formed `?date=` that has no folder is KEPT (`state: empty`, `date` = the asked day) so URL, select and page
agree (critique C8). Card keys: `file src symbol setup setup_text page page_text grade why story ring_id ring_day
carried speed speed_text minutes length_text move_pct move_base trig_pct fill_px no_risk window plan_word potential
group`. The 🎾 tracker = `rs_potentials/ledger.csv` rows of that date, 17 columns (HIS CALL #6), every cell a string,
`""` → `—`, page mapped to 1-min / 5-min; a malformed CSV → no rows + `counts.ledger_error`, never a 500. Its note is
served verbatim: "descriptive — UNMEASURED, not an edge; no placebo, so no average or median return is printed".
The whole body goes through `growth.api._scrub` (NaN / inf → null).

Cache: per (root, day), keyed by ONE scandir `(dir mtime_ns, n_json, max json mtime_ns, n_mp4)` — the max json mtime
catches an in-place sidecar rewrite that the folder mtime misses. The ledger is cached by `(mtime_ns, size)`.

## Range / gzip / HEAD (measured, starlette 0.41.3)
- `FileResponse` is the ONE Range engine: 206 + `content-range`, 416 with `Content-Range: */size`, 400 on a malformed
  header, `accept-ranges: bytes`. Nothing hand-written.
- **The gzip trap:** `main.py` adds `GZipMiddleware(minimum_size=1024)`. A bare `FileResponse` answers
  `Range: bytes=0-10239` + `Accept-Encoding: gzip` with 206 + `content-encoding: gzip` + a ~2 KB body — a corrupt
  partial for a media player. Below the floor (`bytes=100-199`, 100 B) the body passes through UNCOMPRESSED
  (`starlette/middleware/gzip.py:58`: `len(body) < minimum_size and not more_body`), so a small-range test proves
  nothing. `VIDEO_HEADERS["Content-Encoding"] = "identity"` is the lever (the `SSE_HEADERS` precedent). The tests use
  a 32,768-byte fixture and a 10,240-byte range, and keep the trap itself as a NEGATIVE: an unprotected route under the
  same middleware IS gzipped at 10,240 B and is NOT at 100 B. If that NEGATIVE ever stops failing, Starlette changed.
- FastAPI's `@router.get` does not answer HEAD (measured 405) → `api_route(methods=["GET", "HEAD"])`.

## Cloudflare (`Cache-Control: private, no-transform`)
Cloudflare fronts pounce (`server: cloudflare`, `cf-cache-status: DYNAMIC`) and `.mp4` is on its default cacheable
extension list. A 200 cached at the edge would be served to anyone with the URL without reaching the owner gate.
Cloudflare does not cache a response carrying `private` → that header is the gate's second half (HIS CALL #17).
Verify after deploy: an unauthenticated range request never answers 200/206 and `cf-cache-status` is never `HIT`.

## Probe (read-only; run before deploy)
```bash
cd /Users/ajay/clinet-test/.wt-replaytab/backend
REPLAYS_DIR=/Users/ajay/clinet-test/eod-audits/replays .venv/bin/python scripts/replays_probe.py --all
```
Measured 2026-11-17 night on the host folder: 12 dates; 2026-11-17 = 23 videos {🏁 2, losers 5, 🎾 11, mover 1,
other 4}, `skipped_bad` 0, 19 tracker rows; 11-16 = 16 {losers 4, other 12}; 11-13 = 1 {losers 1}; 11-03 = 2
{other 2}. The 🏁 A+ winners group exists on ONE of 12 dates — every older winner was rendered to 16:00 and his
11-16 rule hides it (HIS CALL #16), not a defect.

## HIS CALLs (spec §7)
#1 owner-only · #2 label + slot · #3 carried → other · #4 mover by the pipeline's words · #5 order · #6 the 17
tracker columns · #9 👀/🧠 reels under other · #11 stealth 404 · #16 old winners hidden by his rule · #17 `private`.

## 2026-11-18 — winners / losers as categories, 1-minute reels removed

Ajay 2026-11-18, verbatim: "Also on the videos categorize winners and losers as categories and then remove 1 mins from them".

- A carried after-close A+ ring (rang after the close, graded on the next session) files under 🏁 A+ winners / A+ losers by its grade, like every A+ ring (it used to sit under "other" — HIS CALL #3 of 11-17, answered). "other" keeps only an ungraded ring.
- `constants.EXCLUDED_PAGES = ("gajjala_1m",)`: the 🚩 1-minute page retired 2026-11-18, so its reels (counted `skipped_page`, never `no_sidecar`) and its 🎾 tracker rows are never listed or served. They stay on disk; an empty tuple brings them back.
- 11-17 on the real folder after the change: winners CENN, OGEN (Monday after-hours rings) · losers PAVS, TTEC, CRDF · 🎾 8 potentials (5-min) · 10 one-minute reels skipped · tracker 12 rows.
- The nightly task passes `--pages gajjala`, so no new 1-minute reels are rendered.
