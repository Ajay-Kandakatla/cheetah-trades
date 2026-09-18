# 📁 My holdings — Chart Maps (2026-09-14)

Ajay: *"I about the new portfolio stocks I want to run these against them."*

One chart per name on his Portfolio page, drawn exactly as the Support tab
draws it — `GET /chart-maps/support?symbol=X&window=W(&studies=true)` per
holding, in parallel — then decorated in the browser:

| On the tile | Where it comes from |
|---|---|
| bands, touches, SMC blocks, AMD / Keltner reads | the Support payload, byte for byte |
| **your cost** (pink line, `tone: cost`) | `avg_cost`, else `cost_basis / quantity` from `/portfolio/holdings` |
| **your stop** (blue dotted, `tone: ownstop`) | the stop HE typed on the Portfolio page — **never invented** |
| `−10.5% vs your cost` / `stop 2.1% below` / `⚠ UNDER your stop` | `lib/holdingsBoard.ts` |

Its Window dropdown now opens at **1 week** (2026-09-18, Ajay: *"a weekly
chart for the past week and 2 week inthe charting time frames in all places"*)
— `HOLDINGS_WINDOWS` carries `1w` (5 sessions) and `2w` (10) in front of
1 month. The DEFAULT is unchanged: the tab still opens on **6 months**
(`HOLDINGS_DEFAULT_WINDOW`, and `holdingsWindow(130)` still returns `6m`). At
those two zooms every number on the underlying Support read stays the 1-month
read — see `docs/supply_demand/support_levels_tab.md` §The two short zooms set
the chart, not the numbers.

Worst position first. Its own zoom (the Support windows), the same overlay
ledger and localStorage key as every other tile surface; the study families
fetch only when ticked. A name whose chart fails is listed under the grid
with its error and its 🚀 growth chip; the rest still draw. No holdings →
an empty state that says where to add one.

`position` is a new overlay family (cost + ownstop, prefix `your `), ON by
default and separate from `trade`, so unticking the engine's BUY / STOP /
TARGET never removes his own numbers.

Files: `frontend/src/components/HoldingsBoard.tsx`,
`frontend/src/lib/holdingsBoard.ts`, tests beside each; `chartMaps.ts`
(`holdings` tab, `cost` / `ownstop` tones), `chartOverlays.ts`
(`position` family, marker families).

Nothing here computes a level, gates a scan, or trades. Both study reads
measured INVERTED on 2026-09-13 (`turning_bullish.md`).

**2026-09-14 (evening).** Each tile now carries the demand BOARD's band as a
dashed outline — the band Back in Demand, Deep Demand, the alert gate and the
paper lanes use — beside the Support tab's finer levels. See
`support_levels_tab.md` § 2026-09-14 for the measurement that forced it (the two
resolutions agreed on the nearest demand band 6 times in 46).
