# ✨ Growth arrivals strip — Chart Maps top (2026-10-12)

Ajay 2026-10-12: "In the eplosive growth there are 7 new one can you gave me special
emphasis wiht a tag or something in the chart map pages top and then a link to the
repective tabs with new ticker and also in the explosive growth too" — then "I saw an
alert for 7 in explosive growth".

## What it is
One line at the top of every Chart Maps tab:

    ✨ 11 new on 🚀 Explosive Growth (last 30 days) · why

The count is the SERVED `arrivals_n` from `/growth/tags` (backend/growth/arrivals.py,
reading the one `growth_seen` ledger). The "7" he saw was the push's spill
(`MAX_INDIVIDUAL` singles + one digest); the strip never types a count.

Opening the line shows one chip per arrival, in the board's own served order:
- gold `cm-badge-new` chip for a clean, liquid name;
- `⚠️` after the symbol when the served `liquid` flag is false;
- `⛔` and the red `cm-badge-bad` tone when the served `refused` flag is true
  (⛔ wins over ⚠️). Hover = served arrival date + served warnings.
- a trailing `all 🚀 →` link to the board.
Below the chips sits the served honesty note (`arrivals_note`) verbatim. No
measured number is typed in the frontend.

## Links
Each chip is a real link: `?tab=growth&focus=SYM` built by `arrivalHref` on top of
`tabSearch` (keeps universe/window/etc., drops `pattern`). A plain click routes in
place; ⌘/Ctrl/middle-click is left to the browser (new tab).
Since 2026-10-12 every chip and `all 🚀 →` also carry `show=all` (#5, below).

## Where it mounts
`frontend/src/pages/ChartMaps.tsx`: after `<HotSectors />`, before
`.cm-tabs-sentinel` — so above the pinned tab strip, on every tab EXCEPT `?tab=growth`
(2026-10-12, #3).

## Fold (superseded 2026-10-12 — see "Open rule (#7)" below)
`StudyNote id="growth-arrivals"`, still no `defaultOpen`. As first shipped the strip was
folded on first paint and a fold stayed closed when the next cohort arrived; since his
2026-10-12 "yes" it opens for a first visit and re-opens on a newer batch.

Nothing arrived (or `/growth/tags` is down, or an older API without `arrivals`) →
the strip renders nothing at all: no box, no "0 new".

## Request budget
`useGrowthTags.ts` now caches the whole `/growth/tags` payload (tags + arrivals) behind
the one in-flight promise.
- Every tab that already mounts a `GrowthChip` (tile tabs via `PatternChart`, …):
  **zero extra requests** — the strip shares the same fetch.
- `?tab=growth`: the strip is not mounted there (2026-10-12, #3) and the 🚀 board mounts
  no `GrowthChip`, so that tab makes **zero** `/growth/tags` requests.
Pinned in `ChartMapsGrowthArrivals.test.tsx`.

## Links to "the respective tabs" (superseded 2026-10-12)
As first shipped no per-tab membership was stored, so chips linked to the 🚀 board only.
His 2026-10-12 "yes" built the stored snapshot; see "Also on (#8)" below.

## Files
- `frontend/src/lib/growthArrivals.ts` — pure: `FOCUS_PARAM`, `arrivalHref`,
  `parseFocus`, `arrivalsHeadline`, `arrivalGlyph`, `arrivalTitle`, `StageCode` +
  `STAGE_LABEL` (the 🚀 board's six hide stages), `hiddenArrivals` (first dropping
  stage; an OFF stage is never blamed; optional `universe` so a name off the board is
  never counted).
- `frontend/src/hooks/useGrowthTags.ts` — `fetchGrowthPayload`, `useGrowthArrivals`.
- `frontend/src/components/GrowthArrivalsStrip.tsx`.
- `frontend/src/lib/growthArrivalsFresh.ts` (2026-10-12) — pure: `newestFirstSeen`,
  `withShowAll`, `tabGlyph`, `alsoOnLinks`.
- `frontend/src/components/StudyNote.tsx` — optional `freshKey` prop (2026-10-12).
- CSS: `.cm-badge-new`, `.cm-arrivals-strip`, `.cm-arrivals`, `.cm-row-focus`.

## Tests
`src/lib/growthArrivals.test.ts`, `src/components/GrowthArrivalsStrip.test.tsx`
(folded first paint, remembered open, served order/glyphs, router vs ⌘-click, note
verbatim, NEGATIVE empty/absent/500/network, no "bounce", no 🆕 / `defaultOpen` /
pp-CI literal / admin email in source), `src/pages/ChartMapsGrowthArrivals.test.tsx`
(mount order on zones + amd, nothing without arrivals, chip → focused 🚀 board,
request budget).

## His answers (2026-10-12 — one word, "yes", to the eight questions)
Closed list (spec `arrivals-calls/spec.md`):
1. Cross-tab membership links — **BUILT** (below, "Also on").
2. A "✨ new only" filter toggle — **BUILT** on the 🚀 board
   (`docs/growth/board_new_only_and_focus_2026_10_12.md`).
3. Strip on `?tab=growth` — **BUILT: hidden there.** `ChartMaps.tsx` mounts
   `{tab !== GROWTH_TAB && <GrowthArrivalsStrip />}`; the rows' ✨ pills and the board's
   own arrivals line carry it. Every other tab keeps the strip.
4. The 30-day window (`growth.tracker.NEW_GROWTH_DAYS`) — **KEPT**, no change.
5. Chip links carry `&show=all` — **BUILT** (below).
6. `?focus=` draws a filtered-out name anyway — **BUILT** on the 🚀 board (same doc as 2).
7. Open by default / re-open on a new batch — **BUILT** (below).

### Open rule (#7) — `StudyNote freshKey`
`<StudyNote id="growth-arrivals" freshKey={newestFirstSeen(arrivals)}>` — the key is the
newest SERVED `first_seen` (`frontend/src/lib/growthArrivalsFresh.ts`).
- never folded (no `cm.study.open.growth-arrivals`) → **open** on first paint;
- he opened it → open;
- he folded it → stays folded while the served batch is the one he folded on
  (`cm.study.fresh.growth-arrivals` = the key stored at his fold), and **re-opens** when a
  newer `first_seen` is served — also while the page is mounted (`freshKey` is an effect
  dependency; a refetch of the same batch is the same string → no-op);
- storage blocked / throwing / absent → open (no memory), renders the same;
- no arrivals → nothing renders.
- A viewer who folded before this shipped has no stored key → it re-opens ONCE; his next
  fold stores the stamp. The strip and the board's line keep separate memories
  (`growth-arrivals` vs `growth-arrivals-board`).
- Without `freshKey` every other StudyNote behaves exactly as before.

### `show=all` on every chip (#5)
Every chip href and `all 🚀 →` go through `withShowAll`, which sets the page's own 🎯
override (`ChartMaps.tsx`: `enterableOnly = params.get('show') !== 'all'`), so an arrival
the enterable cut would hide (a BLOCKED read) is drawn on landing. Nothing is persisted —
the 🎯 state lives in the URL only, so his default is untouched by construction.
**Scope, stated truthfully:** `tabSearch` copies every param, so after a chip landing
`show=all` rides on EVERY later tab click in that browser tab until he toggles 🎯 back on
(which deletes it). Scoping it to the growth visit is HIS CALL (spec §7.5 — it would also
drop a `show=all` he set by hand on zones before visiting growth). Pinned by the
`[C5] DOCUMENTED SCOPE` test, which flips loudly if that is ever built.

### Also on (#8) — per-tab links under each chip
The arrivals now carry a served `also_on[]` (backend `chart_maps/membership.py`, see
`docs/chart_maps/membership_snapshot_2026_10_12.md`). `alsoOnLinks` turns it into small
links under the chip (`span.cm-arrival-also`, `data-testid=cm-growth-also-SYM`):
- only tabs on the page (`CM_TABS`), in the page's tab order; `growth`, `supply` and
  anything unknown drop; malformed / absent / empty `also_on` → no links, chip unchanged;
- text = the tab label's leading emoji (the full label when it has none);
- href = `?` + `tabSearch(params, tab)` — **no `focus`**: no other tab honours it, so the
  link lands on the tab without a highlight (HIS CALL spec §7.10);
- hover = `<label> · in the served top {limit} as of <YYYY-MM-DD HH:MM>` — membership is the
  SERVED top `limit` of that tab (80 on a page load), so a name ranked 81st reads as
  absent; "as of" prefers the memo's own `source_as_of`, falling back to the snapshot's
  `built_at`; no served `limit` → "in the served list"; when the server marks the
  snapshot `stale === true` the title adds "stale: older than this tab's cache window
  (<TTL constant name>)". The frontend judges nothing — it reads the served flag.
- Rule #5: 11 chips × up to 22 tab links is dense — kept under the fold, glyph-only with
  the full label on hover; a per-row drawer is where it belongs if he wants more.

### Tests (2026-10-12 additions)
- `src/components/StudyNote.test.tsx` — freshKey: open with no memory; same key folded;
  newer key re-opens and the fold re-stores it; [C7] prop changes to a newer key while
  mounted → opens; NEGATIVE: older served key, pre-stamp folder re-opens once, non-string
  stored key, throwing / absent storage → open, no `freshKey` → today's rule, separate ids.
- `src/lib/growthArrivalsFresh.test.ts` — `newestFirstSeen`, `withShowAll`, `tabGlyph`,
  `alsoOnLinks` (order, labels, no focus, "served top 80" / "served list", source-as-of
  preference, stale only when `=== true`, drops growth/supply/unknown/dupes, malformed).
- `src/components/GrowthArrivalsStrip.test.tsx` — open first paint, fold persists for the
  same batch, newer batch re-opens, `show=all` on all 12 hrefs and never duplicated,
  per-tab links (order, glyph, title, stale marker, routing), NEGATIVE malformed `also_on`.
- `src/pages/ChartMapsGrowthArrivals.test.tsx` — strip on zones / amd / bonde (open);
  `?tab=growth` → no strip and ZERO `/growth/tags` calls; chip → `show=all` landing draws a
  BLOCKED arrival; NEGATIVE: nothing persisted; NEGATIVE: without `show=all` the BLOCKED
  row stays hidden; [C5] scope pin.

## HIS CALL (still open, from the 2026-10-12 spec)
- §7.5 scope `show=all` to the growth visit (side effect above).
- §7.7 one-time re-open for pre-ship folders; separate strip / board-line memories.
- §7.10 a `?symbol=` highlight on the tile boards so the per-tab links land on the name.
- §7.11 a style for `cm-arrival-also` (none shipped; hook only).
