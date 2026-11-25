# 👀 Gajjala's Watch — toggle tickers, 1 per screen, × on every ticker (2026-11-16)

> **2026-11-25 — changed.** With no filter every chip is lit and a tap turns that ONE name off; the tap that lights the last chip clears the filter; ← → only scroll. See [watch_columns_scroll_2026_11_25.md](watch_columns_scroll_2026_11_25.md).

Ajay, verbatim: "make These toggleable and 1 at a time instead of 2 minimum.. I wanna be able to select or remove from
these give me an x option to remove as well".

- **Toggle**: every ticker button flips that name on or off the screen (`lib/gajjalaWatch` `ggwToggleShown` — his list
  order kept; the base is what is on screen now). One name alone fills the width; the grid is `ggwPickGrid(n, cols)` —
  never more columns than names, rows fitted to the window. Toggling the last one off returns to the pages (never an
  empty board). A picked name that leaves the list drops out.
- **1 per screen**: a fourth pick `1` (1 × 1) beside 2 · 4 · 9 (`GGW_LAYOUTS[1]`).
- **×**: beside every ticker — DELETEs that name from the watch (the same write as the tile ✕; no confirm, as the tile).
  It never toggles the view.
- ◀ ▶ / ← → / a per-screen pick clear the pick and move by pages from the current page. The ticker bar now shows
  whenever there are 2+ names (also when all fit, and on a phone), with ◀ ▶ off when there is only one page.
- Lit buttons are FILLED (lime ground, dark text) so they read in the light theme too.

Tests: `GajjalaWatchBoard.toggle.test.tsx` (lib + board, NEGATIVES), `GajjalaWatchBoard.layout.test.tsx` widened (ticker =
toggle, ticker bar on a phone / when all fit). Display only — UNMEASURED.
