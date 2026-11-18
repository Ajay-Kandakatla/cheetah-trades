# 👀 Watch layout pieces, shared (2026-11-18)

Ajay 2026-11-18: "I need the watch list kinda chart formant view video view as default here too from the tabs pages".

The 🚩 Gajjala and 🧪 Audited card grid draws the Watch's own layout (spec `cardview`, WP-B). This step (WP-A) makes the
Watch's pieces shareable first, so the card grid reuses them and never re-implements them. Display only: no rule, gate,
threshold, order, alert or served word changes. No backend change.

## What moved (pure moves, body unchanged)

Out of `frontend/src/components/GajjalaWatchBoard.tsx` into the new `frontend/src/components/GajjalaWatchLayout.tsx`:

| Before (in the board) | Now (exported) |
|---|---|
| `useFitRows` (the fitted row height, measured from the `.ggw-board` top) | `useGgwFitRows` |
| the "1 · 2 · 4 · 9 per screen" pick JSX | `GgwLayoutPick` |
| the pager JSX (◀, the tickers, ×, ▶, "page / pages") | `GgwPager` |

The board now imports the three and passes the same values it used inline.

## Opt-in additions (the Watch passes none of them)

- `GgwLayoutPick` / `GgwPager` take `testidPrefix` (default `ggw-layout` / `ggw-pager`). It renames the testids only.
- `GgwPager` takes an optional `onRemove`. Without it there is no × at all, because a 🚩 card cannot be removed from a board.
- `Tile` (in `GajjalaWatchTile.tsx`):
  - `onRemove` is now optional. Without it there is no ✕.
  - `stack`: on a board tile, the frames are drawn stacked in `order`, which is the ⤢ block. It gets the extra class `ggw-charts--stack` and the testid `ggw-stack-charts`. In this mode only, a fitted frame that prints its served empty words gets `flexGrow: 0`. The words take their own height and the charts take the rest. The ⤢ view keeps `flexGrow: 1` on every frame.
  - `extra`: the caller's content, drawn right after SYM and before the A+ chip. Without it, nothing is drawn there.
- `Frame`: `data-empty="1"` on the `<figure>` when it prints served empty words. A Watch frame never carries `empty_text`.

## The Watch's DOM is byte-identical

The Watch board's rendered `innerHTML` was captured before and after the move for these cases:

- the fixture board
- a 7-row board with an A+ name
- page 2 at 4 per screen
- a toggled pick of two names
- the Watch's ⤢ view

All five were byte-for-byte equal. Every existing test also passed unedited:
`GajjalaWatchBoard*.test.tsx`, `GajjalaWatchTile.test.tsx`, `GgCardView.test.tsx`, `GajjalaBoard.card_view.test.tsx`.

## Tests

- `frontend/src/components/GajjalaWatchLayout.test.tsx`:
  - (a) the Watch board still draws every pick and pager testid, and × still DELETEs that name.
  - (b) NEGATIVE: with no `onRemove`, there is no × node, and the toggles and ◀ ▶ still call back.
  - (c) a prefix renames the testids only. The DOM with the prefix swapped back equals the Watch's DOM.
  - (d) NEGATIVE source guards: the board declares none of the moved pieces and types no `ggw-layout-btn` / `ggw-pager-x`. The layout file draws no chart and makes no fetch.
  - (e) the hook returns null on a phone, with no grid, or on a zero-width box. A measured box gives `ggwFitRowHeight` from the board top. The 3-row default is untouched.
- `frontend/src/components/GajjalaWatchTile.stack.test.tsx`:
  - (a) stack order 15m / 5m / 1m, with no ⤡ and no ◀ ▶.
  - (b) no ✕ without `onRemove`; with `onRemove`, the ✕ is as today.
  - (c) `extra` sits right after SYM; NEGATIVE: without it, the head's children are today's.
  - (d) an empty frame in stack mode gets `data-empty` and flexGrow 0; NEGATIVE: the ⤢ view keeps flexGrow 1, and `onUnstretch` wins over `stack`.
  - (e) NEGATIVE: a Watch tile keeps 1m on top with the 3m + 5m pair and has no `data-empty`.
  - (f) every visible text outside the svg is a served fixture string or a structural glyph, and there is no house chip, 📡 or feed word.
