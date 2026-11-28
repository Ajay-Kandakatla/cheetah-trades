# 👀 Watch — ⋯ drawer un-squished, drawer tags scroll sideways (2026-11-28)

Ajay, on the NXAT tile with the ⋯ drawer open over the 5-min chart:

> "On the cards for show details can you make them available they are getting squished.. Ad the tags to be scrollable"

## What changed (display only — no data, sort, gate or push change)

`frontend/src/styles/gajjalaWatch.css` only.

- **Desktop drawer:** fills the compact tile below the head (`top: 34px; bottom: 8px`). The `max-height: 70%` cap is gone. It scrolls down inside itself (`overflow-y: auto`, `overscroll-behavior: contain`). Its children are `flex: none`, so nothing gets squashed, and the served levels line wraps inside the drawer (no ellipsis there).
- **Drawer tags row, at every width:** ONE line that scrolls sideways (`overflow-x: auto`, `flex-wrap: nowrap`, a thin visible scrollbar, touch scrolling). Every chip, including the 🧭 stage chips, stays whole: `flex: none`, `white-space: nowrap`, `text-overflow: clip`, no `overflow: hidden`. On a phone the row uses `max-width: 100%` and `min-width: 0` and scrolls inside itself, so nothing overflows the page at 430 px. The phone drawer stays static.
- **Unchanged:** the fitted tile-head tags row OUTSIDE the drawer keeps its one-line ellipsis (the 11-16 GP rule). The ⤢ drawer is still static.
- The desktop in-drawer rules win by specificity (`.ggw-grid--fit .ggw-tile--compact .ggw-drawer …`), not by source order. They beat both the fitted ellipsis rules and the ⤢ wrap rules.

## Tests

`frontend/src/components/GajjalaWatchCompact.drawer_unsquish_2026_11_28.test.tsx` covers:
- the stylesheet rules and their specificity;
- NEGATIVES: the outside row keeps its ellipsis, the pre-fix sheet fails every check, and putting back the 70% cap or the chip ellipsis fails;
- a GgwDrawer mount, where the `.ggw-tags` row is the drawer's first child.

No existing test pinned `max-height: 70%`.
