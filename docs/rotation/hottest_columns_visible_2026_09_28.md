# 🔥 Hottest — every column reachable, multi-column sort UX, ⓘ Quality (frontend, 2026-09-28)

Branch `feat/hottest-columns-multisort-quality-2026-09-28`. Backend side (the
`then_by` wire format, the tie rule, the served `quality_info`):
`docs/rotation/hottest_multisort_quality_2026_09_28.md`.

## 0. The ask, verbatim

> "Can you fix the horizontal columns hiding and also can you help me with
> multi column sort also can you help with info icon on the quality?"

Said over a screenshot of the 🔥 Hottest name rows whose last column read only
"N" — Next ER, cut.

## 1. Why Next ER was cut — the root cause

The 2026-09-22 answer to *"last column is hidded"* moved 🌀 AMD out of last
place (`docs/rotation/hottest_expand_all_2026_09_22.md`). It changed which
column was last; it never touched why the last one was cut.

- `.hs` is declared twice in `frontend/src/styles.css`: the Hot-sectors
  strip's rule (`display:flex; flex-wrap:wrap; align-items: baseline; …`) and
  the table's rule (`display:flex; flex-direction:column; gap`). The table rule
  never resets `align-items`, so the table's `.hs` is a column flexbox whose
  children are **not stretched** — each is sized to its own content.
- `.hs-scroll` (`overflow: auto`) was a direct child of that flexbox, so it
  grew to the table's min-content width (`.hs-table { min-width: 900px }`,
  nowrap headers, `.hs-sym { min-width: 190px }`, real name cells with chips).
  A box as wide as its content has **nothing to scroll**.
- `html { overflow-x: hidden }` (the app-wide sideways guard) then cut
  everything past the viewport. The right-hand columns were not "off to the
  side", they were **unreachable**.

## 2. The fix — at the cause, nothing dropped

- A wrapper `.hs-scrollwrap` is now the direct flex child of `.hs`:
  `align-self: stretch; min-width: 0; max-width: 100%`. The stretch has to sit
  on the DIRECT flex child (probe-checked: on an inner element it does
  nothing). `.hs-scroll` keeps `overflow: auto` + its `max-height` (the sticky
  header needs both) and gains `min-width: 0; max-width: 100%`. So the box is
  as wide as the page and scrolls sideways **inside itself**, at every width.
- **Sector / Name is sticky** on the left (`td.hs-sym` / `th.hs-sym`,
  `position: sticky; left: 0`), with an opaque background per row kind (the
  industry row's own background is translucent, so it gets an opaque twin); the
  header corner sits above both sticky axes (`z-index: 3` over the headers'
  `2`). A soft shadow marks the edge once the box is scrolled.
- `.hs-table` switched `border-collapse: collapse` → `separate` with
  `border-spacing: 0`: a collapsed border is painted by the table, so under a
  sticky cell the row separators scroll away from it. Cells only draw a bottom
  border, so the look is unchanged.
- **Full-width rows** (grain labels, 📰 day-tags, "showing N of M") wrap their
  content in `.hs-rowpin` — `position: sticky; left: 0; max-width:
  calc(var(--hs-box-w) - 16px)` — so their text wraps at the visible box and
  stays put while the columns scroll under it. `--hs-box-w` is written on the
  box by `useHScrollCue`, never typed in the TSX.
- **"N more columns →"** (`frontend/src/hooks/useHScrollCue.ts`): a fade on
  the right edge plus a small button naming the off-right columns (labels from
  `colLabel`, never the header text, which carries ⓘ and 2▼). It re-measures
  on scroll, when the box resizes, when the **table** resizes (opening a group
  widens the table without resizing the box — both are observed), and when the
  data / `open` / `byIndustry` change. The button scrolls the box 80% of its
  width.
- Untouched on purpose: `.hs` itself (the strip shares it), `html`/`body`
  overflow (the app-wide guard and every sticky header depend on it),
  `.hs-embed`, every column and its data, the 720px media block (no
  `display: none`).

### Real-browser probe

`frontend/scripts/hottest-layout-probe.mjs <snapshot.html>` renders a snapshot
of the real component with **all eight** of the app's stylesheets in
`main.tsx`'s import order, inside the page's `.app > main.main > .cm-page`
chain, in headless Chrome, one same-origin iframe per width (a true viewport,
so 390 is real). The snapshot comes from
`HS_LAYOUT_SNAPSHOT=<file> npx vitest run src/components/HottestSectors.layout.test.tsx`
(hand-written fixture, every group expanded, one 📰 day-tag open).

Run 2026-09-28 on that fixture snapshot:

| viewport | box / content | scrolls | wrap ≤ .hs | page | last header reachable | sticky Δpx | pins | result |
|---|---|---|---|---|---|---|---|---|
| 1440 | 1336 / 1336 | no | 1336 ≤ 1336 | 1440 | yes (Next ER) | 0 | 5 | PASS |
| 1280 | 1176 / 1176 | no | 1176 ≤ 1176 | 1280 | yes (Next ER) | 0 | 5 | PASS |
| 1024 | 920 / 950 | yes | 920 ≤ 920 | 1024 | yes (Next ER) | 0 | 5 | PASS |
| 768 | 664 / 950 | yes | 664 ≤ 664 | 768 | yes (Next ER) | 0 | 5 | PASS |
| 390 | 322 / 992 | yes | 322 ≤ 322 | 390 | yes (Next ER) | 0 | 5 | PASS |

Mutation checks (`HS_PROBE_EXTRA_CSS` appends CSS after the app's):

- stretch undone (`.hs-scrollwrap{align-self:auto;min-width:auto;max-width:none}`)
  → **1024, 768, 390 FAIL**: the box shrink-wraps to 950 / 950 / 992 inside a
  920 / 664 / 322 parent and Next ER ends past the viewport — the reported bug.
- sticky undone (`.hs-table td.hs-sym{position:static}`) → every width that
  scrolls FAILS (Sector / Name leaves the box).
- row pin undone (`.hs-rowpin{position:static;max-width:none}`) → FAILS on
  every pinned row.

The fixture's name cells are narrower than live ones, so at 1440/1280 its table
fits. **The number to quote is the real-payload run below.**

**Real-payload run (2026-09-29 00:2x ET, the one to quote).** Snapshot from
`HS_LAYOUT_SNAPSHOT=<file> npx vitest run src/components/HottestSectors.realpayload.test.tsx`
— the branch API's own answer to
`?names=3&sort=eq_score&dir=desc&then_by=q_eps_yoy:desc` (fixture
`frontend/src/components/__fixtures__/hottest_real_2026_09_28.json`: 2 rosters,
3 sectors × 2 industries × 3 names, every group expanded, 🌀 AMD column on,
Pre-mkt not served), same probe, all eight sheets:

| viewport | box / content | scrolls | wrap ≤ .hs | page | last header reachable | sticky Δpx | pins | result |
|---|---|---|---|---|---|---|---|---|
| 1440 | 1336 / 1336 | no | 1336 ≤ 1336 | 1440 | yes (Next ER) | 0 | 9 | PASS |
| 1280 | 1176 / 1176 | no | 1176 ≤ 1176 | 1280 | yes (Next ER) | 0 | 9 | PASS |
| 1024 | 920 / 1007 | yes | 920 ≤ 920 | 1024 | yes (Next ER) | 0 | 9 | PASS |
| 768 | 664 / 1007 | yes | 664 ≤ 664 | 768 | yes (Next ER) | 0 | 9 | PASS |
| 390 | 322 / 1021 | yes | 322 ≤ 322 | 390 | yes (Next ER) | 0 | 9 | PASS |

Stretch undone on the same real snapshot → **1024, 768, 390 FAIL** (the box
shrink-wraps to 1007 / 1007 / 1021 and Next ER ends past the viewport).

**WebKit / Safari was NOT machine-checked** — there is no WebKit engine on this
Mac; one iPhone look on the live page is his.

## 3. Multi-column sort — the frontend half

`frontend/src/lib/hottestSort.ts` (pure: no `.sort(`, no clock, no set*):

- **Plain click = today's click**, byte for byte on the client state: a new
  column opens at its default direction (DESC; Next ER ASC), the active one
  flips — and the tie-breaks are cleared. The URL of a single-key read is
  identical to before (`thenByParam([]) === ''`).
- **Shift / ⌘ / ctrl-click** adds a tie-break; clicking a tie-break again flips
  it, a third time removes it; shift-clicking the primary flips it and keeps the
  tie-breaks. At the cap (`sort_max_keys`, default `HS_MAX_SORT_KEYS = 3`,
  pinned equal to `hottest.py MAX_SORT_KEYS` by contract) nothing changes and
  nothing is fetched.
- **Touch**: a "+ then by…" select beside "ranked on" (disabled when the plan is
  full), each served tie-break is a tappable "then Q EPS ▼" (tap flips, tap
  again removes), and "✕ clear" returns to 5 days ▼ with no tie-breaks (hidden
  when already there).
- **Every mark follows `sortBasis()`**: once a read has landed it is the
  SERVED plan (`sorted_dir`, `sorted_then_by`); while a read is in flight it is
  the request. Headers read `5 days 1▼`, `Q EPS 2▼`; one key reads exactly as
  before (`▼`/`▲`). `aria-sort` sits on the primary only; secondaries carry
  `data-sort-priority`. A key the server dropped never shows a mark and never
  eats a slot. The primary KEY keeps the pinned `shownSortKey` rule (state wins
  except a demoted ☀️ `pre_1d`).
- ☀️ Pre-market clears the tie-breaks (one fetch). No sort is persisted — it
  never was (his call below).
- The board ⓘ's sort paragraph now describes tie-breaks and the tie rule
  (names A→Z; sectors, industries and rosters keep their usual order).

## 4. ⓘ Quality — the frontend half

- `InfoButton` gained an opt-in `sheet` mode: the pop is portalled onto
  `<body>` as a fixed sheet (a popover inside the `overflow: auto` box is
  clipped by construction), the outside-click test includes the portal node,
  opening focuses the close button, Esc / × return focus to the trigger.
  Without `sheet` nothing changed.
- `HottestQualityInfo.tsx` renders ONLY the served `quality_info` — the
  measured note first ("not a measured predictor…"), summary, points with
  their maxima, penalties, the ceiling note, tiers + tier note, 🎯 / ⚠️ marks,
  what a blank means, group rows, the fundamentals as-of range, the weights
  note. A contract keeps any number ≥2, page cite, author name or cadence word
  out of the file.
- The ⓘ sits beside the Quality sort button (a sibling, never nested — opening
  it fires no fetch) only when the payload carries `quality_info`; without it
  the header is byte-identical to before. The header title is unchanged.
- A name's Quality hover now prints the served tier label ("Red flag"), the
  raw key only when no explainer came back.

## 5. Tests

- `src/lib/hottestSort.test.ts` — click rules, cycle, cap (same object), param
  encoding, served-only tie-breaks, `sortBasis` settled / in flight, `sortMark`
  byte-identical to `arrow()` for single keys.
- `src/hooks/useHScrollCue.test.ts` — the pure cue (fits / 1px tolerance /
  overflow / scrolled to end); the hook observes the box AND its table; labels
  from the argument; `--hs-box-w` written.
- `src/components/InfoButton.test.tsx` — `sheet` portal, inside click stays
  open, outside closes, Esc returns focus; without `sheet` unchanged.
- `src/components/HottestSectors.multisort.test.tsx` — shift/⌘/ctrl URLs,
  served marks, aria-sort, plain click resets, 4th key no fetch, "then by",
  ✕ clear, ☀️ no `then_by`, served labels only, served row order, served plan
  shorter than requested, demoted ☀️ + shift-click, in-flight composition.
- `src/components/HottestSectors.quality.test.tsx` — the sheet, every served
  part, sentinel payload verbatim, no cites / edge / cadence, Esc / outside,
  no fetch on open, absent block → no ⓘ, tier hover.
- `src/components/HottestSectors.layout.test.tsx` — the DOM chain, `hs-sym` on
  every row kind, one `.hs-rowpin` per full-width row, the cue with mocked
  geometry, the cue appearing when a group opens (and leaving when it closes),
  the gated snapshot writer.
- Contract `🔥 Hottest: every column reachable, multi-sort, ⓘ Quality
  (2026-09-28)` in `frontend/scripts/contracts.mjs`.

## 6. His call (defaults shipped)

1. **Max sort keys = 3.** Alternative: 2 or 4.
2. **Exact ties**: names A→Z; sectors, industries and rosters keep their stored
   order — so a Next ER sort never reorders the sectors. Alternative: group ties
   A→Z, or an implicit 5-days tie-break.
3. **The sort is not remembered** — a reload returns to 5 days ▼. Alternative:
   persist it like ⊞ Expand all.
4. **Sector / Name is sticky on a phone too** (it holds a large share of a
   390px screen). Alternative: sticky above 720px only.
5. **Which column, if any, gives way to END the sideways scroll** — still open
   in `docs/rotation/hottest_expand_all_2026_09_22.md` § His call item 8.
   Nothing was dropped here.

Nothing on this surface is measured, gates anything, or pushes anything.
