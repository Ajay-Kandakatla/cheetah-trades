# 🔑 Key levels on the charts (2026-09-25)

**UNMEASURED.** A drawing and a fact, not a signal. Nothing sorts, gates, sizes, enters or scans on it. No in-house
study measures a break of a prior-day, week, month or 52-week level (`key_levels.MEASURED = False`).

## The ask, verbatim

Ajay 2026-09-25:

> "Can you build be key levels in to our charts? They are like demand zones. but very critical. Research and build thi sin
> to the app. With check box give it a brigh color in the chart. I wanna know when key levels are broken for a stock.
> Figure out if they have to be recalculated by daily closing of revious day or current day dybamincally and time frames
> yourself"

He handed us two decisions by name: the recalculation cadence and the timeframes. Both are decided below.

## Where it lives

| Piece | File |
|---|---|
| Engine (pure, one module) | `backend/supply_demand/key_levels.py` |
| Board post-pass (every tab except `ict`) | `chart_maps/board.py` `attach_key_levels`, after ⚡ `attach_burst`, sharing its ONE `bulk_cached_frames` read |
| Support tab (and 📁 Holdings, built from Support calls) | `chart_maps/api.py` `/chart-maps/support`, after 🪜, `per_side = SUPPORT_PER_SIDE` |
| The day's high on the live row | `sepa/prices.bulk_live_prices` gained `"high"` (additive) |
| Phone push (built OFF) | `supply_demand/key_level_alerts.py` — see `docs/notifications/key_level_alert.md` |
| Checkbox, colour, card chip, fold | frontend — see `docs/supply_demand/chart_overlay_legend.md` |

Payload: `tile["key_levels"]` = `{session, frame, phase, measured, verified, levels[], drawn[], chip, fold, rule,
stale_note}`, plus `key` / `key_broken` lines appended to `tile["lines"]`, every label starting `🔑 `. The board also
carries `key_levels_rule` (the one sentence `rule_text()` builds from the constants).

## 1. Definition — which levels, on which chart

Every level comes from **regular-session (RTH) daily bars** (the cached daily H/L equal the RTH 1-minute H/L on 24 of
24 name-days checked; extended-hours prints go beyond them). Tags: [P] primary source read, [S] third-party summary,
**CONV** = our convention.

| Member id | Chart label | Name | Computed from | Source |
|---|---|---|---|---|
| `day_high` / `day_low` | `🔑 PDH` / `🔑 PDL` | prior-day high/low | the last closed daily bar before the session | TrendStoic TV script: "most recent completed RTH session" [S]; Brooks, "Emini Sellers above Yesterday's High" [P]; ICT school: daily highs/lows = resting liquidity [S] |
| `week_high` / `week_low` | `🔑 PWH` / `🔑 PWL` | prior-week high/low | max high / min low of the last COMPLETE `W-FRI` week before the session's week | ICT school [S]. Taking the completed prior week is **CONV** (the completed-session rule, one period up) |
| `month_high` / `month_low` | `🔑 PMH` / `🔑 PML` | prior-month high/low | the calendar month before the session's month | **CONV** — no primary source defines a prior-month level |
| `year_high` / `year_low` | `🔑 52wH` / `🔑 52wL` | 52-week high/low | max high / min low of the last `YEAR_BARS` = 252 closed bars; **omitted below 252 bars**; `set_on` = date of the extreme bar | Huddart, Lang & Yetman 2009 [P]; George & Hwang 2004 (month-end 12-month high) [P]. Our nightly rolling window is **CONV** after the Turtles' "preceding N days" (Faith p.18) [P] |
| `pre_high` / `pre_low` | `🔑 pre-mkt H` / `🔑 pre-mkt L` | pre-market high/low | today's Support bars with `s == "pre"` dated the session (the 09:25–09:29 bar stamped 09:30 included); drawn only from 09:30 | TrendStoic TV script, 04:00–09:29 [S]; SMB [P, thin]. **CONV**, no evidence |

The 52-week high equals `zone_store.build_doc(...)["high_252"]` on the same closed cut (a test pins it on a ≥252-bar
frame). The member id is `f"{period}_{kind}_{int(round(price*100))}"` (e.g. `week_low_9578`): no dots, stable for the
session because the levels are frozen.

**Per chart frame (CONV, built on TradingView's documented "Auto" mapping [P]: the level period scales with the
chart; a level must come from a period longer than one bar of the chart; `week` is added to the daily chart so the card
draws every level the phone can name):**

| Frame | Periods | Lines per side |
|---|---|---|
| `daily` (every board tab except `ict`) | week, month, year | `GRID_PER_SIDE` = 1 |
| `daily` (Support, Holdings) | week, month, year | `SUPPORT_PER_SIDE` = 2 |
| `60m`, `15m` | day, week, month, year | 2 |
| `5m_today`, `24h` | pre, day, week, month, year — RTH levels say `RTH` in the label | 2 |

Left out, one line each: floor pivots / Camarilla (computed, not printed, no evidence); anchored VWAP (dynamic by
construction); value area / naked POC (needs volume-at-price); gap edges (fills ~20% in 5 days); round numbers (step
size is pure convention — follow-up); opening range (the `range` family draws it); prior-day close (inside the range,
its "break" is a red or green day); all-time high (the 2-year cache cannot see it); swing-cluster bands (that is the
demand/supply geometry already drawn).

## 2. Cadence — recalculated from the PREVIOUS period's close, never intraday

Every practitioner definition found freezes a level at its period's close (PDH/PDL = "most recent completed RTH
session" [S]; the Turtles' "preceding 20/55 days" [P]). A running current-week or current-month extreme is not a level
until its period closes (**CONV**). **Only the break test is live.**

| Level | Frozen at | Becomes the drawn level |
|---|---|---|
| PDH / PDL | prior RTH close | the **20:00 ET roll** (`ROLL_AT` = `zone_edge.SESSION_CLOSE`) after that close |
| PWH / PWL | Friday close | Friday 20:00 roll |
| PMH / PML | last session of the month | that evening's 20:00 roll |
| 52wH / 52wL | each close | nightly 20:00 roll |
| pre-mkt H / L | 09:30 ET (`PRE_FROZEN_AT`) | from 09:30; nothing earlier — running values are not levels |

- `levels_session(now)` = today (ET) when today is a market day and `now < ROLL_AT`; otherwise the NEXT market day
  (the shipped `market_hours.reminder.is_market_day` calendar).
- The closed-bar cut is `zone_store.drop_today(df, session)` — never "the last row", never `partial`. Today's partial
  row (and its spike) can never become a level.
- **State window:** states are computed only when `session == today ET` and `SESSION_START (04:00) ≤ t < ROLL_AT`.
  Outside it the levels draw plain, `state: null`, no chip — so a Friday snapshot is never read against Monday's levels.
  Phases: `pre` 04:00→09:30, `rth` 09:30→`close_confirm_at`, `close` →20:00.
- `close_confirm_at` = `CLOSE_CONFIRM_AT` 16:05, or `CLOSE_CONFIRM_AT_HALF` 13:05 on `timeframes.HALF_DAYS` (**CONV**:
  "the closing cross has printed"). 16:05 is verified by the V-close probe before promote.
- Refresh: board request (grid polls every 5 min), Support request (30 s while live), and the zone_edge pass every
  minute for the push scope.

## 3. Break — what "broken" means (per member)

Three schools: an intraday pierce counts (the Turtles, one tick, even intraday — "one school" [P]; Brooks [P]); a close
decides (Edwards & Magee via Brandt, ~3% for stocks [P]); acceptance by time (Dalton [P]). A failed break is a named
state everywhere (Brooks; Raschke Turtle Soup [S]; the ICT "sweep" [S]). The machine below is **CONV** assembled from
those pieces. **The `PIERCE_PCT` = 0.15% buffer on the pierce AND the close is CONV** — it reuses the house stop-sweep
minimum `sd_liquidity.SWEEP_MIN_PIERCE_PCT` by name (E&M's ~3% is far too wide for week/day levels; HIS CALL #5).

- **Side**, by position (the house rule): `ref_close` (last closed close) > L → `support`, break direction `down`;
  below → `resistance`, direction `up`. A PWH cleared on Monday is support by Wednesday.
  - **Repair 2026-09-25 (review round).** A close exactly AT the level keeps a high as `resistance`/`up` and a low as
    `support`/`down` — a stock that closed at its week or 52-week high no longer reads "broke 52wH ↓" on a 0.2% dip.
  - **Pre-market H/L are sided by kind** (high = `resistance`/`up`, low = `support`/`down`), never by yesterday's close:
    they are set after that close, so the price sits inside their range at 09:30 by construction. On a gap day the
    old rule read a lost pre-mkt L as "tested" (WULX live, 14.39 under 15.71) and a range the price sat inside as "broke".
  - Reclaim wording in the live states: a low crossed upward reads `🔑 back over PWL 183.42 ↑` (gap: `gapped back over`),
    a high crossed downward `🔑 back under …`; "broke" / "gapped through" stay for a low down and a high up.
  - Half days: a fresh print stamped on the session at or after `close_confirm_at` (13:05) counts as after-hours for
    `ah_through` (the clock label only says after-hours from 16:00).
  - The stale-note comparator is the snapshot's own `close` when its last trade is dated the cached bar's day (before
    Massive rolls), else `prev_day_close`. A 52w `set_on` outside the session's year prints the full date.
- `beyond(x)`: through L by at least `PIERCE_PCT` (the house sweep rule is `>=`; compared in %). `back_inside(x)`: back
  on the original side by the same amount. "Tested" band: within `AT_LEVEL_PCT` (= `scalping.candles.LEVEL_TOL_PCT`,
  0.30%) on its side, or through by less than `PIERCE_PCT`.
- **Fresh print** = `zone_bounce_alerts.print_from_snapshot(row, now, STALE_PRINT_SEC=180)` AND
  `prices.extended_print(row)["date"] == session`. Otherwise none — at 04:00 last evening's final after-hours trade is
  NOT a print. The board's `_snapshot_print` is not used for states (no staleness drop, by design).
- **Evidence:** `pre` = the fresh print only (the day aggregate is 0 = unknown) plus the first-seen stamp; `rth` = the
  day's extreme (support reads `low`, resistance `high`) plus the fresh print; `close` = the RTH close decides.

| Phase | State | Rule | Chip? |
|---|---|---|---|
| pre / rth | `broken` | fresh print beyond | **yes** — `🔑 broke PWL 95.78 ↓ 10:42` (time only when known), `🔑 gapped through PWL 95.78 ↓` when the open was already beyond, ` · pre-mkt` in pre-market |
| pre / rth | `reversal` | pierced earlier this session, fresh print back inside | fold only |
| pre / rth | `pierced` | pierced earlier, print missing or inside the buffer | fold only |
| pre / rth | `tested` | the extreme came within the tested band, never beyond | fold only |
| pre / rth | `intact` / `unknown` | none of the above / no print and no extreme | — |
| close | `closed_beyond` | the close beyond | **yes** — `🔑 closed under PWL 95.78` / `closed over` / `closed back over` / `closed back under` |
| close | `reversal` | pierced and the close back inside | fold only |
| close | `tested` | the extreme within the band, or the close inside the buffer | fold only (PWL 100, low 99.50, close 100.10 → tested, never "broke") |
| close | `intact` | otherwise | — |
| close | `ah_through` | a fresh after-hours print beyond, not `closed_beyond` | **yes** — `🔑 after-hrs under PWL 95.78` |

- `closed_beyond` is `null` before the close-confirm minute.
- **Chip precedence:** one chip per tile; winner = highest `PERIOD_RANK` (pre 0 < day 1 < week 2 < month 3 < year 4),
  then the largest `|beyond_pct|`; ` +N` for N further candidates. Never starts with an arrow; never says "bounce".
- Wording is facts only — "under / over / back over / back under" — because Huddart et al. find returns positive after
  BOTH 52-week crossings, so no tone implies a direction.
- `first_through` / `reversal_at` come from `key_level_state` (one doc per session, written by the zone_edge hook for
  the push scope); board-only names show no time.
- `last_close_cross` (week/month): the most recent closed bar after the level's period whose close went beyond the
  level from the side the PRIOR close sat on — the fold reads "closed under Wed 09-23".

## 4. Caps and merge (drawing only)

- **Merge:** members on the SAME side of `ref_close` within `AT_LEVEL_PCT` of the cluster's first member (sorted by
  price) draw as ONE line, e.g. `🔑 52wH = PMH 110.00`. The price is the highest-rank member's printed price, never an
  average. **Opposite sides never merge.** Tone `key_broken` if ANY member is `broken` or `closed_beyond`.
  **State, chip, fold, first-seen and push are per MEMBER** — a merge never hides a member's break.
- **Cap:** the nearest `per_side` clusters above the anchor and below it (anchor = the fresh print, else the day close
  in RTH/AH, else `ref_close`); a tie goes to the higher rank. Every member, drawn or not, stays in `levels` (`drawn:
  false`) and in the fold.
- **52W dedupe:** a tile that already draws a line labelled `52W…` (the Breaking tab) draws no 52-week-high line; the
  member stays in the block and the fold. By label, not price.
- **Guards — `stale_note` set, no lines, no chip, the levels still listed in the fold with the note:**
  - the closed frame ends before `prev_market_day(session)`: "key levels need bars through {d}; cached bars end {last}";
  - the last closed close equals neither the snapshot `prev_day_close` nor its day `close` (to the cent): "the {date}
    bar in our cache is not the final close yet ({cached} vs {official})" — a partial row stuck in the cache;
  - no cached frame: "no cached daily bars for {SYM}". With no snapshot row at all the levels draw with `verified: false`.

## 5. Display first

`key_levels` is imported only by `chart_maps/board.py`, `chart_maps/api.py`, `supply_demand/key_level_alerts.py`,
`supply_demand/rules_info.py` and tests; `zone_edge` reaches it only through `key_level_alerts`, lazily. A source-guard
test (`tests/test_key_levels.py::test_import_guard_display_only`) enforces it.

## 6. Follow-up study (pre-registered, NOT built)

`backend/studies/key_level_break_study.py`, run outside RTH. Universe: zone_store `full` + the push scope, 2y cached
frames. Events per member type (PWH/PWL/PMH/PML/52wH/52wL): E1 close-through (first per life, the push latch), E2
reversal, E3 tested-and-held. Outcomes: 1/5/21-session return and excess vs SPY; stop-out = 1×ATR14 adverse before 2×ATR14
favourable. Placebo: a synthetic level at the same % distance from the prior close, same name and date. Date-block
bootstrap, 2,000 draws, 95% CI on event − placebo; n, win rate, expectancy and stop-out rate side by side. Primary
endpoint: 5-session excess for E1, Holm over 6 types. `measured` only if the CI excludes 0; otherwise every surface
keeps "UNMEASURED". Priors: Huddart (positive after both 52w crossings); the ICT board's PDH/PDL sweeps measured null
(+0.03R vs 0.00R placebo, 6,004 resolved).

## Tests

- `backend/tests/test_key_levels.py` — periods (complete week on Mon/Wed, first session of a month, holiday week,
  251 vs 252 bars + the `high_252` pin, partial-row spike, tz-aware index), roll/phase/half day, pre-market filter,
  fresh print (stale, 181 s, ns/ms, wrong date), live and close states both directions (0.14% vs 0.15%), merge, cap,
  guards, payload finiteness and wording, constant pins, import guard.
- `backend/tests/test_chart_maps_key_levels.py` — board post-pass idempotent, ONE frames read shared with ⚡, a raising
  engine, ICT carries nothing, 52W dedupe, Support 15m / 5m_today, the Support endpoint call, `bulk_live_prices` `high`.

## Sources

- Brooks, "Emini Sellers above Yesterday's High" (2024-08-07) — https://www.brookstradingcourse.com/analysis/emini-sellers-above-yesterdays-high/
- Curtis Faith, *The Original Turtle Trading Rules* (p.18) — https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf
- Brandt, trendlines tag (E&M decisive close) — https://www.peterlbrandt.com/tag/trendlines/
- TradingView, Pivot Points Standard ("Auto" mapping only) — https://www.tradingview.com/support/solutions/43000521824-pivot-points-standard/
- TrendStoic PM/PD levels script — https://www.tradingview.com/script/aagow1P4-Premarket-High-Low-Prior-Day-High-Low-Opening-Price/
- SMB, "Using Premarket Price Action and Levels" — https://www.smbtraining.com/blog/using-premarket-price-action-and-levels
- Wikipedia, Market profile (Dalton / Initial Balance) — https://en.wikipedia.org/wiki/Market_profile
- LuxAlgo, Overnight & ETH levels — https://www.luxalgo.com/library/concept/overnight-and-eth-levels/
- innercircletrader.net (unofficial ICT education) — https://innercircletrader.net/tutorials/liquidity-in-forex-trading/
- Osler 2003, JF — https://ideas.repec.org/a/bla/jfinan/v58y2003i5p1791-1819.html
- Osler 2005, JIMF — https://ideas.repec.org/a/eee/jimfin/v24y2005i2p219-241.html
- Chung & Bellotti 2021 — https://arxiv.org/abs/2101.07410
- George & Hwang 2004 — https://www.bauer.uh.edu/tgeorge/papers/gh4-paper.pdf
- Huddart, Lang & Yetman 2009 — https://pure.psu.edu/en/publications/volume-and-price-patterns-around-a-stocks-52-week-highs-and-lows-/
- Della Vedova, Grant & Westerholm (AFA 2019) — https://www.aeaweb.org/conference/2019/preliminary/paper/yyd8hBtb
- Team LBR, "MP Value Area Rule (80% Rule)" — http://teamlbr.blogspot.com/2008/09/mp-value-area-rule-80-rule.html
- Wikipedia, Pivot point — https://en.wikipedia.org/wiki/Pivot_point_(technical_analysis)
- Shannon, "How To Use The Anchored VWAP" — https://alphatrends.net/archives/2017/12/use-anchored-vwap-avwap/
