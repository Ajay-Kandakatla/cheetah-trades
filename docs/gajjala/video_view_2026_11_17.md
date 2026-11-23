# 📺 Video view on the 🚩 Gajjala cards (2026-11-17)

## The ask, verbatim

Ajay 2026-11-16:
> "Also the graphs in the videos are so clear like I can easily identify the trend
> Why aren't our regular ones like that"

Ajay 2026-11-17, on the spec's HIS CALLs: **"Yes to all defaults"**. So:
1. 📺 Video view is **ON by default**. A toggle turns it off, and the choice is remembered like the other board toggles.
2. The 04:00 → close clock axis is on **every** 🚩 5-min and 🧪 card, always, whether 📺 is on or off.
3. Surfaces: 🚩 5-min and 🧪 Audited now. The 1-minute page is **not** done now.
4. Inside 📺: hide the 🧪 entry band, the ➖ diamonds and the 📶/🎾 circles. Keep the A+ tag, trigger/stop, the now line,
   and volume with its 50-bar average.
5. Dark ground in 📺, even on the light theme.

Spec defaults 6–8 also stand: 🎾 cards keep their prior-session tail and their 190 height; the 📺 chart height is 283; the EMAs
are drawn OVER the candles (21 first, then 9); `ggEllipses.ellipseGeom` was fixed first so it uses the axis.

**Display only. UNMEASURED.** No rule, gate, threshold, alert, ring, push, order or write changed.

## What reads cleaner in the videos (top 5, ranked by how much each helps read the trend)

| # | Video | 🚩 card before | Why it reads cleaner |
|---|---|---|---|
| 1 | Clock axis from 04:00 to the close, empty on the right (replay_video.py:184-185, :274) | One slot per bar, last bar pinned right | Same slope at 07:00 and 15:00, and room for "where it might go" (his 11-15 rule) |
| 2 | 21 then 9 EMA OVER the candles (replay_video.py:347-357) | Curves UNDER the candles | The trend line is the first thing the eye follows |
| 3 | Candles + 2 EMAs + trigger/stop only | Also the A+ tag, ➖ diamonds, 📶/🎾 circles, 🧪 band | Fewer shapes compete with price |
| 4 | Price pane height/width 0.368 (replay_video.py:271) | 190-high viewBox → about 0.23 | About 1.6× steeper |
| 5 | Ground (13,17,23), grid (38,43,52) | The theme; only 👀 / ⤢ forced `.ggw-dark` | Yellow and purple lines stand out |

## What was copied, what was kept

**Copied from the videos:**
- The clock axis from 04:00 ET to the close. It is served by the 👀 Watch's ONE engine: `gajjala_watch.build.axis` +
  `axis_end` through `tab.card_axis`. Half days come from `alerts._closes`, so 2026-11-27 is handled.
- 21 then 9 EMA over the candles, in the replay colours (`EMA_BOLD`: yellow 9, purple 21).
- Only trigger + stop lines (tones `buy` / `stop`) plus the `now` line.
- The dark panel (`GGW_PANEL`, the same set `.ggw-dark` uses, `--ink` included) as inline custom properties on the svg.
- A taller price pane: viewBox 283 (`VIDEO_LOOK_H`).

**Kept as the app already had it (the videos are NOT copied here):**
- Volume and its 50-bar average (his 10-13 call). The videos have no average.
- The 11-15/16 bold tuning: 2 px lines, candle opacity 0.85, body 0.8 of the slot, the bold now line, diamonds 2.4.
  The video's 0.68 body, its 4 % pad and its 5 gridlines are not copied.
- The A+ tag (the video's ring mark).
- Everything outside the svg is unchanged: the ladder's PLAN rows (Entry / Stop), the head, the chips, the stats, the
  "SEPA page" link and the ⤢ click. The strip is applied to the SVG layers only (`videoLayers`), never to the tile.

## Where it lives

- Toggle: `📺 Video view` in the "(5) bar size" row of `GajjalaBoard.tsx`, shown on `gajjala` and `gajjala_audited`
  (`GG_VIDEO_LOOK_VKEYS`). localStorage key `gg-video-look` (`GG_LOOK_LS`): `'1'` = ON, `'0'` = OFF. An absent value or a
  blocked store reads as the default, ON. **Any other value reads OFF**, so a hand-edited `'true'` turns 📺 off; one tap
  then stores `'1'`. The setting is per viewer and per device, like 💋. No GET, query param or fetch reads it.
- Cards: `<PatternChart axis={t.axis ?? null} look={lookOn ? 'video' : undefined} height={…}>`. The axis is passed whether
  📺 is on or off. The height is `VIDEO_LOOK_H` (283) under 📺, except on a 🎾 card, which keeps 190.
- `.gg-board` carries `data-look="video"` while 📺 is on (never on the 1-minute page).
- ⤢ card view: `GgCardView look=` follows the toggle. Its frames were already bold, dark and on the served axis, so the
  look only removes the 🧪 band and the ➖ diamonds there (HIS CALL #1).
- No CSS was added. The button is a wrapping `.cm-phase-btn`.

## The 🎾 exception — most 🎾 cards do NOT get the clock axis

The clock axis covers ONE session. A 🎾 Reversal Squeeze card stores its prior-session tail (`bars5_prior`), so its frame
spans two dates and gets **no axis**: it keeps one slot per bar, its tail and its 190 height, exactly as before.

- Read-only probe 11-17 (`store.reads`): **138 of 141** read docs on 2026-11-16 and **179 of 179** on 2026-11-13 carry
  `bars5_prior`.
- So in practice every 🎾 card AND every 🧠 card of a 🎾 read (both `.gg-wide`, both drawn from the `wide` frame) keeps 190
  and one slot per bar while a tail is stored. The 🎾 sub he reads most does **not** get the axis or the taller chart.
- A 🎾 card whose doc stored NO tail (today-only frame; 3 of 141 on 11-16) does get the axis, but still keeps 190 (HIS CALL #4).
- The toggle title and the ✨ entry both name this exception ("Reversal Squeeze").
2026-11-23 — the 🎾 card drawn as the 👀 Watch tile DOES get a two-session clock axis (`axis.lead`, see squeeze_watch_tile_2026_11_23.md); the small card (Watch layout off) still gets none.

## The stale "now" line off-hours

With 📺 on, the chart uses the bold EMA style, and `boldNowLines` (`chartMaps.ts`) prints "now <last STORED close>" on every
🚩 card. `cardLive` updates it only inside the served window. Overnight and on weekends, every card therefore reads the
last stored close as "now" (on a weekend, Friday's 20:00 close). The 👀 Watch already behaves this way (accepted on his
11-16 ask). It is NEW on the cards and ON by default. HIS CALL #8, not a defect.

## The audit log line

`tab.card_axis` drops the WHOLE axis (never a partial clock) when a bar is junk or its slot cannot be computed: a bar
stamped 04:00 (slot −1), a bar closing after the extended close, or an x-length mismatch. That card then shows one slot
per bar. Each drop is logged once at DEBUG on `chart_maps.gajjala.tab` as `CARD_AXIS_DROP_LOG` = `card_axis dropped
<sym> <tf> <day>: <reason>`, and the EOD audit greps it. Incidence today: **0 / 141** (11-16) and **0 / 179** (11-13). The
🎾 two-date frame and GG1 cards are the rule, not a drop, so they stay silent. The Watch's `build.axis` has no such guard
(it draws a stray bar off-left). This is one engine with two tolerances, by choice.

## Goldens moved

- **GG5 BOARD golden** `backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json`: a dated regen, `axis` ADDED only, on
  the 2×4 setup/🧠 tiles. Expected: 0 changed, 0 removed. The golden's `reversal_squeeze`, `premarket` and `postmarket`
  subs hold 0 tiles, so ☀️ / 🌙 / 🎾 are covered by `backend/tests/test_gajjala_card_axis_2026_11_17.py`, not by this
  golden. Leaf counts (old-vs-new diff, measured 11-17): **+656 leaves on 16 tiles** (the 2×4 tiles in `live` plus the
  2×4 in `shadow`), **0 changed, 0 removed**, every added leaf under `/axis`.
- **FE fixtures** `gajjala_on_open_golden_2026_10_15.json` and `gajjala_potential_golden_2026_10_15.json`: regenerated by
  their recipes (`-k golden`), `axis` added. Leaf counts (measured 11-17): on_open **+84 leaves on 2 tiles**, potential
  **+506 leaves on 11 tiles**. Both are **0 changed, 0 removed**, every added leaf under `/axis`.
- **Byte-identical:** the WRITES golden, `gajjala_1m_board_2026_10_27.json` (GG1 serves no axis), every `PatternChart.*`,
  `GajjalaWatchTile`, `GajjalaWatchBoard.*` test, and the Watch's DOM.
- **+1 pins:** the ✨ first-N window in `contracts.mjs` and the `NEW_FEATURES[n]` index tests (main session).

## UNMEASURED — the videos biased the eye

A clearer chart is display, not evidence. The ema_downcross study (11-15) found that A+ vs the 9/21 cross was NOT SHOWN
DIFFERENT, and cross + trail lost. **The videos biased the eye.** No ✨ entry, doc or card word may say this view finds
better entries. The prior on this signal is null.

## Phone (430 px and 375 px)

Nothing new is a grid item, and `.gg-card` keeps `min-width: 0` (the pinned rule is untouched; the board test guards it).
The toggle is a 2-word wrapping `.cm-phase-btn` with no `nowrap`, and the svg stays `width:100%`.

These numbers are computed from the viewBox, not measured in a browser:

| Width | Card column | 📺 chart height (283 viewBox) | Bold candle body, 144-slot day | Bold candle body, 192-slot day (after-hours) |
|---|---|---|---|---|
| 430 px | ≈ 386 px | ≈ 176 px | ≈ 1.8 px | ≈ 1.4 px |
| 375 px | ≈ 331 px | ≈ 151 px | ≈ 1.6 px | ≈ 1.2 px |

Bodies of 1–1.4 px on a 16-hour axis follow the standing "from 4 AM, gaps on the right" rule (11-15). This is flagged, not
overridden. The worktree Vite preview check (430×932 and 375×812: no element's right edge past the card's `clientWidth`,
no NaN / undefined / Infinity in any svg attribute) is part of the verification plan.

## HIS CALL (built defaults; nothing decided here)

1. **⤢ card view follows 📺 (built: yes).** With 📺 on, the 15m / 5m / 1m frames lose the 🧪 entry band and the ➖
   diamonds. With 📺 off they are byte-identical. Or keep the ⤢ view as it was, always?
2. **Layers hidden inside 📺** (built: 🧪 band, ➖ diamonds, 📶 base circles, 🎾 squeeze circles). His 11-08 "that big of
   circle" is therefore off while 📺 is on. Keep any of them inside 📺? Each is one constant in `lib/videoLook.ts`.
3. **📺 height 283 / 🎾 wide 190** (spec default #7). Confirm after seeing it live; a different number is one constant.
4. **A 🎾 card with no stored tail gets the clock axis** (3 of 141 docs on 11-16). Or never an axis on a 🎾 read? A 🎾 card
   WITH its tail (138 of 141) never gets one; a two-session clock axis is not built.
   2026-11-23 — the 🎾 card drawn as the 👀 Watch tile DOES get a two-session clock axis (`axis.lead`, see squeeze_watch_tile_2026_11_23.md); the small card (Watch layout off) still gets none.
5. **1-minute page:** 📺 and the axis there need the 192-bar cap (`GG1M_TILE_BARS_MAX`) lifted to up to 960 bars, about 5×
   the payload. Not built.
6. **Remembered per device** (localStorage, like 💋 and `ggw.layout`), not in the link. A `?look=` param is not built.
7. **Other surfaces** (stock page Supply/Demand, 🥇 Luk, other Chart Maps boards, 👀 Watch tiles): not built. The Watch
   already has 4 of the 5 differences.
8. **Stale "now" line off-hours under 📺** (built: same as the 👀 Watch). Hide the now line outside the served window on
   the cards? That is one check at the `boldNowLines` call, but the cards would then differ from the Watch.

## Tests

- `frontend/src/components/GajjalaBoard.videoLook.test.tsx`: the toggle, its default, its storage, the axis wiring and the
  NEGATIVES (1-minute page, 🎾 card, an older API with no axis, a blocked store, no fetch on a toggle, ⤢ + SEPA link,
  phone source guards).
- Backend: `backend/tests/test_gajjala_card_axis_2026_11_17.py` (WP-A). FE engine: `lib/videoLook.test.ts`,
  `components/PatternChart.videoLook.test.tsx`, `lib/ggEllipses.test.ts` (WP-B). ⤢ view: `lib/gajjalaCardView.test.ts`,
  `components/GgCardView.test.tsx` (WP-D).
