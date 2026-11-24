# 👀 The 🚩 / 🧪 card grid in the Watch layout — 2026-11-18

## The ask, verbatim

Ajay 2026-11-18 ~03:00 ET, with a screenshot of the ⤢ three-chart view of AZI opened from a 🚩 card:

> "I need the watch list kinda chart formant view video view as default here too from the tabs pages"

His pick: **"Tab cards as Watch tiles"** — the card grid itself switches to the Watch-list layout: big tiles, 2 per screen
side by side, each with the live 15 / 5 / 1-min stacked charts. The small cards are no longer the default.

Scope: 🚩 Gajjala's 5-min tab + 🧪 Gajjala · Audited. The 1-min page (retired 11-18) and 🥇 Luk are untouched.
**Display only, UNMEASURED** — no rule, gate, threshold, order, count, keep-set, alert or ring changed. No backend change.

## What draws where

| Piece | File | What it does |
|---|---|---|
| Mode + pick storage, words, `ggcShown`, `GGC_NO_FRAMES`, `ggcRow(…, { plan: false })` | `frontend/src/lib/gajjalaCardView.ts` | additions only; every 11-16 / 11-17 export byte-identical |
| The state | `frontend/src/hooks/useGgCardWatch.ts` | mode, page / pick / keys / focus, frames GETs, one live fold, fitted rows |
| The pieces | `frontend/src/components/GgCardGrid.tsx` | `GgCardWatchToggle`, `GgCardGridFrame`, `GgCardTile` — the Watch's own `Tile` / `GgwPager` / `GgwLayoutPick` |
| The wiring | `frontend/src/components/GajjalaBoard.tsx` | one hook call, one toggle, the grid wrapper, `hidden` + class on the card div, the chart slot, the divider |
| The look | `frontend/src/styles/gajjala.css` | appended after the pinned `.gg-card` / `.gg-wide` rules, new selectors only |

- **`cw.active` = on && enabled && a card to draw** is the only switch. OFF, an empty setup sub, 🏁 Track record, 📋 All
  strategies and the 1-min page draw today's `.cm-grid` exactly (no shell, no pick, no pager, no GET).
- The card div keeps its whole chrome (chips row above; zone lines, CardExtras — plan, breakout / cross / bases lines, 🎾 SI
  label, live-vs words, criteria, chips, 🧠, stages — and the 🚫 broker toggle below). Only the chart slot swaps: the
  PatternChart card becomes the Watch `Tile` with the frames stacked 15m / 5m / 1m (`GGC_STRETCH_ORDER`), the card's
  lines / bands / A+ marker overlaid (`ggcRow`; 📺 strips the band and the ➖ diamonds through the same `videoLayers`).
- The tile head: SYM, the card's **SEPA page** link (the same href + back state as the PatternChart link — a test pins
  equality), ➕ Watch, the served stamp, ⤢ (opens the existing `GgCardView`), Yahoo ↗. No ✕ (a card is never removed from a
  board), no ⤡. The plan line prints ONCE, in CardExtras (the tile head carries only the served no-bars words).
- Off-page cards stay mounted and `hidden` (the Watch rule); the pager lists the DRAWN cards (💋-hidden ones are not in it).
- A bar-less ☀️ / 🌙 mover card keeps its `.gg-row-head` Link (no tile, never a frames GET).
- 🎾 cards are not full-row (`gg-wide`) under the Watch layout — every cell is equal (HIS CALL #4).
- Phone (≤ 640 px): ONE card per page with the pager, no per-screen pick.

## GET cadence

| Event | Frames GETs (`/chart-maps/gajjala/frames/{sym}`) |
|---|---|
| A landed board read (the 5-min poll, a 🔄 scan-poll read, a `pass` nudge) | one per SHOWN card (≤ the per-screen pick: 2 by default, 9 at most) |
| ◀ ▶ / a ticker / ← → to a page not yet read for this board read | one per newly shown card |
| Paging back to a page already read for this board read | 0 |
| A quotes batch, a new tiles array, a 📺 flip, a 💋 flip | 0 |
| Toggle OFF | 0 (in-flight GETs aborted, loads + live cleared) |
| Toggle ON again (same board read) | one per shown card |
| ⤢ on a tile | the existing GgCardView GET (one) |

The 🔄 scan-on-open poll re-reads the board every `plan.everyMs` while scanning: each landed read is ≤ pick GETs (at 9 per
screen, 9 per step). A batched endpoint is NOT built (HIS CALL #9).

Live: ONE `gajjala.update` subscription folds every quotes batch of THIS board's variant into one map against the frame
metas of every loaded card still listed (all visited pages — `ggwApplyBatch` prunes a symbol without metas), so a card
paged in shows its forming bar at once with no GET; the DISPLAY is gated by `shown`. No live POST (the board's
`useCardLive` holds the interest).

## Storage keys (per viewer, per device; try/catch — a blocked store reads the default)

| Key | Values | Default |
|---|---|---|
| `gg-card-watch` | `'1'` ON, `'0'` OFF; any other value = OFF (the 📺 rule) | absent / blocked → ON |
| `ggc.layout` | `1` · `2` · `4` · `9` (the Watch parser) | 2 |

The Watch keeps its own `ggw.layout`; the two never move each other. Page / pick are session state (not in the URL).

## The OFF proof

`frontend/src/components/GajjalaBoard.card_watch_off.snapshot.test.tsx` and its `__snapshots__/…snap` were written and run
on the UNMODIFIED board (HEAD 3c0a2ade) before any product edit: with `gg-card-watch` = '0', the `.cm-grid` outerHTML of the
🚩 bull_flag, 🎾 reversal_squeeze (hand fixture 2026-10-13) and 🧠 potential (golden 2026-10-15) subs — real PatternChart,
chips mocked, wall clock pinned to 2026-11-13 15:30 UTC. The snapshot passes unchanged after the build. No attribute had to be
stripped (two runs byte-identical).

## The opt-out for the existing board tests

The default flips the small-card grid off in every board test that renders tiles. `frontend/src/test/ggCardWatchOff.ts`
(a side-effect module: a fresh in-memory localStorage with `gg-card-watch` = '0' before every test) is imported FIRST by
the files that went red under the default (build-day run of all 43 `GajjalaBoard.*.test.tsx`, 66 cases in 16 files):

- `GajjalaBoard.test.tsx`
- `GajjalaBoard.all_table.test.tsx`
- `GajjalaBoard.cardLabels.test.tsx`
- `GajjalaBoard.card_view.test.tsx`
- `GajjalaBoard.chart_frame.test.tsx`
- `GajjalaBoard.emaBlink.test.tsx`
- `GajjalaBoard.list_note.test.tsx`
- `GajjalaBoard.live.test.tsx`
- `GajjalaBoard.live_stream.test.tsx`
- `GajjalaBoard.movers_links.test.tsx`
- `GajjalaBoard.payload.test.tsx`
- `GajjalaBoard.potential.test.tsx`
- `GajjalaBoard.squeeze_wide.test.tsx`
- `GajjalaBoard.watch_nobars.test.tsx`

The two files that already stub storage seed the key in their own stub instead (one line each):
`GajjalaBoard.kiss_rvol.test.tsx` (`mem()`), `GajjalaBoard.videoLook.test.tsx` (`mem(seed)` + its `blocked()` store returns
'0' for `gg-card-watch` only). No other line of any existing test changed. A board test file that lands later needs the same
import if it renders tiles.

## Tests

- `frontend/src/lib/gajjalaCardView.test.ts` — load / save (strict '1', blocked, absent), `GGC_WATCH_VKEYS` == the 📺 keys and
  never 1-min / Luk, `ggc.layout` never reads `ggw.layout`, `ggcRow(…, { plan: false })` vs the 11-17 row, `ggcShown`.
- `frontend/src/hooks/useGgCardWatch.test.tsx` — GETs per page / pick / boardSeq, zero on quotes / tiles / 📺, inactive
  idle, newest wins, failed re-read keeps frames, row identity, live over visited pages [C2], StrictMode focus [C3], OFF → ON
  re-measure [C1] and re-read [C5]. Mutation-checked: `fitKey` without the active bit fails C1; metas over shown only fails C2.
- `frontend/src/components/GgCardGrid.test.tsx` — the OFF div exactly, [C7], the shell / pick / pager (no ×), the tile
  (stack order, SEPA href == PatternChart's, ⤢, no ✕ / ⤡, served words, 📺 strip), no FE-typed sentence, the CSS selector
  (0,3,0) [C4], the Watch's own fit rule unchanged.
- `frontend/src/components/GajjalaBoard.card_watch.test.tsx` — the real board, cases (1)–(13) of the spec. Mutation-checked:
  dropping the focus derivation fails (10).
- `frontend/src/components/GajjalaBoard.card_watch_off.snapshot.test.tsx` — the OFF grid, byte for byte.

## Browser acceptance (measured 2026-11-18 10:57–11:05 ET, worktree Vite preview, live api, GET only)

The preview proxied /api to the live api under the owner's header and answered every non-GET with 204, so the
🔄 scan POST and the ✨ / usage POSTs never left the preview. One board read per sub opened; no loop. Page is `<StrictMode>`.

| Check | Measured |
|---|---|
| Default, empty storage, 🚩 `bull_flag` | Watch layout on, toggle pressed, pick 2 pressed |
| 1920×1080, 💋 `kiss_fly` (7 cards) | rows `minmax(1016px, auto)`, 2 × 727.5 px columns, 2 shown / 5 hidden, both cards end at 1080 (the window). Frames 196/196/196 (CLRO) and 270/270 + an empty 1m at 74 px (BRBR). Nothing clipped, nothing past the right edge |
| frames GETs on that load | 2 (CLRO, BRBR) for 7 cards |
| 2560×1440, same board (resize re-fit) | rows `minmax(1376px, auto)`, both cards end at 1440. Frames 316 ×3 / 450, 450, empty 74 |
| 1920×1080, 🎾 `reversal_squeeze` (21 cards) | 1016 px rows, frames 173 / 213, `gg-wide` on 0 cards. Nothing clipped |
| the same board at pick 4 (the long-chrome case) | row floor 501 px, rows GREW to 978 and 762 (never clipped), frames held the 160 px floor, empty 1m = 74 px |
| GET cadence | pick 4 → +2 (NOMA, SVRE); back to 2 → 0; OFF → 0; ON → 2 (PMEC, CLRO); no board re-read on any toggle |
| OFF → ON | OFF: old `.cm-grid`, 21 cards, 0 hidden, 21 `gg-wide`, storage '0'. ON again: re-fit to `minmax(1016px, auto)` with no new board read, storage '1' |
| `?focus=AZI` (8th card) on a reload | page 4 / 11 shown (GMM, AZI) on the first paint, AZI not hidden, the page scrolled (scrollY 1427) |
| 430×932 | one 386 px column, 1 card a page ("1 / 21"), no pick, pager drawn, rows `auto`, frames 148 px each, 0 descendants past `clientWidth`, chips `white-space: normal` |
| 🧪 `gajjala_audited`, `reversal_squeeze`, 1920×1080 | the same: toggle pressed, rows `minmax(1016px, auto)`, 2 shown / 19 hidden |

Not checked: `gajjala_1m` (the page is retired, 11-18). The live forming-bar move (§5.4) was not watched.

**Open, not fixed (outside this package's touch points):** on a `?focus=` reload the board's once-only
`scrollIntoView({ block: 'center' })` (GajjalaBoard.tsx, untouched by §3.6) runs before the tile has its fitted height.
The focused card ends with its top at 530–531 px and its bottom at 1546 px in a 1080 px window, so its head, the 15m
chart and most of the 5m are on screen and the lower half is not. Same reload with the layout OFF: the card is centred
(107 → 1018). A focus change inside the page (cards already fitted) centres it (top 32, 1016 px tall). The fix is a
choice (scroll again after the fit, or `block: 'start'` under the Watch layout) — main session / his call.

## HIS CALLs (built as defaults, nothing decided here)

1. DEFAULT = the Watch layout on BOTH 🚩 5-min and 🧪 Audited.
2. The per-screen pick is its OWN key (`ggc.layout`, default 2) — sharing the Watch's `ggw.layout` = his word.
3. Tile stack order 15m / 5m / 1m (the ⤢ order); the Watch's 1m-on-top split is NOT used.
4. 🎾 cards: not full-row under the Watch layout; the tile shows the stored 15 / 5 / 1 frames (no prior-session tail).
5. The PatternChart card chrome NOT on the tile: the entry ladder, stats, the outer chips row of the svg.
6. Page / pick are session state; the mode and the pick-size are per device.
7. Phone = 1 per screen with the pager.
8. `GGC_FRAME_MIN_PX = 160` (the chart floor in a fitted tile) — MINE.
9. No batched frames endpoint.
10. Whether the in-flight 🧨 Divergence sub follows the layout (if it has its own renderer).
11. Bar-less ☀️ / 🌙 mover cards keep the Link, no Watch tile.
12. The ⤢ view's empty frame keeps its full third; only the board tile shrinks an empty frame to its words.
13. A frames GET on every landed board read while the 🔄 scan polls.
14. The 1500 px Chart Maps page cap stays on these tabs.
15. The retired-1m sentence prints on most board tiles (at its words' height) — a shorter served word or no 1m figure = his word.
16. DEFAULT ON for every viewer (Doug, Chiranjeevi), not the owner only.
17. The 🧪 tab draws GG5's stored frames (the overlay borrows GG5's reads).

## REVERTED 2026-11-23 — default OFF

Ajay ~19:20 ET, verbatim: "The problem with this view is I cannot see the height of the chart its compressed look throws away the move perspective" · "I needed the video view default in all the places of charts" · "Work on reverting and lmk".

`GGC_WATCH_DEFAULT_ON = false`: with nothing saved, the 🚩 / 🧪 tabs draw the 📺 video-view cards again (one tall 5-min chart, docs/gajjala/video_view_2026_11_17.md). The 👀 Watch layout button stays; one tap turns it on and that choice is remembered per device (stored "1"). A device that already saved "1" keeps it until tapped off. The 👀 Watch tab itself is unchanged. Pinned in contracts.mjs (the 👀 card-grid block) and GajjalaBoard.card_watch.test.tsx (1). Display only.
