# Failed-trade autopsy — `backend/trading/autopsy.py`

**Ask (Ajay 2026-09-03):** *"We have alpaca setup you try paper trading on
that account with live execution. I wanna put some money eventually on the
supply demand concept. Please make a rule to add feedback and analysis of
failed trades."*

Every **losing** Auto-Pilot round-trip gets an autopsy: the numbers of the
trade (lag, chase, stop requested vs placed, MFE/MAE in R, band held,
reclaimed, SPY/RSP context), **one class** from a fixed rule table, and
**one feedback line** that states what the numbers say and which owner
decision they point at. It runs inside the engine tick (paper first), shows
on the Trading page and on `GET /trading/autopsies`, so the rules learn
before real money goes into the Supply & Demand concept.

---

## 1. Honesty note — owner rules, no book

| Layer | Source | Where it lives |
|---|---|---|
| **Classification rules + every threshold** (the table in §3) | **Owner rules** for the Supply & Demand strategy — Ajay's playbook. **No book.** Nothing here is Minervini and no SEPA page is cited (`feedback_sepa_book_scope`). | `trading/autopsy.py` (constants locked in `tests/test_trading_contracts.py`) |
| **Placed stop** (`entry.stop_pct` / `entry.stop_price`) | Read back from the journal. It was decided at entry by the engine-wide risk contract `trading/risk_rules.py` — **book, FROZEN, untouched here**. The autopsy only compares it with what the strategy *requested*. | `trading/journal.py` → `trade_journal` |
| **Inputs** (minute bars, daily bars, SPY/RSP, zone state, gauge) | Existing readers, all read-only | `daytrading/data.py`, `sepa/prices.py`, `zone_edge_entry_state`, `sepa/market_gauge.py` |

The module never imports the broker and writes **only** `trade_autopsies`
(plus one `autopsy` row in `trade_ledger` per trade). The contract test
greps it for order tokens and counts its Mongo writes.

Feedback lines are **mechanical statements, never advice**: each template
ends in *"… is an owner decision"* and carries the trade's numbers.

## 2. Scope + strategy detection

Closed `trade_journal` docs with `realized.gain_pct < 0` (any strategy).
Winners, breakeven (0.0%) and open trades are never autopsied.

| Strategy | Detected by | Band / floor |
|---|---|---|
| `zone_edge` | a `zone_edge_entry_state` row with `entered = true` for the symbol on the **ET day of the entry**; when the journal's `entry` ledger row carries a `client_order_id` / `order_id` and the state rows do too, the ids decide (a state row with only foreign ids is never used) | the state row's `band {lo, hi, touches}`, `side` (`demand` / `supply`), `kind` (`demand` / `breakout`), `tier`, `first_seen`, **requested** `stop_pct` |
| `minervini` | `entry.trigger.path` is set (the `auto_entry` funnel) | `band = {lo: pivot, hi: pivot}`, `kind = breakout`, `side = pivot`; no requested stop |
| `manual` | neither | no band → every band read is `None` (never `false`) |

**Floor** = `band.lo` for demand entries, `band.hi` for breakouts (the
cleared ceiling / the pivot).

## 3. Rule table (OWNER rules — first match wins)

| # | Class | Rule | Threshold (constant) |
|---|---|---|---|
| 1 | `stop_clamped` | the placed stop is **tighter** than the requested stop by more than the tolerance **and** the exit printed at/above the requested stop level — the risk contract's clamp took the trade out, not the band | `requested − placed > 0.1 pt` (`CLAMP_TOLERANCE_PT`) |
| 2 | `shakeout` | exit leg = `stop` **and** a close back above the floor within the sessions after the exit day | `leg = stop AND reclaimed_within_2` (`SESSIONS_AFTER_EXIT = 2`) |
| 3 | `band_failed` | exit-day close under the floor | `band_close_held = false` |
| 4 | `market_down` | SPY **or** RSP down on the exit day and the trade never reached the follow-through R | `SPY or RSP ≤ −1.0%` (`MARKET_DOWN_PCT`) **and** `MFE < 0.5 R` (`FOLLOW_THROUGH_R`) |
| 5 | `chased` | entry above the band ceiling by more than the limit | demand `> 1.0%` (`CHASE_DEMAND_PCT`), breakout `> 2.0%` (`CHASE_BREAKOUT_PCT`) |
| 6 | `no_follow_through` | the trade never reached the follow-through R | `MFE < 0.5 R` |
| 7 | `unclassified` | nothing matched — kept as data | — |

A rule whose inputs are `None` never fires (a manual trade has no chase
limit; a missing daily bar cannot make `band_close_held` false).

**Secondary tags** (a list, any number may apply):

| Tag | Rule | Constant |
|---|---|---|
| `first_30_min_entry` | entered before minute 30 of the session | `FIRST_MINUTES = 30` (of `SESSION_MINUTES = 390`) |
| `late_day_entry` | entered after minute 330 | `LATE_MINUTES = 330` |
| `gap_down_open` | entry-day open ≤ −1.0% vs the prior close | `GAP_DOWN_PCT = -1.0` |
| `thin_band` | band touches ≤ 2 | `THIN_BAND_TOUCHES = 2` |
| `wide_stop` | placed stop > 7% | `WIDE_STOP_PCT = 7.0` |
| `partial_data` | status is `incomplete` | — |

**Feedback line per class** (numbers filled from the doc):

- `stop_clamped` — *"requested stop X% was clamped to Y% at entry (risk contract); exit P printed above the requested level L — the clamp took the trade out, not the band; … entry width vs the band is an owner decision"*
- `shakeout` — *"stop X% under the floor F sat inside the noise: MAE −a% vs ATR b%; close back above the floor within 2 session(s) after the exit; a wider buffer is an owner decision"*
- `band_failed` — *"band floor F did not hold: exit-day close C sat x% under it, MFE rR; … band selection (touches t, tier T) is an owner decision"*
- `market_down` — *"SPY s% / RSP r% on the exit day with MFE rR (< 0.5R): the tape took it, not the band; an index filter on entries is an owner decision"*
- `chased` — *"entry E printed c% above the band ceiling H (limit l%): … an entry-distance cap is an owner decision"*
- `no_follow_through` — *"MFE rR (< 0.5R) in m min before the stop: … a time stop or a confirmation wait is an owner decision"*
- `unclassified` — *"no rule matched: MFE …, MAE …, band held …, SPY … on the exit day; stays as data — any new rule is an owner decision"*

## 4. The numbers (how each is computed)

| Field | Definition |
|---|---|
| `entry.entry_lag_sec` | entry timestamp − (`first_seen` HH:MM ET on the entry day); zone-edge only |
| `entry.session_frac` | minutes since 9:30 ET at entry / 390, clamped to [0, 1] |
| `entry.chase_pct` | `(entry_px − band.hi) / band.hi × 100` (both kinds: distance past the ceiling) |
| `entry.stop_requested_pct` / `stop_placed_pct` / `clamped` | strategy's request (state row) vs the journal's placed stop; `clamped` = placed tighter by > 0.1 pt |
| `excursion.mfe_pct` / `mae_pct` | max high / min low of the **RTH** minute bars from the entry's minute through the exit's minute (the exit bar carries the stop print), vs the entry price |
| `excursion.mfe_r` | `mfe_pct / stop_placed_pct` (R = the placed stop distance); `reached_1r` = `mfe_r ≥ 1` |
| `exit.time_to_exit_min` | exit − entry, minutes |
| `structure.band_close_held` | exit-day close ≥ floor (`None` without a floor or without the bar) |
| `structure.reclaimed_within_2` | any of the **2 closed sessions after the exit day** closes ≥ floor → `true`; both exist and neither does → `false`; fewer than 2 exist → `None` |
| `structure.gap_open_pct` | entry-day open vs the prior close |
| `structure.atr_pct_14` | ATR of the 14 closed daily bars **before** the entry day (the entry day's bar is still forming at entry and carries the stop print), as % of the entry price (quoted in the shakeout line) |
| `market.spy_pct_*` / `rsp_pct_*` | close-to-close change of SPY / RSP on the entry day and the exit day, from their daily frames |
| `market.gauge_now` | `auto_entry._gauge_state()` at **run** time (labelled `now` — not the state at entry) |

Daily frames come from `sepa.prices.load_prices(symbol, "2y")` — the
cache-wide default period on purpose: `load_prices` writes a cache miss
back into the shared `price_cache` (Mongo + parquet, 20 h TTL) that the SEPA
scanner, the zone store and the gauge read **without** a period, so a
shorter frame requested here would feed a 3-month history to the 200-DMA
and the 52-week range for the rest of the day (`DAILY_PERIOD` is locked in
the contract test). The live bar is overlaid (`with_today_bar`); the overlay
row is flagged `live` and **never counts as a closed session** (it may serve
as the exit-day close while the doc is still preliminary). Minute bars:
**one** `daytrading.data._fetch_massive_minute(symbol, entry_day, exit_day)`
call per trade.

## 5. Status, retries, idempotence

| Status | Meaning |
|---|---|
| `preliminary` | inputs complete, fewer than 2 closed sessions after the exit day |
| `final` | inputs complete and both sessions exist — **never recomputed or downgraded** afterwards |
| `incomplete` | at least one input missing (`missing[]` names them); re-tried up to `MAX_RETRIES = 5` (count in `retries`); the rules that can read still classify, tag `partial_data` |

- `_id = trade_id` (`{SYM}-{entry epoch}`), upsert in place → re-running is
  idempotent.
- A non-final doc is re-checked at most once per `RECHECK_SEC = 3600`.
- A re-check that **loses** an input (provider hiccup, circuit breaker)
  never replaces computed numbers with `None`: the previous `preliminary`
  doc is kept as is, `last_miss {at, missing[]}` is stamped, `retries` is
  bumped (visible, but a `preliminary` doc is never retry-capped), and the
  trade still finalizes once the input is back. Only a doc that was
  `incomplete` from the start is retry-capped.
- Per run: new losing trades first (newest entry first), then due
  re-checks; at most `MAX_PER_RUN = 3` trades. SPY / RSP frames and the
  gauge load **once** per run, and nothing at all is loaded when nothing is
  pending.
- **One** `autopsy` row in `trade_ledger` per trade, written the first time
  it is classified on complete inputs (`detail`: classification, strategy,
  feedback, tags, gain/R, MFE/MAE, chase, stops, band held / reclaimed,
  SPY/RSP exit day, time to exit) — it shows in the decisions feed. The row
  is written only **after** the doc upsert succeeded (a failed store ledgers
  nothing, so a trade can never be re-ledgered on every re-check). A later
  class revision at finalization (e.g. `band_failed` → `shakeout` once the
  reclaim lands) updates the doc, not the ledger.
- A malformed journal doc (`realized` / `exit` / `entry` not a dict) is
  skipped when its gain is unreadable, otherwise lands as `incomplete` —
  never an exception, never a run-wide abort.

## 6. Reading a doc

```
{ trade_id, symbol, strategy, side, kind, status, computed_at, retries, missing[],
  entry:     {ts, epoch, price, qty, stop_price, stop_requested_pct, stop_placed_pct,
              clamped, first_seen, entry_lag_sec, session_frac, chase_pct, band, tier,
              mode, regime, day},
  exit:      {ts, epoch, price, leg, gain_pct, r_multiple, time_to_exit_min, day},
  excursion: {mfe_pct, mfe_r, mae_pct, reached_1r, n_bars},
  structure: {floor, band_close_held, exit_day_close, reclaimed_within_2,
              sessions_after_exit, gap_open_pct, atr_pct_14, stop_below_floor_pct},
  market:    {spy_pct_entry_day, rsp_pct_entry_day, spy_pct_exit_day, rsp_pct_exit_day,
              gauge_now},
  classification, tags[], feedback, ids: {order_id, client_order_id} }
```

Read it in this order: **class** (the one rule that fired, in priority
order) → the **feedback** line (which numbers drove it) → `status` (a
`preliminary` shakeout/band_failed can still flip once the two sessions
land; `incomplete` means a number is missing, not that the trade was fine)
→ `tags` for the timing / structure context. `mfe_r` is the honest
"did it ever work" read; `chase_pct` is the price paid for being late;
`stop_requested_pct` vs `stop_placed_pct` is the only place the book's
contract and the owner's stop can disagree.

## 7. API

`GET /trading/autopsies?days=30` (admin) →

```
{ rows: [docs, newest exit first, _id dropped],
  summary: {n, by_class: {cls: n}, by_strategy: {s: n}, n_final, n_preliminary,
            n_incomplete, median_mfe_r, median_time_to_exit_min},
  rules: [{class, rule, threshold}, …],   # the table above, from the code
  days }
```

JSON-safe (no NaN / numpy types); medians are `null` when `n = 0`; `days`
is clamped to 1…365. Read-only — the docs are written by the tick.

## 8. Wiring + ops

- `exit_engine.tick()` step **(i)**, right after (g) journal reconcile,
  fenced in its own `try/except` exactly like (f)/(h): an autopsy crash
  lands in `summary.errors` and can never touch stop protection.
- Manual run (api container):

```
docker compose exec api python -m trading.autopsy      # one INFO line: the run summary
```

- Frontend: `TradeAutopsies` on the Trading page under the execution race
  (header "🔬 Failed-trade autopsies (30d)").

## 9. Tests

- `tests/test_autopsy.py` — scope (winners / breakeven / open never
  autopsied; no reads when nothing is pending), strategy detection
  (zone-edge via state, id preference, foreign ids refused, minervini via
  trigger, manual), one test per class **and** the priority order
  (shakeout > band_failed > market_down > chased > no_follow_through),
  the demand vs breakout chase limits, the clamp negative + tolerance,
  tags positive/negative, preliminary → final (live bar never a session),
  final never downgraded, incomplete + retry cap + recovery, throttle,
  idempotent upsert, `MAX_PER_RUN` bound + newest-first + one SPY/RSP/gauge
  read per run, soft failure (journal down, one trade failing, missing
  collection, state read failure), the pure helpers (RTH-only excursion,
  daily reads, ATR, session fraction, lag, floor), pandas frame → records
  through the real seams, report shape + medians at n = 0 + window + NaN
  scrub, API admin gate (403) + `days` clamp, tick step (i) fence + order,
  CLI.
- `tests/test_trading_contracts.py` — constants locked verbatim, class
  order locked, no broker tokens / no book cites / exactly one Mongo write,
  every feedback template names the owner decision, tick (i) fenced after
  (g), `/autopsies` admin-gated.
