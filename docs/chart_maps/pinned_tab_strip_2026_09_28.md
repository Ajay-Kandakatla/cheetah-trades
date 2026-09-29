# 📌 Chart Maps keeps his place — pinned tab strip, active tab in view, return lands where he was (2026-09-28)

Ajay 2026-09-28 (Chart Maps, S3 Topping · Shorts active, the tab strip cut off
on the right): *"Pin the tab I am in, as I navigate back and fort lost where I am"*.

## What was wrong

* The tab strip scrolled away with the page. Deep in a board of 80 tiles there
  was no sign of which tab he was on.
* The strip is about 30 tabs wide. A tab past the right edge (S3 Topping sits in
  the 20s) could be the active one while nothing on screen showed it.
* Opening a ticker and coming back reloaded the tab at the top. The ← Back link
  already kept the tab (`?tab=` in the URL), but the page's scroll position was lost.

## What changed (three parts)

1. **Sticky strip.** The unchanged `.cm-tabs` strip sits inside a new
   `.cm-tabs-bar` wrapper: `position: sticky; top: var(--sticky-top, 0px);
   z-index: 30; background: var(--bg)`. On the phone, `--sticky-top` is the
   sticky nav's measured height, so the strip sits under the nav. On desktop
   the nav scrolls away, so the variable is unset and the strip sits at the top (0).
   The bar is ~45px, one row, at both widths.
2. **Active tab in view.** On mount (coming back included) and on every tab
   change, `revealActiveTab` sets the strip's own `scrollLeft` to centre the
   active tab. It never calls `scrollIntoView`, because that would also scroll
   the page vertically when the strip is off-screen. A tab that is already
   visible never moves. A resize never re-centres, so the strip stays where he
   scrolled it. ‹ › fades show when more tabs exist off that edge. Switching
   tabs from deep in a board opens the new tab at its top, right under the
   strip. Nothing moves when he is above the strip.
3. **A return lands where he was.** On leaving, a one-shot sessionStorage record
   (`CM_SCROLL_KEY`) stores the tab, `scrollY`, and the first tile visible under
   the strip with its offset. The next mount takes it, which removes it, and
   restores **after the board renders**. The anchor tile wins over raw `y`,
   because boards re-order. The restore happens only for the same tab, only
   within `CM_SCROLL_MAX_AGE_MS`, and only before he starts reading: a wheel,
   touch, key or mouse input cancels it. After `CM_RESTORE_DEADLINE_MS` the
   page gives up quietly.

## What counts as a return (HIS CALL #4 / #5)

* **Armed:** leaving for a ticker page (`/sepa/<sym>`, `CM_TICKER_PATH_RE`). He
  comes back by ← Back or the browser ◀ and lands on the same tab and tile.
* **The menu opens Back in Demand.** The menu link is bare `/chart-maps`, which
  stays 🟢 Back in Demand (HIS CALL #1). So a menu return keeps his place only
  when he was on Back in Demand. From any other tab (e.g. S3 Topping) the menu
  lands on Back in Demand at the top and the saved place is dropped, because
  the record belongs to another tab (page test 25).
* **Dropped:** leaving for anything else. A menu round trip with no ticker in
  between (Chart Maps → SEPA → Chart Maps) opens at the top. So does a new
  browser tab.
* **Kept:** the tab going hidden, or `pagehide` (reload, a phone OS tab
  reload). This is the `src: 'hide'` record. Becoming visible again removes it.
  A restore still pending when the tab hides is re-stamped `src: 'hide'`, so it
  is removed the same way (page test 26).
* **StrictMode dev double mount:** a pending restore is written back, and the
  mount never snapshots itself (`leaveAction` returns `'keep'` or `'drop'` for
  `/chart-maps`).

The destination is read from `window.location.pathname` in the layout cleanup.
Under `BrowserRouter`, `pushState` runs before the re-render, so the path is
already the new one. A move to a data router with a deferred URL update would
break this; page tests 15 and 19 catch that.

## Tables under the strip

Boards under the bar stick **below** it:
`.cm-tabs-bar ~ * { --sticky-top: calc(var(--cm-nav-top) + var(--cm-tabs-h)) }`.
The page publishes its bar height as `--cm-tabs-h` through the one offset
engine, `useStickyTop`, which was extended with `{ varName, host }` and is
unchanged for the NavBar. That covers the Catalysts `.pcw` headers, `.hs-scroll`
and `.eg-scroll`, and `.cat-tl-date` through a scoped override.

Two tables have no scroll box of their own. They stick to the viewport through
the global `thead { position: sticky; top: 0 }` and get a scoped `top`:
POTUS `.pb-table` and Catalysts ▸ Timeline `.cat-tl-table`. **Every other
table is left alone** (`.nt-table.nt-sectors`, `.og__table`, `.sl-table`,
`.gnt-table`, `.hs-table`, `.eg-table`). Each sits inside its own `overflow-x`
box, so an offset would push its header down over its own rows. A contract
forbids adding them and forbids a blanket `thead` rule. A future board that
adds a thead table with no scroll box of its own will slide under the strip
until it is added to that `:is(…)` list.

`.cm-head` gets `position: relative; z-index: 31`, so the ℹ️ "how to read this
board" panel paints over the strip. Side effect: the page's ℹ️ button, which
was positioned against the viewport (top-right, inside the nav on desktop and
under the z-100 nav on the phone), now sits at the right edge of the Chart Maps
header.

## Why no overflow changed

`html { overflow-x: hidden }` propagates to the viewport, and `body`, `.app`
and `.main` use `overflow-x: clip`, which does not create a scroll container.
Sticky already works, which is why `clip` was chosen for the promo-board
headers.

## Constants (`frontend/src/lib/cmPinnedTab.ts`)

`CM_SCROLL_MAX_AGE_MS` (30 min) · `CM_RESTORE_DEADLINE_MS` (15 s) ·
`CM_TABS_FADE_PX` (26, the fade width) · `CM_SCROLL_KEY` · `CM_TICKER_PATH_RE` ·
`CM_PAGE_PATH` · `CM_TABS_H_VAR` · `CM_TABS_SB_VAR` (the strip's classic
scrollbar height, so the fades stop above it).

## Unchanged

* Bare `/chart-maps` still opens 🟢 Back in Demand (`DEFAULT_TAB = CM_TABS[0]`).
* The tab order is unchanged.
* A tab click keeps `replace` history.
* The ⌘-click tab links are byte-identical inside the wrapper.
* Filters and sub-tabs keep whatever URL persistence they already had. No new
  persistence was added.

## Tests

* `frontend/src/lib/cmPinnedTab.test.ts` (42) covers:
  * `revealLeft`: centring, clamping, and a tab under a fade counts as hidden.
  * `stripEdges`, `scrollbarPx`, `boardTopScrollY`, `tileSymbolFromHref` and `firstVisibleTile`.
  * `leaveAction` for every destination class.
  * save/take: one-shot, exactly 30:00 is OK, 30:00 + 1 ms is not, other tab, future stamp, v:2, y ≤ 0, bad JSON, a throwing store, a `<script>` sym.
  * `clearHideRec`.
  * `revealActiveTab`: never `scrollIntoView`, focus or `window.scrollTo`.
  * snapshot/restore: the anchor, the y fallback, and a page that is not tall enough.
* `frontend/src/hooks/useStickyTop.test.tsx` (+3): the custom var lands on its host, `<html>` is untouched, and unmount removes only the custom var.
* `frontend/src/pages/ChartMapsPinnedTab.test.tsx` (27) runs on the real page:
  * the sticky wrapper and the links.
  * mount at topping → `scrollLeft` centres it (derived from `CM_TABS.indexOf('topping')`) with the › fade.
  * a click re-centres the strip; an already-visible tab does not move.
  * no page scroll and no `scrollIntoView`.
  * default tab and tab order.
  * restore after the tiles render, not while the board is in flight.
  * the anchor tile.
  * other tab, 31 min, fresh visit, bad JSON / throwing store, one-shot, and a wheel cancel.
  * leave save to a ticker page; a ⌘-click stores nothing.
  * tab switch from deep in a board, and the negative above the strip.
  * hide/visible.
  * menu round trip, ticker-then-menu on Back in Demand, ticker-from-Topping-then-menu (Back in Demand, top, record dropped), and a pending restore dropped by a menu leave.
  * hidden during a pending restore → stored as `src:'hide'`, removed on visible.
  * StrictMode exactly one restore; StrictMode never snapshots itself.
  * a resize never re-reveals.
* Contract `📌 Chart Maps tab strip stays pinned…` in `frontend/scripts/contracts.mjs` pins:
  * the wrapper and the verbatim render guard.
  * one `syncStrip(true)`.
  * replace history.
  * the sticky CSS, and no custom-property cycle.
  * the two-table thead rule and its negatives.
  * the fade scrollbar stop and `.cm-head` z-index.
  * the 30-min age, the ticker route and the one-shot remove.
  * the default tab.

## HIS CALL (defaults as built)

1. Bare /chart-maps reopening the last tab he was on. Default **no**: it stays Back in Demand.
2. Browser ◀ stepping through Chart Maps tabs. Default **no**: tab clicks keep `replace` history.
3. Two defaults set in this build:
   * a tab switch from deep in a board opens the new tab at its top;
   * a return restores once, within 30 min.
4. What counts as coming back. Default: after a ticker page, by ← Back or ◀. The menu opens Back in Demand and keeps the place only when he was on Back in Demand. A menu round trip without a ticker opens at the top.
5. Reload (⌘R) keeps his place. The flip is to drop `src:'hide'` records on a `reload` navigation.
