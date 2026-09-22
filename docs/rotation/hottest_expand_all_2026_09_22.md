# 🔥 Hottest — the 🌀 AMD column and ⊞ Expand all (frontend), 2026-09-22

The surface half of the 2026-09-22 build. The read itself, every sentence it
prints and every count under the table are the backend's
(`backend/rotation/hottest_amd.py`, written up in
`docs/rotation/hottest_amd_column_2026_09_22.md`). This page covers what the
page does with them, and the second thing he asked for in the same message.

## 0. The ask, verbatim

Ajay, 2026-09-22, with a screenshot of the 🔥 Hottest tab showing the Defense
roster expanded (KRMN, RCAT, LASR, KTOS, ONDS, BBAI):

> "Add an AMD tag for these. like a column for me to see which one are getting
>  manipulated. Also give me toggle option to open them app on one click in
>  stead of clicking on the carets"

Two things, one message: a column, and a way to stop clicking carets.

---

## 1. The 🌀 AMD column

**Files.** `frontend/src/lib/hottestAmd.ts` (new),
`frontend/src/components/HottestSectors.tsx`, `frontend/src/styles.css`.

### What this surface is allowed to do

Turn a served `amd` cell into text, a tone and a title. It composes no
sentence, formats no number, parses no date and constructs no `Date` (banned in
every FE file in this app). The wording comes from
`supply_demand.turning_bullish.verdict_text` by way of the backend module — the
same wording engine the 🌀 AMD tab in Chart Maps draws, so the two surfaces
cannot drift into different words for the same cycle phase.

### Placement: immediately after Sector / Name

It shipped LAST on the morning of 2026-09-22. He came back the same day, with a
screenshot of the board scrolled to the Crypto-equities roster:

> "last column is hidded"

He was right. The header read **🌀 A** and the cells read **AM** — the column
was clipped off the right edge of his window. A column he has to scroll
sideways to read does not answer *"a column for me to see which one are getting
manipulated"*.

`visibleCols()` now reads `[🌀 AMD?] + [☀️ Pre-mkt?] + HS_COLS`.

**Why beside the name.** 🌀 AMD is a **state about the name**, and the
Sector / Name cell already carries this row's other per-name state chips —
floor-held, at-band, 🚀 growth, 🎪 promo origin. A state belongs beside the
thing it describes. And the ranked numeric legs (Pre-mkt | Today | 5 days |
21 days) stay **contiguous and in order**, which they do not when a state
column is wedged in after them. Pre-mkt still leads the ranked legs, the way
they already read newest-first, and `HS_COLS` keeps its order untouched. Both
extras stay conditional on the server saying so, so neither adds a column of
em-dashes on a board he already called wide. `colSpanOf()` derives from
`visibleCols().length` — a count, order-independent — so every grain row,
"showing N of M" row and 📰 briefing row spans the whole table before and
after the move, pinned against the rendered header count.

**This does not make the table fit, and no sentence here decides which column
gives way instead.** The move costs nothing in width. `.hs-table` sets
`min-width: 900px` (760px inside the `@media (max-width: 720px)` block) and
this table prints up to **twelve** columns — Sector / Name, 🌀 AMD,
☀️ Pre-mkt and the nine in `HS_COLS`. It scrolled sideways on a narrow window
before the move and it scrolls sideways after it. What the move buys is the
**scroll position**: the state is now the first thing right of the name, so he
reads it without moving anything, which is what he asked for.

**No estimated px figure is quoted on this page.** The version of this doc
written with the change carried an arithmetic width model — an overflow, a
saving, a per-column width for Next ER — built from measured character counts
and *assumed* per-character advances, with no browser ever opened. Rule #1 does
not take a model for a measurement, so those figures are gone rather than
hedged, and none is repeated here for a skimmer to pick up. What is left is
what the source says: the `min-width` values above, the column count, and the
fact that the scroll did not end. The figures that stay are the ones actually
measured off the live payload — character counts and cell counts, in
`docs/rotation/hottest_amd_column_2026_09_22.md`.

**Which column gives way is HIS call, and it is open (§ His call, item 8).**
The earlier draft of this page nominated Next ER as the expendable one. That
was a reviewer-agent deciding which of his columns he loses, which is not ours
to decide — before 🌀 shipped, Next ER was visible at every width where
this board was. The only change that ends the sideways scroll is dropping or
narrowing one of the twelve columns, and that is a board decision.

**The widest state of this table is its PRE-OPEN state**, which is exactly when
he reads the ☀️ board. `d1Label()` prints `Today` only when `d1.live` is true;
otherwise it prints `Last close YYYY-MM-DD`
(`frontend/src/components/HottestSectors.tsx`), and `rotation/hottest.py` sets
`live: False` on every closed-session path — every pre-market and after-hours
read, the `basis=premarket` board included. So the day column's header goes
from one word to twenty-odd characters precisely when he is looking. Any future
measurement of this table has to be taken in **both** header states or it is
quoting the narrow one.

**On a phone** (the `@media (max-width: 720px)` block) the move pushes every
ranked leg one column further right, because 🌀 now sits between the name and
them. Nothing in this change picks a phone layout: the one mobile edit is
`.hs-amd { font-size: 0.70rem }`, which changes no column's presence. Wrapping
the cell there, or not drawing the column on a phone at all, is on the same
his-call list (item 9).

**`visibleCols()` feeds only the `<thead>`.** Every `<tbody>` cell is a JSX
literal in fixed order, so the header and five render sites — the `<td>` in
`NameRow` and `<AmdGroupCell>` on the roster, sector and industry rows — move
in lockstep or the whole board reads one column off. The group rows are the
sneaky half: `GroupFundCells` ends with an empty `<td className="hs-spacer">`
standing in for Next ER, so a mis-ordered group row still has the correct
**cell count** and no colSpan check would catch it. That is why the test pins
the **class of the second `<td>`** on each row kind, not a count.

**§7.2 is closed**, answered by him on 2026-09-22.

### The header does not sort

A non-sorting column renders a plain `<span className="hs-head">`, not a
`<button className="hs-sort">`, with no `aria-sort`. `.hs-head` already existed
in `styles.css` — no new token. The caption above the table says "click any
column header", and a header that looks like the others and does nothing is
worse than one that never offered. (No ordinal in that sentence on purpose —
the count and the order of these columns both change; the argument does not.) `'amd'` is never added to the
backend's `SORT_KEYS` either, so the key cannot arrive through the URL.

Why: the read is measured **inverted on its own claim** —
`51.9% vs 56.1%, −4.2pp [−6.92, −1.89]` against a bar inside its own live base
at the same distance below the top, negative in all seven distance buckets
(re-measured 2026-09-14, `backend/scripts/turning_bullish_amd_study.py`,
`docs/supply_demand/turning_bullish.md`). Ranking a board he trades on a read
measured going the wrong way is the one thing a sort would do.

**His call (§7.1):** make it sortable anyway?

### Why the column is colourless

`amdCell()` returns tone `dim` for **every** grade. The served tone (`good` for
`raided`, `warn` for `failed`) rides in the payload for fidelity and for the 🌀
tab, and is deliberately not mapped to a colour here; the served
`no_colour_reason` is appended to each cell's hover so the refusal is readable
rather than silent. In the backend's own words (constant
`rotation.hottest_amd.NO_COLOUR_REASON`, never retyped on this surface): the 🌀
AMD tab paints "raided" green, and that is the exact state measured −4.2pp
against its own placebo — a green cell scanned at a glance down 600 ranked rows
*is* a ranking, and this read is not one.

`AMD_TONE_CLASS` still holds `hs-amd-good` / `hs-amd-warn` as **whole tokens**,
and `styles.css` carries rules for both, so turning colour on later is a
one-line change. No class is ever built by concatenation anywhere:
`contracts.mjs:1729-1746` harvests every `hs-[a-z0-9-]+` out of the raw TSX
text — comments included — and `'hs-amd-' + tone` would ship `hs-amd-` as a
class with no rule and turn the build red.

**His call (§7.10):** turn colour on, knowing green lands on `raided`?

### Group rows are blank, with a reason

Roster, sector and industry rows print an em-dash carrying the served
`group_note`. A cycle phase has no median, and a per-state count over the 25
names the payload carries would describe a different population from the
medians beside it — those are the **full** membership. That is the exact "two
populations blended" failure `hottest.py`'s docstring exists to prevent. The
counts live in one served sentence under the table (`data-testid="hs-amd-note"`),
which also carries the sweep's ET date and the staleness verdict.

**His call (§7.3):** a per-state member count on each group row instead?

### When the read is missing

`showAmdCol()` is false both when `amd_summary` is absent entirely (the
member-table-unavailable branch never attaches it) and when the backend says
`available: false`. The column then does not draw at all and the served
`unavailable_note` prints under the table instead — 1,476 em-dashes is
furniture (Rule #5), and silence is a lie.

### A blank is never a zero

`known: false` → em-dash plus the served sentence, which says in as many words
that a blank is **not** "no cycle" and **not** "clean" — it is unknown. A
served `known: true` with no wording is a backend bug, and the FE belt still
renders an em-dash with a "Not read:" hover rather than an empty cell. The
string "AMD no cycle" — what `turning_bullish.py:361`'s `or table["none"]`
fallback would lend an ungradeable row — reaches no cell on this board.

---

## 2. ⊞ Expand all

**Files.** `frontend/src/components/HottestSectors.tsx`.

### The depth follows the view, and that is load-bearing

`HottestSectors.tsx` renders a sector's **industries** when "Break into
industries" is on, and its own **names** only when it is off — and that
checkbox defaults to **on**. So in the view that actually loads, a sector's
names hang off the *industry* caret, not the sector's. A "top level only" rule
would have answered his ask for the rosters in his screenshot and opened eleven
sectors into 136 empty industry headers, leaving him clicking carets.

```
inheritsAll(k, byIndustry):
  k endsWith '|tag'  → false      📰 news briefings: NEVER
  k includes  '|i:'  → byIndustry industry rows draw only in that view
  otherwise          → true       t:* rosters and s:* sectors
```

`isGroupOpen(o, k, byIndustry)` gives an explicit per-caret entry precedence
over the blanket answer, so a caret he closes by hand under ⊞ stays closed, and
flipping the checkbox re-derives the depth from the view without touching
anything he moved. There is one state, not two.

**The 📰 guard.** The news-tag rows share the very same open map
(`${k}|tag`, `HottestSectors.tsx:1150,1171` on the pre-change file). Without
the `endsWith('|tag')` clause, one click dumps every LLM briefing into the
table. It is a pinned negative test in both views.

### What one click really costs — measured, on the live payload

Captured from the running API on 2026-09-22 (`GET /rotation/hottest`, 17
rosters · 11 sectors · 136 industries) and rendered through the real component:

| | rows |
|---|---|
| **deep** (`byIndustry` on — the default) | **1,791** = 136 industry rows + 1,655 name rows |
| shallow (`byIndustry` off) | 518 |
| 📰 briefing rows opened | **0**, in either view |
| group keys the click opens | 164 |

The button's hover publishes the deep number for the board in front of him,
computed from that payload by `expandRowCount()` — a fact, not a guess.

**jsdom, not his browser:** the click took **502 ms** in jsdom on this Mac.
jsdom has no layout, no paint and no compositor, so that number bounds nothing
about what his laptop does with 1,791 `<tr>`s; it is reported because it was
measured, not because it predicts anything.

**His call (§7.4):** keep the deep default, or (b) top level only with the
checkbox flipped off first, or (c) deep for the rosters only.

### The choice is remembered

`HS_EXPAND_KEY = 'hs.expandAll'`, values `'open'` / `'closed'`, absent = closed.
Both the read and the write are wrapped in try/catch, so a private window or
blocked site data is a `null` rather than a crash. This is the `pcw.capFloor`
shape and the first preference this board has ever persisted — one scheme, not
two, and individual caret positions are **not** persisted (26+ of them is a
different feature he did not ask for).

**His call (§7.5):** a persisted "open" now renders the deep set on every
visit. If the page feels slow on his laptop, the fix is to stop persisting
"open" — not a row cap invented here.

### Clutter, one line

Six controls on one row now. ⊞ sits beside "Break into industries" and not
beside ↻ / ☀️ because both of those change what the board **fetches** while
these two change what it **shows** — and in the default view it removes ~150
caret clicks a visit, not 28.

---

## 3. Tests

| file | what it pins |
|---|---|
| `frontend/src/lib/hottestAmd.test.ts` (30) | the CELL prints the served **short** and the hover keeps the served **long**, both grades; **NEGATIVE: an arbitrary served short is printed verbatim** — proof this file does no string surgery; **NEGATIVE: no served short → the served long text, unchanged, never a locally shortened one**; **no cell ever yields `hs-amd-good`/`hs-amd-warn`** for any served tone; `amdToneClass` returns a whole token for junk, blank and `undefined`; a blank is an em-dash with a worded reason and wears **none** of the served `grade_labels` words, in cell or hover; a short cannot resurrect a row with no long text; `showAmdCol` false with no block and with `available:false`; `inheritsAll` / `isGroupOpen` in both views |
| `frontend/src/components/HottestSectors.amd.test.tsx` (17) | the header renders **second, after Sector / Name**, is a `<span>`, sorts nothing and fires no second fetch; `visibleCols` puts 🌀 first and the ranked legs **contiguous and in `HS_COLS` order**, with and without ☀️ Pre-mkt; **NEGATIVE: no `amd_summary` → the first column is a ranked leg and `'amd'` appears nowhere**; `colSpanOf` is 10/11 and always `1 + visibleCols().length` — a count, unchanged by the move; the 🌀 cell is the **second `<td>` on every row kind** (name, roster, sector, industry — the pin that catches a mis-ordered group row, whose `hs-spacer` keeps the cell count right); every full-width row spans the **rendered** header count; KRMN prints the served short with the long on the hover, and a row with **no** short prints the long whole; **NEGATIVE: sentinel wordings prove the component composes nothing**; group rows blank and carry none of the served grade words; `available:false` drops the column and prints the served line; the stale sentence reaches the screen; row order and the ranked-on caption byte-identical with and without the block |
| `frontend/src/components/HottestSectors.premarket.test.tsx` (22) | rebound off column indices: Pre-mkt leads the **ranked legs** (not "is column 1"), the four legs run newest-to-oldest unbroken, and the cell is located through `visibleCols()` rather than `td[1]` — so the assertions keep meaning what they say now that 🌀 AMD sits in front |
| `frontend/src/components/HottestSectors.expand.test.tsx` (16) | one click in the **default** view renders the roster's six **and** a provider sector's name rows under their industry; the shallow view has no industry row to open; no 📰 briefing opens in either view; collapse returns the board to its mount state; a caret closed by hand under ⊞ stays closed; the hover carries the exact row count; persistence across remount; a throwing `localStorage` still toggles; a sector that only appears in the second payload renders open; the toggle reorders nothing |

`npx vitest run` — **3,288 passed / 193 files** (2026-09-22, after the move,
the short form and the width guards). `npx tsc --noEmit` clean. `node scripts/contracts.mjs` —
**87/87**, including the `hs-*` class sweep for the four whole tokens
(`.hs-amd`, `.hs-amd-dim`, `.hs-amd-good`, `.hs-amd-warn`). No CSS token was
added by the move; the one CSS edit is `.hs-amd { font-size: 0.70rem }` inside
the existing `@media (max-width: 720px)` block, because the cell set its own
size and so did **not** shrink with the table — at 0.74rem against the table's
0.72rem it rendered as the largest text in the table on the narrowest screen.

---

## 4. His call, in one list

1. **Sorting** — shipped not sortable. Make it sortable? (§7.1)
2. **Column position** — **ANSWERED 2026-09-22.** Shipped last; he replied
   *"last column is hidded"* over a screenshot of it clipped off the right
   edge. Moved to sit immediately after Sector / Name, where he reads it
   without scrolling. §7.2 is closed.
3. **Group rows** — shipped blank with a reason. A per-state count instead? (§7.3)
4. **Expand depth** — shipped deep in the default view: **1,791 rows** on the
   live payload. Keep, top-level-only, or rosters-only? (§7.4)
5. **Persisted default** — "open" now means the deep set every visit. (§7.5)
6. **Colour** — shipped colourless. Turn it on, knowing green lands on
   `raided`, the state measured −4.2pp against its own placebo? (§7.10)
7. **"Make manipulation better"** stays UNANSWERED from 2026-09-21
   (memory `cheetah_amd_manipulation.md`). Nothing here guesses at it.
8. **Which column gives way on a narrow window — OPEN, and it is a board
   decision.** The move changed the scroll POSITION, not the scroll: with
   twelve columns against a 900px floor this table still runs off the right
   edge of a narrow window, and it did before 🌀 shipped too. The only thing
   that ends it is dropping or narrowing one of the twelve. Nothing here picks
   a victim — the earlier draft of this page named Next ER, which was a
   reviewer deciding one of his columns for him, and that sentence is gone.
   Candidates if he wants one: **Next ER** (a date he can get on the ticker
   page), **Sales trend** (a word that repeats what Sales YoY already ranks),
   **Quality**. Remember while choosing that the day column is at its widest
   pre-open (`Last close YYYY-MM-DD`), which is when he reads the ☀️ board.
9. **What a phone shows — OPEN.** 🌀 now sits between the name and the ranked
   legs, so on the `@media (max-width: 720px)` layout every ranked leg is one
   column further right than it was. Two presentation-only options, both inside
   the existing media block, neither taken: **(a)** let the cell wrap there —
   `.hs-amd { white-space: normal; }` — which narrows the column at the cost of
   two-line rows; **(b)** do not draw the column on a phone at all, which needs
   a class on the 🌀 `<th>` first (the header currently renders
   `className={c.num ? 'hs-num' : ''}`, so there is no hook to hide header and
   cells together). Shipped as neither: the one mobile edit in this change is
   `.hs-amd { font-size: 0.70rem }`, which moves no column.

Nothing on this surface is measured, nothing is a gate, nothing pushes, and no
threshold was invented. **No ESTIMATED px figure is quoted anywhere on this
page** — the width model that was here was an arithmetic estimate, not a
measurement. The `px` values that remain are `styles.css`'s own `min-width`
declarations, read off the source.
