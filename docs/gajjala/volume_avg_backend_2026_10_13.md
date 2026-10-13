# 📊 Served 50-bar volume average (2026-10-13)

Ajay 2026-10-13: green / red volume under every chart plus a thin 50-bar simple average of volume (the thinkorswim VolumeAvg default). The pane shipped (351159e9) computing that average in the browser over the bars a tile SHOWS — so a 120-bar Chart Maps tile spent its first 49 bars warming up. Where the backend holds a longer frame than the tile shows, it now serves the true average and the frontend draws it: the board tabs (daily) and the 🌀 Turning Bullish tabs. It does NOT help an intraday Support tile: that frame is the one the tile draws, so on `5m_today` the served line still needs fifty bars of today, and before then the pane draws its own fallback. Display only: no board, filter, gate or alert reads it.

## The rule — full frame, joined by stamp
- `chart_maps/board.py` `VOL_AVG_PERIOD = 50`, `VOL_AVG_LABEL = "50-bar avg volume"`.
- `_vol_avg_series(df, *, stamp=None)` — pure. The simple mean of the current and prior 49 volumes on the frame it is HANDED, which must be the untailed one (the `_ma_series` rule). First 49 bars = None. A window holding a missing, non-finite or negative volume = None (the frontend fallback's own rule, so served and fallback agree on what counts); zero counts as zero; every value passes `_num`, so no NaN reaches JSON.
- `_vol_avg(tile, df, *, stamp=None)` — attaches `tile["vol_avg"] = {"period": 50, "label", "values"}` aligned to `tile["bars"]` BY STAMP: a bar the frame lacks is None, never its neighbour's value. Today's live bar is NOT such a gap on the board tabs: `bars_for` hands `frame_out` the frame AFTER `prices.with_today_bar` (board.py, before any slicing), so the live bar's partial volume is INSIDE the last window, exactly as its partial close is inside the MAs. Omitted when every value is None (frame shorter than 50 bars). Idempotent: a served average is not recomputed by a second pass; a stale `vol_avg: None` is overwritten. Soft-fails — a drawing never empties a tile.
- `stamp` is the caller's key, as for the MAs: date-only on daily frames, `support._intraday_stamp` (`%Y-%m-%d %H:%M` ET) on the Support tab's intraday frames.

## Which builders serve it
- Every `_ma_curves` call site, with no new call: `_ma_curves` calls `_vol_avg` FIRST (before its "MAs already on this tile" return, inside its own try) — board tabs via `_attach_bars`, the 🌀 Turning Bullish tabs, and the Support tab daily + intraday (`support._attach_ma`; intraday it is handed `chart_df`, the same frame the tile draws, so there is no longer history to average over).
- `chart_maps/ema_frames.py` `build()` — the 〰️ 9 EMA · W/M tile, over the resampled weekly / monthly frame: fifty weeks or fifty months. The forming period's partial volume is in its window, exactly as its partial close is in the 9 EMA. A monthly tile under 50 months has none.
- Gajjala tiles (WP1 `bars.tile_payload`) call `_vol_avg_series` on their 2-session frame.

## Which fall back to the frontend
Tiles from builders that never call `_ma_curves` (session, signals, holdings, POTUS, index zones) and the three charts that fetch their own series (`LiveCandlesChart`, `ZoneChart`, `IntradayChart`, which already average over everything they fetched) — the shipped `volumeSma` in `frontend/src/lib/volumePane.ts`.

## Frontend
`lib/volumePane.ts` `paneVolumeAverage(vols, served)` is the one choice point: served wins when `period === 50` and `values.length === bars.length` with at least TWO finite values (one point draws no segment, and winning with it would switch off the fallback's flat line); anything else draws the shipped fallback unchanged. `PatternChart` reads `tile.vol_avg`; with a served line the pane's scale also fits the line (a full-frame average can sit above every shown bar), the fallback scale is the tallest bar as before. The corner label prints that scale top; when a served line lifted it above every bar, the pane's hover title reads `scale top X · tallest bar Y`, otherwise `tallest bar Y`, so the label and the title never name different numbers.

Tests: `backend/tests/test_chart_volume_avg_2026_10_13.py`, `frontend/src/lib/volumePane.served.test.ts`, `frontend/src/components/PatternChart.servedVolAvg.test.tsx`.
