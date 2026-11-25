# 👀 Gajjala's Watch — bigger, clearer charts (2026-11-16)

> **2026-11-25 — changed.** On a desktop every tile is in one scroll; the pick sets columns + row height only, tile size unchanged. See [watch_columns_scroll_2026_11_25.md](watch_columns_scroll_2026_11_25.md).

Ajay, on GP / AKAN / GIPR / ONFO picked at "1 per screen":
"Also the bars are not very visible here" · "Also cannot tell where the GP ticker is now" ·
"All the charts are shrinked too much" · "And the Diamon shapes are too big make them small"

| What was wrong | Fix |
|---|---|
| A pick of 4 names at "1 per screen" split ONE screen four ways (each tile ~200 px) | `ggwPickGrid(n, cols, maxRows)`: a pick never puts more rows on a screen than the per-screen choice holds; extra names scroll |
| A full-width chart stretched the fixed 620-unit viewBox ~3×, blowing up text and diamonds | A fitted chart's viewBox width follows its box: `ggwFitViewW` = box px / `GGW_TEXT_SCALE` (1.3), never under 620 (narrow tiles draw as before); `PatternChart` `viewW` prop |
| Candles faint at 0.55 | `EMA_BOLD_CANDLE_OPACITY` 0.55 → 0.85; bold axis-mode bodies fill `EMA_BOLD_CANDLE_BODY` (0.8) of their slot (0.64 elsewhere) |
| No price marker | Under `emaStyle="bold"`, `boldNowLines` adds the house dashed `now` line + "now 1.46" gutter label at the last bar's close (a served `now` line wins; never two) |
| Diamonds too big | `EMA_BOLD_DIAMOND_R` 2.4 under bold (3.6 elsewhere) — ~6 px across on a full-width chart, was ~25 px |

All numbers are MINE (layout, not rules) — HIS CALL to move. Every other chart (`PatternChart` without `emaStyle="bold"` /
`viewW`) draws byte-for-byte as before (NEGATIVE tests in `PatternChart.watch.test.tsx`, `GajjalaWatchBoard.toggle.test.tsx`).
