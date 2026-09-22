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

### Placement: LAST, after Next ER

`visibleCols()` now reads `[☀️ Pre-mkt?] + HS_COLS + [🌀 AMD?]`. Pre-mkt leads
because the legs already run newest-first; 🌀 AMD trails because it is not a
ranked leg — it is a state, and the nine columns before it are the ones the
board is ordered by. Both are conditional on the server saying so, so neither
adds a column of em-dashes on a board he already called wide. `colSpanOf()`
derives from `visibleCols()`, so every grain row, "showing N of M" row and 📰
briefing row widened with the column and none of them is a cell short.

**His call (§7.2 of the spec):** last, or first beside the symbol where he sees
it without scrolling an eleven-column table.

### The header does not sort

A non-sorting column renders a plain `<span className="hs-head">`, not a
`<button className="hs-sort">`, with no `aria-sort`. `.hs-head` already existed
in `styles.css` — no new token. The caption above the table says "click any
column header", and a tenth header that looks like the other nine and does
nothing is worse than one that never offered. `'amd'` is never added to the
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
| `frontend/src/lib/hottestAmd.test.ts` (27) | the served text/title verbatim; **no cell ever yields `hs-amd-good`/`hs-amd-warn`** for any served tone; `amdToneClass` returns a whole token for junk, blank and `undefined`; a blank is an em-dash with a worded reason and never the phrase "AMD no cycle"; `showAmdCol` false with no block and with `available:false`; `inheritsAll` / `isGroupOpen` in both views |
| `frontend/src/components/HottestSectors.amd.test.tsx` (10) | the header renders, is a `<span>`, sorts nothing and fires no second fetch; KRMN prints its served words and BBAI an em-dash with the reason; group rows blank; `available:false` drops the column and prints the served line; a payload with **no** `amd_summary` draws no column and no em-dashes; the stale sentence reaches the screen; row order and the ranked-on caption byte-identical with and without the block |
| `frontend/src/components/HottestSectors.expand.test.tsx` (16) | one click in the **default** view renders the roster's six **and** a provider sector's name rows under their industry; the shallow view has no industry row to open; no 📰 briefing opens in either view; collapse returns the board to its mount state; a caret closed by hand under ⊞ stays closed; the hover carries the exact row count; persistence across remount; a throwing `localStorage` still toggles; a sector that only appears in the second payload renders open; the toggle reorders nothing |

`npx vitest run` — 3,271 passed / 192 files. `npx tsc --noEmit` clean.
`node scripts/contracts.mjs` — 85/85, including the `hs-*` class sweep for the
four new whole tokens (`.hs-amd`, `.hs-amd-dim`, `.hs-amd-good`,
`.hs-amd-warn`).

---

## 4. His call, in one list

1. **Sorting** — shipped not sortable. Make it sortable? (§7.1)
2. **Column position** — shipped last, after Next ER. First instead? (§7.2)
3. **Group rows** — shipped blank with a reason. A per-state count instead? (§7.3)
4. **Expand depth** — shipped deep in the default view: **1,791 rows** on the
   live payload. Keep, top-level-only, or rosters-only? (§7.4)
5. **Persisted default** — "open" now means the deep set every visit. (§7.5)
6. **Colour** — shipped colourless. Turn it on, knowing green lands on
   `raided`, the state measured −4.2pp against its own placebo? (§7.10)
7. **"Make manipulation better"** stays UNANSWERED from 2026-09-21
   (memory `cheetah_amd_manipulation.md`). Nothing here guesses at it.

Nothing on this surface is measured, nothing is a gate, nothing pushes, and no
threshold was invented.
