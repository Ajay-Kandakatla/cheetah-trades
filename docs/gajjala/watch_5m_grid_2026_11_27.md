# 👀 Gajjala's Watch — 5-min tiles, more names per screen, a frames menu, a clean volume pane (2026-11-27)

Spec: `watch5m` rev 2 (branch `feat/watch-5m-grid-2026-11-27`). Frontend only. Display only: no alert, rule, gate,
threshold or push changed. Paper only.

> **Status: built 2026-11-27 on `feat/watch-5m-grid-2026-11-27`** — the board (`frontend/src/components/GajjalaWatchBoard.tsx`)
> mounts the new props; it is live once that branch is deployed. Before it, Watch tiles and the Watch's ⤢ drew as on
> 11-25 (three charts, the average-volume line on).

## His words (Ajay 2026-11-27 ~02:45–03:00 ET, in order, verbatim)

1. (screenshot: thinkorswim "Day Momentum Grid", 3 columns × 2 rows, six charts)
   > "This is how I want our watch list to be designed.. So I can look at 5 mins charts like 6 in one go..."
2. > "Only 5 mins may be give me option in our existing Watch charts to disable all 15 and all 1 min or on the chart itself.. I wanna see 1 min and 15 min I will expand individuals directly"
3. > "But I can add more and scroll more too If i want to thats the plan"
4. > "its not about the visual to look like but the intention is for me to look at more on my watch at a one point of time"
5. (screenshot: our ⤢ view of BTDR, 15-min / 5-min / 1-min stacked, each with a volume pane)
   > "Also on the expanded view I need 5 mins by default to look in detail and not sure what the line on volume is its blocking my story.."
   > "Give me a drop down or multi select like button to toggle 1 mins and 15 mins 5 mins by default.."

The goal is his #4: more Watch names visible at one time. In ⤢: one big 5-min chart by default.

Source of each item: all five are Ajay's own messages in the main session on 2026-11-27; the full build (grid asks 1–4
and ask 5) was confirmed for this branch.

## Before / after

| | before (11-25) | after (11-27) |
|---|---|---|
| Board tile | 1-min on top + 5-min / 15-min pair (three charts) | **(grid)** the 5-min chart alone (one chart) |
| Per-screen pick | 1 · 2 · 4 · 9 (columns × row height) | **(grid)** 6 · 9 · 12 · 16 · 20 while one frame is on; 1 · 2 · 4 · 9 while two or three are on |
| Default per screen | 2 | **(grid)** 6 (3 columns × 2 rows) |
| Scroll | every name in one scroll | unchanged — every name in one scroll |
| ⤢ (the Watch's) | 15-min / 5-min / 1-min stacked | one full-height 5-min chart; the frames menu adds the others back (order stays 15 / 5 / 1) |
| Line across the volume bars | the 50-bar average volume, on every Watch chart | off on Watch tiles and in ⤢; opt-in in the menu |
| Frames control | none | a dropdown button (multi-select) on the board head **(grid)** and in the ⤢ head |
| Phone | three charts per tile, one column | **(grid)** one 5-min chart per tile, one column, the menu is there, no per-screen pick |

## The frames menu

- One button, `5-min ▾` by default (its text = the served labels of the frames on, joined ` · `). It opens a small list
  of check boxes: one per served frame (1-min, 5-min, 15-min — the server's own labels), then "Average volume line".
- Two menus, two separate choices: the board's (every tile) **(grid)** and ⤢'s (`Frames in this view`). A tick in one
  never changes the other. ⤢'s choice lives in the board, so ◀ ▶ and close / reopen keep it.
- At least one frame always stays on: the last one on is greyed with the title "At least one frame stays on".
- Closes on the button, a tap outside, or Esc. Esc with the menu open closes the menu only; a second Esc closes ⤢.
- A tick never re-fetches, never posts, never writes the link, never stamps the pick time, never clears the chip filter.
- It is a dropdown, not three always-visible buttons — his "drop down or multi select like button". Both pictures are
  shown to him (HIS CALL 8).

## The density rule (grid)

- **Exactly one frame on** → one-chart tiles and the dense picks 6 · 9 · 12 · 16 · 20
  (6 = 3 × 2, 9 = 3 × 3, 12 = 4 × 3, 16 = 4 × 4, 20 = 5 × 4). **Two or three frames on** → today's tile and today's
  1 · 2 · 4 · 9, unchanged.
- **A pick is offered only when its whole count fits in this window with every tile at or above BOTH floors.** No new
  number was invented; the two floors are existing house numbers reused by name:
  - width: `GGW_DENSE_MIN_COL_PX` = 420 px, pinned EQUAL (by a test that reads the sheet) to the Chart Maps card floor
    `.cm-grid { minmax(420px, 1fr) }` in `frontend/src/styles.css`;
  - height: `GGW_FIT_ROW_MIN_PX` = 200 px (`frontend/src/lib/gajjalaWatch.ts`), the Watch's own tile-row floor
    ("below it the page scrolls instead of the charts shrinking further").
- The lit number is always the number drawn: the columns are the largest count at or under both the pick's own columns
  and what the width allows that divides the pick exactly (9 at 2 columns is NOT offered — never 2 × 5 = 10 under a lit 9).
- A pick the window cannot show whole is **greyed**, title "N per screen — Not enough room in this window". It is never
  removed (the head's width must not follow the offer, or the head height and the offer could chase each other).
- A stored pick larger than the window allows is shown clamped (the densest offered pick below it is lit) and is never
  overwritten — moving back to the big monitor restores it.
- **Under the smallest pick** (no pick fits whole) no button is lit, all five are greyed, and the board draws what fits
  (`data-layout="fit"`: columns = what the width allows, at most 3; rows = what the height allows, at most enough for 6).
- jsdom / a grid not laid out yet → no cap, all five offered.

## What a 5-min-only tile carries, what moved, what left the face (grid)

**Kept on the face:** SYM, 🎯, setup chip, float, 🚫 chip, 🩳 / 🔒 / ⛔, row text, stamps, 🔔 rang chips, the ONE time
line, the 5-min chart with everything it draws today (9 / 21 EMA, VWAP, daily zones, marks, `now` line, volume columns),
the 5-min caption (9/21 dot, label · K5, held, 📶 base count, 9/21 sentence chip), ⋯ ⤢ ✕.

**OFF the board face while 1-min / 15-min are unticked** (his ask; one tick on the board, or ⤢ + a tick, brings each
back; nothing is deleted and the server-side reads are untouched):
- the 1-min chart and its caption: the 1-min K5 ✓ / ✕ label, the 1-min 9/21 dot and sentence chip, the 1-min held chip,
  and the 1-min 🔕 "not sent — the watch push is off" chip (served by `backend/chart_maps/gajjala_watch/payload.py`);
- the 15-min chart and its caption: the 15-min K5 label, its 9/21 dot and sentence chip, its held chip;
- the average-volume line on every Watch tile and in ⤢ (see the next section for where it still draws).

**Moved** (desktop with a mouse, dense tile only; nothing leaves the page):
- The tile head is one line; a chip that does not fit is cut with "…" (full words: its hover, the ⋯ drawer, ⤢).
- 🚫 mark · ▶ Rules · TV ↗ · Yahoo ↗ show on tile hover or keyboard focus; ⋯ ⤢ ✕ always show. In ⤢ all of them show as
  today.

**Phone and touch:** nothing trimmed.

## The line on the volume pane (ask 5)

It is the **50-bar average-volume line** (`path.pc-vol-sma`, drawn by `frontend/src/components/PatternChart.tsx` in
`VOLUME_SMA_COLOR`, grey-white, 1 px), fed on Watch frames by the served `vol_avg` — his own 2026-10-13 call ("a thin
50-bar simple average of volume — on EVERY chart", `frontend/src/lib/volumePane.ts`). Because the 09:30 column dwarfs
the rest, the average sits just above the floor and runs through every small column — that is the line across his story.

- Not the cause: the dashed `now` line (price pane only), the hairline above the pane, zones or VWAP (price pane).
- **With the build:** off on Watch tiles and in the Watch's ⤢. Tick "Average volume line" in either menu to bring it back (one
  choice, shared by the board and ⤢). With it off, the pane's scale top is the tallest bar (never lifted by a served
  average), so on a frame where the average sat above every bar the columns now draw taller than before.
- **Where the line still draws (unchanged):** the 📅 runner chart, also when opened from the Watch roster; Chart Maps
  cards; the 🚩 / 🧪 card grid ("Watch layout") tiles and the 🚩 / 🧪 card click ⤢; the zone chart, the live candles
  chart and the intraday chart.

## Storage (per browser)

| key | holds | default | junk / no storage |
|---|---|---|---|
| `ggw.frames` | the board's frames, a comma list in served order (e.g. `5m` or `1m,5m,15m`) | `5m` | `5m` |
| `ggw.stretchFrames` | the Watch ⤢ frames, same format | `5m` | `5m` |
| `ggw.volAvg` | `1` = average volume line on; removed when off | off | off |
| `ggw.dense` | the dense pick: 6 / 9 / 12 / 16 / 20 | 6 | 6 |

- `*` (`GGW_FRAMES_EVERY`) is a real stored value meaning "every served frame": it shows every frame the server sends,
  including one added later, and is never dense. No menu writes it; the first tick replaces it with a concrete list.
- A stored frame the server does not serve (e.g. `3m`) is never shown as ticked-but-missing: the ticks, the toggle and
  the dense rule all start from the served frames. If nothing stored is served, the 5-min frame shows (or every served
  frame when there is no 5-min) — never a blank tile.
- Every read and write is inside try/catch; storage that is missing or throws gives the defaults.

## The live rule (unchanged data path)

- **Every served frame keeps folding its live candle from page open, shown or not.** A tick therefore never restarts a
  candle: a 15-min or 1-min frame ticked on mid-bar appears with the same open, high, low, close and volume it would
  have had if it was on all along.
- There is **no per-frame subscription** on the wire: one bus subscription and one live-interest POST of symbols (no
  frame in it), exactly as before. Nothing is subscribed or unsubscribed by a tick. The POST body is byte-identical.
- A frame that is off costs no draw (the render is per chart); its fold is the same small reduce as before.
- Today's one remaining gap is unchanged: a PAGE opened mid-candle starts its forming candle at that moment
  (`GGW_SEED_FORMING` stays false, contract-pinned; his open call).
- The 1-min 9/21 cross read is server-side on stored bars; the frontend cannot affect it. Its push stays muted by his
  11-24 word.

## The link rule

- `per=` in the link keeps ONE meaning: the 3-frame layout (1 · 2 · 4 · 9), written exactly as before. His open tabs and
  shared links behave as before.
- The dense pick lives in this browser only (`ggw.dense`); it never reaches the link. A dense-pick tap leaves the whole
  query string unchanged. An incoming `per=9` stays `per=9` and shows 9 per screen when all three frames are ticked
  on. An incoming `per=12` is junk for the layout exactly as before (rewritten to `per=2`), never read as a dense pick.
- The frames choice is per browser too; no `tf=` / `dense=` param (not asked; HIS CALL 9).

## What did NOT change

- Backend: `FRAMES` (1m / 5m / 15m) and `PUSH_FRAMES = ("1m",)` in `backend/chart_maps/gajjala_watch/constants.py`,
  the symbol cap, the add flow, the payload (all three frames are still served), every push and every alert gate.
- `GGW_STRETCH_ORDER = ['15m', '5m', '1m']` — ⤢ still stacks 15 / 5 / 1 among the frames on.
- `GGW_LAYOUTS` / 1 · 2 · 4 · 9 and `parseGgwLayout` (shared with the card grid).
- **The 🚩 / 🧪 card click ⤢ and the card "Watch layout" grid:** byte-identical — three charts with the average line,
  no menu. Every new prop is opt-in; those callers pass none. His screenshot is the Watch's ⤢ (▶ Rules, ⋯, "added
  11:23"), not the card's (HIS CALL 1).
- `PatternChart` with no `volAvg` prop draws exactly as today on every other surface.
- The live data path (above) and the link's `per=` (above).

## Code

- New, pure: `frontend/src/lib/ggwFrames.ts` (frames choice, dense picks and shape, the floors by name, storage,
  wording). Hook: `frontend/src/hooks/useGgwFrames.tsx` (`useGgwFrames`, `useGgwGridBox` — the grid's width, gaps and
  free height, read with the same expression as `useGgwFitRows`). Menu: `frontend/src/components/GgwFramesMenu.tsx`.
  Every new CSS rule: `frontend/src/styles/ggwFrames.css` (nothing added to `gajjalaWatch.css`).
- Opt-in props: `PatternChart` `volAvg`; `Tile` `frames` / `one` / `volAvg` / `framesMenu`; `GgwStretch` `frames` /
  `volAvg` / `framesMenu`; `GgwLayoutPick` `options` / `disabled` / `disabledTitle`. Absent → today's DOM.
- Board: `frontend/src/components/GajjalaWatchBoard.tsx` mounts them (built 2026-11-27). Its live fold and its link
  write are unchanged.

## Legacy test seam

Tests written before 11-27 pin the 3-frame tile, 1 · 2 · 4 · 9 and the average line. They keep pinning that mode with
ONE line as the first line of the file (the `frontend/src/test/ggCardWatchOff.ts` precedent):

```ts
vi.mock('../lib/ggwFrames', async (orig) => (await import('../test/ggwFramesLegacy')).ggwFramesLegacy(orig));
```

`frontend/src/test/ggwFramesLegacy.ts` makes the three readers return every served frame (the lib's own `*` token — no
frame list typed) and the average line on. It must be the bare `vi.mock` (an aliased `vi` is not hoisted and changes
nothing — measured). Never imported by app code, never a global setup. A legacy file still red WITH the seam is reported,
never fixed by editing an assertion. The default mode has its own tests:
`frontend/src/components/GajjalaWatchBoard.frames5m_2026_11_27.test.tsx` (S = ⤢ / volume / menu, G = grid), plus
`frontend/src/lib/ggwFrames.test.ts`, `frontend/src/hooks/useGgwFrames.test.tsx`,
`frontend/src/components/GgwFramesMenu.test.tsx`, `frontend/src/components/PatternChart.volAvgOff_2026_11_27.test.tsx`,
`frontend/src/components/GajjalaWatchTile.frames_2026_11_27.test.tsx`,
`frontend/src/components/GajjalaWatchLayout.options_2026_11_27.test.tsx`.

## Measurements (2026-11-27, ~04:30–05:00 ET, headless Chrome 158)

Harness: a scratch copy of the §5.2 harness of `watch_columns_scroll_2026_11_25.md` (scratchpad
`watch5m/preview/`: `vite.harness.config.mjs`, `cdp.mjs`, `measure.js`, `run_geo5.mjs`, `run_cost5.mjs`), serving
PRODUCTION builds (`vite build`) of BASE = `git archive 6a67007f frontend` and NEW = this branch. The stub Watch GET is
the harness's stored payload `A.json` — his real 43-row Watch GET of 2026-11-25 11:32 ET (the 11-25 harness file; not
an 11-23 payload). Upstream pointed at a closed port (`127.0.0.1:1`), never the live API; before any page opened:
`DELETE …/symbols/ZZZZ` 405, `POST …/gajjala-watch/live` 405, `POST /features/seen` 405, `/events` 204, on both builds.
NEW-dense = `ggw.dense` set in localStorage before the load (never through `per=`); NEW-all-frames =
`ggw.frames=1m,5m,15m` + `ggw.volAvg=1`. Run noise was defined before any NEW number: BASE is run twice at every
(viewport, pick); noise = |run 1 − run 2|; "matches BASE" = inside BASE's two-run range widened by the noise each side.

### Geometry — names visible per screen (whole tiles, board scrolled to its top) — MEASURED

| viewport | head height px (BASE / NEW-dense / NEW-all) | grid width × free height px | picks enabled (NEW) | densest enabled shape | after, default (6) | after, densest | before, default (2) | before, 9 |
|---|---|---|---|---|---|---|---|---|
| 1440×900 | 168 / 168 / 168 | 1360 × 732 | 6 · 9 | 3 × 3 | **6** | **9** | 2 | 9 |
| 1440×790 | 168 / 168 / 168 | 1360 × 622 | 6 | 3 × 2 | **6** | **6** | 2 | 6 (9 lit; rows clamp to 200 px) |
| 1920×1080 | 168 / 168 / 168 | 1840 × 912 | 6 · 9 · 12 · 16 | 4 × 4 | **6** | **16** | 2 | 9 |
| 1920×950 | 168 / 168 / 168 | 1840 × 782 | 6 · 9 · 12 | 4 × 3 | **6** | **12** | 2 | 9 |
| 2560×1440 | 108 / 108 / 139 | 2480 × 1332 | all five | 5 × 4 | **6** | **20** | 2 | 9 |
| 2560×1310 | 108 / 108 / 139 | 2480 × 1202 | all five | 5 × 4 | **6** | **20** | 2 | 9 |

- Every count above is a measured whole-tile count; BASE's two runs gave identical geometry at every cell.
- A stored pick bigger than the window allows was shown clamped (e.g. `ggw.dense=20` at 1440×900 lit 9 and drew 9).
- NEW-all-frames drew BASE's geometry at 1440 and 1920. At 2560 its head wraps to a second line (139 px vs 108: the
  1 · 2 · 4 · 9 pick plus the wider `1-min · 5-min · 15-min ▾` button), 31 px less chart height per screen than BASE;
  the whole-tile counts stayed the same (2 and 9).
- "More names at once" is the TILE count, not readability: whether he can read a 5-min chart at the densest pick is
  HIS CALL 2 / 3 (the boxes are below).

### The measured 5-min chart box (`.ggw-chartbox` of the first tile, width × height px) — MEASURED

| viewport | NEW 6 | NEW 9 | NEW 12 | NEW 16 | NEW 20 | BASE 5-min box at 2 | BASE 5-min box at 9 |
|---|---|---|---|---|---|---|---|
| 1440×900 | 421 × 270 | 421 × 146 | greyed | greyed | greyed | 321 × 251 | 206 × 29 |
| 1440×790 | 421 × 215 | greyed | greyed | greyed | greyed | 321 × 204 | 206 × 14 |
| 1920×1080 | 581 × 360 | 581 × 206 | 426 × 206 | 426 × 129 | greyed | 441 × 340 | 286 × 64 |
| 1920×950 | 581 × 295 | 581 × 162 | 426 × 162 | greyed | greyed | 441 × 284 | 286 × 46 |
| 2560×1440 | 794 × 570 | 794 × 346 | 586 × 346 | 586 × 234 | 462 × 234 | 601 × 520 | 393 × 124 |
| 2560×1310 | 794 × 505 | 794 × 302 | 586 × 302 | 586 × 201 | 462 × 201 | 601 × 464 | 393 × 106 |

The spec's "about 398 × 115 px at the floor" was arithmetic; the smallest measured enabled box is 426 × 129
(1920×1080 at 16). NEW tiles carry no `path.pc-vol-sma` (0 on every NEW-dense tile measured; 3 per BASE tile).

### Cost — longest main-thread task (ms); lines set before measuring: P1, P2 50 ms; P3–P5 100 ms; P6 reported

`0` = no task of 50 ms or more (the long-task floor). Picks: "2 / 6" = BASE and NEW-all at 2, NEW-dense at 6;
"9 / densest" = BASE and NEW-all at 9, NEW-dense at 9 (1440×900) or 20 (2560×1440).

| line | viewport · pick | BASE run 1 | BASE run 2 | noise | NEW-dense | NEW-all-frames | verdict |
|---|---|---|---|---|---|---|---|
| P1 live, 60 s | 1440×900 · 2 / 6 / 9 | — | — | — | — | — | **NOT MEASURED** (below) |
| P2 scroll top → bottom → top | 1440×900 · 2 / 6 | 0 | 0 | 0 | 0 | 0 | under; all-frames matches BASE |
| P2 | 1440×900 · 9 / 9 | 233 | 235 | 2 | 0 | 234 | NEW-dense under; all-frames matches BASE (BASE itself over, as on 11-25) |
| P2 | 2560×1440 · 2 / 6 | 57 | 56 | 1 | 0 | 59 | NEW-dense under; all-frames 1 ms outside BASE's band (55–58) |
| P2 | 2560×1440 · 9 / 20 | 346 | 332 | 14 | 0 | 374 | NEW-dense under; all-frames 14 ms outside BASE's band (318–360) |
| P3 pick switch | 1440×900 · 9 ↔ 2 / 9 ↔ 6 | 275 | 274 | 1 | 0 | 295 | NEW-dense under; all-frames 19 ms outside BASE's band (273–276) |
| P3 | 2560×1440 · 9 ↔ 2 / 20 ↔ 6 | 391 | 472 | 81 | 84 | 423 | NEW-dense under; all-frames matches BASE |
| P4 re-GET A → B | — | — | — | — | — | — | **NOT MEASURED** (time) |
| P5 GET 500 and back | — | — | — | — | — | — | **NOT MEASURED** (time) |
| P6 page load | 1440×900 · 2 / 6 | 433 | 422 | 11 | 64 | 389 | reported |
| P6 | 1440×900 · 9 / 9 | 400 | 414 | 14 | 0 | 435 | reported |
| P6 | 2560×1440 · 2 / 6 | 418 | 663 | 245 | 110 | 624 | reported |
| P6 | 2560×1440 · 9 / 20 | 634 | 630 | 4 | 110 | 645 | reported |
| BASE-vs-BASE noise row | as above | | | 0 – 245 | — | — | — |

- **Measured at 1440×900 and 2560×1440 only.** The other four viewports have geometry, no cost lines.
- **NEW-dense (the default) was under every measured line** (P2 0 ms at every pick measured; P3 0 and 84 ms).
- **NEW-all-frames is not shown to match BASE everywhere**: it is outside BASE's two-run band at 3 of 6 P2 / P3 cells
  (by 1, 14 and 19 ms). With two BASE runs the band is thin (P6 at 2560 alone moved 245 ms between BASE runs), so this
  is neither a shown slowdown nor a shown match. BASE itself is over P2 at 9 and P3 (as on 11-25).
- **P1 NOT MEASURED.** The synthetic per-second quote stream reached both builds (124 batches logged) but drew nothing:
  0 mutations of the first tile's 5-min chart in 60 s on BASE and on NEW. The stub's bars are 11-25's and the run was
  11-27 pre-market, so the live fold did not draw; 0 long tasks there is NOT a P1 reading. Re-run on a same-day payload.
- Discarded: a first pass of P2 (2560 rows) and P1 that ran two runners at once on one Chrome (overlap found from the
  output files); every number above is from a single-runner pass.

### Live check (C1) — NOT MEASURED in a browser

Not run in the harness (the live stream drew nothing, above). The rule is pinned in jsdom by test S5 of
`GajjalaWatchBoard.frames5m_2026_11_27.test.tsx` (⤢ on 5-min, three batches in one 15-min bucket, then tick 15 + 1 →
their forming candles equal a board that had every frame on from the start).

| step | 15-min forming `data-vol` | 15-min forming high | equals NEW-all-frames at the same batch? |
|---|---|---|---|
| NEW-dense, ⤢ on 5-min, N batches, then tick 15-min | not measured | not measured | not measured |
| untick + re-tick | not measured | not measured | not measured |

Not done here: the screenshots of §5.4 (board at 6 / densest, greyed picks, menu open, ⤢ on 5-min and with all three,
volume pane with and without the line, the dropdown-vs-buttons pair for HIS CALL 8, the 430 × 932 phone).

## HIS CALL (nothing below is decided for him)

1. **🚩 / 🧪 card click ⤢ — NOT built.** It keeps 15 / 5 / 1 and its average line (his 11-16 ask there was three
   charts). On his yes: the same menu and the same 5-min default there, on its OWN remembered choice.
2. **Default density 6** (his "6 in one go"). A denser default (9 / 12 / 16 / 20)? Which picks exist (25 = 5 × 5 would
   also fit at 2560×1440; a narrow window gets only 6 — add 8 / 10 for two columns?).
3. **The two floors** used for "readable": 200 px tall (`GGW_FIT_ROW_MIN_PX`) and 420 px wide. The 420 is pinned EQUAL to
   the Chart Maps card floor, so a later change to Chart Maps cards fails a Watch test and forces a Watch decision. The
   alternative — a Watch-only number — is a NEW number, his to name.
4. **Dense-tile chrome**: head on one line (chips cut with "…"), 🚫 mark · ▶ Rules · TV ↗ · Yahoo ↗ on hover only.
   Alternative: always visible (a second head line, about 24 px of chart).
5. **Average volume line**: off on Watch tiles and in ⤢, opt-in in the menu. His 10-13 call was "on every chart"; the
   surfaces listed above keep it. Remove it elsewhere too? Drop the opt-in?
6. **⤢ remembers its frames** (tick 1-min once and ⤢ opens with it next time). Alternative: ⤢ always opens on 5-min alone.
7. **5-min itself can be unticked** as long as another frame is on (e.g. 1-min-only tiles). Alternative: 5-min locked on.
8. **Dropdown vs always-visible toggle buttons.** Built: the dropdown, on the board and in ⤢ (two clicks per toggle).
   Three buttons are one click and the ⤢ head has the room. He is shown both pictures.
9. **Per browser, not in the link**: the frames AND the dense pick. A dense pick in the link = its own param, on his word.
10. **Two or three frames on** → the old tile and the old 1 · 2 · 4 · 9 picks, unchanged.
11. **Small windows**: a pick the window cannot show whole (at both floors) is greyed; under the smallest pick the board
    shows what fits and lights nothing. Alternative: let a pick shrink tiles below a floor.
12. **Payload**: the GET still serves all three frames (2.49 MB on 11-25); trimming unused bars is a later call.
13. Cost lines: NEW-dense was under every line measured; P1, P4, P5 and the C1 browser check are NOT measured yet;
    BASE (and the 3-frame mode) stay over P2 at 9 and P3, as on 11-25.
14. **Scope — settled 2026-11-27**: asks 1–4 (the grid) and ask 5 (⤢ / volume line / menu) are all his own messages;
    the full build ships.

## UNMEASURED

This is a display. No signal, entry, gate or push reads which frames are shown or the dense pick, and no study has
measured whether seeing more 5-min names at once helps a decision. Prior on any new signal from it: null.
