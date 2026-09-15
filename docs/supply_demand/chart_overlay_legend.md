# Chart overlay legend + TradingView link-out (2026-08-31)

> Ajay: "Chart feel so clumsy can you give me a ledger and some check boxes
> to toggle these off from the view" · "I wanna able to toggle these" (the
> right-edge swept / BOS / overhead / support / now labels) · "Same for other
> charts too where ever you are showing these also give me a trading view
> pre configured chart please."

## What it is

Every surface that draws `PatternChart` tiles — the Chart Maps grid (all
tabs), the Support tab, and the Session tab — now renders an
`OverlayLegend`: one checkbox per overlay FAMILY actually present in the
view, with a swatch that reuses the chart's own color. Unchecking a family
removes its bands AND its lines from every tile. Choices persist in
`localStorage` under one key (`cm-hidden-overlays`), so hiding FVGs on the
Session tab hides them on Chart Maps too — one preference, not three.

## The families (frontend/src/lib/chartOverlays.ts)

| key         | matches                                                        |
|-------------|----------------------------------------------------------------|
| demand      | bands `demand`/`base` + lines labelled `support …`             |
| supply      | band `supply` + lines labelled `overhead …`                    |
| order_block | band `order_block` + lines labelled `Order block …`            |
| fvg         | bands `fvg_demand`/`fvg_supply` + lines labelled `FVG …`       |
| range       | band `neutral` + lines labelled `ORB …`                        |
| trade       | lines toned `buy`/`stop`/`target` (BUY / STOP / TARGET)        |
| structure   | lines labelled `BOS …` / `CHoCH …` / `swept …`                 |
| now         | the `now` marker line                                          |

## The two rules that carry the design

1. **Label prefix beats tone.** `chart_maps/support.py` draws its
   `support 68.43` label with tone `buy` and `overhead 70.85` with tone
   `target`. Grouped by tone alone, the Trade-lines checkbox would silently
   eat them. A line is therefore classified by its label prefix FIRST
   (case-insensitive), and only lines with no known prefix fall through to
   the tone map. Locked in `chartOverlays.test.ts` ("prefix beats tone").

2. **Unknown overlays are always KEPT.** A band kind or label the legend has
   never heard of renders even with every checkbox off — a new overlay must
   appear by default, never vanish silently. Also test-locked.

## The TradingView button

Every tile header (and the Support tab head) carries `TV ↗`, opening
`tradingview.com/chart/?symbol=SYM&interval=…` in a new tab — `D` for daily
charts, `15`/`60` for the session views; dash share classes are rewritten to
TradingView's dot style (`BRK-B` → `BRK.B`).

This is deliberately a **link-out, not an embed**: the TradingView Charting
Library application was REFUSED (2026-08-16 — they require a public website,
and this app is auth-gated; see `docs/tradingview_charting_library.md`). The
public chart page needs no license and opens in his own TV account with his
own layout. The tile is wrapped in a router `<Link>`, so the button cancels
the tile navigation before opening the tab (locked in
`PatternChart.test.tsx`).

## Tests

- `frontend/src/lib/chartOverlays.test.ts` — filtering, prefix precedence,
  unknown-kept, persistence round-trip.
- `frontend/src/lib/tvChart.test.ts` — URL shape, interval mapping,
  dash→dot, the double-cancel click handler.
- `frontend/src/components/OverlayLegend.test.tsx` — render + show-all reset.
- `frontend/src/components/{PatternChart,SupportLevels}.test.tsx` — the TV
  button/anchor on real surfaces.

## 2026-09-14 — dated markers, your position, stale flat lines

* Families own **marker kinds** now: `demand` → `touch_d` (▲ the swing lows
  that made a band), `supply` → `touch_s` (▼ swing highs), `amd` →
  `amd_a / amd_m / amd_d / amd_x` (A on the base, M on the raid bar, D on
  the markup, ✗ on the failure), `keltner` → `kc_sq` (the TTM squeeze dot
  row). `filterTile` drops them with the family; unknown kinds are kept.
* New family **`position`** — his cost (`cost`, pink) and the stop he typed
  (`ownstop`, blue), matched by the `your ` label prefix. ON by default; a
  saved v2 hidden-set from before it existed does not list it, so it shows.
* `filterTile` drops a flat `keltner`-tone line whenever the tile carries a
  Keltner curve, even with nothing hidden — the 2026-09-13 curve fix left the
  three flat lines behind on every non-🌀 tab.
* `quiet: true` lines (BOS / swept / ORB) now mean something on the
  frontend: priority 0 in `lineLabels` — the line draws, the label yields.
* `toneColor('now')` is the ink the swatch shows (it fell to grid grey).
* Board-tab windows: `_zone_window(zone, days)` never draws FEWER bars than
  the Window dropdown asks for; the Breaking / Quick Bounce / Deep Demand
  tiles size to the band's oldest touch (`zone_store` and `deep_demand.read`
  now carry `oldest_touch_bars`).
