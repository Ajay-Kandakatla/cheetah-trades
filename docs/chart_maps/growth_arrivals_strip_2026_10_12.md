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

## Where it mounts
`frontend/src/pages/ChartMaps.tsx`: after `<HotSectors />`, before
`.cm-tabs-sentinel` — so above the pinned tab strip, on every tab.

## Folded by default
`StudyNote id="growth-arrivals"`, no `defaultOpen`: first paint is ONE line on every
tab. His open/closed choice is remembered in localStorage
(`cm.study.open.growth-arrivals`; a blocked store just forgets). Because the id is
fixed, a fold he closed stays closed when the next cohort arrives — the headline count
still updates.

Nothing arrived (or `/growth/tags` is down, or an older API without `arrivals`) →
the strip renders nothing at all: no box, no "0 new".

## Request budget
`useGrowthTags.ts` now caches the whole `/growth/tags` payload (tags + arrivals) behind
the one in-flight promise.
- Every tab that already mounts a `GrowthChip` (tile tabs via `PatternChart`, …):
  **zero extra requests** — the strip shares the same fetch.
- `?tab=growth`: the 🚀 board mounts no `GrowthChip`, so the strip's call is the
  **one** `/growth/tags` request on that tab (it made none before).
Pinned in `ChartMapsGrowthArrivals.test.tsx`.

## Why the chips do not link to "the respective tabs"
No per-tab membership is stored: `chart_maps/board.py` computes every tab per
request. Answering "which tabs is PGEN on" would rebuild ~20 tabs per page load (the
65 s AMD failure). Chips link to the 🚀 board focused on the name instead.

## Files
- `frontend/src/lib/growthArrivals.ts` — pure: `FOCUS_PARAM`, `arrivalHref`,
  `parseFocus`, `arrivalsHeadline`, `arrivalGlyph`, `arrivalTitle`, `StageCode` +
  `STAGE_LABEL` (the 🚀 board's six hide stages), `hiddenArrivals` (first dropping
  stage; an OFF stage is never blamed; optional `universe` so a name off the board is
  never counted).
- `frontend/src/hooks/useGrowthTags.ts` — `fetchGrowthPayload`, `useGrowthArrivals`.
- `frontend/src/components/GrowthArrivalsStrip.tsx`.
- CSS: `.cm-badge-new`, `.cm-arrivals-strip`, `.cm-arrivals`, `.cm-row-focus`.

## Tests
`src/lib/growthArrivals.test.ts`, `src/components/GrowthArrivalsStrip.test.tsx`
(folded first paint, remembered open, served order/glyphs, router vs ⌘-click, note
verbatim, NEGATIVE empty/absent/500/network, no "bounce", no 🆕 / `defaultOpen` /
pp-CI literal / admin email in source), `src/pages/ChartMapsGrowthArrivals.test.tsx`
(mount order on zones + amd, nothing without arrivals, chip → focused 🚀 board,
request budget).

## HIS CALL (not decided here)
1. Cross-tab membership links — needs a stored per-tab symbol snapshot.
2. A "✨ new only" filter toggle.
3. Whether the strip shows on `?tab=growth` too (built: every tab).
4. The 30-day window (`NEW_GROWTH_DAYS`) — unchanged.
5. Whether a chip link should carry `&show=all`.
6. Whether `?focus=` should auto-un-hide the focused name.
7. Open by default / re-open on a new cohort (built: folded).
