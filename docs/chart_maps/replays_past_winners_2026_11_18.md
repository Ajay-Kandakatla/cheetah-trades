# 🏆 Past winners on 🎬 Replays (2026-11-18)

Ajay 2026-11-18 ~21:45 ET, verbatim: **"can you work on todays videos and also..  Winners in general from the past"**.

"Today's videos" of OUR rings stay with the nightly task (`videos/<date>/`). This section is **winners in general**:
market-wide big movers we may never have rung, today and in past sessions, plus the 15 multi-day runner reels.
**Owner only. Hand-picked winners (survivorship): descriptive, UNMEASURED, not a signal.** No rule, gate, threshold,
push or trade changes. Spec: scratchpad `pastwinners/spec.md` §3.5–§3.6 (WP-APP). The reels and the finder are WP-VID
(`eod-audits/replays/replay_winners.py`, `eod-audits/research/2026-11-18_past_winners/`).

## Placement (Rule #5)
~500 rows is long, so the section sits at the bottom of 🎬 Replays, collapsed, rows are text until tapped, one video at
a time. Nothing is fetched on the tab's mount; opening the section sets `?winners=1` and makes ONE GET.

## Routes (both `Depends(require_primary_admin)` — the ONE owner gate; anyone else → stealth 404, no header → 401)
| Route | Answer |
|---|---|
| `GET /chart-maps/replays/winners` | `store.winners_payload`, `Cache-Control: no-store` |
| `GET\|HEAD /chart-maps/replays/winners/video/{sub}/{name}` | the bytes of a LISTED mp4 under `videos/<sub>/`, Starlette `FileResponse` + `VIDEO_HEADERS` (identity + private) |

`sub` must be exactly `winners` or `multiday` (`C.WINNER_SUB_KEYS`); anything else (a date, `..`, `phone`, `_bars`,
`Winners`) → 404. The day routes (`/chart-maps/replays[?date=]`, `/chart-maps/replays/video/{day}/{name}`) and the day
listing are unchanged — a golden test pins `payload` / `dates` / the HTTP body byte-for-byte with both folders present.
`api.py` now declares FOUR routes.

## Accept rule (per `.json` in `videos/winners/` and `videos/multiday/`, non-recursive)
The day folder's rule (`_parse_day`) with the window decided by `winner_window_ok`:
- `winners/` → `window == FULL_DAY_WINDOW` ("04:00-20:00 ET", his 11-16 rule; one session).
- `multiday/` → `window` starts with `MULTI_WINDOW_PREFIX` = `FULL_DAY_WINDOW + " x "` ("04:00-20:00 ET x N sessions (…)"):
  every session of the reel runs 04:00–20:00.
- Else `skipped_window`. `jobs.json`, `runners.json`, `winners.json` are never read. `multiday/phone/` is never listed.
- `file` = the json's stem + `.mp4`, present in the same scandir (a `.part.mp4` render is not listed until the `mv`).
- Each card is built inside `try … except CARD_ERRORS` → one bad sidecar is one `skipped_bad`, never a 500. A card is
  refused when: `symbol` not a non-empty str; `day` / `days[]` not `YYYY-MM-DD`; `speed` / `minutes` not finite numbers;
  `close_gain_pct` not a finite number (NaN, a string, missing); `spike_print` not a bool; `spike_print` true without a
  finite `spike_x > 0`; a `winners/` `pick` not `plus100` / `today_top`; a `today_top` reel without a positive int
  `today_n` (judgement call: no sensible words without it).
- The 15 multi-day sidecars need WP-VID's `mbackfill` (adds `kind, day, close_gain_pct, high_pct, spike_print, spike_x`);
  until then they read `skipped_bad` (measured on the host folder 2026-11-18: 15 skipped_bad, 0 listed).

## The card (every word composed from constants + sidecar NUMBERS)
`file, sub, src (…/winners/video/<sub>/<file>), symbol, kind (from the FOLDER), kind_text (single-day / multi-day),
date, label_date ("Thu 2026-11-12"), days, days_text (single: the day; multi: "A → B · N sessions"), close_gain_pct,
gain_text ("+120% on the close" / "+300% best close vs the day before" — U+2212 minus), high_pct (null when not finite),
high_text ("+180% high" / "+492% run high"), spike_print, spike_text ("⚠ high more than 2× the close — a spike print?",
only when spike_print is true), pick_text ("top N mover of its day (high under +100%)" for a today_top reel; "your
example — not a +100% run" for a forced multi-day reel), speed, speed_text, minutes, length_text`.

The headline is ALWAYS the close (`close_gain_pct`). The multi-day sidecars' legacy `gain_pct` is HIGH-based and is
never read. Sidecar free text (`label`, `ask`, `why`, `category`, the `forced` sentence) is never served.

Payload: `title, tab, state (no_folder / empty / ready), text, note (WINNERS_NOTE, built from GC.SA_BIG_RUNNER_PCT,
GC.SCAN_MIN_VOLUME, GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE), window, window_note, summary_text ("N videos · a single-day ·
b multi-day"), counts {videos, single_day, multi_day, skipped_window, skipped_bad, no_sidecar}, groups [{date, label,
videos}]` — groups by date DESC; inside a date by close gain DESC, then symbol, sub, file. NaN scrubbed (`_scrub`).

## Frontend
`lib/replays.ts`: `RP_WINNERS_PATH`, `RP_WINNERS_PARAM` (`winners`), `RP_WINNERS_TITLE` (== backend `WINNERS_TITLE`),
the payload types, `rpWinnerSrc` (only `…/winners/video/` srcs), `rpWinnersParams` (keeps `tab` / `date`).
`components/ReplaysPastWinners.tsx`: the collapsed header button (the one FE word), the lazy GET, states loading /
failed (`FETCH_FAILED`) / no_folder · empty (served text) / ready (served note, window note, summary, per-date served
label, one text row per card: ticker + served chips + ▶). Exactly one video element (`controls preload="metadata"
playsInline`; never autoplay / muted / poster / download) under the tapped row. `ReplaysBoard.tsx` mounts the section
AFTER `.rp-board` in every state, so the board's one GET and its text are unchanged. `styles/replays.css`: `.rpw-*`
rows wrap, `min-width: 0` on every flex child (430 px).

## Tests
- `backend/tests/test_replays_winners_2026_11_18.py` (103).
- `frontend/src/lib/replays.winners.test.ts`, `src/components/ReplaysPastWinners.test.tsx`,
  `src/components/ReplaysPastWinners.phone.test.tsx`.

## HIS CALL (defaults built; nothing decided as a rule)
1. Winner = the day's HIGH ≥ +100% (`GC.SA_BIG_RUNNER_PCT`) over the prior close — or on the CLOSE?
2. Floors reused from GG's scanner: volume ≥ `SCAN_MIN_VOLUME`, prior close in [`SCAN_MIN_PRICE`, `SCAN_MAX_PRICE`].
3. `WINNERS_CAP = 480` and `TODAY_TOP_N = 5` are MINE.
4. Spike flag = high > 2 × that day's close (it also flags real fades).
5. Placement: bottom of 🎬 Replays, collapsed, text rows, one video at a time, no paging.
6. The 10 phone copies in `videos/multiday/phone/` are not listed.
