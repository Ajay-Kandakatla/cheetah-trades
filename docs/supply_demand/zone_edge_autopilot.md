# Zone-edge Auto-Pilot — `backend/trading/zone_edge_entry.py`

**Ask (Ajay 2026-09-03):** *"by the time the alert reaches me I am late and the
stock is already bouncing off ... Can you autopilot this and make buys and
sells tomorrow in RTH? ... We already have an autopilot based on Minervini ...
Paper trade ... I wanna see the execution time comparison between you and I."*

Decisions he made: arm the **paper** engine with the Minervini `auto_entry`
flag **OFF** (zone-edge only); trade **both** zone-edge signals (demand
arrivals + breakouts); his reaction clock = the first time he opens the
ticker page after the signal **and** his manual Portfolio fill.

---

## 1. Honesty note — what is a book rule and what is not

| Layer | Source | Where it lives |
|---|---|---|
| **Entry rules** (which board rows, the requested stop, the room check, the daily cap, the entry window) | **Owner rules** for the Supply & Demand strategy — Ajay's playbook. **No book.** Nothing here is Minervini, and no SEPA page is cited for any of it (`feedback_sepa_book_scope`). | `trading/zone_edge_entry.py` (constants locked in `tests/test_trading_contracts.py`) |
| **Signal** (the bands, touches, "near / in / broke", arrival, new highs) | Configured price-structure heuristic (`docs/supply_demand/demand_zones_methodology.md`, `session_board.md`) | `supply_demand/zone_edge.py` → Mongo `zone_edge_latest` / `zone_edge_track` |
| **Risk math** (stop clamp to the absolute 10% line, target ≥ 2:1, 25% sizing, losing-streak multiplier, never average down, earnings shield, MAX_POSITIONS) | The engine-wide risk contract, `trading/risk_rules.py` — **book, FROZEN, unchanged by this feature** | applied by `trading/entries.enter()`, the **only** buy path |

The module only *requests* a stop; `risk_rules` decides. It never places an
order at the broker itself (contract test greps it for `submit_` /
`replace_order` / `cancel_order` / `close_position`).

## 2. Signal source (read-only)

`supply_demand/zone_edge.py` runs once a minute in RTH and upserts
`zone_edge_latest` (`_id: 'latest'`):

```
{as_of: ET ISO, date: 'YYYY-MM-DD', in_session, counts,
 breaking:    [row],   # supply side — tier 'near' | 'broke'
 near_demand: [row]}   # demand side — tier 'near' | 'in', arrival flag
row = {symbol, name, last, dist_pct, tier, side, role,
       band:{kind, lo, hi, touches, strength}, cap, new_highs, high_252,
       pct_to_52w, overhead_bands, arrival, first_seen ('HH:MM' ET), url}
```

and appends `zone_edge_track` rows `{symbol, date, ts, side, tier, px,
dist_pct, band}` per listed row per pass. The engine reads both through the
same Mongo handle `exit_engine` uses and never writes to them.

## 3. Entry rules (owner rules)

| Constant | Value | Meaning |
|---|---|---|
| `MAX_ZONE_ENTRIES_PER_DAY` | 4 | zone-edge buys per ET day (counted from `zone_edge_entry_state` successes) |
| `STOP_BUFFER_PCT` | 0.5 | the requested stop sits this far **under the band floor**: `stop = band.lo × (1 − 0.5%)` |
| `MIN_TOUCHES` | 2 | band must be proven structure (same floor as the board's pushes) |
| `MIN_CAP_USD` | 1e9 | "billion or at least bigger than a billion" (mirrors `zone_store.MIN_CAP_USD`) |
| `SIGNAL_MAX_AGE_SEC` | 180 | a `latest` doc older than this (or from another day, or without a readable `as_of`) is **stale → no entries** |
| `LAST_ENTRY_ET` | 15:45 | no new entries at/after this; the 15:44 tick is the last |
| `RISK_STOP_FLOOR_PCT` | 1.0 | **not an owner rule** — a mirror of the bare literal `pct = max(pct, 1.0)` in FROZEN `trading/risk_rules.py` (the floor every placed stop gets); the room gate measures 2R off the stop that will actually be placed. Pinned to the literal in `tests/test_trading_contracts.py`. |
| `alert_gates.ALERT_MIN_ROOM_PCT` | 5.0 | **phone gate = entry gate (2026-09-05)** — at least 5% room from the print to the first *unbroken* band overhead (imported from `supply_demand/alert_gates.py`, never redefined). Owner setting — Ajay 2026-09-05: *"atleast 5% to Supply"*. |
| `alert_gates.ALERT_MAX_ABOVE_DEMAND_PCT` | 1.0 | **phone gate = entry gate (2026-09-05)** — a demand buy only while the print sits between the band floor and 1% above its top (imported). Owner setting — Ajay 2026-09-05: *"<1% bounce from demand zone"*. |

Candidates per tick, in this order:

1. **Breakouts** — `breaking` rows with `tier == 'broke'` **and** `new_highs`
   **and** `touches ≥ 2` **and** `cap ≥ $1B`. Stop under the floor of the band
   just cleared (it becomes support). A **`near` resistance row is never
   bought** — it is not through yet. Least-extended first.
2. **Demand arrivals** — `near_demand` rows with `arrival == true`, `tier in
   ('near','in')`, `touches ≥ 2`, `cap ≥ $1B`. Residents (`arrival` false or
   missing) are never bought. Closest to the band first (`dist_pct` asc).

Then, per candidate:

- `stop_pct = (last − stop) / last × 100`. `stop_pct > risk_rules.ABS_MAX_STOP_PCT`
  (10) → **blocked** `stop wider than book max`; `stop_pct ≤ 0` → blocked.
  Otherwise the stop is handed to `entries.enter(sym, limit_price=None,
  stop_pct=…, stop_price=stop, allow_earnings=False)` as the **absolute
  level** (`stop_price`, since 2026-09-05 — `stop_pct` rides along as the
  signal-time request the ledgers record). `entries` converts the level to a
  percent **at its own planning price** (the live print at order time), so
  the broker stop rests at `band.lo × 0.995` on the cent grid whatever the
  tape printed since the board saw the row; risk_rules sizes / targets from
  there. If the print drifted so far that the level is past the 10% line, or
  the print is already **through** the level, `entries` **refuses** (a
  `blocked` attempt with the reason) — it never clamps the stop back up into
  the band.
- **Room sanity** — the **first band overhead** (from the symbol's
  `zone_store` doc for the day — **one read per candidate**) must be at least
  `risk_rules.MIN_REWARD_RISK × max(stop_pct, RISK_STOP_FLOOR_PCT)` (2R of
  the stop that will be *placed*) away in %, else **blocked** `room < 2R`.
  Overhead is kind-agnostic, the same rule the Portfolio supply watch
  (`portfolio/supply_watch.overhead_bands`) and the bounce-room read
  (`supply_demand/bounce_room.first_overhead`) apply: a **supply** band with
  `hi ≥ last` — one that **contains** the print is zero room → **blocked**
  `inside supply band` — and a **demand** band with `lo > last` (broken
  support is resistance). A demand band containing or below the print is
  support, never overhead. Nothing overhead = unbounded room = ok. **No zone
  doc = unknown = blocked** (fails closed). Breakouts to new highs with
  `overhead_bands == 0` skip the check. The gate's detail carries
  `need_pct`, `room_pct`, `next_band {kind, lo, hi}` and `reason`.
- Every missing input (no print, no band, unknown touches/cap, unknown
  overhead) **fails closed**.

Skips that are **not** attempts (nothing recorded, re-evaluated next tick):
flag off / disarmed / not configured / market closed (one `zone_entry_disabled`
ledger row per ET day), stale signal (older than 180 s, another day, unreadable
`as_of`, or stamped more than 180 s in the **future**), at/after 15:45, symbol
already held (`broker.positions()`), symbol already **bought today under
another band** (the broker's same-day `client_order_id` would reject it
anyway), daily cap reached, no position slot (`risk_rules.MAX_POSITIONS`),
same band already attempted today, a `market closed` veto from `entries`
(clock flipped mid-tick).

**Attempts** — one per `(symbol, band lo-hi, ET day)`, written to
`zone_edge_entry_state` **before** `entries.enter` is called. Blocked and
error attempts are recorded too, so a rejected name is never retried every
minute.

**The attempt store fails closed.** If today's state rows cannot be read the
tick sits out (`reason: state_unavailable`); if one band's record cannot be
read that candidate is skipped; if the attempt record cannot be **written**,
`entries.enter` is **not** called (a crash mid-enter without a durable record
would otherwise be retried every minute). Each case lands in the tick's
`errors[]`, nothing is ordered, and the next tick re-evaluates.

**Once `entries.enter` returns, an order exists.** The `try/except` wraps only
that call; the bookkeeping after it (ledger, state, race doc, push) each
swallow their own failures, so a placed order is always recorded as
`entered` / `ordered` and never relabelled blocked or error. Malformed board
rows (non-string symbol, band that is not a dict, sections that are not
lists) are rejected, and a `zone_store` doc whose `bands` is not a list of
dicts is *unknown room* (blocked) — never a crash out of `run()`.

### Phone gate = entry gate (2026-09-05)

> **2026-09-06 — proven lids.** Both the alert gate's room read and `room_ok`'s
> 2R check skip a lid with < 2 touches or strength < 40 and measure to the next
> proven band (the KLAC lesson). See `docs/supply_demand/proven_lids.md`.


**Ask (Ajay 2026-09-05, verbatim):** *"What ever rules I created for the alerts
are the ideal conditions for a stock to be bough in Autopilot. Keep the
minervini entries but also make sure you have demand zone and catalyst based
entries time to time and journal it appropriately."*

The two phone rules in `supply_demand/alert_gates.py` are now an **AND on top
of every gate above** — none of them moved. Measured on the same `zone_store`
doc the 2R gate reads (one read per candidate), in `zone_edge_entry.alert_gate`:

| Rule | Function | Applies to | Detail |
|---|---|---|---|
| ≥ 5% room to the first **unbroken** band overhead | `alert_gates.room_gate(last, bands, prev_close)` | every candidate | overhead = supply bands with `hi ≥ last` that yesterday did **not** close above (`hi < prev_close` = broken lid = support), plus demand bands with `lo > last` (broken support = resistance). **CLEAR** (nothing overhead) passes; **IN_BAND** (the print inside a supply band) fails; room under 5% fails. **Breakouts** are measured against the bands strictly **above the band being cleared** (`hi > band.hi`) so the cleared band is never its own lid; a breakout to new highs with `overhead_bands == 0` is CLEAR by the board's own read (no doc needed). For demand rows the entry band itself is excluded (it is support). |
| print within 1% above the demand band top | `alert_gates.demand_proximity_gate(last, band)` | demand candidates only | `band.lo ≤ last ≤ band.hi × 1.01`. Under the floor = fell through; above the line = *"I am late by the time it reaches me"* — both fail. |

**Why TRU was on the board and must not be bought:** print 79.88 inside demand
band 78.34–81.08, which *contains* a supply band 80.12–82.10 → the first
unbroken band overhead is 0.3% away → `alert gate: room 0.30% < 5% (supply
80.12-82.1)`. The old 2R gate would also have refused it (`room < 2R`), but the
alert gate now speaks first and in the owner's own units. The refusal quotes
the **raw** pct at 2 dp (`room["room_pct_raw"]`, added to `alert_gates.room_read`
2026-09-05): the 1-dp display number can read "5.0% < 5%" at the 4.995%
boundary, and `room_gate` itself now compares the unrounded value (it used to
rebuild the pct from a cents-rounded target and let 4.995% through).

**A failure is a SKIP, not an attempt** — the room can open later in the day
(a lid breaks, the print pulls back to the level), so the row is re-read next
tick. It lands in the tick summary's `skipped[]` with reason `alert gate: …`,
is counted in `skipped_alert_gate`, and writes an `execution_race` row with
`outcome: 'skipped'` and the gate detail (`gate: {ok, room, proximity,
reason, min_room_pct, max_above_demand_pct}`), so the race still records that
the engine saw the signal and why it stood aside. An **unknown** doc (missing,
or `bands` not a list of dicts) is not a gate verdict — the 2R gate then blocks
`room unknown` as before (fails closed either way).

Order per candidate: stop gate → **alert gate** (skip) → 2R room gate (blocked
attempt) → `entries.enter`. `GET /trading/status .zone_edge_entry` gains
`alert_gate {min_room_pct, max_above_demand_pct}` and
`skipped_alert_gate_today` (distinct race rows skipped today); the `rules[]`
list carries both rules with the dated quote as their source.

**Journal lane tag.** The ONE `entries.enter` call now passes
`strategy="demand_zone"` for demand rows and `"breakout"` for supply-side rows,
with `reason = {side, tier, band, room (2R detail), proximity, gate, dist_pct,
first_seen}` — see `docs/sepa/journal_analytics_methodology.md` §2a. The
Minervini funnel tags its buys `minervini`; the catalyst lane
(`docs/supply_demand/catalyst_entry.md`) tags `catalyst`. Every lane is still
**paper** and still flows through the same `entries.enter → risk_rules` path.

Ledger kinds: `zone_entry` (side, band, stop_pct, dist_pct, first_seen,
order id, `gate`; `dry_run=false`), `zone_entry_blocked` (`dry_run=true`),
`zone_entry_error` (`dry_run=false`, "verify at the broker whether an order
exists"), `zone_entry_disabled` (once per day). Push on a buy: owner-only,
title `🎯 Zone-edge paper buy {SYM} {side}` (the mode word follows the
broker: paper / sim / LIVE).

Wiring: `exit_engine.tick()` step **(h)**, right after (f) `auto_entry`,
fenced in its own `try/except` — a zone-entry crash can never break stop
protection. `GET /trading/status` carries `zone_edge_entry`
(`enabled, entries_today, max_per_day, last_entry_et, signal{fresh, age_sec,
reason…}, rules[], attempts[]`).

## 3b. Quick Bounce day-trade variant (Ajay 2026-09-06)

> "automating this with paper trade I think we will see more value for day
> trading."

A demand-zone entry on a name the weekly Quick Bounce study lists
(`supply_demand.quick_bounce.qualifies`: ≥ 3 visits to a proven demand band,
≥ 50% of them a same-day / next-morning-gap turn) is journaled as strategy
**`quick_bounce`** instead of `demand_zone` — same entry rules, same alert
gate, same stop — and the state doc carries `strategy`. Tick step **(h2)**
(`zone_edge_entry.quick_bounce_eod`, owner switch `quick_bounce_eod_flatten`,
default ON, `POST /trading/config`) flattens every quick_bounce entry of the
day still held at/after **15:55 ET** through `exit_engine.flatten` (queued
when Alpaca refuses, like any owner exit); once per symbol per day
(`eod_flattened` on the state doc). Names not held any more (stopped,
targeted, unfilled) are skipped and noted. The Journal's by-lane table
therefore reports `quick_bounce` next to `demand_zone`, so the day-trade
variant is measured on its own (Rule #9 autopsies apply). Study + list:
`docs/supply_demand/quick_bounce.md`.

## 4. The execution race ledger (`execution_race`)

One doc per `(symbol, side, band, ET day)`, `_id = "{SYM}:{side}:{lo}-{hi}:{day}"`,
written for **every** candidate attempt — blocked ones included, so the race
still records that the engine saw the signal at signal time.

| Field | Meaning |
|---|---|
| `signal_first_seen`, `signal_ts` | the row's `first_seen` (HH:MM ET) and the ET ISO built from `day + first_seen` (`signal_ts_basis: 'first_seen'`; falls back to the doc's `as_of`) |
| `signal_px` | `row.last` when the engine first saw it |
| `engine_order_ts`, `engine_order_id`, `engine_client_order_id` | UTC ISO when `entries.enter` returned + the ids from its `entry` ledger row |
| `engine_fill_ts`, `engine_fill_px` | reconciled from `broker.closed_orders_since` (matched by `client_order_id` / id, filled buys only) — the same read `exit_engine` uses for fills |
| `user_view_ts`, `user_view_px` | the owner's first `usage_events` row with route `/sepa/{SYM}` (any query string) started after `signal_ts`; px = the `zone_edge_track` print nearest that minute (within 5 min, else `None`) |
| `user_fill_ts`, `user_fill_px` | the owner's `portfolio_holdings` row for SYM added/updated after `signal_ts`; px = `cost_basis / shares` |
| `outcome`, `reason` | `ordered` \| `blocked` \| `error` \| `skipped` (alert gate, 2026-09-05 — re-read next tick) |
| `gate` | the alert-gate detail `{ok, room, proximity, reason, min_room_pct, max_above_demand_pct}` (2026-09-05); `null` on rows written before the gate existed |

`reconcile_race()` runs at the end of every `run()` and on every
`GET /trading/race`; it touches **only** today's and yesterday's docs and is
**read-only** over every other collection and the broker.

`GET /trading/race?days=5` → `{rows, summary, days, owner}`. Each row is the doc
minus `_id` plus `engine_lag_sec`, `engine_fill_lag_sec`, `user_view_lag_sec`,
`user_fill_lag_sec` (all vs `signal_ts`), `px_base` (engine fill px, else
signal px), `px_gap_view`, `px_gap_fill`, `px_gap_fill_pct`. Summary: `n`,
`n_ordered`, `n_engine_filled`, `n_user_viewed`, `n_user_filled`,
`median_engine_lag_sec`, `median_engine_fill_lag_sec`,
`median_user_view_lag_sec`, `median_user_fill_lag_sec`,
`median_px_gap_fill_pct`. JSON-safe (no NaN).

Reading it honestly: `user_view_lag` is the time to *look*, `user_fill_lag`
the time to *act*; `px_gap_fill_pct > 0` means the manual fill paid more than
the engine's. A blocked row with a user fill is a signal the engine refused
and Ajay took — those rows are the ones to argue about.

## 5. Ops recipe (paper)

```
POST /trading/arm?armed=true
POST /trading/auto-entry?enabled=false          # Minervini funnel OFF
POST /trading/config  {"zone_edge_entry": true}  # zone-edge ON
GET  /trading/status                             # .zone_edge_entry.signal.fresh must be true in RTH
GET  /trading/race?days=5                        # the comparison
```

Turn it off with `POST /trading/config {"zone_edge_entry": false}` (or
`null` — the default is OFF in every mode). Disarming (`/trading/arm?armed=false`)
stops every buy path at once.

Pre-flight checks the morning of: the 9:20 `zone_store` warm ran (room checks
fail closed without it), the zone-edge cron is writing `zone_edge_latest`
every minute (`status.zone_edge_entry.signal.age_sec` under 180), broker mode
reads `paper`.

## 6. Tests

- `tests/test_zone_edge_entry.py` — phone gate = entry gate (2026-09-05): the
  TRU shape (0.3% room → skipped, race row `skipped` + gate detail, no
  attempt, re-read next tick), a resident in its band with 8% room passes
  (strategy `demand_zone`), 1.5% above the top fails proximity, a breakout
  measured to the band above the cleared one (3% skip / 6% pass / none pass,
  strategy `breakout`), pure-function edges (unknown doc → 2R gate, broken
  lid, under the floor), status `skipped_alert_gate_today`; gates, every
  funnel negative, stop/room
  blocks, skips vs attempts, success/veto/error/market-closed paths,
  ordering, reconcile + report (lags, medians, NaN safety, window), tick
  hook fence, status block, config + race routes; review regressions: state
  read/write failure places no order, post-order bookkeeping failure never
  relabels a placed order, malformed rows / zone docs never raise or buy,
  future-dated `as_of` not trusted, same symbol under another band skipped.
- `tests/test_trading_contracts.py` — constants locked verbatim, no book
  cites, risk numbers read from `risk_rules` (never re-derived), no direct
  broker order tokens, factory invariant, tick (h) fenced and ordered,
  config whitelist, `/race` admin-gated.

## Rule switches (owner, 2026-09-03 evening) — `zone_edge_rules` in the engine config

Ajay: "Enter anything that is in demand zone to buy but if it crosses the stop loss sell it ...
Any time any stocks crossing the resistance or supply zone buy them too. Usually they are likely
to go much higher."

| key | default (STRICT) | WIDE (paper run from 2026-09-04) | effect |
|---|---|---|---|
| `demand_residents` | false | true | buy names already **in** a demand band, not only fresh arrivals |
| `breakout_any_band` | false | true | buy **any** cross through a supply band (tier `broke`), not only the last one toward new highs |
| `min_touches` | 2 | 1 | bands tested fewer times are skipped |

Everything else is unchanged in both modes: stop 0.5% under the band floor, placed at that level
(refused past the book's 10% — at the signal or after the print drifted), room ≥ 2R to the first band
overhead, supply or broken demand (breakouts to new highs with nothing overhead skip it),
cap ≥ $1B, max 4 a day, none at/after 15:45 ET, one attempt per band per day, never a held name,
every buy through `entries.enter` → `trading/risk_rules.py`. The **stop is the "sell it" half** of
his ask: the bracket's stop leg rests at the broker; a stopped name is done for that band that day.

Ordering with wide rules: breakouts (least extended first) → demand arrivals (closest to the band
first) → residents by band quality (touches desc, strength desc, distance asc), so the 4 daily
slots go to the freshest touch and the most-tested bands.

Set: `POST /trading/config {"zone_edge_rules": {"demand_residents": true, "breakout_any_band": true,
"min_touches": 1}}`; `null` resets to STRICT. `GET /trading/status` → `zone_edge_entry.active_rules`.
Strict vs wide is the first named paper experiment (see the S&D research-loop rule).


## Fixes 2026-09-05 — stop anchoring, room gate (Ajay 2026-09-05: "yes please fix the bugs")

A six-agent review of the Supply & Demand zone logic reproduced these on synthetic frames; Ajay
signed off on fixing every one.

| # | Was | Now | Test |
|---|---|---|---|
| stop as a percent of a stale print | `stop_pct` (derived from the **board** print) was re-applied by `risk_rules.initial_stop` to the **order-time** print, so a print 1.5% higher than the signal put the broker stop **inside** the band being bought (signal 100 / band 98–100 → stop 97.51 requested, 98.97 placed at a 101.50 print). | `entries.enter(..., stop_price=level)`: the absolute level is converted at the planning price; the placed stop is `band.lo × 0.995` regardless of drift. Drift that pushes the level past `ABS_MAX_STOP_PCT`, or a print already through the level, is **refused** with a reason — never clamped. | `test_stop_is_anchored_under_the_band_floor_when_the_live_print_drifts_up`, `test_stop_anchor_refused_when_drift_pushes_risk_past_the_ceiling`, `test_stop_anchor_refused_when_the_print_is_already_through_the_level` |
| room gate blind to broken demand overhead | only `kind == 'supply'` bands counted, so a demand band 3% above a deep-demand arrival (broken first band = the Portfolio page's "overhead (old support)") was invisible and the buy went in under a lid the app reports. | kind-agnostic first band overhead (supply `hi ≥ last`, demand `lo > last`), the rule `supply_watch.overhead_bands` / `bounce_room.first_overhead` already use. | `test_room_gate_counts_a_broken_demand_band_overhead` |
| inside a supply band = "no supply overhead" | `lo > last` excluded a supply band containing the print. | a containing supply band is zero room → blocked `inside supply band`. | `test_room_gate_blocks_a_print_inside_a_supply_band` |
| need vs the engine's 1% floor | `need = 2 × requested stop_pct` while `risk_rules` places at least 1.0%, so a 0.9% request under-asked room by 0.2pp. | `need = 2 × max(stop_pct, RISK_STOP_FLOOR_PCT)`; the constant mirrors the risk_rules literal and is pinned to it. | `test_room_need_floors_at_the_engine_minimum_stop` |

The FE ⓘ panel text (`rules_list`) now says "first band overhead … or a demand band above it =
broken support … a print inside a supply band has no room" instead of "nearest supply floor above".
Source guards: `test_zone_edge_entry_hands_entries_the_absolute_stop_level`,
`test_zone_edge_room_gate_is_kind_agnostic_and_floors_need_at_the_placed_stop`
(`tests/test_trading_contracts.py`).
