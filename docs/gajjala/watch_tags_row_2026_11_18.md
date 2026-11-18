# 🏷️ Tags row above every 👀 Gajjala's Watch tile (2026-11-18)

## The ask, verbatim

Ajay 2026-11-18 ~12:00 ET, with a screenshot of the 👀 Watch tile for SLSN (the head showed only `SLSN 11:49`, ⤢, Yahoo, ✕, then the chart):

> "Also add Short Interest tag and other tags on top of stock ticker information for me to read, like here"

"like here" = his earlier screenshot of the 🚩 Gajjala card grid, where a row of chips sits ABOVE each card (`🩳 SI 2.5M sh · 9.0d · 10/30` · `🧨 room +1.1% · floor not held` · `⛔ not at band`) and the 🧭 stages line (`🎾 Reversal Squeeze · 🧠 potential → today 💋 EMA Kiss & Fly · 🧠 potential 04:21`).

Display only. Nothing rings, orders, sorts or gates. UNMEASURED.

## Where it shows

- **👀 Watch board tile** and its **⤢ stretch view**: a `tags` row is the FIRST child of the tile, above `SYM HH:MM`.
- **Not** on the 🚩 / 🧪 card grid (`GgCardGrid` mounts the same `Tile` without `tags`) and **not** in `GgCardView` (a card's own ⤢). Their DOM is unchanged.

## FE row order (the card's own order)

1. 🚀 `GrowthChip` (only for a name on the 🚀 board; ONE cached `/growth/tags` GET per page).
2. 🩳 `ShortInterestChip`: every Watch name with a served `chip`. **EXTREME → nothing here.** The head's `GgSiExtremeNote` is the ONE SI line on that tile. A stale read prints its served text with its own "stale" word. No record / loading / failed → nothing, never "0".
3. Only for a name **carded on today's 🚩 board**: 🧨 `ExplosiveChip` + 🎯/⛔ `EnterableChip` (fed by ONE `useBounceRoom` POST for the carded names only), 📌/🎪 `GgTraderChip`, 🚫 broker span, Float chip, then the 🧭 `GgStages` line. When no stages block exists, one setup chip per carded setup appears instead, with the served `state_label` on hover.

Every chip wears the house `cm-badge` skin. When nothing would print, the row renders nothing (the DOM stays byte-identical).

## The served `tags` block (backend `chart_maps/gajjala_watch/tags.py`)

Every Watch row now carries `tags`: either `null` (not carded on today's 🚩 board, or the read faulted, never an invented tag) or:

| key | value | source (imported, never retyped) |
|---|---|---|
| `on_board` | `true` | `tags.on_board(doc)` = the 🚩 board's card rule |
| `setups` | `[{setup, label, state, state_label}]` in `GC.SETUPS` order, carded setups only | `tab._setup_label`, `tab.state_label(r, tab._rang(entries_raw, session, SYM, setup))` (the 🚩 tab's own call) |
| `stages` | the 🧭 block, or `null` | `SG.by_symbol(...)` → `SG.for_tile(block, None, session)` (no `here`: no single card) |
| `float` | `{shares, src, text, as_of, suspect}` or `null` | `tab._float_chip(tab._float_read(doc, None))`: the read's own `ctx.float` |
| `broker_text` | `🚫 not eligible at Fidelity` or `null` | `tab.broker_text_for(SYM, flags)`. A broker read **fault** serves `null`, never the seed guess |
| `trader_text` | `📌 handle` or `null` | `trader_names.tag_map(scan docs)` |
| `promo_text` | the 🎪 served text or `null` | `promo_names.tag_map(scan docs)` |

`payload._build` adds `r["tags"] = tags_by.get(r["symbol"])` through a lazy wrapper, `_tags_section`, that calls `importlib.import_module("chart_maps.gajjala_watch.tags").section(...)`. Any fault returns `{}`, and the board still answers. The pending poll (`?symbols=`) passes only its own subset of names.

### "Carded on today's board"

A GG5 reads doc of **this session** (`_id = ST.key(session, SYM)`) counts when it has a setup whose `state ∈ tab.TILE_STATES` (`aplus`, `triggered`, `forming`, `partial`, `stopped`) **and** that setup passes `tab._vcp_listed` (the 🌀 D3 count). This is the 🚩 board's own card test (`tab.py:1905`). Consequences:

- A 🧠 tracker doc is **not** a card. A potential that died this session (its tracker doc is today's, but its read is now `none` / `invalid`) has no card on his board, so it gets **no tags** here. It is also never POSTed for room, and it is never in the stages or scan reads.
- A 🌀 read with fewer than `GC.vcp_list_min_cycles()` contractions is not carded.
- Yesterday's read never tags (the `_id` carries the session).
- 🧪 Audited-only cards (K3S admits) and the retired 1-min page are not sources (HIS CALL #4).

### D10: the `rang` rule for `state_label`

`tab._entry_times(st, window, V.GG5)` is kept **raw** (tri-state) for `tab._rang`:

- `{}`: the ledger read was fine and nothing rang. A `triggered` read says `tab.NO_RING_TEXT` ("…broke on the HH:MM bar, no alert rang"), never "A+".
- `None`: a ledger fault or no handle means the answer is UNKNOWN. Today's words stay as they are; unknown is never "nothing rang".
- A pushed `GG:` claim means the alert rang, and today's words stay.

`entries_raw or {}` is used **only** for `SG.by_symbol`, matching `tab._stage_tag`'s own recipe.

### One clock

`section(names, session, is_today)` takes `_build`'s own `tab.session_for(now)` answer. `tags.py` reads no clock (a source guard pins this). Example: a pre-open Monday (before `GC.PASS_OPEN_ET`) serves Friday's session with `is_today` False, so the stages show Friday's date label and no clock.

## Reads per Watch GET (cost)

| case | reads |
|---|---|
| no Watch name carded today | **1**: the projected reads find (`TAGS_READ_FIELDS = {symbol, setups, ctx.float}`, never the tile bars) |
| at least one carded | 1 reads find + 3 tracker finds (`SC._window`: the session + `GC.STAY_LISTED_SESSIONS` before it) + 1 alert-rows find + 1 broker state find + 1 projected scan find (`SCAN_TAG_FIELDS`, `symbol $in` the carded names only) = **7** |

The GET runs every `GC.GG1M_CADENCE_SEC` while in the window. The 🚩 board GET makes the same reads every 5 minutes. Mongo only: no Massive call, no bar fetch.

**Rejected alternative, kept for HIS CALL #10 (C4):** pass `auto_section`'s whole-session reads (`auto._read_docs`, `ctx` included) and today's tracker docs into `tags.section`. That saves 2 finds, but it means holding every GG5 doc of the session and changing `auto_section`'s return tuple, an 11-17 module that has its own pins. The other option is to build the tags in the minute loop and store them on the tile doc. That makes the serve free of reads but adds a new writer and raises a stale-tags question.

## Tests

- Backend `backend/tests/test_gajjala_watch_tags_2026_11_18.py`:
  - **Positive:** the served block, key by key.
  - **D10 trio:** an empty ledger → `NO_RING_TEXT`; a raising ledger → today's words with the stages still served; a pushed claim → rang.
  - **Carded NEGATIVES:** no doc / none / invalid / a died potential / a tracker doc alone / 🌀 under the D3 count / yesterday's read → `None`; a `partial` read is carded.
  - **Faults:** broker → `broker_text None` even with a seed; tracker → `stages None`; reads → `{}` and the GET still answers 200; a raising tags module → every row `None`.
  - **Projection pins** (checked through recording colls): a board with no carded name makes exactly ONE find; an unlisted `only` name appears in no find.
  - **Clock:** the pre-open Monday case.
  - **Source guards:** no Massive call; no digit in any string constant (checked with `ast`, excluding the module docstring and the two field dicts); no f-string; no clock; no b-word in any served string.
- Moved pin: `backend/tests/test_gajjala_watch_aplus_2026_11_17.py` `test_row_keys_are_the_old_keys_plus_aplus`, whose row key set gains `"tags"`.
- Frontend (WP-B): `gajjalaWatch.tags.test.ts`, `GajjalaWatchTags.test.tsx`, `GajjalaWatchBoard.tags.test.tsx`.

## HIS CALL (defaults built; nothing decided as a rule)

1. **EXTREME names:** the head note (short form `🩳 EXTREME SI 36.4% float`, shipped 11-18) stays, and the tags row prints NO plain SI chip, so each tile has one SI line (default). Alternative: the 🎾 card's label form `🩳 EXTREME SI 36.4% float · 1.0d · 10/30` in the tags row, with the head note dropped (this moves yesterday's pins).
2. **Fitted board tile:** the tags row is ONE line with an ellipsis (the 11-16 GP caption rule; the ⤢ view and the phone wrap). Alternative: wrap on the board tile too (the charts lose a line per wrapped row).
3. **Room / band chips scope:** ONE bounce-room POST for the names CARDED on today's 🚩 board only (default: no on-demand zone building for an off-board name like SLSN). Alternative: every Watch name (his own off-board names would queue daily-bar zone builds on the server).
4. **"Carded on today's board"** = a GG5 reads doc of this session with a setup in `tab.TILE_STATES` that passes the 🌀 D3 count, the 🚩 board's own card rule (`tab.py:1905`). 🧪 Audited-only cards (K3S admits) and the retired 1-min page are not sources. Alternative: add 🧪 through `audited_tab.overlay_reads` (one more call).
5. **Stages `here` highlight:** none on the Watch (no single card). Alternative: bold today's carded setups.
6. **Setup chips print only when there is no stages block** (the setup is named once). Alternative: always print both.
7. **Float chip** reads the pass's own `ctx.float` only. The 🎾 daily-doc fallback (`tab._float_read(doc, daily)`) is not read (it would cost one find per 🎾 name). Alternative: read it.
8. **📌 / 🎪 source tags** are included (one projected scan find per GET). Alternative: drop them (saves one find).
9. **✨ wording** (§4 main-session): his words verbatim; approve or edit.
10. **Cost model:** +7 Mongo reads per Watch GET when a Watch name is carded (+1 when none is), every 60 s in the window. Alternatives [C4]: (a) thread `auto_section`'s reads + today's tracker docs into `tags.section` (−2 finds; `auto.py`'s return tuple changes, 11-17 module); (b) build the tags in the minute loop and store them on the tile doc (read-free serve; a new writer, stale-tags question).
11. **Stale SI** prints the served chip with its own "stale" word (the card's behaviour). Alternative: hide it on the Watch.
12. **GgCardView ⤢ from a card** gets no tags row (default: the card's own chips are on the card). Alternative: pass `tags` there too.
13. **`state_label` as the setup chip's hover** (the long served sentence, with the D10 `rang` answer: a `triggered` read whose alert provably did not ring says "no alert rang", never "A+"). Alternative: no hover.
14. **[C2] A potential that DIED this session** (tracker doc today, read now `none` / `invalid`): no card on his 🚩 board → `tags: null` on the Watch (default: the Watch shows what the board shows). Alternative: serve its 🧭 stages line anyway (the Watch would then show a tag the board does not).
15. **[C6a] 🚀 GrowthChip** included FIRST (his "like here" row starts with it; one cached `/growth/tags` GET per page; renders only for a name on the 🚀 board). Alternative: drop it from the Watch row (the row would then differ from the card's by one chip).
16. **[C6b] Two 🎯 glyphs on one tile:** the head's `🎯 A+` (11-17, "A+ on the Gajjala boards this session") and the row's `🎯 at the band` (the card's enterable chip) mean different things. Default: keep both, each the served word byte-for-byte (Rule #5: one line is his pick). Alternatives: drop the band chip from the Watch row, or drop the head 🎯 when the row prints one.

UNMEASURED. Not advice.
