# 🎾 Reversal Squeeze cards drawn as the 👀 Watch tile — 2026-11-23

**Display only. UNMEASURED.** Nothing rings, gates, sorts, orders, sizes or trades differently. No rule, threshold or job cadence changes.

## The ask, verbatim

Ajay 2026-11-23 ~16:45 ET: **"In the reversal squeeze can you make the charts same as in watch list please"**.

His answers on the question card:
- Today he sees the 🎾 cards in the 👀 Watch layout as three full-width charts stacked 15 / 5 / 1.
- Make them look like the 👀 Watch tile: the 1-min on top at full width, the 5-min and 15-min **side by side** below. Same
  heights and fit rules as the Watch tile, the 9/21 EMA cross markers on every frame, the caption chips (K5 ✓/✗, EMA blink), VWAP and the dashed daily zones.
- KEEP (all four ticked): (1) the TRIGGER / STOP lines; (2) GG's squeeze marks on the 5-min frame; (3) yesterday's
  afternoon tail (15:00 → 20:00) ahead of today on the 5-min frame; (4) the card text below the charts.

## What a 🎾 tile draws now

| Frame | Where | What is on it |
|---|---|---|
| 1-min | top, full width | candles, bold 9 / 21 EMA, 9/21 cross diamonds, TRIGGER / STOP, VWAP, dashed zones, K5 + EMA blink chips |
| 5-min | bottom left | the same, plus **yesterday's tail** ahead of 04:00 (its own date tick, e.g. "Nov 20") and **GG's squeeze marks** |
| 15-min | bottom right | the same as the 1-min |

- **🚩 and 🧪 Audited share this grid — a 🎾 card on either gets it.** So does a 🧠 card of a 🎾 read (the board's own 🎾 rule).
- The card text below the charts (zone lines, plan, state pill, chips row) is untouched — it sits outside the tile.
- One cell, not full row (the 11-18 rule stands).

## Both looks (📺 on or off)

**The cross diamonds and the squeeze marks show under BOTH looks** on this tile. 📺 still strips the 🧪 band and the
card's own ➖ diamonds (as on every card). This is HIS CALL 6 below.

## The 15-min toggle

With the board's 15-min toggle on, a 🎾 card is read on 15-min bars and serves **no squeeze marks** (the 11-08 "read
frame only" rule). The marks go to the 15-min frame only when that frame holds them. HIS CALL 8.

## Three safety rules, plain words

1. **The split draws only from a payload that says it is the squeeze card.** An older api ignores the new ask, so
   the tile shows today's stacked 15 / 5 / 1 with its charts. It never shows a split in the wrong order.
2. **A name on two subs shows "loading" for one round trip after a switch** (🎾 ↔ another setup). It never shows the
   other setup's charts in the meantime. If that read fails it prints "Could not load the three charts.". A failed
   re-read of the SAME shape keeps the charts on screen, the same as before.
3. **The forming candle is kept across that switch.** Live buckets always sit on today's grid. Only the drawing adds the tail's offset.

## What did NOT change

| Surface | Today |
|---|---|
| Every other setup's card in the Watch layout | stacked 15 / 5 / 1, byte-identical; its frames GET carries no `?` |
| ⤢ full screen (any card, 🎾 included) | 15 / 5 / 1, no `card` param, no tail, no squeeze marks |
| Small cards (👀 Watch layout off) | unchanged; the 🎾 card is still `gg-wide`, with no clock axis |
| Cadence | one frames GET per shown card per landed board read; zero on a quotes batch / 📺 flip / new tiles |
| Source | the same stored GG5 / GG1 docs; no new read, no fetch, no write |

Not touched: `GajjalaWatchTile.tsx`, `GajjalaWatchBoard.tsx`, `PatternChart.tsx`, `GgCardView.tsx`, `GajjalaBoard.tsx`,
`tab.py`, `squeeze_marks.py`, `run.py`, `constants.py`, every pass / push / lane module, `gajjalaWatch.css`.

## How (frontend, WP fe-grid)

| File | Change |
|---|---|
| `frontend/src/lib/gajjalaCardView.ts` | `GGC_CARD_PARAM` / `GGC_CARD_SQUEEZE`, `ggcPath(sym, card?)`, `ggcIsSqueeze`, `ggcCardParam`; `parseGgc` keeps the echo `card` only for the exact value; `ggcRow` splits only when the caller asks **and** the payload echoes, then marks the row (`card`); `ggcRowSplit(row)` |
| `frontend/src/hooks/useGgCardWatch.ts` | a 🎾 card asks `?card=squeeze`; each load carries its `ask`; `rowOf` refuses a load of the other ask (loading row); a failed re-read keeps only a same-ask load. `GgCardWatch` type unchanged |
| `frontend/src/components/GgCardGrid.tsx` | `GgCardTile` passes no `stack` only when `ggcRowSplit(row)` — it reads the ROW, never the card |
| `frontend/src/styles/gajjala.css` | ONE new `@media (min-width: 641px)` block after the 11-18 block: the split charts grow the row instead of shrinking under a long card, floor `--ggc-frame-min` (160 px). No `!important`. ≤ 640 px: the Watch's own phone rules (one column) |

The backend side (`?card=squeeze` on the frames GET, the lead axis, cross markers + K5) is in
`card_frames_squeeze_card_2026_11_23.md`.

Fit arithmetic (§3.9 of the spec): the Watch shares 120 : 90 (top : pair) hold only while the chart block is ≥ 160 × 210 / 90 ≈ **373 px**.
Below that the pair sits on the 160 px floor. Below 2 × 160 both sit on the floor (1 : 1) and the row grows. So pick 4 / 9 with a long card reads 1 : 1, and that is the rule working.

## Tests

| File | What |
|---|---|
| `frontend/src/lib/gajjalaCardView.squeeze_2026_11_23.test.ts` | the route param, the 🎾 predicate, the echo parse, the split gated by the echo (NEGATIVES under both looks), marks / A+ on `card.tf` only, no doubled cross |
| `frontend/src/hooks/useGgCardWatch.squeeze_2026_11_23.test.tsx` | URLs per setup, cadence, ownership NEGATIVES (a)–(f): loading row after a switch, failed first read of the other shape, same-shape re-read kept, deploy skew, one GET on a setup flip, no live on a loading row |
| `frontend/src/components/GgCardGrid.squeeze_2026_11_23.test.tsx` | REAL Tile / Frame / PatternChart: split DOM, fit shares, marks incl. tail bars, diamonds + K5 on every frame; NEGATIVES: bull-flag card and a 🎾 card on a plain row stay stacked; CSS source reads |
| `frontend/src/components/GajjalaBoard.card_watch_squeeze_2026_11_23.test.tsx` | REAL board: deploy-skew NEGATIVE, the split tile + card text, ⤢ unchanged, OFF unchanged, 🧪 Audited, phone, live 1-min fold |

## Measured in a real browser (spec §5.4b) — 2026-11-23 ~18:40–19:00 ET, after hours

Worktree Vite preview (`vite.local.config.ts`, local only) with the frames GET proxied to a throwaway branch api
(`verify-rswatch`, its own container, live feed off, the three changed backend files mounted read-only); the board and quotes
from the live api, GET only. Measured with `getBoundingClientRect` in headless Chrome (scratch script `gate.mjs`, not committed).

| # | Check | Where | Result |
|---|---|---|---|
| G1 | split tile: no stack; 1-min first full width; 5-min then 15-min side by side | 1920×1080 pick 2 | **PASS** — both 🎾 tiles: no `ggw-stack-charts`, top 704 px wide, pair 348 + 348 side by side |
| G2 | top : pair = 1.33 ± 0.03 | pick 2 at 1920×1080 and 2560×1440 | **PASS** — 1.333 at both (top 268 / pair 201 px; 447 / 336 px) |
| G3 | no chart below 160 px; card ends inside its row; expect 1 : 1 | pick 4 / pick 9, long card | **PASS** — smallest chart 160 px, none below; ratios 1.00–1.29 (pick 4), 1.00–1.15 (pick 9); 0 elements past the card |
| G4 | one card a page, one column, nothing past the card's width | 430×932 | **PASS** — 1-min, 5-min, 15-min in one column, 0 elements past the 386 px card. Note: the charts are 128–146 px tall there — the 160 px floor is a desktop rule (§3.9), not applied at phone width |
| G5 | squeeze-mark labels never overlap, never leave their svg | pick 2, pick 9, 430 | **FAIL, NOT caused by this change** — 1–3 overlapping label pairs per 5-min chart (e.g. three "earlier try" boxes), 0 outside the svg. The SAME overlap is on today's small 🎾 card at full width (1444 px, 📺 off): 1 / 1 / 5 / 1 / 1 / 0 overlapping pairs on the first six cards. The label placement is the existing squeeze-marks engine; halving the width did not add overlaps. With 📺 on (default) the small card and ⤢ draw no marks, so this tile is where he will first see them. Not self-fixed (a look decision) — HIS CALL 12 |
| G6 | prior-day tick, "04:00", TRIGGER / STOP, diamonds, K5, VWAP, zones | pick 2 | **PASS** — 5-min: "Nov 20" tick then "04:00"; BUY / STOP lines on all three charts of a card with a trigger (cards with no trigger yet show STOP only, as today); cross diamonds on all three; K5 chip per chart; VWAP on all three; dashed daily zones drawn. The "Nov 20" tick is clipped by ~3 px at the left edge — the same pre-existing PatternChart month-tick clamp that clips "Oct 13" on today's small cards (pinned by the OFF snapshot), not touched |
| G7 | px per 5-min slot | pick 2, pick 9, 430 | **MEASURED** (5-min svg width ÷ 252 slots, plot ≈ 87 % of the svg): pick 2 ≈ 1.2 px (svg 348 px, same at 2560×1440), pick 9 ≈ 0.8 px (svg 224 px), phone ≈ 1.25 px (svg 362 px). Today's stacked full-width 5-min ≈ 3.2 px (704 px over 192 slots) |
| G8 | other setups stacked, no `?`; ⤢ 15 / 5 / 1; OFF small card; 🧪 Audited split | pick 2 | **PASS** for bull-flag (stacked, three full-width 704 px charts), toggle OFF (small cards, no Watch tile) and 🧪 Audited → 🎾 (same split, ratio 1.333). The no-`?` and ⤢ rows are covered by the hook / grid tests, not re-watched here |
| G9 | sub switch: loading, then its shape; forming 5-min candle on both | one session minute | **MOVED to §5.5** — not watched in the preview; the cross-package test `GajjalaBoard.card_watch_squeeze_live_2026_11_23.test.tsx` pins it |
| G10 | screenshots pick 2, pick 9, 430 | — | taken (scratchpad `rswatch/shots/`), shown to him in the ship report |

## HIS CALL (built as the stated default; nothing below is decided for him)

Listed, nothing built:
1. Frames re-read cadence on the cards: once per landed board read (~5 min). The Watch re-reads every 60 s.
2. The 5-min / 15-min source: the GG5 pass doc (it can sit one bar behind the Watch). The alternative is reading the Watch's own tile.
3. Sections / headers like the Watch on the card grid.
4. The Watch arrangement on every other setup's cards.
5. ⤢ full screen: stays 15 / 5 / 1, no tail, no squeeze marks.

Built defaults he can overturn:
6. **📺 ON still shows the squeeze marks and the 9/21 cross diamonds on the 🎾 Watch tile.** His 11-17 "no ➖ diamonds"
   call for 📺 is not applied to this tile's frame diamonds. Say the word to strip them.
7. The tail is laid **by clock** ahead of 04:00 (60 five-minute slots, 15:00 → 20:00; empty slots stay empty) with ONE
   tick, the prior day's date. Today's stored tails hold **min 3 / median 44 / max 60** bars of the 60 slots. The lead is 24–29 % of the frame.
8. Under the 15-min toggle a 🎾 tile shows no squeeze marks. The alternative is to always serve them for the 5-min frame.
9. K5 chip = the frame's own stored 9/21 EMA over today's bars, so it reads "K5 —" for the first bars of the day (15-min: until
   05:00), while the 👀 Watch may already read "K5 ✓" for the same name.
10. NOT added from the Watch caption: the 🔕 held chip and the 📶 base-count chip. The per-frame as-of chip stays.
11. Chart floor in a long card: 160 px (`GGC_FRAME_MIN_PX`) for the 1-min chart and for the 5- / 15-min row.
12. **Density: the 5-min chart is HALF width and gains up to 60 tail slots.** Arithmetic, not measured: ≈ 1.2–1.5 px a bar at pick 2
    (≈ 3.1 px today), ≈ 0.8 px at pick 9. His 11-08 ask was a WIDER 🎾 chart. He sees the screenshots (G10) and the measured G7 before the push.
13. A 🧠 card of a 🎾 read gets the same tile; 🧪 Audited 🎾 cards too, on GG5's stored frames.
14. A name with no bar today draws no tail.
15. The 🎾 tile is one grid cell, not full row; the toggle's hover text is unchanged.
16. 11-18 calls #3 (stack order) and #4 (no tail on the tile) are **reversed for 🎾 cards only**, by his word today. So is the
    11-17 Video-view default "no two-session clock axis" (`video_view_2026_11_17.md`). The small card keeps no axis.
17. After a 🎾 ↔ other-sub switch a name on both shows "loading" until its own charts land. The alternative (keep the other
    shape's charts meanwhile) is not built: it would draw the 🎾 tail on a plain card, or a wrong-order split.
18. A stored tail that cannot be laid is dropped for that read with ONE debug line. The tile then shows today only (0 of 97 docs today).
