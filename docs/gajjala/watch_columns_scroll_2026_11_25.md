# 👀 Gajjala's Watch — "per screen" = columns, every tile in one scroll (2026-11-25)

> **2026-11-27 — built (frontend, branch `feat/watch-5m-grid-2026-11-27`).** Now, while exactly one frame is on (its default: the 5-min chart alone) the per-screen pick is 6 · 9 · 12 · 16 · 20, offered only when the whole count fits at both floors (`GGW_DENSE_MIN_COL_PX` = the `.cm-grid` 420 px, `GGW_FIT_ROW_MIN_PX`); two or three frames on → 1 · 2 · 4 · 9 exactly as here. `per=` still means this doc's layout; the dense pick is per browser. See [watch_5m_grid_2026_11_27.md](watch_5m_grid_2026_11_27.md).

Ajay 2026-11-25 ~11:30 ET, on the 👀 Gajjala's Watch tab (screenshot: per-screen pick `1 · 2 · 4 · 9` with 2 lit, pager
`▶ 1 / 21`, two tiles BTDR + EMBC showing), verbatim:

> "When I say 2 per screen I mean 2 columns do not remove other, I need other to be avtive while I scroll.
>
> Can you fix that instead of removing the other?"

Spec: `ggwcols` rev 2 (planner scratch, not in the repo). Branch `fix/gajjala-watch-columns-scroll-2026-11-25`.
Frontend only — no backend, push, gate, rule or threshold changed.

## Before / after (desktop)

| | Before | After |
|---|---|---|
| What the pick is | The PAGE SIZE: 2 per screen = 2 tiles shown, every other tile mounted but `hidden` | The GRID SHAPE only: columns + the fitted row height |
| Tiles on the board (his 43-row list, 2 per screen) | 2 shown, 41 hidden, 22 pages (`▶ 1 / 21`-style pager) | all 43 shown in ONE grid the window scrolls, 0 hidden |
| Ticker chips | lit = the names on the current page | every chip lit ("active" — his word, 11-19 / 11-22) |
| ◀ ▶ and the `n / m` counter | page the board | ◀ ▶ greyed (nothing to page), no counter |
| ← → keys | move a page (and cleared a chip filter) | scroll one screen row group under the pinned tab strip; nothing else |
| The link | `per`, `show`, `page` | `per`, `show` — `page=` is dropped on the first write (junk included) |
| Live render | only the tiles on the page drew live bars | every tile in or near the window draws live bars |

The phone is unchanged (it was already this unpaged state: one column, every unfolded tile shown, every chip lit,
◀ ▶ off, no counter), apart from the all-on toggle rule below.

## What he gets, per pick (desktop, N tiles, no chip filter)

Row counts are "about" on purpose: the scrolled numbers come from a geometry sketch with ASSUMED head heights, not his
screen. The real numbers go in the §5 results table below.

| pick | columns | at the board top | once the head has scrolled away |
|---|---|---|---|
| 1 | 1 | head + 1 row = one window | about 1.1–1.5 rows a window |
| 2 | 2 | head + 1 row | about 1.1–1.5 |
| 4 | 2 | head + 2 rows | about 2.2–3.0 |
| 9 | 3 | head + 3 rows | about 3.4–3.7 |

`N` tiles in the DOM, 0 `hidden`, every chip lit, ◀ ▶ greyed, no counter. Tile size is unchanged: rows still fit
"head + ticker row + N rows = one window at the board top" (`useGgwFitRows`, `ggwFitRowHeight`, floor `GGW_FIT_ROW_MIN_PX`).

## What stayed

- Chip filter results once a filter exists (a filtered grid still uses `ggwPickGrid`; one name alone fills the width).
- ⤢ full screen (the stretch view, its own key steps, always live).
- ✕ on a tile and × beside a ticker (the same DELETE as before).
- `?focus=SYM` (scrolls to that tile once).
- The served row order (DOM order = served `rows` order in every pick).
- The phone layout and its folded sections.
- The light theme (lit chips filled, tiles dark).
- Tile size (the fitted row height per pick).
- The data path: one board GET per `refresh_sec`, ONE bus subscription, ONE live-interest POST (already carrying every
  row, `ggwLiveSymbols`) renewed every `CARD_LIVE_MS`. No request was added.
- The 🚩 / 🧪 card "Watch layout" still PAGES — its shared code (`GgwPager`, `GgwLayoutPick`, the lib page math) is
  byte-identical.

## What changed

1. **No hidden tile.** With no chip filter every watched tile is shown; `.ggw-tile[hidden]` stays only for a chip filter,
   a folded phone section and the card grid.
2. **Every chip lit** with no filter; a tap turns that ONE name off (was: lit = the page).
3. **◀ ▶ greyed and no `n / m` counter** on the desktop (`paged={false}`); the titles still name the ← → keys.
4. **← → scroll**: one screen row group (the pick's `cols × rows` tiles) under the pinned tab strip, read from the DOM at key
   time (no state, no scroll listener). ← from the first group goes to the board top. Never while typing, never under ⤢,
   never on a phone. A key press no longer clears a chip filter, stamps `ggw.pickAt` or writes the link.
5. **`page=` out of the link.** An incoming `page=` (any value) is dropped by the first write; `per` and `show` are still
   written. A reload comes back through Chart Maps' own scroll restore.
6. **The pages anchor is replaced by the scroll hold** (`useGgwHold`): when the list, the row height, the pick or a head
   line changes, the tile he is looking at keeps its place on screen (one `scrollBy` after layout). Skipped while a box
   add's focus scroll is pending, while the head is still in view, and when that tile left the list or a filter hides it.
   A live batch reads no tile rect.
7. **The all-on toggle rule.** The tap that lights the LAST unlit chip clears the filter (no `data-pick`, no `show=`,
   `ggw.pick` removed) — a pick naming every name hides nothing today but would hide every machine name (🤖 / ✅ / ⛔🩳🔒)
   added later. Applies on the phone too (the one phone change).
   **2026-11-25 (fix pass):** the same rule runs on all three paths that can make a pick cover every listed name, through
   ONE helper, `ggwCoverAll(pick, list)` in `GajjalaWatchBoard.tsx` (a pick holding every listed name → no filter; a pick
   missing any name is kept as it is): (a) the chip toggle above; (b) the load's activation pass — when a fresh name of his
   (or a 🎯 A+) joins the pick, or a machine name the pick was hiding leaves the list, and the result covers every name →
   no filter; (c) the box-add join — a name he adds from the box joins the pick, and a join that covers every name → no
   filter. Pinned in `GajjalaWatchBoard.columns_2026_11_25.test.tsx` (one definition, three call sites, the box-add join
   with a NEGATIVE: a pick still missing a name is kept) and `GajjalaWatchBoard.newest.test.tsx` (a 🤖 turning 🎯 A+ joins
   at a load → no filter; ➕ again on a hidden name → no filter).
8. **Live gate = near the window.** The data fold still covers every row; only the RENDER is gated: a tile draws live bars
   when it is shown AND in or near the window (ONE IntersectionObserver per board, half a window above and below).
   Fail-open: no `IntersectionObserver` → every shown tile is live. Under ⤢ no board tile redraws; the ⤢ tile does.
   The phone is not gated (unchanged).
9. **⤢ close lands on the stock last viewed** when ⤢ stepped to another name (the page used to do this); a close without
   stepping moves nothing.

## MINE constants (layout, not rules — HIS CALL to move)

| Constant | Value | What it is |
|---|---|---|
| `GGW_NEAR_MARGIN` (`frontend/src/lib/ggwScroll.ts`) | `'50% 0px'` | the live gate's IntersectionObserver rootMargin; `null` = gate OFF |
| `GGW_SCROLL_EPS` (`frontend/src/lib/ggwScroll.ts`) | 1 px | tolerance when a tile edge is compared with the strip line; the hold ignores a move under it |
| §5.4 cost lines | 50 ms / 100 ms | the longest-main-thread-task acceptance lines, written BEFORE measuring (table below) |

The scroll target's inset is the CSS `scroll-margin-top: calc(var(--sticky-top, 0px) + 0.5rem)` on
`.ggw-grid--all > .ggw-tile` (the same value as the Replays precedent) — read back from the computed style, never a typed
pixel number.

## Numbers measured before the build (§1.7)

- Live GET 2026-11-25 (one read, 0.47 s, 2.49 MB): **43 rows**; 👤 18 · 🎯 2 · 🤖 9 · ✅ 13 · ⛔🩳🔒 1 (23 machine rows);
  14,713 bars (avg 342 a row). At 2 per screen before this change: **22 pages, 41 tiles he could not scroll to.**
- Probe (throwaway copy, repo untouched): nothing paged on the desktop + `page` out of the link + the all-on toggle rule →
  61 files / 858 tests: **27 fail in 9 files** (add_keeps_active 3 · auto 3 · float 4 · layout 3 · link 3 · live 1 ·
  newest 5 · sections 1 · toggle 4); 52 files stay green. A FLOOR: the probe had no ← → scroll, no ⤢ close scroll, no hold,
  no near gate.
- Geometry sketch (head heights ASSUMED, not his screen): once the head has scrolled away a window shows about 1.1–1.5 rows
  at picks 1 / 2, 2.2–3.0 at 4, 3.4–3.7 at 9.
- The render cost of 43 laid-out tiles (129 svg charts, 14,713 bars) was UNMEASURED before this change.

## §5 results (measured 2026-11-25, 13:05–14:40 ET, main session)

**Verdict, updated 2026-11-25 ~15:10 ET (fix pass — lever 1 now IN the branch, re-measured, table "Lever 1 in the branch"
below): P1 is UNDER its 50 ms line at every pick and size (0 long tasks in 60 s), so the NOT-READY condition of the ladder
is cleared. P2 at 9, P3, P4b at 9 and P5 / P5-back are STILL OVER their lines with lever 1 — reported with the numbers,
HIS CALL (lever 2 = draw a far tile's charts only once it is near, a design change). No further lever was added.**

Verdict as first measured (13:05–14:40 ET, before lever 1 was in the branch, kept for the record):
**NOT READY as built.** P1 (the per-second live path) is over its 50 ms line at 9 per screen, and P2–P5 are over
their lines at several picks. By the ladder below the next step is lever 1 in WP `board`, then all six re-measured. Lever 1
was tried in a SCRATCH copy only (not in the branch): it brings P1 under the line everywhere, but P2 at 9, P3, P4 (A→B)
and P5 stay over — so even with lever 1 the remaining overs are HIS CALL (lever 2).

How it was measured: the spec §5.2 harness (a local Vite config in the session scratchpad, never in the repo) serving
PRODUCTION builds (`vite build`; dev-mode React inflates every number) of three trees — NEW = this branch, BASE =
`git show HEAD:` of the four touched files, GATE-OFF = NEW with `GGW_NEAR_MARGIN = null` — plus a scratch LEVER-1 tree.
Driven by headless Chrome 158 over CDP (Chromium only). Long tasks = `PerformanceObserver('longtask')`. The stub Watch
GET is his 11:32 ET payload (43 rows); `refresh_sec` set to 15 in the stub so the re-GET paths run inside the test, and to
600 for P1 so no re-GET lands inside the 60 s window. Proof before the page opened (upstream pointed at a closed port):
`DELETE …/symbols/ZZZZ` 405, `POST /features/seen` 405, `POST …/gajjala-watch/live` 405, `/events` 204. Harness logs:
66 requests reached :8000 in the whole session — every one a GET (each URL at most twice: the first instance had no shared
cache) + the one LIVE-TAIL Watch GET + the one `/events` stream. No POST, PUT or DELETE reached the api.

### 5.3 Geometry, hold and live (STUB unless said)

| Check | 2560×1440 | 1440×900 | Expected | Result |
|---|---|---|---|---|
| tiles in the grid = served rows (43); `[hidden]` = 0; DOM order = served order | 43 · 0 · yes (picks 1/2/4/9) | 43 · 0 · yes | yes | ✅ (BASE: 1/2/4/9 shown, 42/41/39/34 hidden) |
| grid columns at picks 1 / 2 / 4 / 9 | 1 / 2 / 2 / 3 | 1 / 2 / 2 / 3 | 1 / 2 / 2 / 3 | ✅ |
| every chip lit; ◀ ▶ disabled; no counter; 5 section labels in the ticker row | 43/43 · both · none · 5 | 43/43 · both · none · 5 | yes | ✅ (BASE: lit 1/2/4/9, `1 / 22` at 2) |
| rows per window once scrolled, pick 1 | 1.03 | 1.14 | about 1.1–1.5 | 2560 just under the sketch |
| rows per window once scrolled, pick 2 | 1.03 | 1.14 | about 1.1–1.5 | 2560 just under the sketch |
| rows per window once scrolled, pick 4 | 2.06 | 2.28 | about 2.2–3.0 | 2560 just under the sketch |
| rows per window once scrolled, pick 9 | 3.10 | 3.42 | about 3.4–3.7 | 2560 under the sketch |
| → / ← move one row group; tile head below the pinned strip | 1344 px a step (1 / 1 / 2 / 3 rows); head 52.5 ≥ strip 45.2 | 744 px a step; head 53 ≥ strip 45.2 | yes | ✅ 0 hidden at every step; the first → from the board top lands group 0 (748 / 843 px); ← from group 0 → board top |
| hold across A → B → A: anchor tile `top` before / after (Chrome) | shift 0 px at picks 1 / 2 / 9 | shift 0 px at picks 1 / 2 / 9 | under `GGW_SCROLL_EPS` | ✅ |
| hold across A → B → A (Safari) | — | — | under `GGW_SCROLL_EPS` | **NOT VERIFIED** — Safari cannot be driven from this session |
| hold across the 500 (`⚠️` head line): anchor tile `top` shift | 0.4 px (line 18.2 px; rows re-fit 1331 → 1301) | 0 px (line 18.2 px; no re-fit) | at most that line's height | ✅ |
| no double correction with Chrome's own scroll anchoring | see note 1 | see note 1 | none | no overshoot; two opposite corrections cancel (note 1) |
| a ✅ tile in the RIGHT column, a row removed above it (pick 2 / 9) | GDRX top 2.5 → 1346.5 | GDRX top 3 → 747 (of 900) | §6.7: "the tile stays in view" | **NO** — note 2 |
| LIVE-TAIL: in-view chart mutates on batches; far one does not; near within about 1 s | — | — | yes | **NOT MEASURED live** — note 3; on the synthetic stream: in view 60/60 batches, far 0 of 41, scrolled-near tiles redraw within 50 ms |
| LIVE-TAIL: `/events` connections; live POST bodies carry every symbol; nothing mutates under ⤢ | — | 1 stream; no live POST was sent (note 3); synthetic: ⤢ chart 8 redraws in 8 s, board tiles 0 | 1; yes; yes | partly — note 3 |
| 430×932 and 375 px: one column, no pick, ◀ ▶ off, no element past the board width | 430: one column, no pick, ◀ ▶ off, none past | 375: one column, no pick, ◀ ▶ off; `.ggw-actions` / ✕ end at 377 px vs board 353 px | yes | ✅ 430; 375 overflow is PRE-EXISTING (BASE identical), no page sideways scroll (doc width 375) |
| light theme: lit chips readable, tiles dark | chip 13.8 : 1 contrast; tile `rgb(22, 26, 34)` | same | yes | ✅ |

**Which build (2026-11-25 review).** The table above was measured BEFORE lever 1 was in the branch. Re-checked on the
lever-1 build (`dist_5201`), Chrome only: the **hold** rows (`run_hold.mjs`, A → B → A and the 500, picks 1 / 2 / 9, both
sizes) — all 24 steps hold, anchor shift 0 to 0.4 px, and the right-column drop reproduces (GDRX 2.5 → 1346.5 at 2560,
3 → 747 at 1440). Raw: `resil7/hold_lever1.txt` (2560 rows) and `resil7/hold_lever1_1440.txt` (session scratchpad).
**NOT re-run under lever 1:** the → / ← step rows and the geometry rows (`run_geo.mjs`) — those cells are pre-lever-1 only.

1. A → B (a row removed above): Chrome's own anchoring corrected alone; the hold measured 0 and called nothing.
   B → A at picks 2 / 9: Chrome anchored a different tile than the hold — Chrome scrolled one row down, the hold scrolled
   one row up (`scrollBy(0, −1344 / −448 / −744 / −248)`) in its layout effect, net `scrollY` change 0, anchor tile shift 0.
   No overshoot was measured; whether a frame shows between the two was NOT checked (headless). Fallback
   (`overflow-anchor: none` on `.ggw-grid--all`) NOT added — spec §6.8.
2. The hold keeps the FIRST tile of the row in view. At picks 2 / 9 a row removed above shifts every later tile one slot,
   so the row's first tile moves up a row and the tile beside it (here the ✅ GDRX) lands one screen row lower — mostly
   out of view (747 of 900; 1346 of 1440). At pick 1 the tile itself is held. Not fixed (WP `board`); reported.
3. The ONE LIVE-TAIL window (13:49:46–13:51:11 ET, 85 s, NEW build, pick 2, 1440×900) received no `gajjala.update`
   batches: the page never sent its live-interest POST in that window (the same payload served from a stub does POST
   0.5 s after the GET; cause not found). The stream carried 969 `quote.update` events only. The window was not repeated
   (spec: one check, at most 2 minutes). P1 was therefore measured on a SYNTHETIC stream: one `gajjala.update` quotes batch
   a second carrying ALL 43 symbols (an upper bound — a live batch carries only the names that printed that second).

### 5.4 Cost — longest main-thread task in ms, 43 tiles (lines written before measuring)

Cells: longest task (count of long tasks). Two picks per size; 1440×900 first, then 2560×1440.

| Path | Mode | Line | Baseline @2 | New @2 | Baseline @9 | New @9 | Gate off (`GGW_NEAR_MARGIN = null`) |
|---|---|---|---|---|---|---|---|
| P1 at rest, live batches, 60 s | SYNTHETIC 1 s batches (note 3) | 50 ms | 0 · 0 | 0 · 0 | 0 · 0 | **118 (4)** · **81 (359 tasks, 23.4 s busy of 60 s)** | @2 **94 (60)** · @9 **131 (76)** / **156 (446)** |
| P2 scroll top → bottom → top, 120 px a frame | STUB | 50 ms | 0 · 0 (2 / 9 tiles) | **120 (65)** · 0 | 0 · 0 | **116 (4)** · **125 (32)** | @2 **117 (22)** · 0; @9 **112 (3)** · **131 (36)** |
| P3 per-screen switch 2 → 9 → 2 | STUB | 100 ms | **114** · **111** | **246** · **372** | — | — | — |
| P4 the re-GET commit, same rows | STUB | 100 ms | 76 · 77 | **145** · 75 | 74 · 68 | 88 · 64 | — |
| P4b the re-GET commit, a row removed (A → B) | STUB | 100 ms | 53 · 50 | **115** · 63 | 60 · 63 | **128** · **126** | — |
| P5 a head line appearing deep in the list (the 500) | STUB | 100 ms | 0 · 0 | 0 · **174** | 0 · 0 | 0 · **190** | — |
| P5 back (the line going away) | STUB | 100 ms | 0 · 50 | 70 · **199** | 53 · 53 | **116** · **270** | — |
| P6 first paint | STUB | no line — reported | 213 · 226 | 581 · 424 | 239 · 235 | 399 · 434 | @2 433 · 419; @9 402 · 449 |

Lever 1 (`.ggw-grid--all.ggw-grid--fit > .ggw-tile { content-visibility: auto; }`) measured in a SCRATCH copy only:

| Path | Line | Lever 1 @2 (1440 · 2560) | Lever 1 @9 (1440 · 2560) |
|---|---|---|---|
| P1 synthetic | 50 | 0 · 0 | 0 · 0 |
| P2 | 50 | 0 · 0 | **229 (30)** · **241 (30)** |
| P3 2 → 9 → 2 | 100 | **295** · **344** | — |
| P4 · P4b | 100 | 71 · 72 / 87 · 62 | 62 · 60 / **143** · **116** |
| P5 · back | 100 | 0 · 0 / 71 · **166** | 0 · **192** / **137** · **174** |
| P6 | — | 442 · 417 | 409 · 417 |

Reading: the BASE is over the P3 line too (114 / 111). With 43 tiles laid out, a commit that touches the whole grid
(the per-screen switch, a row removed, a head line) costs 115–372 ms against 50–114 ms paged; at 9 per screen a live tile
redraw forces the whole grid's layout (P1 81–118 ms, at 2560×1440 about 6 long tasks a second). The near gate is worth
it: gate off, P1 is over at 2 as well (94 ms, a long task every second). Lever 1 removes the P1 cost; it does not fix the
commits.

**Lever 1 in the branch (2026-11-25 fix pass, ~14:50–15:10 ET).** The rule is now at the end of
`frontend/src/styles/gajjalaWatch.css`, top level, the spec §3.4 text exactly:
`.ggw-grid--all.ggw-grid--fit > .ggw-tile { content-visibility: auto; }` (no `contain-intrinsic-size` — §3.4 fixes the
text without it). It reaches the desktop board's tiles only: the ⤢ stretch grid, the phone grid and the 🚩 / 🧪 card grid
carry no `.ggw-grid--all`. Pinned in `GajjalaWatchBoard.layout.test.tsx` ("CSS lever 1 …" and "lever 1 reach …", with
NEGATIVES for ⤢, the phone and the card grid). Re-measured with the SAME harness, the same runners (`run_live.mjs`
synthetic 1 s batches for P1 with `refresh_sec` 600; `run_cost.mjs` for P2–P6 with `refresh_sec` 15), a production build
of the branch tree as it stood at ~14:48 ET, served as port 5201. Proof before the page opened: `DELETE …/symbols/ZZZZ`
405, `POST …/gajjala-watch/live` 405, `POST /features/seen` 405. Harness log: 0 requests forwarded to :8000 (every GET
replayed from the session cache), 107 POSTs answered 405 locally, no POST / PUT / DELETE reached the api.

| Path | Line | Lever 1 in branch @2 (1440 · 2560) | Lever 1 in branch @9 (1440 · 2560) | Over? |
|---|---|---|---|---|
| P1 synthetic, 60 s | 50 | 0 · 0 | 0 · 0 | no |
| P2 scroll | 50 | 0 · 0 | **237 (31)** · **235 (30)** | at 9 |
| P3 2 → 9 → 2 | 100 | **267** · **260** | — | yes |
| P4 re-GET, same rows | 100 | 61 · 75 | 60 · 68 | no |
| P4b re-GET, a row removed | 100 | 89 · 65 | **150** · **116** | at 9 |
| P5 head line appears | 100 | 0 · 0 | 0 · **221** | at 9, 2560 |
| P5 back | 100 | 75 · **168** | **133** · **164** | yes |
| P6 first paint | — | 440 · 407 | 453 · 406 | reported |

Reading: the branch numbers match the earlier scratch lever-1 copy within run noise (P1 0 everywhere; P2 at 9 229 / 241
→ 237 / 235; P3 295 / 344 → 267 / 260). Lever 1 trades P1 for P2 at 9: without it P2 at 9 was 116 / 125, with it
237 / 235 (tiles entering the window now lay out as they arrive). Tiles past the first screen that redrew on a batch in
the P1 runs: 0 / 3 / 2 / 6 (@2 1440, @9 1440, @2 2560, @9 2560) — the same counts as the scratch lever-1 run.
Single runs, no repeats. Raw: `ggwfix/p1_lever1b.txt`, `ggwfix/cost_lever1b.txt`, `ggwfix/harness_5201.log`,
`ggwfix/run_all.sh` (session scratchpad, never in the repo).

The ladder, decided before measuring: any line exceeded → lever 1
(`.ggw-grid--all.ggw-grid--fit > .ggw-tile { content-visibility: auto; }`, with its own source pin) and all six
re-measured. Still exceeded → STOP: P1 over = NOT ready; P2–P5 over = reported with the numbers, HIS CALL (lever 2 = draw
a far tile's charts only once it is near — a design change).

Re-run (all in the session scratchpad `ggwcols/preview/`, never in the repo): `vite.harness.config.mjs` (the harness),
`build.sh` + `serve.sh` (the builds and servers), `run_geo.mjs`, `run_hold.mjs`, `run_live.mjs`, `run_cost.mjs`,
`run_phone.mjs` (headless Chrome over CDP, `cdp.mjs` + `measure.js`), raw results `geo_results.json`, `hold_5190.json`,
`p1.txt`, `p1_lever1.txt`, `cost.txt`, `cost_lever1.txt`. Single runs, no repeats: a long-task max is noisy (± tens of
ms between runs); the overs above are by 1.2–3.7× the line.

## Open items (2026-11-25 fix pass — NOT fixed)

1. **Safari scroll hold: NOT VERIFIED.** The hold across A → B → A and across the 500 was measured in Chrome only (§5.3);
   Safari cannot be driven from this session. Open until it is checked on his Mac.
2. **The right-column tile drops one screen row when a row above it is removed** (§5.3 note 2: at picks 2 / 9 the ✅ GDRX
   went from the top to 747 of 900 / 1346 of 1440 — mostly out of view). The hold keeps the row's FIRST tile; the tile
   beside it moves a row down. Not fixed; spec §6.7 expected "the tile stays in view" and it does not.
3. **P2 at 9, P3, P4b at 9, P5 / P5-back over their lines with lever 1** (table above) — HIS CALL (lever 2).
4. **→ / ← step and geometry NOT re-run under lever 1** (§5.3 "Which build"). The hold was re-checked on the lever-1
   build (Chrome); `run_geo.mjs` was not.
5. **LIVE-TAIL not measured live; P1 is on a synthetic stream** (§5.3 note 3: the one live window got no
   `gajjala.update` batches). Open until a live window carries real batches.

## HIS CALL

1. **Chips when nothing is filtered.** Built: every chip lit, a tap turns that ONE name off, the tap that lights the last
   one clears the filter. Costs: "just these 3" of 43 is 40 taps; with any chip off a 🤖 / ✅ / ⛔🩳🔒 name added later
   stays hidden. Options: a tap shows ONLY that name (more taps add) · a tap jumps to that tile (no filter) · lit = the
   screenful in view.
2. **The ticker row is out of reach while scrolling.** It scrolls away with the head; ◀ ▶ are greyed on the desktop and the
   `n / m` counter is gone. Option: pin the row under the tab strip (one line, sideways scroll, about 40 px) — then ◀ ▶ can
   jump a screen and a chip can jump to its tile.
3. **Row height.** Rows still fit "head + ticker row + N rows = one window at the board top", so once scrolled a window shows
   a bit more than N rows. Option: fit rows to the window under the strip — exactly N per screen while scrolling, and a
   head line no longer resizes every tile; tiles get taller.
4. The label "per screen" stays though 2 and 4 are both two columns (they differ in rows a screen).
5. Section header lines (👤 / 🎯 / 🤖 / ✅ / ⛔🩳🔒) inside the desktop scroll, and ✅ / ⛔🩳🔒 folded by default there as on
   the phone. Built: none — the desktop shows every row in served order, labels in the ticker row only.
6. The link no longer carries `page=`; a reload comes back through the page's own scroll restore.
7. ← → only scroll now: they no longer clear a chip filter (a per-screen tap still does).
8. The same columns-and-scroll on the 🚩 / 🧪 card "Watch layout" — NOT done; each tile there is its own request.
9. The MINE numbers: `GGW_NEAR_MARGIN` 50 %, `GGW_SCROLL_EPS` 1 px, the §5.4 lines (50 ms / 100 ms); and whether the phone
   gets the same live gate (every unfolded tile is live there today, untouched).

## Code and tests

Code: `frontend/src/lib/ggwScroll.ts` (new: `GGW_SCROLL_EPS`, `GGW_NEAR_MARGIN`, `ggwViewAnchor`, `ggwStepTarget`,
`ggwStepNow`, `ggwAnchorNow`) · `frontend/src/hooks/useGgwScroll.ts` (new: `useGgwNear`, `useGgwHold`) ·
`frontend/src/components/GajjalaWatchBoard.tsx` · `frontend/src/styles/gajjalaWatch.css` (`.ggw-grid--all` rule and the lever-1 `content-visibility` rule, top level).
Tests: `frontend/src/lib/ggwScroll.test.ts`, `frontend/src/hooks/useGgwScroll.test.tsx`,
`frontend/src/components/GajjalaWatchBoard.columns_2026_11_25.test.tsx` (new, NEGATIVES on every path) plus the pins restated
for the new rule in the layout / toggle / link / live / add_keeps_active / auto / float / newest / sections board tests.

Superseded parts of older docs carry a dated pointer to this one: `watch_two_up_stretch_2026_11_16.md`,
`watch_view_in_link_2026_11_16.md`, `watch_newest_active_2026_11_19.md`, `watch_live_2026_11_16.md`,
`watch_toggle_tickers_2026_11_16.md`, `watch_bigger_clearer_2026_11_16.md`.
