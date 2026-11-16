# 👀 Gajjala's Watch — thinner 9 / 21 EMA, lighter candles (2026-11-16)

Ajay, verbatim (on the ⤢ full-screen POLA chart): "This is good but they are not very clear as the lines are too thick may
be reduce thick ness and make the bars lil more transparent to be over the EMA lines?"

- `frontend/src/lib/chartMaps.ts` `EMA_BOLD` widths 3 → 2 px (non-scaling — the same on a tile and full screen; 11-15 had
  taken them 2 → 3). New `EMA_BOLD_CANDLE_OPACITY = 0.55` (MINE, layout — HIS CALL to move).
- `frontend/src/components/PatternChart.tsx`: under `emaStyle="bold"` (the 👀 Watch charts only) each candle group's
  opacity is multiplied by it, so the 9 / 21 (already drawn over the candles) read clearly. Every other chart is
  byte-identical.
- Tests: `PatternChart.watch.test.tsx` (width pin widened 3 → 2; new candle-opacity test with the NEGATIVE that a chart
  without the prop keeps its opacity), `gajjalaWatch.test.ts` EMA_BOLD pin widened.
