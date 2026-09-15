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
