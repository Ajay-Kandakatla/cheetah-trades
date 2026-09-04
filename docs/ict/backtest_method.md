# ICT board — walk-forward backtest method

**Code:** `backend/ict/backtest.py` · **Rules under test:** `backend/ict/structure.py`,
`backend/ict/engine.py` (`macro()` / `micro()` / `_plan()`, unchanged) ·
**Tests:** `backend/tests/test_ict_backtest.py` · **Board doc:** `docs/ict/ict_chart_maps.md`

> Ajay 2026-09-04: *"Did you back test this?"* … *"yes please run it."*

The question is whether the ICT Chart Maps board — the one that reads the
daily key levels, wakes the 60-minute loop on a tap and grades
accumulation → manipulation → confirmed → entry — would have shown anything
worth acting on, measured honestly. This document is the method. The numbers
live in the run output (`/tmp/ict_bt.md` + `/tmp/ict_bt.json` inside the api
container); the verdict paragraph at the bottom of that report is written by
whoever runs it, from the table, not from the code.

Not a book method. Nothing from any trading book is imported into this
strategy or its test; the rules are Ajay's spec plus the video cited in
`ict/structure.py`, and every number the video does not state is an owner
constant listed below.

## What "walk-forward" means here — the six rules

The engine is not re-implemented. At every 60-minute bar close the backtest
hands `engine.macro()` and `engine.micro()` frames cut to what existed at that
moment and records what the board would have shown. Each rule has a test.

1. **Time axis.** The 60m bars are the ones `supply_demand.timeframes.frame_for(symbol, "60m", raw=minutes)`
   produces — the house left-closed / right-labelled resample, never re-done by
   hand — evaluated in order over the whole span. Seven closes a session:
   10:00 ET (the 09:30–09:59 half hour), 11:00 … 16:00 ET.
   At close `t` the model sees:
   * **micro** = the 60m bars with index ≤ `t` (the bar closing at `t`
     included), windowed the way the cron fetches them:
     `engine.micro_raw_window` = `MICRO_DAYS` + 4 calendar days back from the
     session, then `frame_for`'s bar budget;
   * **macro** = the daily sessions that CLOSED strictly before `t`'s session
     (from `sepa.prices.load_prices(symbol)` — no `period` argument, it would
     poison the shared cache) **plus one partial bar** for `t`'s session built
     from that session's 1-minute bars with stamps `< t`: open = the first
     minute's open, high/low = the running extremes, close = the last minute's
     close, volume summed. Never the live today-bar overlay (that is a
     snapshot, not history), never the session's full daily bar, never a bar
     after `t`. At the 16:00 close the partial bar is the whole RTH session by
     construction — still built from the minutes, not read from the cache.
2. **One plain `macro()` per close.** The closed-session frame is built once
   per session with a placeholder row that the walk overwrites per close;
   the read is a plain `engine.macro(df=as_of_frame)` call. Profiled at
   ~2.5 ms on a 500-bar frame and ~1.6 ms per `micro()`, so ~880 closes a
   symbol cost 2–4 s and no structural cache is needed; a test asserts the
   incremental frame equals a freshly built one and yields the identical
   `macro()` dict.
3. **Dormant loop, like production.** `micro()` runs only when `macro()['tapped']`
   is not `None` at that close. An untapped close never reads the 60m frame.
4. **A signal** is the FIRST close at which `(symbol, bias, manipulation bar
   time)` reaches state `entry` on the board's best read. Dedupe key = those
   three. Recorded: the ET timestamp, bias, grade, tap kind, tap bias and age
   (sessions), whether the read's bias agrees with the tap's (the board scans
   both biases; the tap's bias is only a tiebreak, so a bullish read can sit
   on a swing-high tap — the report buckets on that), the manipulation
   source (Power of 3 range vs the tapped daily level), the plan (entry /
   stop / target / rr / zone kind ifvg|fvg), the 60m close at `t`, and
   **fill = that close** (a market fill, not the zone edge). An entry whose
   plan or stop is `None` is skipped and counted.
   Keys that reach `confirmed` (MSS + FVG) without ever reaching `entry` are
   kept in a second table, filled at their confirmation close, so the report
   can say what "confirmed but price never came back to the zone" did.
5. **Outcome** from the 1-minute bars strictly after `t` (stamps `≥ t`),
   through the rest of the signal session plus `HORIZON_SESSIONS` sessions:
   first touch of stop vs target — bullish `low ≤ stop` → stop, `high ≥ target`
   → target, bearish mirrored; **both inside the same minute = STOP**; no
   target → stop or horizon only. Recorded: `outcome` (target|stop|horizon|
   unresolved), `bars_to_outcome` (1-minute bars), `mfe_r` / `mae_r`
   (measured through the exit minute, or the whole window on a horizon exit,
   with R = |fill − stop|), `ret_at_horizon_r` (mark at the LAST close of
   the window, whatever the exit — what holding would have paid), and the
   raw % versions. A window that runs past the data end is `unresolved`:
   counted, excluded from every resolved statistic, only its partial first
   touch kept for reference.
6. **Placebo** — same geometry, random timing: for each signal a seeded
   random 60m close of the SAME symbol whose own outcome window (rest of its
   session + `HORIZON_SESSIONS`) ends strictly before the signal's session —
   i.e. at least `HORIZON_SESSIONS` + 1 sessions earlier, so no minute is
   read by both windows — entered at that close in the same direction with
   the same stop and target distances **in percent** (so the same R
   multiple), scored by the same outcome logic. Seed = `--seed` + symbol, so
   workers and reruns do not perturb it. The placebo line in the report is
   over the placebos of the **resolved** signals only (like for like: an
   unresolved signal's placebo always resolves and would pad the placebo
   population). SPY and RSP close-to-close returns from each signal session
   to `HORIZON_SESSIONS` sessions later (daily frames, same `load_prices`)
   are the market-context line.
   A plan whose stop the fill has already crossed (R ≤ 0) **or whose target
   the fill has already passed** is `bad_geometry`: skipped and counted,
   never an instant target hit.

## Data

* Minutes: `daytrading.data.load_intraday_range(symbol, start, end)` with
  pre/post market off (RTH only, the frame policy of every structure read in
  this app). `start` = today − months×31 − `WARMUP_DAYS`; signals are only
  evaluated from today − months×31, the warm-up days feed the micro window.
  `--minute-source range` swaps in one paged provider call per symbol
  (fastest on a cold per-day cache; writes nothing back).
* Daily: `sepa.prices.load_prices(symbol)` — the 2y cache, cut at each
  session. So the frame a signal 6 months ago was read from starts ~18
  months before it rather than 24; only the display-side consolidation
  count can differ from the live board's, not the tap, swings, gaps or plan.
* Guards (each counted in `skip_reasons`): fewer than `MIN_SESSIONS`
  minute sessions → `short_minute_history`; no daily frame → `no_daily`;
  daily close vs minute session close disagreeing by more than
  `MISMATCH_TOL_PCT` on more than `MISMATCH_MAX_FRAC` of shared sessions →
  `daily_minute_mismatch` (a split adjusted in one cache and not the other
  would put every level off by the ratio). If the run starts during RTH the
  open session is dropped: its last bucket would be a partial bar wearing a
  close label. A daily session inside the minute span with NO minutes (a
  provider call that failed) is not a skip — the horizon counts the sessions
  that exist — but it is counted per symbol as `missing_sessions` and the
  report's Counts section prints the total, so a run with holes says so.
* Universe: `--names N` random names (seeded) from
  `supply_demand.zone_store.big_cap_universe()` — **today's** big caps, so
  a name that fell out during the span is not tested (survivorship). The
  sample is printed into the JSON.

## Owner constants (none from the video)

| key | value | what it does |
|---|---|---|
| `HORIZON_SESSIONS` | 10 | sessions after the signal session an outcome may take |
| `MIN_SESSIONS` | 60 | fewer minute sessions than this = skip the name |
| `SMALL_N` | 30 | a bucket with fewer resolved rows is flagged ⚠ small n |
| `MISMATCH_TOL_PCT` | 3.0 | daily close vs minute close tolerance per session |
| `MISMATCH_MAX_FRAC` | 0.02 | share of mismatched sessions that skips the name |
| `WARMUP_DAYS` | 25 | calendar days of minutes fetched before the evaluated span = `MICRO_DAYS` + 4, the cron's own micro window, so the first evaluated close sees the same frame the board would have |

The engine constants in force during the replay are the live ones and are
printed with their values under `params` in the JSON and "Owner constants in
force" in the markdown — the ones that shape a signal most: `TAP_LOOKBACK`
(2 sessions a tap stays live), `TAP_TOL_PCT`, `TAP_SWING_WINDOW`,
`ENTRY_TOL_PCT` (0.5 % of the zone = entry), `STOP_BUFFER_ATR` (0.2 × 60m
ATR beyond the manipulation extreme), `MIN_TARGET_R` (the next daily swing
is the target only when it pays ≥ 1 R), `MICRO_DAYS` (21 calendar days of
minutes behind the micro frame), `MACRO_MIN_BARS`, `MICRO_MIN_BARS`, and the
structure rules `CONSOL_MIN_BARS`, `CONSOL_MAX_ATR`, `DISPLACE_MIN_ATR`,
`CONFIRM_MAX_BARS`, `MSS_FVG_WITHIN_BARS`.

## What the numbers mean

House style (`docs/supply_demand/zone_backtest.md`): medians lead, the mean
appears once as the expectancy line, nothing is ranked on win rate, and a
bucket under `SMALL_N` resolved rows is flagged and is not evidence.

| column | meaning |
|---|---|
| n / resolved / unresolved | signals; those whose horizon window fit inside the data; those that did not |
| target-first % (n w/ target) | of RESOLVED rows that had a target, the share whose target printed before the stop; the denominator is beside it |
| stop % / horizon % | of resolved rows: stopped first / neither touched inside the horizon |
| med MFE R / med MAE R | median best / worst excursion through the exit, in R (R = fill − stop) |
| med ret@H R | median mark at the end of the horizon window, in R, whatever the exit — the honest "what would holding have paid" |
| mean ret@H R | the expectancy line, same quantity, mean |

A signal only means something **against its own placebo**: the same stop
and target distances entered at a random earlier close of the same name.
If `med ret@H R` and target-first % are not clearly above the placebo's, the
board is showing geometry, not timing. SPY/RSP over the same windows say
whether the raw number was the market.

The **confirmed-but-never-entered** table is a diagnostic: those keys were
never shown as entries. Filling them at the confirmation close answers
"did waiting for the pullback cost anything" — read it beside the entry
table, never instead of it.

## Caveats printed with every run

* Survivorship — today's big caps.
* Fills are the 60m close of the signal bar, not the zone edge; no slippage,
  no commissions.
* Same-minute stop + target = stop; a target already passed at the fill or a
  stop already crossed is bad geometry, skipped and counted.
* The placebo line is the placebos of the resolved signals only, each placed
  so its own window ends before its signal's session.
* The board is read at 60m closes only; the cron re-reads every 15 minutes
  with a partial hour bar, so a state that flickered intra-hour is not a
  signal here.
* The as-of daily bar is RTH minutes; the live board overlays the provider's
  day bar, which can differ by the auction prints.
* The daily frame start sits ~18 months before an early signal instead of 24
  (2y cache cut at the session).
* Every threshold is an owner constant unless the video states it.

## Re-run

Inside the api container (the price cache, the per-day minute cache and
Mongo live there; nothing is written to Mongo by this script):

```
cd /app && PYTHONPATH=/app python -m ict.backtest --names 300 --months 6 \
    --out /tmp/ict_bt.json --md /tmp/ict_bt.md --seed 7 --workers 4
```

* One JSON line per finished symbol goes to `<out>.partial.jsonl` as it
  finishes (a fresh run truncates the file first); `--resume` re-reads it
  and skips the symbols that finished `ok` or were skipped for a data reason
  — a symbol that errored (provider timeout) or had no minutes at all (the
  circuit breaker was open) is re-run, and its newer line wins.
* `--symbols AAPL,MSFT` overrides the sample (smoke runs);
  `--minute-source range` for a cold minute cache; `--horizon` overrides
  `HORIZON_SESSIONS` for a sensitivity pass (report it as such).
* Progress: one log line per 25 symbols with elapsed time and an ETA, one
  total at the end. Workers are threads; the walk is pure Python, so
  expect ~1.3× from 4 workers, not 4× — the I/O is what parallelises.
* Tests: `cd backend && .venv/bin/python -m pytest tests/test_ict_backtest.py tests/test_ict.py -q -p no:cacheprovider`.
