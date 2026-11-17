# 🎯 A+ tag on 👀 Gajjala's Watch (2026-11-17)

Ajay 2026-11-17 ~12:58 ET, verbatim: "Also add an A+ tag on watch list as they become A+".

## 🎯 A+ tag

**What it shows.** Every Watch row (his names and the 🤖 auto names) carries a served `aplus` block when any Gajjala
board's stored read of that name this session has a setup in `tab.MARKED_STATES`: A+, A+ (triggered), A+, then stopped.
The tile head prints the chip `🎯 A+ HH:MM` right after the ticker (the first item's clock), and its hover lists every
board, setup and state. The ticker button in the pager gets a 🎯 prefix and a green outline.

**Display only.** Nothing pushes, rings, claims, gates or gets written. UNMEASURED.

**Where it reads (backend `chart_maps/gajjala_watch/payload.py` → `aplus_section`).**
- 🚩 5-min: GG5's `gajjala_reads`. 🚩 1-min: GG1's `gajjala_1m_reads`. Each store gets ONE projected
  `find({_id: {$in: [store.key(session, SYM)…]}}, {symbol, setups, updated_at})` per Watch GET. The tile bars are never
  loaded and nothing is fetched from Massive. A read from another session never matches, because the date is part of
  the `_id`.
- 🧪: the 🧪 board's own function, `audited_tab.overlay_reads`, which `tab.py` calls on GG5's reads. It is reused as is
  on the GG5 reads above: one more read of the 🧪 overlay docs, nothing re-implemented. If the audit holds a 🚩 A+, its
  state is served as `aplus_held` and no 🧪 item appears; the 🚩 item stays. A K3S admit can be a 🧪-only A+. When the
  overlay is older than the read, or no overlay is on file yet, the 🧪 board serves the 🚩 A+ as it is, and so does the
  tag. `updated_at` is in the projection only because the overlay's freshness check reads it.
- Items are ordered by clock (one with no clock goes last), then by `GC.SETUPS` order, then by board (🚩 5-min, 🚩 1-min, 🧪).
- If any read fails or a store handle is missing, every row serves `aplus: null` and the board still answers.

**Words.** All words are constants in `payload.py`: `APLUS_TEXT`, `APLUS_TEXT_AT`, `APLUS_WORDS`, `APLUS_ITEM_TEXT`,
`APLUS_ITEM_NO_TIME_TEXT` and `APLUS_TITLE_TEXT`. `APLUS_WORDS` copies the inline map in `tab.recap` (tab.py ~1796),
which is a dict literal there and not a constant. A test pins its keys to `MARKED_STATES` and checks that each word
matches what `recap` serves. The board names come from `C.AUTO_SOURCE_WORDS` and the setup names from `tab._setup_label`.

**Frontend.** `lib/gajjalaWatch.ts` (`GgwRowAplus`, `parseRowAplus`; junk → null), `GajjalaWatchTile.tsx` (the
`.ggw-chip.ggw-aplus` chip), `GajjalaWatchBoard.tsx` (pager prefix = the served `tag`, class `ggw-pager-sym--aplus`) and
`styles/gajjalaWatch.css` (`--positive` outline, readable in both themes; the chip wraps at 430 px).

**Tests.** `backend/tests/test_gajjala_watch_aplus_2026_11_17.py` and
`frontend/src/components/GajjalaWatchBoard.aplus.test.tsx`.
