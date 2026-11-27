# Chart display fixes: frontend (2026-11-27)

Spec: sicheck rev 2, §3.6 D1 and the frontend half of D4 (package `fe-chart`). Display only. No stored stamp, clock axis, detector, ledger, gate, push or count changes.

## D1: the hover shows the bar's clock range (🚩 board and 👀 Watch only)

The 11-27 volume check found that our bars are stamped with their END time. Massive, Alpaca, Yahoo, ToS and TradingView stamp the START. So NXAT's `08:10` bar of 771,509 shares is the 08:05–08:09 bar. The volume was right, but the label was 5 minutes later than on his other charts.

- `chartMaps.tfBarMin(tf)` gives `'1m'` → 1, `'5m'` → 5 and `'15m'` → 15. Any other frame gives null.
- `chartMaps.barRange(t, barMin)` takes a `YYYY-MM-DD HH:MM` stamp and a positive whole `barMin`, and returns `HH:MM–HH:MM`. The start is the stamp minus `barMin`, and it wraps past midnight (`00:00` → `23:55–00:00`). The date shown stays the stamp's date. Any other stamp or `barMin` gives null.
- `chartMaps.hoverLines(bar, barMin?)`: when a range exists, line 1 is `2026-11-27 08:05–08:10 · pre`. Otherwise line 1 is exactly today's line. The OHLC lines and the `Vol` line (`shortVol`) never change.
- `PatternChart` prop `barMin?: number`. The hover box stays `HOVER_TIP_W` (104, today's width) and widens only when line 1 is longer than today's. The new width is `textWidth(line 1, HOVER_FONT_SIZE) + 2 × HOVER_TEXT_INSET`, built from the old 8.6 font and 6 inset, now named.
- Only two places pass `barMin`: the 🚩 card (`GajjalaBoard`, `tfBarMin(t.tf)`) and the 👀 Watch frame (`GajjalaWatchTile`, `tfBarMin(f.tf)`). A source pin checks that no other component passes it, so every other tab renders byte-identical.

Live 👀 Watch bars (the forming candles, `ggwLive.ggwBarStamp`) are stamped the same way: fromEt + (bucket + 1) × frame. So the range of a live bar is exactly the bucket its prints went into. A test pins this for every bucket of the 1, 5 and 15 minute frames (refix 2026-11-27).

Examples: 5-min `08:10` → `08:05–08:10`; 15-min `08:15` → `08:00–08:15`; 1-min `08:10` → `08:09–08:10`.

## D4: the "as of HH:MM" stamp on a card (frontend half)

- `GgChips.row_asof?: GgChipValue` is the served `{"text": "as of HH:MM"}` (K-3; `tab.py` serves it, see `chart_display_fixes_2026_11_27.md`).
- `GajjalaBoard` prints `chipText(chips.row_asof)` on the chip row right after the volume chip. If the key is absent or holds junk (null, a number, an object without text, blank text, an array), nothing prints and the row stays identical.
- The stamp shows how old the volume is. The volume number itself stays the stale one (HIS CALL #15).

## Tests

- `frontend/src/lib/chartMaps.hoverRange.test.ts` covers `tfBarMin`, `barRange` (the 5 / 15 / 1 examples and the midnight wrap) and `hoverLines` with a range. Negatives: no `barMin`, 0, NaN, a fraction or a date-only stamp gives today's line; the AH / pre / forming suffix is kept; the Vol line is unchanged; the box stays 104 without a range.
- `frontend/src/components/PatternChart.hoverRange.test.tsx` uses a real served tile: NXAT's 5-minute frame of 11-27, read once from the container (read-only, through `tab._tile_frame`). Its 08:10 bar has v 771,509. With `barMin={5}` the hover shows `08:05–08:10`; without it the hover shows today's text at width 104. The un-hovered svg is byte-identical either way. The source pin covers the two call sites.
- `frontend/src/components/GajjalaBoard.rowAsof.test.tsx` checks that the chip prints right after the volume chip. Negatives: an absent key or junk gives no chip and an identical row.

## Not built

D2 (odd lots) and D3 (whole-share volume) were not built. Their files (`live_events.py`, `live_hub.py`, `support.py`) are in no package (HIS CALL #16).
