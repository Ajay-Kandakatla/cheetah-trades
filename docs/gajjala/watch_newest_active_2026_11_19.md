# 👀 New Watch names: newest first, active, with charts, and a ✕ that always answers (2026-11-19)

> **2026-11-25 — changed.** No pages on a desktop: "its page" is now a scroll to the tile, and the pages anchor is replaced by the scroll hold. See [watch_columns_scroll_2026_11_25.md](watch_columns_scroll_2026_11_25.md).

Ajay, verbatim: "When ever I push something to watch it make it active by default and also on top" · "I do not see the new ones active" · "The X buttons are not working" · "When I add a new ticket they are gettinf added in to que but not active  charts are not loading I amhaving to click on the chips again".

Spec: `scratchpad/watchnew2/spec.md` (v3, nine critique findings fixed). This doc is the standing record.

## What changed (display + store only — no rule, gate, push or threshold)
- **Store.** The owner list doc carries an `added` map (symbol → UTC time). Written in the same compare-and-set as `symbols`. A re-add (`already`) writes only the time; a failing time write still answers `already`. Old docs without `added` keep working (those names sort after the dated ones, in stored order).
- **Rows.** The owner's rows are served newest-added first (`added_at` on every row); the 🤖 auto rows stay after, unchanged. The card ➕/➖ symbol list keeps stored add order.
- **Cap.** Unchanged: at the cap an add still replaces the name added first (never a 🎯 A+). The words now say "on your watch the longest".
- **Build at add.** In the window the add route starts the add-time child with `--new-only`: it reads only names with no tile doc, or an add time later than the doc's last write. Cost 1–2 Massive minute calls per added name, single-flight, inside the existing ≤ 90/min budget. Outside the window nothing new is read.
- **Pending tile.** A name with no read yet prints the served words in the tile body (`GajjalaWatchPending.tsx`); after the pending cap it prints the served "still reading" words and keeps filling by itself.
- **View.** Names HE added (and 🎯 A+ names) that are new to this browser join the saved/linked `show=` pick, first, and the first one is outlined and scrolled into view once. 🤖 auto names do not join. A name he hid on purpose stays hidden. A shared link opened cold keeps exactly its own names.
- **✕.** Never disabled by another write; writes run in order and one failure never blocks the next; the tile leaves at once and comes back with the served words if the server refuses.

## HIS CALLs (defaults built)
1. A browser with no `ggw.pickAt` treats his names added in the last 24 h as new (`GGW_NEW_FALLBACK_HOURS`, MINE).
2. A re-add puts the name first but the full-watch cap still removes the name added first — default kept (his 11-18 "oldest added"); alternative: a re-add resets the age.
3. 🤖 auto names join the pick: OFF.
4. A 🤖 potential promoted to A+ in place joins only if seated after his last view.
5. Add-time read cost: 1–2 Massive minute calls per added name.
6. A card ➕ while the Watch is open on page 2+ goes to the top of page 1 but his screen stays on his page.
7. "Still reading": polls every 60 s out of window only; in window the minute re-GET re-reads it.
8. Optimistic ✕ (leaves at once, returns with the served words if refused).
9. A dismiss failure on his own name still answers removed and a 🤖 seat could bring it back.
10. Wording of the pending / still-reading / cap sentences.
11. Served symbols stay in stored add order; only the board rows go newest first.
12. No per-write abort time: a write that never answers holds later ✕ requests in the queue (the tiles still hide at once).

Tests: `test_gajjala_watch_newest_2026_11_19.py`, `test_gajjala_watch_build_now_2026_11_19.py`, `test_gajjala_watch_x_2026_11_19.py`, re-pinned store / replace_oldest / fixes / aplus / api tests; FE `gajjalaWatch.newest.test.ts`, `GajjalaWatchBoard.newest.test.tsx`, `GajjalaWatchBoard.remove.test.tsx`, `GajjalaWatchTile.pending.test.tsx`, `newFeatures.watch_newest.test.ts`.
