# 🏆 past-winner chip → that win's replay, at the peak minute (2026-11-22)

Ajay 2026-11-22, verbatim: **"New feature when I click on this past winner tag take me to that video so change the date
and focus me on that video at that. time"** then **"past winner 11-18 +57%"** (with a screenshot of a 🎬 Replays day
card: VWAV · 2026-11-20 · Reversal Squeeze · 5-min · L −1R · 45x · 21 min, chip "🏆 past winner 11-18 +57%").

**Navigation only.** No gate, push, rule, label, rank or ordering changes. Owner-only stays owner-only (no new route;
`require_primary_admin` on all four routes untouched). No reel is re-rendered — the renderer and the reels under
`eod-audits/replays/` are read, never written. **UNMEASURED:** nothing here is a number to trade on; the 🏆 list stays
"hand-picked winners (survivorship): descriptive, UNMEASURED, not a signal" (`constants.py:76-79`).

Spec: scratchpad `pwjump/spec.md` (revision 2). Earlier 🏆 work: `replays_past_winners_2026_11_18.md`.

## Where the reel lives
- The chip's target is NOT in a day view. `videos/2026-11-18/` holds no VWAV reel; the win is
  `videos/winners/2026-11-18_VWAV_45x.mp4`, listed only in the 🏆 Past winners section (one row per stock, collapsed,
  at the bottom of 🎬 Replays): `store.winners_payload` / `store.winner_rows`, FE `ReplaysPastWinners.tsx` (`StockRow`,
  `Row`, the ONE `<video>`).
- The chip entry already names its reel: `_PW_SERVED = ("day","kind","close_gain_pct","file","sub")` + `text`
  (`store.past_wins_before`). Live read 2026-11-22, `?date=2026-11-20`, VWAV card →
  `{"day":"2026-11-18","kind":"single_day","close_gain_pct":57.07…,"file":"2026-11-18_VWAV_45x.mp4","sub":"winners","text":"🏆 past winner 11-18 +57%"}`.
  The entry gains NO key.
- A chip exists only for a currently listed 🏆 reel (the index is built from the accepted cards of `read_winner_sub`).
  A removed mp4 moves the folder key → the chip is gone at the next GET. The only "missing target" left is a stale
  open page.
- A single-day win inside a listed multi-day run is already served as the RUN (`_one_per_run`): `sub == "multiday"`,
  `file` = the run's reel. The jump lands on the multi-day reel with no new server rule.
- "Only wins that ENDED before the card's day" (`w["day"] < day`) is unchanged.

## What the chip does now
Each day-card 🏆 chip is a real link (`<a href>`, keyboard reachable, ⌘-click / middle-click = new tab) to

`?tab=replays[&date=<win day>]&winners=1&sym=<SYM>&reel=<sub>/<file>`

Landing: the 🏆 section opens, the stock's row opens, THAT reel becomes the one mounted video, its row is scrolled to
(under the sticky bars, once the board has left `loading`) and outlined, and the video opens at the reel's SERVED
`seek_s`, paused. Under it, the served `seek_text`. The app never calls `play()` or `pause()`; no autoplay, never muted
(the existing `<video>` contract).

- `date` moves to the win's session ONLY when that session is in the served `dates` (it has day replays). Otherwise
  `date` stays exactly as it was.
- `reel` is read only when it is exactly `<sub>/<file>` with `sub` ∈ `winners` / `multiday` and `file` matching the
  backend `FILE_RE`. The reel is found only inside the row whose served symbol (trimmed + upper-cased, the `sym` normal
  form) equals `sym`, and only the video whose `<sub>/<file>` equals `reel` — never another row, never another reel.
- A row his saved 🏆 setup filter would hide is shown for the visit (filter set to All in state only); the saved pick
  in `localStorage` (`rp_winners_setup`) is NOT overwritten.
- A row he closed by hand reopens on every jump to it.
- "+N more" and the "🏆 won before" chips inside a 🏆 row stay text.
- The seek second is never typed in the URL: it always comes from the served card of the reel the URL names.

FE pieces: `lib/replays.ts` (`RP_REEL_PARAM` `reel`, `RP_CARD_PARAM` `card`, `rpReelKey`, `rpPastWinItems`,
`rpJumpParams`, `rpCardKey`, `rpOriginParams`, `rpCardParam`, `rpJumpReel`, `rpJumpKey`, `rpFindReel`, `rpSeekSeconds`,
`rpSeekSrc`, `rpPlainClick`; `rpDateParams` now also drops `card`), NEW `hooks/useRpFocus.ts` (scroll + focus once per
key), `ReplaysBoard.tsx` (chips → links, origin mark, origin focus, `jumpN` click counter), `ReplaysPastWinners.tsx`
(the jump effect, the seek, the missing-target line), `styles/replays.css` (link underline, outline-only focus,
`scroll-margin-top` under the sticky bars, `.rpw-seek` wraps at 430 px). No clock arithmetic in the FE.

## URL and history — four worked examples
The board's other URL writes stay `replace: true`. The chip click does TWO things in one render: a REPLACE of the
current entry with the origin mark (`card=<served date>/<file>`, and `reel` removed — the origin entry is the card),
then the Link's own PUSH of the target. A ⌘ / middle click does neither (the browser opens the target in a new tab;
the origin tab is untouched). `/` is written `%2F` in the URL.

**1. VWAV — the date switches.** Origin `/chart-maps?tab=replays&date=2026-11-20`. Click "🏆 past winner 11-18 +57%" →
1. replace: `…?tab=replays&date=2026-11-20&card=2026-11-20%2FVWAV_reversal_squeeze_potential_45x.mp4`
2. push: `…?tab=replays&date=2026-11-18&winners=1&sym=VWAV&reel=winners%2F2026-11-18_VWAV_45x.mp4`

Landing: board GET `?date=2026-11-18`; ONE 🏆 GET; VWAV row open; video
`src = …/winners/video/winners/2026-11-18_VWAV_45x.mp4#t=952.05`; row outlined and scrolled to;
"⏩ opens at the peak minute, 15:54 ET" under it; paused.
Back → URL 1 → the 11-20 board → the VWAV card scrolled to and outlined; the 🏆 section closed.
From the tab's normal URL (`?tab=replays`, no `date`): URL 1 is `?tab=replays&card=2026-11-20%2F…` — the SERVED date
(the payload's, never the URL param) — and Back focuses the card the same way.

**2. AKAN — the date does not switch; the same chip twice.** "🏆 past winner 05-01 +1657% multi-day" →
`reel=multiday%2F2026-04-22_AKAN_45x.mp4`, `date` unchanged (05-01 has no day replays); the multi-day reel opens at the
start with "no peak time on this replay — it opens at the start". He scrolls back up and taps the SAME chip: the
history index does not move, the URL is identical, the click counter `jumpN` goes 1 → 2 → the row is scrolled to
again, a row he closed reopens, the video is the mounted one again (a reel with a served second is put back at it).
One Back still returns to the origin card.

**3. Chained.** After the AKAN jump he taps the VWAV chip: the AKAN entry is replaced with
`…&winners=1&sym=AKAN&card=2026-11-20%2FVWAV_…` (`reel` gone), then the VWAV target is pushed.
Back #1 → that entry: ONLY the VWAV card is outlined (no 🏆 row focus).
Back #2 → `?tab=replays&date=2026-11-20&card=2026-11-20%2FAKAN_…` → the AKAN card.

**4. After Back, another session.** Picking a session in the select writes `date` and drops `card` (`rpDateParams`);
coming back shows no outline and scrolls nothing. A date pick keeps `reel`, so a playing video is not reloaded and
nothing re-scrolls.

Why a click counter and not history state: every other URL write on this tab sets `location.state = null`, so a
nonce in the Link's state would change on a date pick and re-scroll / re-seek a playing video. The jump's identity is
`<reel>|<jumpN>` (`rpJumpKey`).

## Clock → video second (derived from the renderer, verified on real frames)
- Every 🏆 reel (single-day AND multi-day) is rendered by ONE schedule: `eod-audits/replays/replay_winners.py:166-169`
  (`RM.Plan(…)`, `RM.render(…)`) → `replay_multiday.py:173-183` `Plan.times`: per session `step = speed / fps`,
  `n = int((t1 - t0) // step)`, frame j (0-based) shows clock `t0 + (j + 1) * step`, plus one frame at `t1` only when
  the last step lands before it (`out[-1][1] < t1`). `t0, t1` = `replay_multiday.py:45`
  `DAY_T0, DAY_T1 = dtime(4, 0), dtime(20, 0)`.
- A minute enters a frame only once the frame clock is PAST its start: `replay_multiday.py:196`
  `hi = bisect.bisect_left(self.m_t, t)` ("minutes that STARTED before t"). A frame whose clock EQUALS the minute start
  does not include it.
- Inside a started minute the 5-min candle gets a PARTIAL path of that minute (`replay_multiday.py:197-201`,
  `RV.minute_path_partial`), while the "high so far" TEXT takes the minute's full high at once (`:213-218`). **So the
  frame the video opens on shows the peak in the "high so far" text while the candle is still forming; the candle
  reaches that high within the same minute.**
- No intro, no title frames. The only extra frames are an END hold written after the session loop:
  `replay_multiday.py:408-419` `render`, `hold = max(1, int(round(RG.HOLD_MS / 1000 * p.fps)))`;
  `replay_gif.py:40` `HOLD_MS = 3000`; `replay_video.py:49` `FPS = 10`; `replay_multiday.py:42` `SPEED = 45.0`.
- Encode keeps the frame clock: `run.sh:10` (`-movflags +faststart`), `run.sh:36/52/72` (`-framerate "$fps"`).
  ffprobe `winners/2026-11-18_VWAV_45x.mp4`: 960x540, 10 fps, 12,830 frames, 1283.000 s, start 0.000.
  `multiday/2026-11-12_GP_45x.mp4`: 64,030 frames, 6403.000 s.
- So frame n is on screen from `n / fps` to `(n + 1) / fps` and shows clock `04:00 + (n + 1)·step`. The first frame
  inside the minute that starts `c` seconds after 04:00 is the first n with `(n + 1)·step > c`.
  **Served second = the MIDDLE of that frame: `seek_s = (n + 0.5) / fps`.** Any player rounding lands on frame n or
  n + 1, both inside the peak minute; the exact boundary `n / fps` could round back to the pre-peak frame.
- `peak_t` = the START minute (ET) of the first 1-minute bar whose high is the highest 09:30–20:00 high:
  `eod-audits/research/2026-11-22_winner_setup_labels/label_winners.py:377-386` (`peak_of`), written to `timing.peak_t`.

**Verified on real frames (ffmpeg, read-only, frames taken by INDEX, 2026-11-22):**

| reel | peak_t | frame n | on screen (s) | **seek_s served** | what that frame shows |
|---|---|---|---|---|---|
| winners/2026-11-18_VWAV_45x.mp4 | 15:54 | 9520 | 952.0 – 952.1 | **952.05** | clock 15:54:04 ET; text "high so far 0.8400 (+69.0%)" = sidecar `high` 0.84; candle still forming ("now 0.7942", wick near 0.82) — it reaches the high within the minute (at most ~1.3 s of video later) |
| same, frame 9519 | | 9519 | 951.9 – 952.0 | — | clock 15:54:00 ET, high so far 0.8217 — the peak minute not started |
| winners/2026-06-25_NEXR_45x.mp4 | 17:13 | 10573 | 1057.3 – 1057.4 | **1057.35** | clock 17:13:03 ET, after-hours peak |
| winners/2026-11-13_AKAN_45x.mp4 | 19:59 | 12786 | 1278.6 – 1278.7 | 1278.65 | (computed) last minute, still before the 1280 s end hold |
| winners/2026-08-06_ENSC_45x.mp4 | 09:49 | 4653 | 465.3 – 465.4 | 465.35 | (computed) first-hour peak |
| multiday/2026-11-12_GP_45x.mp4 | — | 12800 | 1280.0 | — | 04:00:04 ET, "run day 1 of 4": a session boundary = 1,280 s |
| VWAV frame 0 | | 0 | 0.0 | — | 04:00:04 ET — no intro |

The ask's arithmetic (714 min × 60 / 45 ≈ 952 s of 1283 s) is confirmed: frame 9520 starts at 952.0 s.
`ffmpeg -ss X` returns the first frame AT OR AFTER X (`-ss 952.05` → 15:54:09, the next frame), so it is not a model
of what a browser shows at `currentTime = X`: frames are proved by index, and the browser frame is a check on his
surface, not a claim here. **The seek on a real iPhone (Safari) is not proven by anything above — he is the check.**

All 317 real sidecars (read-only scan): speed 45.0 / fps 10 on all; `frames == sessions × 12800 + 30` on all;
`timing.peak_t` on every single-day reel and on no multi-day reel; served seconds 457.35 – 1278.65 s, all before the
1280 s end hold.

Other schedules (so a renderer change never seeks wrong): plain `int(c // step)` sits one frame early on many
schedules (36x / 10 fps: 09:30 → frame 5499, the renderer first shows that minute on 5500). The helper uses a BOUNDED
correction (two steps up, two down, never a `while`) plus a 1e-6 s float tolerance (`C.SEEK_EPS` — the renderer adds
the frame offset to an epoch ≈ 1.8e9, where a float cannot hold a smaller excess) and a final bracket check, else
None. Checked against the renderer's own arithmetic across 254 schedules: no minute off.

## Served keys and words (backend)
`backend/chart_maps/replays/constants.py`, appended block (nothing existing changes):
`WINDOW_T0`, `WINDOW_T1` (sliced from `FULL_DAY_WINDOW`, never retyped: "04:00", "20:00"), `SEEK_SESSION_SEC` (57600,
derived from them), `SEEK_HOLD_SEC = 3.0` (== the renderer's `HOLD_MS / 1000`; a test pins the source), `SEEK_EPS`
(1e-6 s), and the three sentences below.

`backend/chart_maps/replays/store.py`, four pure helpers beside the sidecar label read: `_seek_step`,
`session_frames`, `_seek_frame`, `seek_seconds`. `winner_card` gains two keys at the end; `winners_payload` gains one.

| where | key | VWAV 11-18 | otherwise |
|---|---|---|---|
| 🏆 card | `seek_s` (float or null) | `952.05` | `null` |
| 🏆 card | `seek_text` (str) | "⏩ opens at the peak minute, 15:54 ET" | "no peak time on this replay — it opens at the start" |
| 🏆 payload (all three states) | `jump_missing_text` | "That replay is no longer listed." | same |

The FE prints only these served sentences, plus the existing `FETCH_FAILED` line.

## None rules and the never-raise rule
`seek_seconds(side, kind)` returns None unless ALL hold, in this order:
1. `kind == "single_day"` (the labeller writes no multi-day peak; a stray `timing` on a multi-day sidecar is ignored).
2. The ONE existing label rule (`_timing_fields`) accepts the `timing` (known bucket, `HH:MM` peak, bucket agrees with
   the minute).
3. `window == FULL_DAY_WINDOW`.
4. `speed` finite > 0 and `fps` an int > 0 (bool refused) with a finite step > 0; `frames` an int > 0 (bool refused);
   `days` a list of one session.
5. `frames == session_frames(speed, fps) + hold` — the reel was made by the schedule this mapping was derived from. An
   intro, another hold, another window → None.
6. The peak minute lies inside 04:00–20:00.
7. A frame index is proved (`_seek_frame`) and lies inside the session.

Return `round((n + 0.5) / fps, 3)`. Never a guessed time.

**Never raises.** `C.CARD_ERRORS` does not hold `ZeroDivisionError` / `OverflowError`, so an arithmetic raise inside
`winner_card` would be a 500 on `/winners` AND on the day GET (the past-winner index reads the same cards). Both public
helpers (`session_frames`, `seek_seconds`) end in `except (ArithmeticError,) + C.CARD_ERRORS: return None`; `C.CARD_ERRORS`
itself is not widened. Absurd inputs (`speed` 5e-324 / 1e-300, `fps` 10 ** 400, `frames` 10 ** 400) give a LISTED card
with `seek_s` null — never `skipped_bad`, never a hang (no unbounded loop anywhere).

FE: `rpSeekSeconds` takes the served second only when it is a finite number > 0; anything else → the video opens at the
start. The seek is the media fragment `#t=<seek_s>` on the `src` (iOS ignores `currentTime` before metadata), a
`loadedmetadata` fallback that writes `currentTime` only when it is more than 0.5 s away, and on a repeat jump one
write of `currentTime` inside `try`. Every other row's `src` is exactly today's.

Missing target (a stale page, a wrong `sym`, a reel no longer listed): the served "That replay is no longer listed."
prints as the first line of the 🏆 body and is scrolled to; no video is mounted, nothing seeks; the `sym` row still opens
by today's rule. The 🏆 GET failing with a `reel` in the URL: the existing `FETCH_FAILED` line is scrolled to. Deploy
skew: new FE + old api → the link works, the video opens at the start with no line, a missing target prints nothing;
old FE + new api → the extra keys are ignored.

## What is NOT changed
`store.payload` (the day listing and its golden), `video_payload`, `past_winner_index`, `past_wins_before`,
`_PW_SERVED` (the past_winner entry key set), `_tag_day_groups`, `winner_rows`, every order key, `api.py` (still four
routes, both gates), `C.CARD_ERRORS`, `read_winner_sub`'s cache key, the accept rules, the `<video>` attribute
contracts (`controls preload="metadata" playsInline`; never autoplay / muted / poster / download), the chip size and
the chip row layout. No reel is re-rendered. No push, no gate, no rank, nothing on 🚩 Gajjala's tab.

## Tests
- `backend/tests/test_replays_past_winner_jump_2026_11_22.py` (new); re-pin of the 🏆 card exact dict in
  `backend/tests/test_replays_winners_2026_11_18.py`.
- `frontend/src/lib/replays.jump.test.ts`, `frontend/src/hooks/useRpFocus.test.tsx`,
  `frontend/src/components/ReplaysPastWinJump.test.tsx`, `frontend/src/components/ReplaysPastWinJump.phone.test.tsx`
  (new); re-pins in `ReplaysPastWinTag.test.tsx` (the chips are anchors) and `ReplaysPastWinners.test.tsx` (the three
  section mounts).

## HIS CALL (each built to the default named; nothing decided as a rule)
1. **Seek point.** Default: the first frame inside the peak minute (VWAV 952.05 s, reel clock 15:54:04 — the "high so
   far" text already reads +69.0% while the candle is still forming; the candle reaches that high within the next
   ~1.3 s of video). Or the moment the peak minute's candle is complete (VWAV 953.35 s), or N minutes before the peak so
   he watches the move — he names it.
2. **After the seek.** Default: paused, he taps play (no autoplay, never muted — the existing contract). Or autoplay
   muted. A second tap on the same chip scrolls back and puts the video at the peak again; the app never presses play
   or pause.
3. **"at that time".** Built as "open at the peak". If he meant only "the video from that day" → open at the start.
4. **Date switch.** Default: the session picker moves to the win's day only when that day has day replays (4 of the 12
   chips on 11-20 — VWAV 11-18 is one); otherwise it stays. Or always move it (the picker then shows a session with
   nothing to list).
5. **Multi-day reels** carry no labelled peak → open at the start with the served words. Or open at the start of the
   run's last session ((sessions − 1) × 1,280 s) — a new semantic, his word.
6. **Other chips.** "+N more" and the "🏆 won before" chips inside a 🏆 row stay text. Make them links too?
7. **Where the reel lives.** It stays in the 🏆 Past winners section (opened and scrolled to). A "🏆 winners of this
   session" group inside the day view is a listing change — not built.
8. **Saved filter.** A jump to a row his saved 🏆 filter hides shows All for that visit and keeps his saved pick.
9. **Words are mine:** "⏩ opens at the peak minute, 15:54 ET" · "no peak time on this replay — it opens at the start" ·
   "That replay is no longer listed." Also mine, with no market meaning: the 1e-6 s float tolerance and the half-frame
   offset.
10. **Tap target on the phone.** The chip is about 18 px tall (0.72 rem text) — the size of every chip on the card
    today; built at that size. A bigger tap area changes the chip row on a dense card — his word.
