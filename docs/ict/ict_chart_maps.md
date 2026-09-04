# ICT Strategy — the Chart Maps tab (took the Into Supply slot)

Shipped 2026-09-03 (late). Ajay: *"create a new chart maps tab for ICT
Strategy, replace supply tab with this new tab."*

Code: `backend/ict/` (`structure.py` pure rules, `engine.py` macro/micro/scan,
`board.py` tile geometry), `backend/chart_maps/board.py::ict_tiles`,
`GET /chart-maps?tab=ict&bias=&micro=`. Tests: `backend/tests/test_ict.py`.

## Source status — read this first

| What | Where it comes from | Status |
|---|---|---|
| Manipulation = lack of displacement | Jesse Rogers, https://www.youtube.com/watch?v=Q7Ryv1M7CvI **02:39** | video |
| Two or more consolidations toward an HTF fair value gap | same video, **03:57** | video |
| Power of 3: accumulation first, then the manipulation below its lows | same video, **05:30** | video |
| Confirmation = opposite displacement that creates a new FVG | same video | video |
| Fractal swings, raw FVG, MSS, inverted FVG, daily-sets / 60m-triggers | Ajay's own spec (2026-09-03) | spec |
| Every number below marked **owner rule** | this app | **not from the video** |

Nothing here is a book method. No Minervini / SEPA gate, threshold or cite is
imported into this strategy, and there is no moving average or volume-weighted
price anywhere in the logic — purely price action, as asked. `test_ict_sources_
cite_the_video_and_nothing_else` locks that.

## The concepts, and how each one is mechanised

Frames: **macro** = the daily frame (`sepa.prices.load_prices` with today's
live bar overlaid by `with_today_bar` — one bulk snapshot for the whole
universe, never one HTTP call per name; a name the bulk call omits stays on
closed bars rather than fetching its own snapshot); **micro** = the 60-minute
RTH frame (`supply_demand.timeframes.frame_for(symbol, "60m")`, left-closed
resample — never re-implemented here). `micro=15m` is accepted and cached
separately.

**Live bars.** The newest daily bar (the snapshot overlay) and the newest 60m
bar (the hour in progress) are partial during RTH. Wick rules (a tap, the
manipulation's low) are facts the moment they print; close rules (the
manipulation's close-back, an inversion, the MSS close) read the partial bar's
last print as its close, the same convention `supply_demand.smc.liquidity_sweeps`
uses — so a state reached on the live bar can still change until that bar
closes. The 15-minute cron re-reads it; nothing here is a fill.

### Swing points — 3-candle fractals (spec)

`High[i-1] < High[i] > High[i+1]`, lows mirrored, **strict on both sides**: an
equal high is not a swing. These are the take-profit targets (external
liquidity): stops rest under swing lows and over swing highs. The community
wider-window variant (`supply_demand/smc.py`) is exposed as
`swing_points_window` for comparison only.

### Fair value gap — the raw three-candle gap (spec)

```
bullish:  Low[i+2] > High[i]   -> band [High[i], Low[i+2]]
bearish:  High[i+2] < Low[i]   -> band [High[i+2], Low[i]]
```

Touching is not a gap. **No displacement or width filter** — the spec's FVG is
the raw gap, so `supply_demand.patterns.fair_value_gaps` (which filters on
0.8 ATR and 0.15%) is not used here. A gap is recorded with `i` = its third bar
(the bar it exists from) and `disp_i` = the displacement candle that left it.

State against the bars after it: `active` (untouched) → `mitigated` (a wick
traded into it) → `filled` (a wick reached the far edge) → `inverted` (**a
candle CLOSED beyond the far edge**). A bearish gap closed above its top
becomes inverted bullish support; a bullish gap closed below its bottom
becomes inverted bearish resistance. A wick through the far edge fills the gap
and does not invert it — the inversion is the close.

### Consolidation (video says "consolidation", gives no number)

A run of ≥ `CONSOL_MIN_BARS` consecutive bars whose combined high-low span is
≤ `CONSOL_MAX_ATR` × ATR14. One bar too wide ends the run on the bar before
it. Non-overlapping, oldest first.

### Manipulation — lack of displacement (video 02:39)

The newest bar that traded THROUGH a key level but failed to displace:

```
Low < key_low  AND  Close >= key_low - DISPLACE_MAX_ATR x ATR      (bullish)
High > key_high AND Close <= key_high + DISPLACE_MAX_ATR x ATR     (bearish)
```

`DISPLACE_MAX_ATR = 0.0` means the bar must close back at or above the level.
The scan is newest-first and **decides on the newest bar that traded through
the level**: if that bar closed through by more than the tolerance it is a
true break, the level is gone, and the answer is None — an older manipulation
that a later break invalidated is not resurrected.

### Power of 3 (video 05:30)

Find the accumulation range FIRST (a consolidation), then the manipulation
beyond it: a wick under its low that closes back inside = bullish; over its
high = bearish. Newest complete range first; a range still forming on the last
bar has no manipulation yet.

### Confirmation — opposite displacement that leaves a new FVG (video)

On the manipulation bar itself or within `CONFIRM_MAX_BARS` after it, a bar
whose **body** is ≥ `DISPLACE_MIN_ATR` × ATR in the opposite direction AND
which is the displacement candle of a raw FVG in that direction. A big candle
that leaves no gap does not confirm; a gap left by a small candle does not
either.

### Market structure shift — the primary entry condition (spec)

Newest bar first, reading **nothing after the bar it labels**:

* the **cross** is bar k — its close is beyond the most recently formed
  opposing fractal swing while bar k-1's close was not;
* the **gap** is a raw FVG in the breakout direction whose third bar is g (the
  bar the gap exists from);
* the MSS bar is the **later** of the two, `i = max(k, g)`, with the earlier
  one within `MSS_FVG_WITHIN_BARS` of it and bar i's close still beyond the
  swing.

The displacement candle that crosses usually leaves its gap one bar later, so
the MSS is most often labelled on the gap's third bar — the first bar on which
both conditions are facts. It is never labelled on a bar whose gap is only
known from the bar after it (the first cut did that; reviewer fix 2026-09-03,
`test_mss_never_reads_the_bar_after_the_one_it_labels`). A cross with no gap
inside the window is not an MSS; the scan keeps looking older. The engine only
accepts an MSS whose cross is on or after the manipulation bar.

### Inverted FVG — the entry trigger (spec)

An OPPOSING gap that a candle closed through **after the manipulation** (a
bearish gap a bullish candle closed above, for a long). Its band is the entry
zone when present; otherwise the new FVG from the displacement / MSS is.

### Stacked consolidations toward the HTF gap (video 03:57)

Nearest unfilled daily gap to the last print; within `STACK_LOOKBACK_BARS`
daily bars, the consolidations that sit on the price side of that gap and step
toward it (each successive range's midpoint closer than the one before).
Count ≥ `STACK_MIN` (video: "two or more") = stacked, shown as a warn badge.

## Multi-timeframe: macro sets, micro triggers, micro is DORMANT

1. **Macro (daily)** per name: last `N_SWINGS` fractal swing lows/highs, key
   low / key high (the nearest recent swing below / above the last print; the
   extreme one when price is beyond them all), live daily gaps
   (active / mitigated / inverted), daily consolidations, the stack read, and
   **tapped**: within the last `TAP_LOOKBACK` sessions the bar's low reached a
   recent swing low × (1 + `TAP_TOL_PCT`), or its high reached a swing high ×
   (1 − tol), or its range intersected a live daily gap (tolerance on both
   edges). The swing must have formed before the tapping bar. Newest bar wins;
   on one bar a swing beats a gap. The tap carries a bias (swing low / bullish
   gap → bullish; swing high / bearish gap → bearish; an inverted gap carries
   its inverted bias).
2. **Micro (60m)** runs **only for tapped names** — the dormant loop. An
   untapped name never loads an intraday frame (`test_the_micro_loop_stays_
   dormant_for_untapped_names` asserts it through an injected loader counter).
   When more names tapped than `MICRO_MAX`, the cap keeps the newest taps by
   session **date** (not bar index — frames differ in length), then the most
   liquid. Both biases are read; the best by state, then grade, then the
   tapped side wins.
3. **State machine** per bias:
   `accumulation → manipulation → confirmed (MSS + new FVG) → entry`
   (price within `ENTRY_TOL_PCT` of the IFVG or the new FVG).
   Manipulation comes from Power of 3 first, else from the tapped daily level.
4. **Grade** 0-100 (owner scoring): manipulation 30 + opposite displacement 20
   + MSS 30 + entry 20.
5. **Plan** (display only — not advice): entry zone = the IFVG (preferred) or
   the new FVG, entry price = the zone's proximal edge (bullish: its top;
   bearish: its bottom); stop = the manipulation extreme ∓ `STOP_BUFFER_ATR` ×
   60m ATR; target = the next daily swing in the trade direction (external
   liquidity); `rr = reward / risk`, None when no daily swing lies beyond the
   entry.
6. Rows sort **entry > confirmed > manipulation > accumulation**, then grade
   desc, then symbol.

## Owner constants — every number the video does not give

| Constant | Value | Where | Status |
|---|---|---|---|
| `FRACTAL_WINDOW` | 1 | structure | spec / video (3-candle fractal) |
| `STACK_MIN` | 2 | structure | video 03:57 ("two or more") |
| `ATR_PERIOD` | 14 | structure | **owner rule — not from the video** |
| `CONSOL_MIN_BARS` | 5 | structure | **owner rule — not from the video** |
| `CONSOL_MAX_ATR` | 1.5 | structure | **owner rule — not from the video** |
| `DISPLACE_MAX_ATR` | 0.0 | structure | **owner rule — not from the video** (must close back at/above the level) |
| `DISPLACE_MIN_ATR` | 1.0 | structure | **owner rule — not from the video** |
| `CONFIRM_MAX_BARS` | 3 | structure | **owner rule — not from the video** |
| `MSS_FVG_WITHIN_BARS` | 1 | structure | **owner rule — not from the video** |
| `STACK_LOOKBACK_BARS` | 60 | structure | **owner rule — not from the video** |
| `N_SWINGS` | 5 | engine | **owner rule — not from the video** |
| `TAP_LOOKBACK` | 2 sessions | engine | **owner rule — not from the video** |
| `TAP_TOL_PCT` | 0.25 % | engine | **owner rule — not from the video** |
| `ENTRY_TOL_PCT` | 0.5 % | engine | **owner rule — not from the video** |
| `STOP_BUFFER_ATR` | 0.2 (60m ATR) | engine | **owner rule — not from the video** |
| `MICRO_MAX` | 40 names | engine | **owner rule — not from the video** |
| `MICRO_DAYS` | 21 | engine | calendar days of 1-minute bars behind each 60m/15m frame (~15 sessions), resampled by the house closed=left resampler; frame_for's own 70-day span cost ~20 s a name and starved the micro budget (2026-09-04) |
| `MIN_TARGET_R` | 1.0 | engine | the next daily swing counts as the target only when it pays at least this many R; nearer 3-candle fractals are skipped (2026-09-04, first seed read R:R 0.01) |
| `BUDGET_SEC` | 120 s | engine | **owner rule — not from the video** |
| `ICT_TTL_SEC` | 900 s | engine | **owner rule — not from the video** |
| `KEEP_DAYS` | 5 | engine | **owner rule — not from the video** |
| `MACRO_MIN_BARS` | 60 | engine | **owner rule — not from the video** |
| `MICRO_MIN_BARS` | 30 | engine | **owner rule — not from the video** |
| `MACRO_FVG_LOOKBACK` | 120 daily bars | engine | **owner rule — not from the video** |
| `MACRO_FVG_KEEP` | 6 | engine | **owner rule — not from the video** |
| `LIQ_WINDOW` | 50 sessions | engine | **owner rule — not from the video** |
| `GRADE_MANIPULATION` / `GRADE_DISPLACEMENT` / `GRADE_MSS` / `GRADE_ENTRY` | 30 / 20 / 30 / 20 | engine | **owner rule — not from the video** |

`ict.engine.params()` returns this list with `from_video` flags; the board
envelope carries it as `params` and the page prints it under the tiles, so a
setting is never mistaken for a rule.

## Tile legend (chart_maps tile contract, drawn on DAILY bars)

| Element | Kind / tone | Label |
|---|---|---|
| accumulation range (60m) | band `base` | `accumulation` |
| bullish / bearish 60m FVG | band `demand` / `supply` | `FVG` |
| inverted 60m FVG | band `neutral` | `IFVG` |
| live daily FVGs | band `demand` / `supply`; inverted → `neutral` | `daily FVG` / `IFVG (daily)` |
| entry zone | band `demand` (bullish) / `supply` (bearish) | `entry` |
| stop / target | line `stop` / `target` | `STOP x` / `TARGET x` |
| key low / key high | line `neutral` | `key low x` / `key high x` |
| last print | line `now` | `now` |
| manipulation bar | marker `sweep` | `MANIP` |
| MSS close | marker `bos` | `MSS` |
| IFVG close (or the FVG entry) | marker `buy` (bullish) / `sell` (bearish) | `IFVG` / `ENTRY` |

The tile chart draws daily bars, so every 60-minute event is placed by the
**ET date** of its bar (intraday stamps are UTC; daily stamps are session
dates and are not shifted). Several micro events can share a date; the newest
per marker kind wins. Stats: State · Grade · R:R · Bias · Micro tf · Tapped.
Badges: `MSS ✓`, `no displacement ✓`, `push N ATR + FVG ✓`, `IFVG`,
`at entry zone` (good); `stacked consolidations` (warn); `tapped …` (muted).

Envelope: `{tiles, dropped_thin, min_tier, ..., note, warming, as_of,
generated_at, cached, stale_sec, truncated, counts: {macro_n, tapped_n,
micro_n, rows, matched}, params, source: {video, timestamps, note}, bias,
micro, disclaimer}`. The liquidity floor works on these rows because each
carries `liquidity.avg_dollar_vol_50` from the daily frame.

## Ops

* **Store**: Mongo `ict_board` — `{_id: "latest"}` (60m; `"latest:15m"` for
  the other micro frame) plus dated copies `{_id: "YYYY-MM-DD:HHMM:tf"}`
  purged after `KEEP_DAYS`. The cache is Mongo, not process memory, so the
  cron container's scan IS what the api container serves (unlike the demand
  board's curl-warm).
* **Cron** (`backend/crontab`): `*/15 9-16 * * 1-5 python -m ict.engine` and
  `50 16 * * 1-5 python -m ict.engine` (post-close pass so the tab is fresh at
  the next open). One scan, one INFO line.
* **Request path**: `ict.engine.cached_or_warm` serves the latest doc; older
  than `ICT_TTL_SEC` → it still returns the stale rows with `warming: true`
  and kicks ONE background thread per timeframe (Cloudflare cuts at ~100 s;
  nothing on the request path blocks). No store → `warming: false` with a
  note, never a pointless scan.
* **Manual run** (api or cron container): `python -m ict.engine`; single
  name: `python -c "from ict import engine as E; print(E.macro('NTAP'))"`,
  then `E.micro('NTAP', '60m', macro_ctx=E.macro('NTAP'))`.
* **Budget**: `BUDGET_SEC` wall clock across both passes; `MICRO_MAX` caps
  the intraday loads. Either cut sets `truncated: true` on the doc and the
  board, which says so rather than pretending it saw everything.
* Universe: `supply_demand.zone_store.big_cap_universe()` (~1,124 names,
  cap ≥ $1B) — the same list the zone store draws.

## Tests

`backend/tests/test_ict.py`. The negatives: a tie is not a swing; touching
candles leave no gap; a wick through the far edge fills but does not invert; one
wide bar breaks a consolidation; a close through the level is a break, not a
manipulation, and a later break cancels an earlier manipulation; a big candle
without a gap does not confirm, nor a small one with a gap; a cross without a
gap is not an MSS, nor a gap without the cross; a single range is not a stack;
the micro loop never loads a frame for an untapped name; `micro_max` and a
spent budget flag `truncated`; `cached_or_warm` answers a stale doc in
milliseconds while the scan runs in a thread, and starts one warm at a time.
Source discipline: every `ict/*.py` carries the video URL and none carries a
book cite, a page cite or a moving-average token.

*Decision support, not advice. The rules are one video's plus the owner's
settings; nothing here is backtested yet.*

## 2026-09-04 fix after the first live seed

The first seed woke **1,122 of 1,123** names (any bar sitting under an old swing low counted as a tap), so the micro loop was not dormant and the 120 s budget covered 17 names. The tap now requires a **fresh touch**: the bar before the tap must still be on the far side of the level (or outside the gap). `MICRO_DAYS` and `MIN_TARGET_R` above were added the same night.
