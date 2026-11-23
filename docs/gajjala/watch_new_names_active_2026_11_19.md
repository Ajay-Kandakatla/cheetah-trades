# 👀 New Watch names are active (2026-11-19)

Ajay, verbatim: "Add things to my auto watch list please and make them active I see not active on my page. Becuz they are in query params".

**Defect.** The board's view lives in the link (`show=`) and in this browser (`ggw.pick`). A pick lists the names on screen, so a name added to the list after the pick was made was never in it — it sat there inactive.

**Change (display only).** `lib/gajjalaWatch.ts` — `ggw.seen` records the list this browser last loaded. On load, a name on the list that was not in `ggw.seen` joins the pick, first (`ggwActivateNew`). The new pick is written back to the link and the browser as every other pick change is.

**Stays as it was.** No pick (the pages) → untouched. A name he saw and left out of the pick stays out. No `ggw.seen` (a shared link opened cold, or a browser from before this build) → nothing is new; the first visit only records it, so a shared link keeps exactly its own names.

**Not done.** Newest-first row order on the board and an `already` re-add moving to the top are separate (still his queued ask). No rule, gate, push or threshold changed. UNMEASURED.

Tests: `gajjalaWatch.activate_new.test.ts`, `GajjalaWatchBoard.link.test.tsx` (two board cases incl. negatives), `newFeatures.watch_activate.test.ts`.

## 2026-11-22 — an add never turns the other names off

Ajay, verbatim: "There is a bug, I added WETO as new one to watch list everything got de activated from watch list".

**Defect.** A saved pick (`ggw.pick` / `show=`) was pruned only by HIS × on that browser. When its names all left the list (a 🤖 name leaving, a replace at the cap, a removal on another device) it sat inert — a pick with no listed name shows the pages. If that dead pick still held the name he then added (or a name the server served again), the pick switched back on with that one name and every other tile and chip went off. Most likely mechanism, reproduced in a test; his browser's saved pick cannot be read from the server.

**Change (display only).** `ggwPrunePick` (lib) — every full load (the activation pass keyed on `ggwRowsKey`) keeps only the pick's names that are listed, plus any name a × is still hiding (so a × that fails comes back ON). None left → null: the pages show, and `ggw.pick` / `show=` are cleared at the load where the pick died. A name served again then joins ONLY by the existing fresh rule (his names and 🎯 A+ join; an ordinary 🤖 potential does not). `ggwJoinPick`, `ggw.seen`, `ggw.pickAt`, the cap (18), row order, sections, gates and pushes are unchanged; no backend change.

Tests: `GajjalaWatchBoard.add_keeps_active_2026_11_22.test.tsx` (phone + desktop per=4 add, live pick + add, server removal / replace / all-stale / junk link, × and failed ×, 🎯 A+ join, stale 🤖 not taking over, pages view), `gajjalaWatch.prune_pick_2026_11_22.test.ts`.

**Review residual (same day).** The prune alone misses a dead pick whose name is re-added ELSEWHERE (a card ➕ or another device) before this browser reopens the Watch: at the first load the name is already listed, so the prune keeps it. `ggwLivePick` — a pruned pick whose names were ALL added after this browser's `ggw.pickAt` cannot be his pick of them → null (the pages). No `ggw.pickAt` on this browser (a shared `show=` link, a cold browser) → the pick is honoured; a name he picked himself after it was added (pickAt later than its add) stays. Tests: `GajjalaWatchBoard.dead_pick_elsewhere_2026_11_22.test.tsx` (phone + desktop NEGATIVES, live pick, shared link, his own later pick); a mutation that keeps the pick fails both NEGATIVES.
