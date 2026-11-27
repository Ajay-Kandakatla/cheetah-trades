# 👀 Gajjala's Watch — two stocks a screen, pager, ⤢ full screen (2026-11-16)

> **2026-11-27 — built (frontend, branch `feat/watch-5m-grid-2026-11-27`).** Now the Watch's ⤢ opens on one full-height 5-min chart; a frames menu in the ⤢ head ticks 15-min / 1-min back on (order stays 15 / 5 / 1) and the average volume line is off there by default. The 🚩 / 🧪 card click ⤢ is unchanged. See [watch_5m_grid_2026_11_27.md](watch_5m_grid_2026_11_27.md).

> **2026-11-25 — changed.** On a desktop the pick is no longer the page size: it sets the columns and row height, every tile is shown in one scroll, ◀ ▶ are greyed, ← → scroll a row group (⤢ unchanged). See [watch_columns_scroll_2026_11_25.md](watch_columns_scroll_2026_11_25.md).

Ajay, verbatim:
- "I need bigger may be 2 on each screen side by side its not clear and give me a strech button to see full chart"
- "I wanna see all 3 of one stock for stretch like 5, 3 and 1"
- "right now its hard to see but on regular view two charts to fit the screen"
- "I mean to say two stocks heighted a little but two stocks with 3 charts each at any given moment iinstead of 6 like in
  the screen I wanna see 2 but I also wanna be able to move current one in the view"

## What changed (layout only — no word, rule, gate, order or push changed)
- **Per-screen pick** in the board head: `2 · 4 · 9 per screen` (`lib/gajjalaWatch` `GGW_LAYOUTS`). **2 is the default**
  (2 columns × 1 row); 4 = 2 × 2; 9 = his 11-15 3 × 3. The pick is remembered in this browser (`localStorage`
  `ggw.layout`; blocked / junk storage → 2). No pick on a phone (one column, every tile shown).
- **The pick is also the page size.** With more names than the pick, the board shows that many tiles; the rest stay
  mounted (their charts keep their bars) but hidden. ◀ ▶, one button per ticker (the shown ones lit) and ← → move the
  view (never while typing in the add box); a move scrolls the board's top to the window's top. His list order is
  unchanged. A `?focus=SYM` push link opens the page holding SYM.
- **Rows are measured from the board's top**, not the page's. The banners above the tabs had grown past one screen, so
  the old page-top measure left every row at the 200 px floor (the "not clear" tiles in his GP screenshot). Now the
  head + pager + `rows` rows fill exactly one window once the board is scrolled to the top
  (`ggwFitRowHeight(..., rows)`; 1440 px tall → about 1,350 px a row at 2 per screen).
- **One-line captions in a fitted tile**: in his GP screenshot the 5-min caption wrapped to two lines and squeezed the
  chart to a strip; the caption now stays on one line (ellipsis) and the full sentence is one ⤢ away.
- **⤢ Stretch** on every tile: the stock over the whole window (a portal on `<body>`, page scroll locked), its frames
  stacked **5-min, 3-min, 1-min** (`GGW_STRETCH_ORDER`), each full width and the same height. ◀ ▶ / ← → step to the
  previous / next stock of his list (wrapping) and the board page follows; ⤡, Esc or a click on the dark margin closes it.
  ✕ (remove) is not offered in the full-screen view. A name removed while stretched closes the view; it never re-opens
  by itself.

## Tests
`frontend/src/components/GajjalaWatchBoard.layout.test.tsx` (lib + board, NEGATIVES: junk/blocked storage, no picker or
pager on a phone, typing never pages, no paging before the first page, no ✕ in full screen, a click on the tile keeps it
open, removed name closes and never re-opens, no frame dropped, no duplicate id). Widened:
`GajjalaWatchBoard.fixes.test.tsx` (default = one fitted row, board-top measure), ✨ index pins +1, contracts slice 8 → 9.

UNMEASURED — a layout, not a signal.

## Review fixes (independent review, 5 confirmed, all fixed)
1. A `?focus=SYM` push link to a name on page 2+ never scrolled (scrollIntoView ran on the still-hidden tile) → the
   scroll now waits until the tile is shown.
2. The stored page went stale after removals (a later add jumped the view back; a pick change landed on the wrong
   tiles) → the page is clamped to the list, and the pick change starts from the shown page.
3. "9 per screen" below 1260 px drew 2 × 5 → `.ggw-grid--cols3` keeps 3 columns at every desktop width.
4. The ⤢ view also cut captions to one line → captions wrap again there.
5. Two tests could not fail (board-top measure; duplicate id) → rewritten; both review-fix tests mutation-checked.
