# 📅 Runners on one continuous chart — the frontend (2026-11-26)

Ajay, 2026-11-26, verbatim: "I want you to have continous charts for previous day runners we have some examples with
traderview charts with couple of indicators can you set that up? I wanna able to horizontal scroll tp check continuity
like he does"

GG tag: 🟡 display — supports GG's own "Multi-Day Movers" characteristic. No decision changes. Display only — nothing
here rings, gates, sorts or adds a name. UNMEASURED.

Spec: runcharts rev 2, §3.6 (lib), §3.7 (chart), §4.2 (package `fe-chart`). The backend engine and its words are in
`runners_continuous_chart_2026_11_26.md`; where the chart opens from is in `runners_continuous_chart_mounts_2026_11_26.md`.

## Files

| File | What it is |
|---|---|
| `frontend/src/lib/ggRunChart.ts` | pure lib: the path, parse, series shaping, ranges, pixel geometry, the hover readout, the busy re-ask delay, the open / closed store |
| `frontend/src/components/GgRunChart.tsx` | the overlay (default export; imports `lightweight-charts`; loaded lazily by the host) |
| `frontend/src/components/sessionsPrimitive.ts` | the shading + dated session lines, drawn through the chart's own time scale |
| `frontend/src/styles/ggRunChart.css` | the overlay's stylesheet, phone target 430 px |

## What he sees

One chart over the whole window: every closed bar of the served sessions (5 by default, backend
`RUNCHART_SESSIONS`), 04:00–20:00 ET, one after another with no overnight gap.

- Candles green `#22c55e` / red `#ef4444` (`GGRC_UP` / `GGRC_DOWN`, = `LiveCandlesChart.tsx` UP / DOWN; a test reads
  that file).
- 9 EMA yellow `#FACC15` and 21 EMA purple `#BE78FF` at 2 px — `EMA_BOLD` and `EMA_LINE_W` from `lib/chartMaps.ts`
  (his 11-15 word: never the old blue 9 / amber 21). The values are the server's (the cards' engine, run over every
  loaded bar in time order, extended hours included, never restarted at a session). The chart computes no EMA.
- Volume at the bottom (the house overlay band — lightweight-charts v4 has no panes), coloured by
  `volumePane.volumeColor`, with its served 50-bar average in `VOLUME_SMA_COLOR`.
- Pre-market and after-hours shaded in one grey (`GGRC_SHADE`), from the served `shade` runs.
- A dashed line (`GGRC_SEP`) at the start of every session after the first, and each session's served date label at the
  top. The session under the left edge keeps its label pinned at the left, so the day on screen is always named.
- VWAP only when the server sends it (backend `RUNCHART_VWAP_ON`, OFF — HIS CALL #2): one thin `GGRC_VWAP_COLOR`
  (`#38bdf8`, the hex inside `toneColor('vwap')`) line PER session, never joined across the overnight.
- Head: ‹ › (only when the strip handed a list of names; disabled at its ends) · the served title · the served "ran"
  chip · the served frame buttons (1-min / 5-min / 15-min, the pressed one marked) · ◀ day · day ▶ · all · latest ·
  ⓘ (a closed fold holding the served hint) · ✕.
- Under the head, always visible: the served `notes` (a split, a day that could not be read, the bar cap), then the
  muted `as_of_text` ("last bar closed … · read …").
- A one-line legend (each drawn curve's served label, the volume average's served label, the grey swatch with the
  served "pre-market / after-hours" words) and a one-line readout of the hovered bar (the last bar when nothing is
  hovered): when, session word, O / H / L / C with the change from the prior bar's close, volume, the 9 / 21 values.
  The readout line keeps a fixed height, so the chart never jumps.

## Which clock a time is

A time on this chart — the axis and the readout — is the START of its bar. The server sends `x` = the ET wall clock of
the bar's start written as if it were UTC, so the chart prints ET with no timezone code in the browser; the readout
reads `x` with UTC getters for the same reason. The 5-minute bar drawn at 10:00 is the one a 🚩 card or the 👀 Watch
stamps "10:05" (they stamp a bar when it CLOSES). The only close time on the chart is `as_of_text`, and it says
"closed". Bar `t` (the close stamp) is carried for a like-for-like check and never printed.

## Controls and gestures

| Gesture | What it does |
|---|---|
| drag (mouse) / one-finger drag (touch) | move across the days |
| wheel / pinch / drag on the price axis | zoom |
| ← / → | move a quarter of the screen (`GGRC_KEY_PAN_FRAC`) — not while typing in a field |
| ◀ day / day ▶ | the left edge jumps to the previous / next session's first bar, the zoom kept |
| all | every loaded bar on screen |
| latest | back to the opening view |
| 1-min / 5-min / 15-min | another frame (fetched at once); the choice stays across ‹ ›, not across opens |
| ‹ › | the strip's previous / next name |
| Esc / ✕ | close |

The opening view: the last `view.sessions` sessions on a desktop (2), `view.sessions_phone` on the phone (1), plus
`view.right_gap_bars` (12) empty bars to the right of the last candle — all three served (HIS CALL #8). A refresh keeps
his pan and zoom: when the newest bar was in view the window follows the new bar, otherwise it stays where he left it.
A click on the dark margin does NOT close (a drag that ends there must not lose the chart).

## Fetching

- ONE GET per open, per frame change, per refresh tick and per busy re-ask — never per bar. Credentials included, no
  cache, the newest answer wins, the previous request is aborted.
- A ‹ › step waits 250 ms before it asks (the lib's step-wait constant): a name he steps past never reaches the
  server. The first open, a frame change and a refresh tick ask at once.
- While the market is open the server sends `refresh_sec` (60 on every frame); the chart asks again on that cadence
  only while the page is visible. A refresh updates the SAME series — the chart is not rebuilt.

## States

| Served | On screen |
|---|---|
| `ok` | the chart |
| `empty`, `bad_symbol` | the served sentence; no chart |
| `error` | the served sentence + ↻ try again; no chart |
| `busy` on the first read | the served "Still reading …" sentence, asked again after the served `retry_sec`; after `GGRC_BUSY_TRIES` (5) busy answers in a row it stops and offers ↻ try again |
| `busy` on a re-read | the chart stays; nothing extra is asked (the next refresh tick asks) |
| `owner_only`, `off`, an answer that does not parse, an HTTP error, no network — first read | "The chart could not be loaded." + ↻ try again |
| any of those on a re-read | the chart stays on screen |
| waiting | "Loading…" |

An answer is not trusted when it holds a non-finite number anywhere, one invalid bar, or bar times that are not
strictly ascending — the whole payload is dropped rather than drawn with shifted indexes. A curve or volume average of
the wrong length is dropped on its own; so is a session or shade entry with a bad index.

## Focus and keys

On open the ✕ has focus; on close focus goes back to what opened the chart (the strip's chip), when it is still in the
page. Tab / Shift+Tab wrap inside the overlay. One key listener on the window in the capture phase handles Esc, ← →
and a wrapping Tab and stops them there, so nothing under the overlay reacts. The page under it does not scroll while
it is open.

## Phone (430 px)

Every flex child shrinks (`min-width: 0`), the head wraps, long served sentences wrap anywhere, the canvas takes the
rest of the window (`min-height: 0`, `100dvh` where supported), the overlay sits at z-index 5100 above the ⤢ stretch
view (5000), and at ≤ 640 px every button is at least 32 × 32. Phone detection reuses the Watch's `usePhone`.

## Tests

- `frontend/src/lib/ggRunChart.test.ts` — parse (good payload; NEGATIVES: null / array / unknown state, NaN or
  Infinity anywhere, a bar without `x` / fractional `x` / price ≤ 0 / negative volume, `x` equal or decreasing, a
  wrong-length curve dropped, a mismatched volume average dropped, bad session / shade indexes dropped, an unknown tone
  dropped, `owner_only`, `busy` with its `retry_sec`, a negative `retry_sec`); shaping; precision against `pxText`;
  ranges (initial desktop / phone / one session / none, keep, pan, step at both ends); geometry with a linear fake
  scale (clipping, null and zero-width skipped, the first session without a line, the left-edge label at 0, off-screen
  skipped); hover (the START clock: a bar whose close stamp is 20:00 reads 19:55; the session word; no prior bar → no
  change); the busy delay (NEGATIVES: tries used up, `retry_sec` 0, state ok); the store (open, step clamped, close,
  subscribers told); the path; source guards (no `matchMedia(`, no `EventSource`, no at-sign, no host-mount or glyph
  export; the VWAP hex and the candle colours read from their source files).
- `frontend/src/components/GgRunChart.test.tsx` — lightweight-charts mocked: one GET at once on open; candles get every
  bar; EMA colours and width; drag / touch / wheel / pinch on; the first range; a frame button asks at once and moves
  `aria-pressed`; a refresh tick updates the same series and keeps the range (NEGATIVES: panned away stays, a hidden
  page never asks, not live never asks); ← → pan, Esc closes (NEGATIVES: a bubble listener on the document never sees
  Esc / ← / → and does see "a"; arrows in a field are not taken); three ‹ › steps → one GET for the last name
  (NEGATIVE: none for the names stepped past); busy (one re-ask; NEGATIVES: 5 in a row stop with ↻ and a click asks
  once, busy on a re-read keeps the chart with no extra timer, unmount during the wait asks nothing); focus (✕ on open,
  the opener back, Tab wraps both ways; NEGATIVES: a middle Tab is not prevented, a removed opener does not throw);
  ‹ › absent without a step handler and disabled at the ends; a backdrop click does not close; notes outside the
  closed fold, the hint inside; the body scroll lock; three line series without VWAP, one more per session with it;
  `empty` / `bad_symbol` / `error` / `owner_only` / junk / HTTP 500 / no network; a failed re-read keeps the chart.
- `frontend/src/components/sessionsPrimitive.test.ts` — a fake canvas and a fake time scale: the two views' z-order;
  one full-height rect per shade run, clipped; positions asked at draw time (a pan re-places them); one dashed line
  per session after the first and a label per visible session, the left-edge label pinned; NEGATIVES: nothing drawn
  with no data, with null coordinates, or detached; `setData` swaps and asks for a redraw.
- `frontend/src/components/GgRunChart.phone.test.tsx` — stylesheet source guards (head wraps + shrinks, canvas
  shrinks both ways, readout / title / notes wrap anywhere, the z-index above `.ggw-stretch` read from
  `gajjalaWatch.css`, the 32 px tap target at ≤ 640 px), each with a NEGATIVE stylesheet that lost the rule.

## HIS CALLs (from the spec, unchanged here)

1. How many sessions back — 5 (backend constant; no picker on the chart).
2. VWAP on this chart — OFF (backend constant; the FE draws it per session when served).
3. EMA colours — the house 9 yellow / 21 purple; GG's are green / teal.
8. What is on screen when it opens — 2 sessions on a desktop, 1 on the phone, 12 empty bars on the right (served).
9. A live candle — not built: closed bars, re-read every 60 s while the market is open.
16. Which clock a bar carries — this chart shows a bar at its START; the cards and the Watch keep the CLOSE stamp.
