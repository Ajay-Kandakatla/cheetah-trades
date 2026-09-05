# Multi-timeframe zones, ORB, Fair Value Gaps, and computed entry/stop

Shipped 2026-08-29. Ajay: *"What are the concepts or ORB and Fair value gap
and can do this in Daily, Market hourly, 15 mins time charts ... For supply
and demand zone ... Give me stop loss and Entry calculated dynamically ...
I need this in Support level and also on the supply demand zone drop downs"*
plus *"any other bullish patterns on an hourly chart ... Cup handle or
Inverse head and shoulder or Flat top"*.

## Source status — read this first

This page mixes three tiers of evidence. They are not equal and the code
labels which is which on every record.

| Concept | Source | Status |
|---|---|---|
| Opening Range Breakout | Toby Crabel, *Day Trading with Short Term Price Patterns and Opening Range Breakout* (1990); Linda Raschke, *Street Smarts* (1995) | **Cited** — already the basis of `daytrading/signals/orb.py` |
| Cup w/ handle, inverse H&S, double/triple bottom | Bulkowski (cup.html et al.), Lo-Mamaysky-Wang | **Cited**, verbatim in `patterns/detector.py` |
| Fair Value Gap | ICT (Inner Circle Trader) — video/community material | **No canonical text in the library.** Definition stated in full below so it is auditable without a source |
| Flat top (ascending triangle) | — | **CONVENTION.** Parameters are this app's choices, labelled `cited: false` |
| Zone clustering, dynamic entry/stop | `supply_demand/price_zones.py` | App's own configured method, never a book method |

**The statistics do not travel across timeframes.** Bulkowski's 62% throwback,
his 61%/74% measure-rule factors and the "47% dropped substantially within two
months" warning were all measured on *daily* bars. The shape rules are
scale-free; the hit rates are not. Every non-daily pattern record carries
`stats_transfer: false` and a caveat string, and the UI prints it. The app's own
forward ledger (`GET /patterns/accuracy`) is likewise daily-only and is not fed
by intraday scans.

## The concepts

### Fair Value Gap — a three-bar imbalance

A gap in *traded price*, not in time. Bar 2 moves so hard that bar 1 and bar 3
never overlap, leaving a price band inside which almost nothing changed hands.

```
bullish (demand):  bar1.high < bar3.low   → band = [bar1.high, bar3.low]
bearish (supply):  bar1.low  > bar3.high  → band = [bar3.high, bar1.low]
```

Why it is a zone: the band is unfinished business. If buyers ran price through
it without transacting, the resting orders that would have filled there are
still there. Price returning offers those fills — the same premise as every
supply/demand zone in this app, arrived at from the tape instead of from a
swing pivot.

Two filters keep it off noise (`supply_demand/patterns.py`):

* **Displacement** — bar 2's range must exceed `MIN_DISPLACEMENT_ATR` (0.8) ×
  ATR. A gap left by a sleepy bar is a rounding error.
* **Mitigation** — once price trades back in, the gap is filling. `fill_pct`
  tracks how much is gone; past `MAX_FILL_PCT` (50%) the zone is spent and is
  dropped. An unfilled gap is the whole signal.

### Opening Range — the session's first agreed band

High/low of the first N minutes of regular trading. Overnight orders, gap
reactions and the first institutional prints clear inside it, so it is the day's
first honest agreement on value. Above it, buyers won the auction; below,
sellers did. Window scales with the chart: 15 min on a 15m chart, 60 on hourly,
30 on daily — ORB is intrinsically intraday, and a daily chart borrows it as
"where today's auction opened", not as a daily-bar pattern.

### Dynamic entry and stop

Every band already implies the trade:

```
entry = the PROXIMAL edge (the side price reaches first)
stop  = the DISTAL edge, plus an ATR-scaled buffer beyond it
```

The buffer exists because a stop resting exactly on the level everyone can see
is the liquidity that gets taken. It scales with ATR (`STOP_BUFFER_ATR` = 0.25)
with a `MIN_STOP_BUFFER_PCT` floor of 0.10%, so a quiet name gets a tight stop
and a volatile one is not shaken out by its own noise.

Target 1 is the **next opposing band** when one exists — real structure — and
otherwise a measured `DEFAULT_TARGET_R` (2.0) multiple, labelled as such so a
computed target is never mistaken for a level. Risk is a fact of the geometry;
position size comes off the stop distance (`desk/scoring.position_size`), never
off conviction.

## Timeframes

`supply_demand/timeframes.py`. Nothing about the zone methodology changes —
only the frame it reads.

| Key | Label | Bars | Span | Source |
|---|---|---|---|---|
| `daily` | Daily | 252 | 1 year | `sepa.prices.load_prices` |
| `60m` | 1 hour | 330 | ~47 sessions | 1-min Massive bars resampled |
| `15m` | 15 min | 260 | ~10 sessions | 1-min Massive bars resampled |

Two decisions worth keeping:

* **Resampling is left-closed, right-labelled.** The bar stamped 09:45 holds
  09:30–09:44. Closing on the right instead looks equivalent and is not: it
  orphans the session's opening minute into a bucket of its own, so every
  session starts with a one-minute bar wearing a 15-minute label — a fake
  extreme the swing and gap detectors would read as structure. Locked by
  `test_resample_is_right_closed_and_drops_empty_buckets`.
* **The hourly budget is 330 bars on purpose.** Bulkowski's minimum cup is
  "7 weeks" = 245 hourly bars; a smaller budget would make the cup detector
  silently barren on this timeframe and look like a bug.

RTH only on intraday frames. A swing low made on 400 shares at 07:12 is not a
level anyone defended.

## Pattern gates scale by calendar time, not by bar count

Bulkowski cites cup duration as "7 to 65 weeks" — calendar, not bars. On a daily
chart 7 weeks is 35 bars; hourly it is 245; on 15-minute, 910. Copying the daily
bar-count to a fast chart would find a "7-week cup" inside two sessions and label
it with a citation it does not have. `patterns/timeframe.BARS_PER_SESSION`
converts, so the cited *duration* survives the timeframe change.

The consequence is honest and is surfaced rather than hidden: on 15-minute bars
the cup, double bottom and triple bottom cannot reach their own minimum inside a
10-session window, so `reachable()` reports them as out of range and the UI names
them. Only inverse head-and-shoulders and flat top fire there.

## Where it appears

* `GET /chart-maps/support?symbol=&window=&tf=` — Support tab, second dropdown
* `GET /supply-demand/price-zones/{symbol}?tf=` — per-ticker zone drill-in

Both carry `trade_levels` (every band with its entry/stop/target/R),
`fair_value_gaps`, `opening_range`, and `bullish_patterns`. Omitting `tf` is the
historical daily path, byte for byte — the intraday branch is additive.

A board-wide timeframe dropdown was **not** built: it would need intraday bars
for ~1,700 symbols per refresh. The per-ticker drill-ins are where an intraday
level is actually read.

## Tests

`backend/tests/test_timeframes_patterns.py` (24) and
`frontend/src/components/SupportLevels.test.tsx`. The negatives carry the
weight: junk timeframes fall back to daily, a filled gap is dropped, a sleepy
bar leaves no gap, nonsense geometry returns no stop rather than a fabricated
one, and an hourly shape can never claim daily statistics.

*Decision-support only. Not investment advice.*

---

# Smart Money Concepts: sweeps, BOS/CHoCH, order blocks

Added 2026-08-29. Ajay supplied Brad Goh's mechanical five-step model:
identify liquidity → wait for the sweep → mark the order block → mark the FVG
→ execute on mitigation.

## Source status

**No canonical text.** SMC is community-taught (ICT lineage; Brad Goh is a
YouTube educator). Unlike the trend template (Minervini, page-cited) or the cup
(Bulkowski, verbatim), nothing in the library backs these definitions. Every
threshold in `supply_demand/smc.py` is labelled CONVENTION and every record
carries `cited: false`.

That is a reason to **measure** it, not skip it. Setups are written to
`learning.observations` and resolved against real forward prices, so
"does sweep→BOS→OB actually pay on my names" becomes a number rather than a
video claim.

## Definitions as implemented

**Liquidity** rests where stops rest: above swing highs (buy-side), below swing
lows (sell-side).

**Liquidity sweep** — price trades THROUGH a prior swing extreme and closes back
on the original side. The wick took the stops; the close says the move was not
accepted. *A close beyond the level is a breakout, not a sweep, and the two mean
opposite things* — so the close is the entire test. Locked by
`test_a_sweep_needs_the_close_back_inside_or_it_is_a_breakout`.

**BOS vs CHoCH** — both are a CLOSE beyond the most recent opposing swing. BOS
continues the prior leg; CHoCH reverses it. After a sweep the CHoCH is the one
that matters, because a sweep is a reversal premise. `grade()` pays +15 for it.

**Order block** — the last opposing candle before the displacement (last down
candle before an up-move). The displacement must exceed
`MIN_DISPLACEMENT_ATR` = 1.2× ATR: without an impulse it is a red candle, not an
institutional footprint.

**FVG** — the three-bar imbalance inside the displacement, used to refine the
entry inside the block (step 4).

## The two entries, and the trap in the second one

| Style | Entry | Why |
|---|---|---|
| aggressive | order block's proximal edge | fills more often, wider stop |
| conservative | the FVG inside the block | deeper, better R, fills less often |
| aggressive_tight | same entry, stop beyond the sweep wick | Brad Goh's refinement note |

Each leg reports its **own** risk and R, because a blended number would hide the
trade-off the choice exists for.

**Noise floor.** A deeper entry against the same stop produces a huge R
arithmetically — the synthetic fixture yields 23.62R on the conservative leg.
A stop closer than `MIN_STOP_ATR` = 0.5 ATR is inside the bar-to-bar noise of
the timeframe: it gets taken out by wiggle, not by the idea being wrong. Such
legs are flagged `too_tight` with a warning, and the R is still shown — hiding
it would be its own dishonesty. Same lesson as the Desk's ASH row (2026-08-28).

## Quality over quantity

The model's own rule, made operational: `grade()` scores 0-100 (CHoCH +15,
displacement ≥2 ATR +15, FVG present +12, fresh sweep +10, mitigated +8) and
`find_setups` returns nothing when any step is missing. Measured 2026-08-29 on
live bars: AMD produced 3 setups on 15m and 1 on hourly; AVGO and KTOS had all
four primitives but **zero** complete sequences. That asymmetry is the filter
working.

*Decision-support only. Not investment advice.*

## Live frame — `5m_live` (2026-09-02)

Ajay: *"Can you add live chart please, for supply demand? I wanna see where
things bounced over night."*

| | |
|---|---|
| Bars drawn | last ~2.5 sessions of **5-minute** bars **including pre-market (04:00) and after-hours (to 20:00 ET)**; extended-hours bars carry `s: 'pre' \| 'ah'` and are shaded on the chart |
| Levels | the **6-month DAILY window** (`window=6m`) — the same zones the daily views print. Not the intraday frame: after a gap, 2.5 sessions of 5-minute swings can hold no level at all (CRDO 2026-09-02, −8% overnight: no support on the intraday frame; on the daily frame it broke 198.8–201.2 and bounced off 184.75–186.98) |
| Structure/mood/signal/SMC/patterns | computed on the daily frame; the signal is **not** re-recorded under `5m_live` (it is the daily signal) |
| Refresh | `live.refresh_sec` = 30 while any extended session is open, 0 when closed (`timeframes.live_state`, ET clock, weekdays); the FE polls quietly on that cadence |
| Overnight read | `overnight` = bars since the last RTH bar: low/high/last with ET times, `change_pct` vs the RTH close, and every daily band the tape ENTERED with `held` / `broke` — stated as a print, not a defended level |

**Session tag through the resample.** `resample_ohlcv` keeps the minute
loader's `session` column (`first` per bucket). Safe on the 5- and 15-minute
grids because every boundary (04:00, 09:30, 16:00, 20:00 ET) sits on them;
the 60-minute frame is RTH-only so it never sees a straddling bucket.

**ET on the axis.** Intraday bar stamps (`_frame_bars`) and every overnight
time are now America/New_York. They were UTC before — a 13:30 stamp over the
opening bar read as a lunch print. This applies to the 15m / 60m / 15m-open
views too.

## 2026-09-05 — engine fixes (Ajay: *"yes please fix the bugs"*)

Sign-off covers every item, including the ones that change what the tab
prints. No threshold changed. Tests: `tests/test_timeframes_patterns.py` and
`tests/test_price_zones.py` blocks "engine fixes 2026-09-05"; guards in
`tests/test_supply_demand_contracts.py`.

**The in-progress bucket is not structure.** `frame_for` now flags the last
intraday bucket `partial: true` when the minute before its close label has not
printed, and `price_zones.for_symbol` keeps that bucket out of the swings,
gaps, ATR and trade levels — the intraday twin of the daily rule above (a
"three-bar imbalance" whose third bar has not closed is not a gap yet; its edge
was the low-so-far and repainted all session). The partial bucket still prices
the verdict. This narrows the 2026-09-03 CHPT decision on purpose: verdict and
chart see the live bar, structure does not. `chart_maps/support`,
`session_board` and `catalysts/signal_watch` follow the same rule since the
integrator pass of 2026-09-05 (Ajay: "yes please fix the bugs"): the Support
tab computes swings, gaps and ATR on the frame without today's live bar
(`_frame_for(..., with_closed=True)`; intraday: without the `partial` bucket)
and still prices the levels at the live print; the session board's
`fair_value_gaps` and signal-watch's zones / ATR / gaps drop the `partial`
bucket, the live close still prices the read. `mood` / `signal` keep their own
closed-bar discipline on the whole frame. Tests:
`test_chart_maps_support.py::test_the_support_tab_reads_structure_off_the_closed_frame_not_the_live_bar`,
`test_session_board.py::test_the_boards_gaps_come_from_closed_buckets_not_the_partial_one`,
`tests/test_signal_watch.py`.

**`meta.as_of` is the last raw minute actually seen**, never the last bucket's
future close label. At 10:07 ET the 15m frame ends in a bar stamped 10:15; the
session-board payload was carrying that as the read's timestamp. (The Support
tab's stamp drops the string before it renders, so this was latent there.)

**Hourly buckets are clock-anchored and the FIRST one is the half hour.** RTH
resamples to 30, 60, 60, 60, 60, 60, 60 minutes labelled 10:00 … 16:00 ET; the
module docstring said the *last* bar was the short one. Docstring fixed; the
anchoring itself is unchanged.

**ATR is the simple 14-bar mean of true range.** `patterns.atr` said
"Wilder-style" while computing `tr.rolling(14).mean()`; a spike therefore leaves
the number abruptly on bar 15 instead of decaying (10-point spike five bars back:
1.643 here vs 1.444 smoothed). The **math stays** — every stop buffer on the S/D
surfaces is `STOP_BUFFER_ATR × this value`, and a smoothing change would move
them all — only the label is fixed. No S/D surface labelled it Wilder; the
"Wilder for ATR" note on the SEPA trade-plan panel refers to
`backend/analysis/trade_plan.py`, a different module.

**A supply band that contains the price yields no plan.** `trade_levels` never
read `band.kind`, so a name inside 100–104 supply printed a *long* at 104 with a
stop under 100 on the same row whose verdict said `AT_SUPPLY` / caution.
Inside a supply band it now returns `None` and `attach_levels` carries
`trade_reason: "price is inside this supply band — no long plan while under
resistance"`. A supply band above price is still the short; below price it is
broken supply trading as support (long); a demand band containing price is
still the long-from-support read. Every consumer already handled a `None` plan
(`mood.signal` blockers, `demand_reentry`, the Support-tab table filter).
