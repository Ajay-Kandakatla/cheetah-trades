# 👀 New Watch names are active (2026-11-19)

Ajay, verbatim: "Add things to my auto watch list please and make them active I see not active on my page. Becuz they are in query params".

**Defect.** The board's view lives in the link (`show=`) and in this browser (`ggw.pick`). A pick lists the names on screen, so a name added to the list after the pick was made was never in it — it sat there inactive.

**Change (display only).** `lib/gajjalaWatch.ts` — `ggw.seen` records the list this browser last loaded. On load, a name on the list that was not in `ggw.seen` joins the pick, first (`ggwActivateNew`). The new pick is written back to the link and the browser as every other pick change is.

**Stays as it was.** No pick (the pages) → untouched. A name he saw and left out of the pick stays out. No `ggw.seen` (a shared link opened cold, or a browser from before this build) → nothing is new; the first visit only records it, so a shared link keeps exactly its own names.

**Not done.** Newest-first row order on the board and an `already` re-add moving to the top are separate (still his queued ask). No rule, gate, push or threshold changed. UNMEASURED.

Tests: `gajjalaWatch.activate_new.test.ts`, `GajjalaWatchBoard.link.test.tsx` (two board cases incl. negatives), `newFeatures.watch_activate.test.ts`.
