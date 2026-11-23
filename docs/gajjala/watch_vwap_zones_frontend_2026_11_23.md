# 👀 Watch FE — frames 1 / 5 / 15 · VWAP · daily supply & demand zones (2026-11-23)

Spec: vwapzones REVISION 2, §3.9 (WP fe-watch). Backend: `watch_frames_vwap_2026_11_23.md` (frames + VWAP) and
`watch_daily_zones_2026_11_23.md` (zones). Chart core (PatternChart / chartMaps `ctx` bands, `.pc-vwap`): fe-chart.

## His words (2026-11-23, ~00:45–00:55 ET, in order)

1. "can you add vwap and supply demand zone in the daily time frame on the watch list please"
2. "I think we have 15 mins too"
3. "on the watch list I think we switch to 15 when candles are available for full chart"
4. "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board"
5. "Add vwap and supply demand too"

## What the Watch draws now

| Piece | Where | Source |
|---|---|---|
| Frames | 1-min full width on top, the 5-min + 15-min pair below; ⤢ 15 / 5 / 1 (= the 🚩 card view's order) | served `frames` (1m, 5m, 15m) |
| Chart heights | `GGW_CHART_H = { 1m: 120, 5m: 180, 15m: 180 }`; the pair's fit share = the 5-min height / 2 (unchanged 90) | `lib/gajjalaWatch.ts` |
| 15-min with no closed bar / an old 1m/3m/5m doc | the served `empty_text` in place of the chart (the tile is never blank, never "3m") | served |
| VWAP | thin blue line over the candles, under the 9 / 21 EMA, on every frame with bars | served `tile.curves` (tone `vwap`) |
| Daily zones | dashed green / red outlines (the board-band look), drawn only where they cross the chart; never move the price scale; no edge marker | served `tile.bands` (`ctx: true`) |
| Zones line | the row's served `levels.text` verbatim (hover = served title) — under the head on a plain tile, inside ⋯ on a compact tile | served `levels` (ok / retry / none / pending) |
| Legend | 9 EMA · 21 EMA · VWAP · daily demand · daily supply; each swatch = the look the chart draws (zones = dashed outline box); hover = served `title` | `ggwLegendSwatch` + served `legend` |
| ℹ️ | + the served `info.vwap_text` and `info.zones_text` (a phone has no hover) | served |
| 🚩 card ⤢ / card tiles | `ggcRow` keeps the SERVED `ctx` bands (both looks — `videoLayers` strips only the card's overlay) and hands `levels` to the row | `lib/gajjalaCardView.ts` |

The FE composes no word: every visible string is served. Display only — nothing gates, sorts, caps or rings on VWAP or
the zones. UNMEASURED.

## The forming 5- / 15-min candle — BUILT, OFF (HIS CALL #13)

`GGW_SEED_FORMING = false` sits beside `GGW_LIVE_EMA_TIP`. Off = main's forming candle: only the prints seen since the
page opened (after a reload up to 15 minutes of the 15-min candle can be missing; was up to 5 on the 5-min chart).

On, `lib/ggwLive.ggwSeedLive` builds the forming bar from the row's OWN 1-min chart: the stored 1-min bars of the bucket,
then the live 1-min bars PAST the stored ones (bucket > the 1-min frame's last stored bucket, < its slots — the same
render-time filter `ggwLiveFrame` uses, so a minute the server now stores is counted once, from the store [C8]). It needs
the same `start_epoch`, an integer frame ratio > 1, a non-stale 1-min frame and at least one live 1-min bar; anything
else → main's candle. No live print → no forming candle (as today). His word turns it on.

## Tests

- `frontend/src/components/GajjalaWatchBoard.frames_vwap_zones_2026_11_23.test.tsx` — constants + source guards (no `'3m'`
  literal in the lib / tile / board; seed constant false beside the tip; CSS wraps), board layout and ⤢ order, placeholder
  frame, older payload still draws, VWAP + zone outlines on every frame with bars, out-of-range zone draws nothing, levels
  line once per state (drawer when compact), legend swatches + titles, ℹ️ lines, the tile with the seed OFF (main's bars,
  same array) and ON (mocked), the card view (ctx bands under both looks, levels, byte-equal without them).
- `frontend/src/lib/ggwLive.seed_2026_11_23.test.ts` — the pure `ggwSeedLive` incl. every NEGATIVE of §3.9 and the 15-min
  bucket boundary (:14:59 → :00 bucket, :15:00 → the next) with the seed off.
- `frontend/src/components/GajjalaWatchBoard.real_payload_2026_11_23.test.tsx` — reads the backend JSON
  (`__fixtures__/gajjala_watch_board_2026_11_23.json`): every served `ctx` band meeting a frame's candle range has a drawn
  band group, the sub-$1 zero-width one included [C3]; an "inside" band is on the chart. Reports WAITING (skipped) until
  the main session regenerates the fixture.
- Pins moved (all predicted by the spec, plus one in the same family): `gajjalaWatch.test.ts` (heights),
  `GajjalaWatchBoard.fixes.test.tsx` (fit share, old-payload heights), `.phone.test.tsx`, `.test.tsx` (an older 3-min
  frame → the 5-min height), `.layout.test.tsx` (order 15 / 5 / 1), `GajjalaWatchTile.test.tsx` (old payload ⤢ order;
  the no-order fallback now 15 / 5 / 1), `gajjalaCardView.test.ts` (Watch order == card order).

## HIS CALLs touching this surface

#3 zones per kind · #4 zones never move the scale · #6 ⤢ order 15 / 5 / 1 (he listed 1 / 5 / 15) · #8 looks (dashed
outline, VWAP blue) · #9 legend toggle (not built) · #13 the seeded forming candle (built, OFF) · #14 📺 card look shows
VWAP + zones · #17 "across board" = the Watch + the card frames' charts.
