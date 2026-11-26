# 📅 Runners continuous chart — where it opens (2026-11-26)

Ajay 2026-11-26, verbatim: "I want you to have continous charts for previous day runners we have some examples with
traderview charts with couple of indicators can you set that up? I wanna able to horizontal scroll tp check continuity
like he does"

Spec: `runcharts/spec.md` rev 2, §3.8 and §4.3 (package `fe-mount`). GG tag: 🟡 display — supports GG's own "Multi-Day
Movers" characteristic. Display only: no alert, push, gate, sort, lane, Watch-list or strip-rule change.
The chart itself is documented in `runners_continuous_chart_frontend_2026_11_26.md` (FE) and
`runners_continuous_chart_2026_11_26.md` (backend).

## Where it opens — the 📅 strip only

| Opener | Where | What a click does |
|---|---|---|
| a chip's symbol | the 📅 Previous day runners strip on 🚩 (desktop, folded or open; the phone once opened) | `openGgRunChart(symbol, list)` |
| a mini (`MEDS +165%`) | the phone's folded one-line strip | the same |

- `list` = every served row symbol of the strip, in served order — the chart's ‹ › steps through it (clamped, no wrap),
  even the names folded behind "+n more".
- A removed name (the closed "not running" fold) gets no opener and is not in the list.
- The ➕ Watch button and "+n more" do not open the chart. Each opener's `title` / `aria-label` is `ggrcOpenTitle(sym)`.
- Nothing else opens it: no button on a 👀 Watch tile, a ⤢ view, a 🚩 / 🧪 card or a board tile (HIS CALL #4).

## Who sees it

The strip's own audience: the page mounts `<GgRunChartHost />` behind the EXISTING `showRunners` flag (🚩 tab, a LOADED
primary owner) — no new flag. A co-owner, any other user, any other tab, and the moment while `/auth/me` loads get no
host. The route behind the chart is owner-only on the server as well.

## How it mounts

- `frontend/src/components/GgRunChartHost.tsx` (new): reads the open store; nothing while it is empty; else the chart
  inside `<Suspense fallback={null}>`, loaded through `lazyWithReload(() => import('./GgRunChart'))` — lightweight-charts
  is fetched only when a chart opens. `onStep` is null for a one-name list. One `trackFeature('gg-run-chart:open')` per
  open (a ‹ › step is not a new open). Unmounting the host (leaving 🚩) closes the store, so the chart never reopens by
  itself on the way back.
- `frontend/src/pages/ChartMaps.tsx`: one line, `{showRunners && <GgRunChartHost />}`, right after
  `{showRunners && <GgRunnersStrip />}`. The host draws no element in place (the chart portals onto `<body>`), so the
  strip stays the 🔥 wrapper's next sibling.
- `frontend/src/components/GgRunnersStrip.tsx`: the chip's `<b>{sym}</b>` is wrapped in `<button class="ggr-open">`; the
  phone mini `<span class="ggr-mini">` became `<button class="ggr-mini">` with the same children. It imports only
  `ggrcOpenTitle` and `openGgRunChart` from `lib/ggRunChart` — never the chart, the host or the library.
- `frontend/src/styles/ggRunners.css`: `.ggr-open, .ggr-mini` reset to text (font inherit, no border, no background,
  pointer, underline on hover); the mini keeps its 12 px.

## What did not change

`GajjalaWatchTile.tsx`, `GajjalaWatchBoard.tsx`, `GgCardView.tsx`, every ⤢ view and card action row; every served word
on the strip (the chip's title, run text, timing, float, 🏆, broker mark, the ➕); the strip's fold rules; the 👀 Watch's
frame order.

## Pins respected

- `GgRunnersStrip.test.tsx` literal guard: the three strip files (`lib/ggRunners.ts`, `components/GgRunnersStrip.tsx`,
  `styles/ggRunners.css`) still hold none of the banned substrings (the date-like digit pair, the "+40" / "09:45"
  literals, the running / not-read / "Ran " words, `EventSource`, an own media query), nor `ggw-card-btn` /
  `HotSectors`.
- The import guard: the strip still imports `GgWatchButton` from `./GgWatchButton` and `usePhone` from
  `./GajjalaWatchTile`.
- The phone mini's text is still exactly `MEDS +165%`.
- `ChartMaps.runnersStrip.test.tsx`: the strip is still the 🔥 wrapper's `nextElementSibling` — with the chart open too.

## Tests

- `frontend/src/components/GgRunChartHost.test.tsx` — nothing before an open; symbol + list handed to the chart; onClose
  clears; a step moves; NEGATIVES: one-name list → no `onStep`; a step is not a new open (tracked once), a close + reopen
  is; unmounting the host closes the store and a re-mount draws nothing; source: lazy only, no static chart import, no
  library, no raw `lazy(`.
- `frontend/src/components/GgRunnersStrip.test.tsx` (added block) — chip and mini open with the full served list, folded
  or not; the mini is a button with the pinned text; NEGATIVES: ➕ and "+n more" do not open; a removed row has no opener
  and is not in the list; `error` / `empty` / `owner_only` draw no opener; source: only `lib/ggRunChart` is imported,
  the reset rule exists.
- `frontend/src/pages/ChartMaps.runnersStrip.test.tsx` (added block) — the owner on 🚩 gets the host (an open draws the
  stubbed chart); the strip stays the 🔥 wrapper's next sibling; NEGATIVES: 👀 Watch tab, a co-owner and a loading
  `/auth/me` get no host; the page mounts `<GgRunChartHost` exactly once, after the strip, with no new flag.
- `frontend/src/lib/ggRunChart.golden.test.ts` — the backend's golden payload parses whole: every bar kept, `x`
  ascending, the sessions partition the bars, both EMA curves and the volume average kept and index-aligned; NEGATIVES:
  swapped bars and a NaN price are refused, a short curve is dropped, the partition / ascending checks reject bad input.

## HIS CALLs touched here

- #4 Where else it opens — built: the 📅 strip only.
- #13 The ✨ badge spot — the nav ✨ only (the entry is the main session's).
