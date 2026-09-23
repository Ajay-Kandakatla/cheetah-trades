# Support Levels — one ticker, on demand, at a chosen zoom

Ajay 2026-08-19:

> *"Can you help me with a new feature where I can look at support levels on
> demand may be a new tab in the chart maps. Where I can toggle a drop down to
> check montly vs 3 months vs 6 months demand zones please. I should be able to
> a search of all the Ticker I do today and then drop down or something to check
> supports... I want look at recent support levels as well."*

Code: `backend/chart_maps/support.py`, read at `GET /chart-maps/support`.
Zones from `supply_demand/price_zones.py` (new `lookback_bars` knob).
FE: `frontend/src/components/SupportLevels.tsx`,
`frontend/src/lib/supportLevels.ts`, tab registered in `lib/chartMaps.ts`.
Tests: `backend/tests/test_chart_maps_support.py` (48),
`backend/tests/test_price_zones.py` (+7),
`frontend/src/lib/supportLevels.test.ts` (33),
`frontend/src/components/SupportLevels.test.tsx` (14).

---

## 1. Not a book method, and it says so

`price_zones` opens with the line that governs this whole feature:

> a **PRAGMATIC** price-structure read, **not** a named book methodology — every
> threshold below is a CONFIGURED house value.

No Minervini page backs a single number here and none is cited. Nothing in the
SEPA engine reads this tab. It is decision support for a stop, not a signal.

## 2. Why a new zoom knob instead of a new module

`price_zones` has only ever answered at 252 bars. That is the right lookback for
*"where is the structural floor"* and the wrong one for *"where is support for
the trade I'm in this week"* — a level turned at four times in the last three
weeks does not survive a year-long clustering pass, it gets merged into whatever
larger band contains it.

So the dropdown drives `compute(lookback_bars=…)` and **nothing else about the
rule changes**. Two knobs move, and only two:

| knob | 1M | 3M | 6M | 1Y |
|---|---|---|---|---|
| `bars` | 21 | 63 | 126 | 252 |
| `swing_window` | 2 | 3 | 4 | 4 |

`swing_window` **has** to move. At the module default of 4 a swing low must be
the lowest of nine consecutive bars; over a 21-bar month that is 43% of the
entire window, and the shortest option would return one band or none. Scaling it
holds swing *density* roughly constant, which is what makes the four views
comparable at all.

`merge_pct` and `half_width_pct` are deliberately **left alone**. Widening the
bands at short zooms was the obvious next move and it is wrong: the four views
would then differ for three reasons at once, and "why does 1M disagree with 6M"
would have no answer. One rule, four zooms, one explanation.

**1Y is not in the request.** It is offered because `/supply-demand/price-zones`
and the /zones page both read 252 bars, and a tab that could not reproduce their
answer would look like it *disagreed* with them rather than zoomed differently.

## 3. The floor had to move with the window

`compute` gated on a 60-bar frame. A 21-bar month cannot clear that, so before
this change the dropdown's first option could only ever have returned `None` —
which the UI would have rendered as "no structure found".

```
need = MIN_BARS (60)                         when lookback_bars is not passed
need = max(MIN_BARS_ABS (12), 2*w + 3)       when it is
```

The conditional is the point: **every pre-existing caller passes no window**, so
the /zones page, `orderflow.signals`, `sd_sweep`, `sd_backtest`, `sd_bounce` and
`demand_reentry` are byte-for-byte unaffected. `2w + 3` is the smallest frame
that can hold a swing at all — `_local_extrema` scans `range(w, n - w)` and
compares `w` bars either side.

## 4. Position decides the column, not origin

`price_zones` keeps the supply/demand label for **colour**. Broken support
trades as resistance and reclaimed resistance trades as support, so the table
splits by where a band sits relative to price, and carries the origin as
evidence (`· was resistance`) rather than as the sort.

`nearest_support` is merged into the pool explicitly. It is computed over
**every** band while the returned lists keep only the strongest four per side, so
building the table from the lists alone could put a top row on screen that
disagreed with the verdict's own `support_pct`.

## 5. What the live smoke test changed

The synthetic fixture proved the zoom works. Running it against real tickers
found something the fixture could not:

| ticker | zoom | nearest support | touches |
|---|---|---|---|
| NVDA | 1m / 3m / 6m | 214.90–217.50, **0.03% below price** | **1** |
| BRKR | 1m / 3m / 6m | every listed level | **1** |
| DHI | 6m | 146.97–148.75, 2.05% below | **1** |

A one-touch "band" is a single swing low with `half_width_pct` of synthetic
width painted around it — the weakest evidence the clustering pass can emit. On
a short frame it is also the **commonest**, because 21 bars rarely contain two
turns at the same price. Nearest-first sorting therefore promoted noise to the
top row on almost every read, and NVDA's "support" was functionally *yesterday's
low*.

They are still shown — a recent swing low **is** where the next bid sat, and
filtering them would empty the short windows. They are **labelled**:

* `MIN_TOUCHES_TESTED = 2` → per-level `tested` flag
* table prints `1 touch · single low`, at lower contrast
* the headline appends *"Single swing low, not a tested floor."*
* the stats separate **touched in last month** from **turned at more than once**

That separation is the honest one, because neither implies the other: a level
touched yesterday once is recent and untested; one turned at four times last
year is tested and stale.

After the change, DHI at 6M reads correctly — nearest is a 1-touch low at 2.05%,
but the real floor is the **4×-tested** band at 4.41%. That is the read that
was previously buried.

## 6. Where the honesty is enforced

| Decision | Guard |
|---|---|
| The zoom actually changes the answer | `test_a_one_month_read_finds_the_RECENT_floor_and_not_the_old_one`, `test_a_six_month_read_reaches_the_DEEPER_floor`, `test_the_two_zooms_disagree_on_purpose` |
| A short window is reachable at all | `test_the_shortest_window_is_actually_reachable` (regression) |
| Existing callers are untouched | `test_the_default_lookback_is_unchanged_and_still_gated_at_60_bars`, `test_price_zones_globals_are_untouched_by_this_module` |
| Only two knobs vary | `test_the_band_geometry_knobs_are_deliberately_NOT_varied_per_window` |
| A short frame is declared, not mislabelled | `test_a_frame_shorter_than_the_window_is_ANSWERED_but_declared` |
| The chart shows what was read | `test_the_chart_shows_the_bars_actually_read_not_the_bars_requested` |
| A single low is not a floor | `test_a_single_touch_band_is_flagged_as_NOT_tested`, `test_the_why_line_says_so_when_the_nearest_support_is_one_touch` |
| …but is still listed | `test_a_single_touch_level_is_STILL_listed_not_filtered_away` |
| Polarity, not origin, picks the column | `test_a_broken_supply_band_below_price_is_listed_as_SUPPORT` |
| The table cannot contradict the verdict | `test_the_nearest_support_is_never_dropped_by_the_strength_cap` |
| Recency is a flag, never the ordering | `test_recency_is_a_FLAG_not_an_ordering` |
| Distance is to the edge price touches | `test_distance_is_measured_to_the_EDGE_price_touches_not_the_midpoint` |
| No universe scan behind a page load | `test_this_module_never_scans_a_universe` |
| Tile helpers reused, not reimplemented | `test_it_reuses_the_boards_tile_helpers_rather_than_reimplementing_them` |
| A miss keeps the controls usable | `test_an_unknown_ticker_answers_an_error_not_an_exception`, `keeps the zoom dropdown usable after a miss` |
| Never prints NaN | `never prints NaN when the backend omits a distance` |

## 7. Known limits

* **Bands are capped at four per origin** by `price_zones.MAX_ZONES_PER_SIDE`,
  so the table sees at most eight candidates below price. `levels_capped` says
  when more structure existed than was listed.
* **`strength` is relative to the other bands in the same window.** It is not
  comparable across zooms and is deliberately not surfaced in the table.
* **No stop rule is computed.** Placing a stop is methodology, `demand_reentry`
  already owns that question, and inventing a second rule here would be a drift
  with no source behind it. The band's low is printed; the stop is the reader's.
* **Nothing feeds back.** No scan, no alert, no ledger reads this tab.

## Stale-response race (fixed 2026-08-31)

Ajay: "The months at the bottom do not change when I try to change to 1
year from 6 months." A cold window computes for ~5s (measured on GEV)
while a warm one answers in ~50ms, so the request you switched AWAY from
routinely resolved last and repainted the old bars under the new dropdown
value. Fix: a request sequence counter — whoever asked last owns the
screen; late responses are dropped, in-flight fetches aborted on switch.
The same guard now protects the Chart Maps board fetch (tab/phase/target
flips) and the Session board (a quiet poll could overwrite a timeframe
switch). A switch over an existing chart also now says "updating the
view…" instead of looking dead while a cold window computes.
Regression tests are mutation-verified: removing either guard fails
SupportLevels.test.tsx / SessionBoard.test.tsx.

## Live view (2026-09-02)

The Chart control's Intraday group gained **"5 min · live · pre/post market"**:
the overnight tape (shaded) drawn against the 6-month daily levels, a `● LIVE`
chip with the session state and as-of time, quiet 30-second re-reads while the
extended session is open, and a one-line 🌙 overnight read ("broke support
$198.80–$201.20 at 16:30; bounced off support $184.75–$186.98 at 17:35 ✓").
Method and contracts: `timeframes_orb_fvg.md` → *Live frame*.

## 2026-09-05 — structure off the closed frame (Ajay: *"yes please fix the bugs"*)

The tab computes its swings, fair value gaps and ATR on the frame **without** today's live
bar (`_frame_for(sym, bars, with_closed=True)` returns both; on an intraday timeframe the
`partial` last bucket is dropped the same way) and still **prices** the levels at the live
print (`pz.compute(closed, last_price=live_last, ...)`). Before this a displacement bar plus
the live bar printed a demand FVG whose top was the live bar's low-so-far, and a partial-day
true range leaked into the ATR the entry/stop buffer is scaled by. Same rule as
`price_zones.for_symbol` (`price_zones_methodology.md` → 2026-09-05). Test:
`test_chart_maps_support.py::test_the_support_tab_reads_structure_off_the_closed_frame_not_the_live_bar`.

## 2- and 3-year zooms (2026-09-06)

Ajay 2026-09-06: "Can you add 2 years to the time frame down please for demand
zone calculation. I do seem sometime we have bounces off the 2 years as well;
also add 3 years and then keep 5 years. Make sure we have this in all the chart
map calculations and dropdown time frames."

| zoom | bars | swing window | frame |
|---|---|---|---|
| **1 week** | **5** | — (every read from 1m) | shared 2y frame |
| **2 weeks** | **10** | — (every read from 1m) | shared 2y frame |
| 1 month | 21 | 2 | shared 2y frame |
| 3 months | 63 | 3 | shared 2y frame |
| 6 months | 126 | 4 | shared 2y frame |
| 1 year | 252 | 4 | shared 2y frame |
| **2 years** | **504** | **5** | shared 2y frame, or the deep 5y fetch when it holds more |
| **3 years** | **756** | **5** | deep 5y fetch (`_frame_for`, 6-hour in-process cache) |
| 5 years | 1260 | 5 | deep 5y fetch |

The zoom IS the demand-zone lookback (`price_zones.compute(lookback_bars=…)`),
so 2y / 3y are new reads of the structure, not longer pictures of the 1-year
one. The swing window matches 5y: past a year only structural pivots are
levels. The overlay view now clusters seven windows, so its "N windows agree"
counts can rise by up to two for old structure.

Same lists everywhere — FIVE of them since 2026-09-18:
`chart_maps/support.SUPPORT_WINDOWS` (server, wins), `FALLBACK_WINDOWS` and
`CHART_VIEWS` in `frontend/src/lib/supportLevels.ts` (the ticker page's Supply
/ Demand chart uses the same control), and `HOLDINGS_WINDOWS` in
`frontend/src/lib/holdingsBoard.ts` (📁 My holdings). The FIFTH list, the board
tabs' Window dropdown on `ChartMaps.tsx`, carries 2 / 3 / 5 years but
**deliberately does NOT carry 1 week or 2 weeks** — its tiles floor at
`board.BARS_FLOOR` (20) and `ZONE_BARS_MIN` (130), so a "1 week" option there
would draw 20 or 130 bars under a one-week label; honouring it would mean
moving two floors, which is a threshold change (`docs/sepa/chart_maps.md`).
Board bars past `DEEP_BARS_FROM` (480) come from the same deep fetch;
`board.BARS_MAX` is 1260. Pinned in `backend/tests/test_chart_maps_support.py`,
`backend/tests/test_chart_maps.py`, `frontend/src/lib/supportLevels.test.ts`,
`frontend/src/lib/holdingsBoard.test.ts`, `frontend/src/pages/ChartMaps.test.tsx`
and the contract "Chart Maps time frames carry 2 / 3 / 5 years".

## The two short zooms set the chart, not the numbers (2026-09-18)

Ajay 2026-09-18, verbatim: *"Also a weekly chart for the past week and 2 week
inthe charting time frames in all places."*

Asked which he meant, he chose **short WINDOWS**: *"Add '1 week' and '2 weeks'
to the zoom list, which today starts at 1 month. Same daily/intraday candles
you have now, just zoomed into the last 5 or 10 sessions."* He **declined**
weekly CANDLES — there is no new bar interval, no resample, no `closed=left`
anywhere in this change (pinned: `test_no_bar_interval_was_introduced`).

**Bars are SESSIONS.** The list's own convention (`support.py`: *"`bars` are
TRADING days: 21/mo"*) makes a trading month 4.2 trading weeks, so a week is
**5** sessions and two weeks is **10**. Never 7 or 14 — pinned as a negative in
`test_a_week_is_five_sessions_and_two_weeks_is_ten` and its FE twin.

### Why every NUMBER stays the 1-month read

`CHART_ONLY_LEVELS_FROM = {"1w": "1m", "2w": "1m"}` (`chart_maps/support.py`).
At these two zooms the candles are the last 5 / 10 daily sessions and **every
analytic read — levels, mood, signal, SMC, patterns, trend — runs on the
1-month window's 21 bars.** Two floors force it:

- `price_zones.MIN_BARS_ABS` (**12**) is the hard floor for a custom lookback:
  `_local_extrema` scans `range(w, n-w)`, so `2*w+3` is the smallest frame that
  can hold a swing at all. `pz.compute(lookback_bars=5)` returns `None`
  unconditionally. The floor is an S&D evidence threshold and was **not**
  lowered — a 5-bar frame would otherwise mint a band from one swing with
  synthetic width painted around it.
- `supply_demand/mood.py` drops the still-forming bar only when
  `len(df) > 5`, **strictly**. A caller handing it exactly 5 bars gets a
  repainting read while `signal()` stamps `no_repaint: True` regardless. This
  change **routes around** that hole (1w reads 21 bars) rather than changing a
  guard every timeframe shares; `test_a_short_zoom_never_ships_a_repainting_no_repaint_flag`
  documents the hole with an assertion. Closing it is a separate branch and
  HIS call.

Measured on a synthetic ramp: `mood(tail(21))` scores **49.6**, `mood(tail(5))`
scores **10.0**, against `MOOD_BUY = 25.0` — i.e. a 5-bar read would print
**WAIT where the 1-month read prints BUY** on identical bands. `_record_signal`
writes every BUY/SELL under `mood_signal:daily` deduped per (symbol, timeframe,
bar), so a contradicting 1w action would also have raced the forward ledger.

This is the same split the **5-minute live views** used until 2026-09-22
(`5m_live` / `5m_today` drew an intraday tape against the 6-month DAILY
levels) — one existing engine for "chart at one scale, levels from another",
not a second mechanism. **Those two frames no longer take that split by
default**: an intraday frame reads its own levels now, and the daily read is a
NAMED fallback. See *Five frames, named by the job* below. The split itself is
unchanged and still drives the 1W/2W daily zooms.

### What the tab says on its face

- `chart_span` → `last 5 sessions · every read from 1 month of daily bars`
- a served line under the chart → `Every number on this tab is the 1 month read.`
- the `note` names the floor by value read from `pz.MIN_BARS_ABS`: *"This zoom
  sets the CHART only — the last 5 sessions. A frame that short is under the
  12-bar floor a swing needs, so every number here — levels, mood, signal,
  trend, patterns — is the 1 month read, the same numbers the 1 month zoom
  shows."* The old sentence ("Levels are read from this window only") is FALSE
  here and is not printed.
- new payload keys `levels_window` / `levels_window_label`, both `None` on
  every other window, so a response served before this change renders exactly
  as it did.

Verified on real NVDA payloads from this branch: `supports`, `overhead`,
`verdict`, `mood`, `signal.action`, `trend_read`, `bullish_patterns` and `smc`
are **identical** across `1w`, `2w` and `1m`; only `tile.bars` (5 / 10 / 21)
and `chart_span` differ. `mood.bars` is 20 at 1w, not 5.

### Thin symbols

Three different things: `short` is CHART truncation, `level_short` is an
evidence shortfall behind the READS, `chart_only` is which window asked. A
13-bar symbol MEETS the 5-bar chart budget at `1w`, so `short_history` checks
the chart-only arm first and reports `{"have": 13, "asked": 21}` — the same
object `window=1m` gives. Without it the same name warned at 1m and went
silent at 1w, which is backwards.

Under the floor, the tab refuses rather than drawing a confident empty chart:
an 11-bar frame at `1w` returns `bars_used: 11` and *"TEST has only 11 bars of
history — too few to read a 1 month window."* with no chart, no levels and no
verdict. The "No swing structure — try a longer window" message is reserved
for a frame that HAD the history and found nothing.

**No default moved.** `DEFAULT_WINDOW` is still `1y`, `SEPA_SUPPLY_WINDOW`
still `1y`, `HOLDINGS_DEFAULT_WINDOW` still `6m`. (`DEFAULT_VIEW` was the
merged picker's `daily:1y`; the merged picker was collapsed on 2026-09-22 and
the default is now the two facts `DEFAULT_TF = daily` + `DEFAULT_WINDOW = 1y`,
which is the same opening view.) No rule, gate, band, threshold or S&D constant changed. The overlay view
skips both keys — their bands ARE the 1m bands, and a duplicate row would
inflate the "N windows agree" denominator.

**A shorter zoom is a VIEW. Nothing about it is measured**, and no edge is
claimed. The one prior measurement in this area (`sd_zone_timeframe_studies`,
2026-08-24) found no lookback has an edge.

## Default zoom: 1 year (2026-09-06)

Ajay 2026-09-06: "Can you make support default to 1 year on all the tabs? I
think its safer and more accurate."

`support.DEFAULT_WINDOW` is `"1y"` (was `"3m"`), mirrored by
`frontend/src/lib/supportLevels.ts` `DEFAULT_WINDOW` and `SEPA_SUPPLY_WINDOW`
(the ticker page's Supply / Demand chart, which had opened on 6 months since
2026-09-02). Until 2026-09-22 a third mirror, `DEFAULT_VIEW = 'daily:1y'`,
carried the merged picker's composite key; the picker was collapsed that day
and the pair is now carried by `DEFAULT_TF` + `DEFAULT_WINDOW`. Every surface opens on the
1-year read; an unknown or missing `?window=` lands there too; a shared URL
omits `window` only when it is 1y. The 1m / 3m / 6m zooms are unchanged as
choices. Pinned in `backend/tests/test_chart_maps_support.py`
(`test_the_default_zoom_is_one_year_on_every_surface`),
`frontend/src/lib/supportLevels.test.ts` ("default zoom — 1 year on every
surface") and the contract "Chart Maps time frames carry 2 / 3 / 5 years".

## 2026-09-14 — the partial bar the closed-bars rule missed, and more

Found by a review of every chart surface (Ajay: *"verify the supply demand
logic on all charts"*). Tests in
`backend/tests/test_chart_studies_verified_2026_09_14.py`.

1. **The hourly cache patch defeated "closed bars only".** `sepa.cli
   vcp-watch` runs hourly 09–16 ET and `patch_latest_closes` writes today's
   in-progress bar INTO the shared frame from ~10:00. `with_today_bar` then
   saw `snap_date <= last_date`, returned the frame untouched, and
   `_frame_for` took the whole frame as closed: swings, ATR, gaps and the
   verdict price all read a partial bar that was also up to an hour stale,
   while the `now` line moved to the live print (NVDA: verdict "into supply
   +1.4%" at 210.96 with the tape at 216.50 inside that band). Now
   `with_today_bar` refreshes that row from the snapshot in the returned
   copy and reports `partial=True`; `_frame_for` (and
   `price_zones.for_symbol`) drop a partial last row from the structure
   frame. After-hours stays as it was: the day bar is complete.
2. **A supply band you stand IN was painted green** ("here"). The box now
   takes its colour from its origin — `here · in supply` in red when the
   verdict says resistance right here (63 of 388 ticker-windows).
3. **SMC order blocks, BOS/CHoCH, sweeps and the pattern scan read the LIVE
   frame** while the zones read the closed one; a live bar could mint a BOS
   that vanished at the close (ESI: "BOS 33.49" only with the live bar).
   All read `closed.tail(budget)` now.
4. **`window=all` read the live-overlaid frame** for its swings. Now closed
   bars priced at the live print, like every other window.
5. **The 2y/3y/5y deep frame was never phantom-scrubbed.** `_drop_phantom_tail`
   runs on it now.
6. **studies=true ignored the zoom** — the endpoint passed `res["bars"]`
   (does not exist) so `days` was 0 and the mean-reversion channel was a
   2-year fit drawn over a 1-month chart. It passes `bars_used`. On an
   intraday timeframe the daily-frame studies are no longer painted over
   hourly bars; `studies_note` says why.
7. **Intraday tiles said "6 months"** in the stats and the why-line. They
   say `330 x 1 hour bars`.
8. **Touch markers.** Every band drawn on the tile marks the swings that
   made it — ▲ under swing lows, ▼ over swing highs (by the band's ORIGIN,
   so a broken lid now acting as support still shows its swing highs) —
   and a tested band says `3× tested`. `price_zones` carries
   `touch_dates` on every band (additive; `None` on a frame without dates).

## 2026-09-14 — the BOARD's band on every daily view

Ajay: *"Basically I wanna make sure the overhead supply and demand zone logic
is accurate across board."*

**What was measured.** `scripts` in the session's scratch, re-runnable from the
api container: for 46 tickers drawn from his holdings and the live Deep Demand,
Zones, Breaking, Quick Reversal and Into Supply boards, the nearest demand band
at or below the close and the nearest overhead above it were pulled from every
source that draws a band:

| Sources compared | Nearest demand agrees | Nearest overhead agrees |
|---|---|---|
| Board geometry fresh vs the nightly zone store | 42 / 46 | 40 / 46 |
| Scan record vs board geometry fresh | 36 / 46 (the rest are lids turned floor — the scan's rule, not a different band) | 46 / 46 |
| **This tab (fine geometry) vs the board geometry** | **6 / 46** | **9 / 46** |

Every board, the alert gate and the paper lanes share ONE engine
(`price_zones.compute`) at ONE geometry (`demand_reentry.zone_geom()`: swing 5,
merge 4%, 252 bars) and agree with each other; the four misses against the
store are names with no store doc (no market cap → no bands, the known gap)
and one-day staleness (the store is built at 04:05 ET from the prior close).
This tab reads the same engine at the finer geometry §2 documents (merge
1.75%, swing by zoom) and agreed with the boards on the nearest demand band
six times in 46: LQDA read "support 63.08–63.84, 2.25% below" here while the
demand board had price *inside* 64.94–67.26; ESI read "in a demand zone
31.99–32.38" here while the board's nearest demand was 28.94–29.98. §2's own
promise — *"a tab that could not reproduce their answer would look like it
disagreed with them rather than zoomed differently"* — no longer held, because
the boards moved to the wider geometry after §2 was written.

**What changed.** Every daily-structure view (every zoom, and the holdings tab,
which is built from this tab) now ALSO carries the board's band:

* `support.board_read(closed, sym, last_price)` calls
  `demand_reentry.decide_from_frame` — the one rule the boards, the alert gate
  and the lanes run — on the SAME closed frame, priced off the live print, and
  takes its entry band (else its nearest support, which may be a lid turned
  floor) and the alert gate's `first_overhead`. No second engine, no
  reimplementation; a source guard pins that nothing else from that module is
  reached for (it is pure per frame — no universe pass can start from a page
  load).
* Drawn as a **dashed outline** in the support / overhead colours, band kinds
  `board_demand` / `board_supply`, its own overlay family **"Board band ·
  alerts"**, ON by default and hideable without hiding the finer levels.
* Two stats rows (`board demand band`, `board overhead`) and the why-sentence
  now opens with *"BOARD (what alerts and lanes use): demand … · overhead …"*.
* The finer levels are unchanged. Two resolutions remain, now both on screen
  and both named; making the board's geometry the ONLY one is a methodology
  call and is not taken here.

**UPDATED 2026-09-22 — the board band is now on EVERY frame.** It used to be
absent from `15m` / `60m` / `15m_open` (the frames that read their own bars)
and present on the daily views and the two 5-minute frames. Since every
intraday frame reads its own levels, the board reading is the thing that keeps
them honest: two readings, each labelled, never conflated. It is still
computed by `decide_from_frame` on the **daily closed frame** and priced off
the **daily** last close, so it is byte-identical on all five frames — pinned
by `test_the_BOARD_block_is_the_SAME_on_every_frame`. Nothing the alerts, the
gate or the paper lanes read follows the chart.

Tests: `tests/test_zone_consistency_2026_09_14.py`, `chartOverlays.test.ts`,
`PatternChart.test.tsx`.

## 1W / 2W on an intraday frame (2026-09-18, second ship)

Ajay, on a 1W chart showing its honest 5 daily bars: *"Can you increase the bars
on the weekly chart please? I am trying to read more on the weekly chart"*.
Offered three readings he chose **"1 week of HOURLY bars"** — keep the span,
raise the resolution. He **declined weekly candles**, so nothing resamples.

Before, a short window was inert on every intraday frame: `1w + 60m` drew the
frame's whole 330-bar budget (~47 sessions) under a label that said one week.

| view | before | after |
|---|---|---|
| `1w` daily | 5 bars | 5 bars (unchanged) |
| `1w` + 60m | 330 | **32 over 5 sessions** |
| `2w` + 60m | 330 | 67 over 10 sessions |
| `1w` + 15m | 260 | 116 over 5 sessions |
| `1y` / `6m` + 60m | 330 | 330, `zoom_applies: false` (unchanged) |

Measured on MU, 2026-09-18.

**Sliced by ET session date, never by bar count.** A count (`5 × 6.5`) needs a
bars-per-session number this repo does not have, and it bleeds into the prior
session on a half-day and clips on a full one. Counting dates needs neither.

**The index is UTC and naive.** Verified live at 12:23 ET / 16:23 UTC: MU's last
60m bar stamped `16:30`, and 2026-09-17 ran `17:00 → 20:00` — 13:00 → 16:00 ET,
the RTH afternoon into the close. For an RTH frame a raw `.date()` happens to
agree with the ET session, but the extended session runs to 20:00 ET = **00:00
UTC the next day**, so on `5m_live` a raw date files the last after-hours hour
under tomorrow and drops it from today. `_last_sessions` converts to
`America/New_York` first. This is the container-UTC vs provider-ET trap the repo
already carries elsewhere.

**Only the drawn frame is trimmed.** `chart_df` and `df` were already separate;
the slice touches only what is drawn, so every level, mood, trend and pattern
read still runs on the untrimmed frame. Verified: `1w + 60m` and `6m + 60m`
return identical supports, overhead, verdict and `bars_used` (330).

`chart_sessions` carries how many ET sessions the drawn frame actually holds —
never more — and is `null` when the window did not trim it. A shallow intraday
cache returning fewer sessions than asked is normal, not an error.

## Five frames, named by the job (2026-09-22)

Ajay, across three messages that day:

> *"Once done can you add a 24 hour window for me on the supply demand chart
> please. I am tired of the pre live post.. It give me for an entire week with
> lil candles. I mainly need the support levels for the last 24 hours to see
> the support.. just last 24 hours if you cannot do it then support level from
> market open but I do not have to see previous days in that.. even if Pre post
> I am not expecting to see Sept 15 why do I need the look at the drop down"*

and, after seeing `5 min · today only · from 04:00 ET`:

> *"Just simpliyfy this drop down. I wanna use this for entries during the day
> and it been useless for that It does help with 6 months but when it comes to
> daily charts and checking support levels for daily. at any giving point This
> has been useless"*

### The defect, measured

`GET /chart-maps/support?symbol=PTGX&tf=<frame>&window=6m`, PTGX last **145.07**,
2026-09-22:

| frame | nearest support band |
|---|---|
| `5m_live` | 142.43–144.15 ← the 6-month **daily** band |
| `5m_today` | 142.43–144.15 ← the 6-month **daily** band |
| `15m` | 140.44–142.48 ← its own bars |
| `60m` | 140.44–142.38 ← its own bars |
| `15m_open` | **none at all** — 26 bars is too thin to cluster |

`support.py` replaced the analysed frame with the daily frame for any frame
carrying `ext_hours`, and the two 5-minute frames are the only ones that do.
So the frames a person picks **for an entry** were the only ones serving coarse
6-month daily bands. Meanwhile PTGX's own 5-minute tape that day put price
**inside** a $144.50–$145.96 band tested **14×**. The number he needed was
computable and was being discarded. That is a defect, not a preference.

### (1) An intraday frame reads its own levels

`own_bars = intraday` — one assignment. The 5-minute frames now go through the
**same path** `15m` / `60m` already used; no new level maths, no new geometry,
no threshold moved.

After, on the same tape:

| symbol / frame | before (daily 6m) | after (own bars) |
|---|---|---|
| PTGX `5m_today` | support 142.43–144.15 · overhead 150.33–152.15 | standing **in** 144.50–145.96 (14× tested) · overhead 145.53–147.71 |
| PTGX `24h` | — | standing **in** 144.50–145.96 (14× tested) · overhead 145.53–147.71 |
| PTGX `15m` / `60m` | unchanged | 140.44–142.48 / 140.44–142.38 |
| NVDA `5m_today` | support 214.90–217.50 · overhead 232.28–234.76 | standing **in** 225.56–229.44 (29× tested) |
| NVDA `24h` | — | standing **in** 225.56–229.44 (29× tested) |
| NVDA `15m` / `60m` | unchanged | 224.38–227.68 / 224.76–227.95 |

Both names were standing *inside* a band rather than above one. That band is
`standing_in`, which `_bands` already draws labelled **"here"** and the verdict
already names — so "supports is empty" is not "no level", and the fallback
below is deliberately **not** gated on an empty `supports`.

### The named fallback — never silent

The 2026-09-02 comment that justified the daily swap was right about one thing:
an intraday window, *"after a gap, may hold no level at all"*. That risk is
handled, not ignored:

* `_holds_a_level(zones)` — true when the read produced **any** band: below
  price, above it, or `standing_in`.
* If it is false, the daily frame is read at the selected window. If **that**
  holds a level, the payload carries
  `levels_fallback = {from, from_bars, to, note}` and:
  * `note` **starts** with *"The 5-minute window held no level, so these levels
    are the 6 months daily read — not this chart's own."*
  * `chart_span` ends with *"(the 5-minute window held no level)"*.
  * `levels_window_label` names the daily window; `zoom_applies` becomes true.
* If the daily frame holds nothing either, the fallback is **abandoned** and
  the intraday read is served as asked. Turning an empty read into an error
  would be a fresh regression on `15m` / `60m`, which render one today.
* The **chart** never moves. `tile.bars` reads `chart_df`, so a fallback
  changes the numbers and never the candles.

### `chart_span` — one sentence, two clauses, on every frame

> *"why do I need the look at the drop down"*

| frame / zoom | `chart_span` |
|---|---|
| `daily` + 6m | `6 months · levels from these daily bars` |
| `daily` + 1w | `last 5 sessions · levels from 1 month of daily bars` |
| `15m` | `260 x 15-minute bars · the last ~10 sessions · levels from these 15-minute bars` |
| `5m_today`, fallback | `79 x 5-minute bars · today only, from 04:00 ET · levels from 6 months of daily bars (the 5-minute window held no level)` |

Every sentence names the bar size via `bar_label`, never the job `label` —
*"79 x Today, for an entry bars"* is not a sentence.

### (2) Six frames became five

| Key | Label (the job) | Bar size | Span | Bars | Days |
|---|---|---|---|---|---|
| `5m_today` | Today, for an entry | 5-minute | today only, from 04:00 ET | 192 | 1 |
| `24h` | Last 24 hours | 5-minute | the 24 hours up to the last print, pre-market through after-hours | 288 | 3 |
| `15m` | The last two weeks | 15-minute | the last ~10 sessions | 260 | 15 |
| `60m` | The last two months | 1-hour | the last ~47 sessions | 330 | 70 |
| `daily` | The big picture | daily | 1 year by default — the Zoom dropdown sets how far back | 252 | — |

Ordered **shortest first** — *"I wanna use this for entries during the day"*.
`DEFAULT_TF` is still `daily`, so nothing opens on a different frame than it
used to. `span` is built once as `f"{bar_label} bars · {window_label}"` and
rides in `tf_options()`, so the span is readable **without opening the option**.

**Which option answers which ask:**

* *"last 24 hours"* → **`24h`**.
* *"support level from market open but I do not have to see previous days"* →
  **`5m_today`** (04:00 ET, which is the day-start he himself chose on
  2026-09-17).

#### Retirements, and where an old link lands

| Retired | `?tf=` now resolves to | Why |
|---|---|---|
| `15m_open` (`open`, `session`, `15open`) | **`15m`** | Its 26-bar session budget is too thin to cluster — measured 2026-09-22, PTGX *and* NVDA both returned **no support band at all** on it. `5m_today` answers the same "today only, no previous days" question with 192 bars. The alias points at `15m` rather than `5m_today` because `15m` is the nearest key that resolves on **every** surface: `frame_for` refuses an extended-hours frame to any structure caller, so an old `/zones?tf=15m_open` bookmark would otherwise start erroring. **HIS CALL:** if he would rather old `15m_open` links land on the 5-minute today frame, that is a one-line alias change and costs the `tf` overlay on `/supply-demand/price-zones` for that key. |
| `5m_live` (`live`, `5m`, `5min`, `5m_ext`) | **`24h`** | Same bar size, same pre/post policy, a span that is **true**. Both keys are extended-hours and therefore Support-tab only, so the alias adds no new refusal anywhere. |

Neither retired key falls back to `daily`, and
`test_NEGATIVE_a_retired_tf_key_still_resolves_and_never_errors` asserts it.

#### Why `24h` is TIME-windowed and nothing else is

A fixed **bar count** makes the span a function of **liquidity**. Measured
2026-09-22, the retired `5m_live`'s 480-bar budget drew:

* **NVDA** — 480 bars over **3** sessions (09-18 → 09-22)
* **PTGX** — 393 bars over **5** sessions (09-16 → 09-22)

under one label claiming *"last ~2.5 sessions"*. PTGX barely prints outside
RTH, so the same budget reaches further back — which is exactly the *"I am not
expecting to see Sept 15"* complaint. A 24-hour slice cannot do that.

* `bars: 288` is a **ceiling**, not a budget: 24 h × 12 buckets = 288, the most
  a 5-minute grid can hold in a day, so `tail(288)` is a no-op after the slice.
* The slice is **anchored on the last bar present**, not on wall-clock `now()`.
  Anchoring on `now()` would serve an empty chart every weekend and every
  holiday, and would make the frame untestable without freezing time. Anchored
  on the tape, *"the last 24 hours"* is true in session and still answers
  "Friday's day plus Thursday's close" on a Sunday — which is what the span
  text says: *"the 24 hours up to the last print"*.
* `days: 3` is the same calendar fetch `5m_live` paid for, so provider load per
  open tab is unchanged.
* It shares the **one** session-slice block in `frame_for` with `5m_today`
  (`if key in (M5_TODAY, H24):`), off the same ET conversion — one place a
  timezone can be got wrong, not two.

### What deliberately did NOT change

* **The board block.** Same daily-derived numbers, on every frame, still
  labelled *"BOARD (what alerts and lanes use)"*. See the updated section
  above.
* **The signal ledger.** `_record_signal` still skips the 5-minute frames. The
  reason changed — it used to be "their signal IS the daily signal, recording
  it twice double-counts"; now it is that the horizon table knows `15m` and
  `60m` and defaults everything else to **72 hours**, which would file a
  five-minute call under a three-day outcome. Giving a 5-minute signal a
  horizon is a measured question, not a view change.
* **The pattern scan.** It still reads the **daily** frame on the 5-minute
  timeframes. `patterns/timeframe.py` converts Bulkowski's cited calendar
  durations through `BARS_PER_SESSION`, which knows `daily` / `60m` / `15m`;
  an unknown key falls through to the daily gates and would find a "7-week cup"
  inside one session, stamped with a citation it does not have. **HIS CALL:**
  adding a 5-minute row is a cited-duration question.
* **Every gate, threshold, roster and cohort.** Nothing here is measured and
  nothing here is a methodology change.

### Tests

`backend/tests/test_support_frame_levels_2026_09_22.py` — the levels differ
from the daily ones on a disjoint fixture; the structureless window falls back
**and says so**; the fallback is abandoned when daily holds nothing either; the
board block is identical across all five frames and is never handed intraday
bars; a retired key resolves and never errors; a **thin** name gets the 24 hours
it was promised; the 24h slice is anchored on the tape; an empty intraday fetch
refuses with a named reason; no NaN or Inf anywhere in the payload, fallback
path included.

Updated: `test_chart_maps_support.py`, `test_support_live.py`,
`test_5m_today_frame_2026_09_17.py`, `test_timeframes_patterns.py`,
`test_short_window_intraday_2026_09_18.py`,
`test_chart_studies_verified_2026_09_14.py`.

---

## The control he actually reads (frontend, 2026-09-22)

> *"Just simpliyfy this drop down."*

### Which list renders — and the finding that came first

There were **three** lists and they could disagree:

| List | Where it lives | What it actually drove |
|---|---|---|
| `CHART_VIEWS` | `frontend/src/lib/supportLevels.ts` | **The dropdown on the Support tab** — Chart Maps ▸ Support Levels *and* ticker ▸ Supply. **17** options across three optgroups (`Zoom`, `Daily candles`, `Intraday`). |
| `FALLBACK_TIMEFRAMES` | same file | Only `ZoneMap` (ticker ▸ **Setup**), and only until the server's list lands. Six entries. |
| served `timeframes` | `tf_options()` | `ZoneMap`'s dropdown in practice, and served into the Support payload where **the Support tab ignored it**. |

**The finding:** the six-option list quoted in the ask (`Daily`, `1 hour`,
`15 min`, `15 min · from the open`, `5 min · today only · from 04:00 ET`,
`5 min · live · pre/post market`) is `FALLBACK_TIMEFRAMES` — which is *not* the
list on the Support tab. His Support tab rendered `CHART_VIEWS`: seventeen
options, and it was the only list the served `timeframes` could not reach. A
frame retired backend-side would have vanished from the Setup tab and stayed on
the Support tab. That drift is fixed here: **every picker now renders the
server's list**, with a mirrored constant used only for the first paint.

### The final option list, verbatim

The `Chart` control, top to bottom. Option text is `{label} · {span}`, both
strings **served** — the page composes neither:

```
Today, for an entry · 5-minute bars · today only, from 04:00 ET
Last 24 hours · 5-minute bars · the 24 hours up to the last print, pre-market through after-hours
The last two weeks · 15-minute bars · the last ~10 sessions
The last two months · 1-hour bars · the last ~47 sessions
The big picture · daily bars · 1 year by default — the Zoom dropdown sets how far back
```

No optgroups. Five rows need no headings, and the headings were part of the
chore. **Which answers which ask:** *"last 24 hours"* → **Last 24 hours**;
*"support level from market open but I do not have to see previous days"* →
**Today, for an entry**.

The span rides on every row, so it is readable **without trying an option** —
that is the *"why do I need the look at the drop down"* complaint. A native
`<select>` sizes to its widest option, so `.sl-ctl-frame select` is capped
(`max-width: min(24rem, 52vw)`, ellipsised, full-width under 720px); the **open**
list still renders every row in full, and the same provenance is on the header
chip regardless.

### The zoom did not die — it moved

`How far back` is a **second** control that renders **only on `daily`**, with
the served `windows` (`1w 2w 1m 3m 6m 1y 2y 3y 5y all`). Every zoom he asked for
— 2y/3y/5y (2026-09-06), the 1-week and 2-week (2026-09-18), the overlay — is
still one click away. *"It does help with 6 months"* keeps working.

This does **not** undo the 2026-08-29 merge that killed the two contradicting
dropdowns. The contradiction was *"1 month" + "15 min"* — a pair with no
meaning. It stays unreachable because the zoom control **does not exist** off
the daily frame, and each intraday frame states its own span beside its name.
The `window` still goes on the wire for every frame (it decides the **board**
block and the named fallback, both daily reads) — it is simply pinned per frame
rather than picked: `5m_today`→`6m`, `24h`→`6m`, `15m`→`1m`, `60m`→`3m`. Those
are the pins `CHART_VIEWS` already carried; `24h` inherits `5m_live`'s.

### Retired from the picker, with the reason

| Gone from the dropdown | A `?tf=` link now lands on | Why |
|---|---|---|
| `15m_open` — *15 min · from the open* | **`15m`** (via `parseTf`) | Backend retirement. 26 bars is measurably too thin to cluster. |
| `5m_live` — *5 min · live · pre/post market* | **`24h`** (via `parseTf`) | Backend retirement. Its *"~2.5 sessions"* was false for a thin name. |
| `60m:1w` — *1 week* (hourly) | frame `60m`; `?tf=60m&window=1w` **still trims to 5 sessions** | Not deleted anywhere — only un-offered. The picker cannot express a (frame, zoom) pair any more, and *The last two weeks* (15-minute) answers the same span at a finer resolution. **HIS CALL** — see below. |
| `60m:2w` — *2 weeks* (hourly) | frame `60m`; `?tf=60m&window=2w` still trims to 10 sessions | Same. |
| `daily:1w` / `daily:2w` — *1 week · daily candles* | the `How far back` control, unchanged | Moved, not retired. |
| `daily:1m…daily:all` | the `How far back` control, unchanged | Moved, not retired. |

`retiredTf()` mirrors the backend `RETIRED` table. When a URL names a retired
key, Chart Maps passes it down and the tab prints, above the chart:

> The "5 min · live · pre/post market" chart was retired — showing "Last 24
> hours" instead. Nothing you had bookmarked has stopped working.

Junk (`?tf=weekly`) still degrades to daily **silently** and on purpose — no
real frame was asked for, so there is nothing to announce.

### Where the levels came from, on every frame

The header chip is the served `chart_span` on **every** frame. It used to fall
back to the zoom label unless the zoom did not apply, which left `15m` / `60m`
naming a daily window that was not where the numbers came from. And when the
intraday window held no level, `levels_fallback.note` renders as its own warned
line above the chart — the one state a reader must not have to infer.

### Other surfaces

* `ZoneMap` (ticker ▸ Setup) prints the span beside each job name too, and its
  first-paint fallback is now `STRUCTURE_TIMEFRAMES` — the **non-extended**
  frames only. Offering `5m_today` / `24h` there would be a dropdown entry that
  errors, because `frame_for` refuses an extended-hours frame to every caller
  but the Support tab.
* `tvChart.ts` gains `24h → 5` and **keeps** rows for both retired keys, so a
  caller still holding a raw key opens the right bar size rather than daily.

### Frontend tests

`frontend/src/lib/supportLevels.test.ts` — the agreed five in order; ≤5 as a
hard ceiling; every option's `span` equals `{bar_label} bars · {window_label}`;
both retirements resolve and are flagged; junk stays silent; the zoom ladder is
byte-for-byte unchanged; no intraday frame can carry a long zoom; a TradingView
interval exists for every offered frame; source guards — the component composes
no span or level-source phrase, holds no bare `Date` constructor, never says
"bounce", never carries the admin email, and the picker is width-capped.

`frontend/src/components/SupportLevels.test.tsx` — exactly five options and
**no** optgroups; every option renders its served span; the served list beats
the mirror; the zoom appears only on `daily` and reports both halves in one
call; a retired `tf` prints the notice and an ordinary load does not; the
level-source string renders; the named fallback is announced.

### HIS CALL

1. **The hourly 1-week / 2-week charts are no longer offered.** They still work
   by URL (`?tf=60m&window=1w`) and nothing backend-side changed, but they are
   out of the picker, because a five-row list cannot also express (frame, zoom)
   pairs. If he wants them back, the honest place is a sixth row — which breaks
   the five-option ceiling he asked for.
2. **`scripts/contracts.mjs` fails on this change and was not edited.** The
   guard pins the seventeen-option design by name (`CHART_VIEWS`, `DEFAULT_VIEW`,
   the derived optgroups, `viewKeyFor`'s internals). It is doing its job — the
   picker really did stop offering entries it protects — so updating it is a
   policy call, not a refactor. The failure is quoted verbatim in the ship
   report.

---

## The review round (2026-09-23) — what the four reviewers found, and the fix

Four adversarial reviewers read the 2026-09-22 package. Sixteen findings, nine
distinct defects (several were reported twice). Every one was reproduced from
this worktree against the live tape before anything was touched:

```
frame     PTGX 145.07                            NVDA 228.56
5m_today  supports []   overhead 145.53-147.71   supports []  overhead []
24h       byte-identical to 5m_today             byte-identical to 5m_today
15m       supports 140.44-142.48                 supports 224.38-227.68
60m       supports 140.44-142.38                 supports 224.76-227.95
daily     supports 142.43-144.15                 supports 215.52-218.13
```

### 1. The backend suite was RED (findings 1, 8)

`test_no_default_points_at_the_new_frame` still asserted a frontend constant
the FE package deleted (`DEFAULT_VIEW = 'daily:1y'`). The test now asserts the
two constants that carry the same meaning — `DEFAULT_TF = 'daily'` and
`DEFAULT_WINDOW = '1y'` — plus a NEGATIVE that `DEFAULT_VIEW` is really gone,
so the guard still catches a default drifting onto an intraday frame.

### 2. A JOB name is not a noun (findings 2, 9)

Since 2026-09-22 `tf_spec(key)['label']` names the question ("The big
picture"), which is right for a dropdown row and nonsense inside a sentence.
Three sentences outside the dropdown still spliced it in:

| where | was | now |
|---|---|---|
| `chart_maps/support.py` "no bars" error | `No Today, for an entry bars for THIN` | `No 5-minute bars for THIN` |
| `ZoneMap.tsx` entry table | `Entry & stop on The big picture bars` | `Entry & stop on daily bars` |
| `chart_maps/api.py` studies note | `not drawn on the The last two weeks chart` | `not drawn on the 15-minute chart` |

`bar_label` was already on the spec for exactly this. It is now SERVED beside
the job name as `timeframe_bar_label` from three endpoints
(`chart_maps/support`, `supply_demand/api`, `price_zones.for_symbol`), so no
surface derives it.

### 3. Recency was printed in daily units on five-minute frames (findings 5, 13)

`bars_since_test` is a BAR count. Before 2026-09-22 the 5-minute frames read
the DAILY frame, so "tested N sessions ago" was true there. It is not any
more: PTGX `5m_today` served `bars_since_test: 6` for a band touched half an
hour earlier, and the tab rendered "tested 6 sessions ago". The header was the
same error — `RECENT_BARS = 21` rendered as "21 sessions" where it is 1h45m.

The unit is now SERVED as `levels_bar_label` — the bar size the LEVEL READ ran
on, which is `daily` on the daily frame **and on the named fallback**, where
the frame is 5-minute but the numbers are not. `recencyLabel` and
`recentWindowLabel` take it as an argument; neither guesses from the frame key.
No conversion to minutes: that is arithmetic the frontend would have invented.

### 4. The empty support table named the wrong window (findings 3, 12, 4, 14)

`supports` is EMPTY on both 5-minute frames for PTGX, NVDA and CRML — this is
structural, not a fluke: on a one-session frame price is almost always INSIDE
the lowest band, so `levels_from_zones`' `hi < last_price` test finds nothing
below. The table then said, verbatim:

> No band below price in the last **6 months** — nothing here to place a stop
> under. **Try a longer zoom.**

Three things wrong at once: the emptiness came from 79 five-minute bars; the
6-month read is *not* empty (PTGX has a band at 142.43-144.15 and the board's
139.46-144.43 is printed on the same page); and the zoom control does not
render on any intraday frame. The sentence is now built by one helper
(`emptySupportNote`) from served keys only:

* `levels_scope` — the read's own scope as a noun phrase, the SAME string the
  stats row is labelled with, so the two cannot drift;
* the band price is standing in, when there is one;
* the BOARD's demand band when it really is below price, labelled as the daily
  read the alert gate and the paper lanes use — never as this chart's;
* the zoom hint only where `zoomApplies`, otherwise the surviving longer frame
  by its own served name.

### 5. The forward-ledger claim (finding 6)

`_record_signal` skips `ext_frame`. Until 2026-09-22 the ext-frame signal WAS
the daily signal, so "Every BUY/SELL is written to the forward ledger" held. It
is now the frame's own signal and nothing records it. `signal.recorded` is
served (`False` on `5m_today` / `24h`), with `signal.recorded_note` carrying
the reason. **No horizon was added** — that is a measured question, not a view
change.

### 6. The verdict contradicted the band beside it (finding 16)

`verdict` is `pz.compute`'s RAW pool; the chart draws the DE-DUPED, merged
pool. NVDA `5m_today` drew a demand band at 225.56-229.44 while the sentence
beside it read "In an overhead-supply band ($226.40-$229.98)" — neither the
numbers nor the side matched, and 226.40-229.98 was drawn nowhere. Pre-existing
in the engine (it shows on 15m), newly exposed on the 5-minute frames.

`_why` now takes the in-zone sentence from the DRAWN band. The mapping is
`price_zones._verdict`'s own, verbatim (kind `demand` → "support is right
here", kind `supply` → "resistance right here") — no new rule and no new
maths. When the two agree the sentence is the engine's to the character; when
nothing is drawn the band numbers are dropped rather than pointed at. The
engine's `verdict` object is still served untouched at the payload's top level.

### 7. The board band that is pointed at but not drawn (finding 7)

`barDomain` will not stretch to a band more than one chart-height away and
`clipBands` then discards it, so on an intraday frame the board's daily band
usually is not on the plot at all — while the served note ends "The dashed band
is the demand BOARD's band". Measured: NVDA `24h`, candles 225.56-229.44, board
demand 212.19-216.82, domain {lo 225.33, hi 229.67}. `offDomainBands` (pure)
reports what the plot dropped and `PatternChart` draws an edge marker with the
band's numbers and the side it fell off — for `board_*` kinds only.

### 8. The daily zoom did not survive a round trip (finding 10)

Every intraday frame PINS its window into the shared `window` param, so
daily 1y → "The last two weeks" → "The big picture" handed the daily frame a
current of `1m` and came back at ONE MONTH. He has said the long daily read is
the one thing that works. `SupportLevels` now remembers the window in force
while `zoomApplies` was true and hands that back. Seeded from the window the
tab mounted on, so a link that spells out `?window=` still carries it.

### 9. `24h` and `5m_today` collapse onto one chart (findings 11, 15)

The 24-hour slice is anchored on the LAST BAR PRESENT and the extended session
is 16 hours, so once the tape stops the 24-hour window IS that one session.
Measured after the close on 2026-09-22: PTGX both frames 79 bars 04:10→16:05,
NVDA both 192 bars 04:05→20:00, identical levels. They diverge intraday and on
a name with no pre-market (ANTX: 24h 66 bars / 2 sessions vs 5m_today 65 / 1).

**The slice did not change** — only the wording. `frame_for` counts the ET
sessions the slice actually holds and, at one, narrows the served
`window_label` to "the last 24 hours up to the last print — only
&lt;date&gt; printed in it". Every sentence on the tab that names the span now
reads the FRAME's label, falling back to the spec's. Whether the two rows
should be merged is **his call** — see below.

### Tests

* `backend/tests/test_support_frame_fixes_2026_09_23.py` — 33 tests: the bar
  size in the "no bars" error and in the zone-map payloads; `levels_bar_label`
  and `levels_scope` on every frame; `signal.recorded` on and off; `_why` on a
  disagreeing verdict, an agreeing one, nothing drawn, and a non-in-zone state;
  the `24h` one-session label and the two-session NEGATIVE; and a Rule #10
  guard that the BOARD block is still the daily read on all five frames.
* `frontend/src/lib/supportLevels.units.test.ts` — 20 tests: the recency unit
  in both directions plus the pre-2026-09-23 fallback; `recentWindowLabel`;
  `headline`'s unit; every branch of `emptySupportNote` including the NEGATIVEs
  (no board band above price, nothing said about a band price is not in);
  `offDomainBands` above, below, straddling and non-finite.
* `frontend/src/components/SupportLevels.review.test.tsx` — 10 tests, rendered:
  the empty table's sentence, the zoom hint, the recency column and header, the
  ledger sentence on and off and on an older payload, and the daily-zoom round
  trip with its NEGATIVE.
* `frontend/src/components/chartSurfaces.labels.test.tsx` — 6 tests: the
  off-plot board marker and its two NEGATIVEs; the zone map's two sentences and
  an older payload.

### HIS CALL (this round)

1. **Should the fallback also fire when there is no support BELOW price?**
   `_holds_a_level` counts `standing_in` and `overhead`, so the most common
   entry-frame state — price inside the lowest band, nothing under it — gets
   neither the intraday support nor the daily fallback. Widening that gate is a
   rule decision, so it was NOT changed; the surface now states the frame's own
   scope and names the board's band below instead.
2. **Should "Last 24 hours" and "Today, for an entry" be one row?** They are
   the same chart every evening, weekend and pre-market. The no-code half is
   done (the label says when they collapse); merging them is a dropdown
   decision.
3. **NVDA on `5m_today` has no entry/stop table at all** — `supports`,
   `overhead` and `trade_levels` are all empty and only `standing_in` exists.
   Before 2026-09-22 that frame served the coarse daily bands, which is the
   defect being fixed, but it did give a stop reference. Deciding what a stop
   references on a one-band frame is level maths — his call, not built.
4. **`scripts/contracts.mjs` still fails** (see the previous section). It is
   off limits and was not edited; it now also fails on `DEFAULT_VIEW`, which
   this round's pytest change stopped asserting but did not restore.
5. **No ✨ NEW highlight** — `frontend/src/lib/newFeatures.ts` is off limits for
   this round, so the entry this change is owed has not been written.
6. **The tile's own "touched in last month" stat** (`_stats`, support.py) is
   the same daily-unit wording on an intraday frame. It was not in the
   findings and was left alone rather than widening scope.
