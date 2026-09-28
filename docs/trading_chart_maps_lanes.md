# Auto-Pilot: every Chart Maps strategy as a paper lane, with a journal and a daily loss review

**Owner ask, 2026-09-27:** *"stop minerviews use all strategies from Most used from Chart maps. All of them and journal the,"*

His answers the same day:

| question | his answer | what it means in the engine |
|---|---|---|
| Size | *"Small: 0.25% risk, 15 open max"* | 0.25% of equity at risk per stock trade; each strategy at most **1 new buy a day** and **2 open**; the whole program at most **15 open** (stocks and options, pending orders counted); at most **1 new buy per minute** across every lane |
| Losers | *"analayze losses everyday with a routine or something and restategize and confirm with me"* | **no auto-pause.** A daily loss review after the close; each proposed change is a Confirm/Dismiss card on the Trading page; Confirm applies config keys only, anything needing code becomes a TODO; every decision is ledgered |
| Start | *"Top 10 most-used first"* | the 10 most-opened tabs that are long buy lists start ON; every other strategy is built, OFF, and switchable from the Trading page |

The Minervini lane was stopped the same day (`auto_entry` false). The engine stays armed and manages the positions it already holds.

**Status: UNMEASURED forward paper measurement.** No lane in this program trades a measured edge (see [Priors](#priors-every-lane-starts-null-inverted-or-unmeasured)). The program exists to learn, per strategy and on paper, which entries make money. Judge it in R, not dollars.

Spec: `scratchpad/autopilot_chart_maps_lanes_spec.md` (rev 2). Related docs:
[`trading_engine_inflight_cap.md`](trading_engine_inflight_cap.md) (the chokepoint caps),
[`trading_lane_review.md`](trading_lane_review.md) (the review job),
[`trading_safety_floors.md`](trading_safety_floors.md) (the $2 / $700M floors),
[`trading_options_lane.md`](trading_options_lane.md), [`trading_zero_dte_lane.md`](trading_zero_dte_lane.md).

---

## Where it lives

| piece | file | role |
|---|---|---|
| Roster | `backend/trading/strategy_tags.py` | one row per strategy (sid = tab key), usage order, ON defaults, priors, legacy tag map |
| Chokepoint caps | `backend/trading/program_caps.py` | in-flight cap, one lane per name, per-strategy caps, one entry per minute, 0.25% sizing, ON/OFF |
| Buy chokepoint | `backend/trading/entries.py` `enter` / `_evaluate` | every stock buy; calls `program_caps` |
| Generic lane + dispatcher | `backend/trading/chart_maps_lanes.py` | runs every lane in usage order; one adapter per tab |
| Snapshot job | `backend/chart_maps/lane_snapshot.py`, route `GET /chart-maps/lane-snapshot` | calls each tab's OWN builder every 5 min in RTH, stores slim long candidates |
| Journal exits | `backend/trading/journal.py` | market exits now close the round-trip, priced off broker fills |
| Review + scoreboard | `backend/trading/lane_review.py`, routes under `/trading/review*` and `/trading/strategies` | 17:00 ET scoring, loser lines, proposals |
| Page | `/trading?view=strategies` (🗺️ Chart Maps, second view after Dashboard) | switches, scoreboard, skips, proposal cards |

Live link: https://pounce.ajaykandakatla.dev/trading?view=strategies

---

## The roster

Priority is **live usage order** (`usage_stats` tab opens, `chart-maps:tab:<tab>`), re-read once per ET day by `program_caps.priority_order()`. An empty or unreadable read falls back to `strategy_tags.FROZEN_USAGE_2026_09_27`. The **default-ON set is frozen** from the 2026-09-27 counts, so defaults never shift under him as the counts move.

Opens on 2026-09-27: zones 268, deep_demand 125, hot_sectors 122, support 96, catalysts 85, amd 72, bonde 69, hot_pullback 69, growth 59, quick_bounce 57, patterns 49, breaking 39, keltner 30, signals 27, ict 23, gnt 21, ipo 18, gabbar 17, potus 17, session 11, holdings 10, ema_frames 9, vcp 8, undervalue 8, overnight 6, news 4, earnings / winners / zero_dte 1 each, topping 0.
Ties: bonde and hot_pullback (69, identical `last_seen`) break on sid ascending, so **bonde first**; gabbar and potus (17) break on `last_seen`, so **potus first**. A strategy with two tabs (signals = signals + zero_dte) sums them.

### Lanes (22)

| rank 09-27 | sid | lane | adapter | default | ledger tag | notes |
|---|---|---|---|---|---|---|
| 1 | `zones` | `zone_edge_entry` demand side (existing) | — | **ON** | `demand_zone` | zone gate + `zone_edge_rules` unchanged |
| 2 | `deep_demand` | generic | PLAN | **ON** | `deep_demand` | served BUY/STOP; READY |
| 3 | `catalysts` | `catalyst_entry` (existing) | — | **ON** | `catalyst` | |
| 4 | `amd` | generic | LIST | **ON** | `amd` | prior INVERTED |
| 5 | `bonde` | generic | LIST | **ON** | `bonde` | arrivals only (served `is_new`); prior INVERTED |
| 6 | `hot_pullback` | `hot_pullback_entry` (existing) | — | **ON** | `hot_pullback` | **gains the standing alert gate**; prior null |
| 7 | `growth` | generic | LIST | **ON** | `growth` | |
| 8 | `quick_bounce` | `zone_edge_entry` demand, Quick Reversal variant (existing) | — | **ON** | `quick_bounce` | label "Quick Reversal"; shares the zones slot |
| 9 | `patterns` | generic | LIST | **ON** | `patterns` | `status == "confirmed"` only, bought as a READY demand reversal, never on the neckline break |
| 10 | `breaking` | `zone_edge_entry` supply side (existing) | — | **ON** | `breakout` | |
| — | `keltner` | generic | LIST | OFF | `keltner` | prior INVERTED |
| — | `signals` | `zero_dte_lane` (existing) | — | OFF | `zero_dte` | OFF once the program is ON; with the program OFF, 0DTE runs as today |
| — | `ict` | generic | PLAN | OFF | `ict` | `bias == "bullish"` and `state == "entry"` only |
| — | `gnt` | generic | LIST | OFF | `gnt` | served `fresh` only |
| — | `ipo` | generic | LIST | OFF | `ipo` | demand read computed (tab kind n/a) |
| — | `potus` | generic | LIST | OFF | `potus` | served `is_new` only |
| — | `gabbar` | generic | LIST | OFF | `gabbar` | |
| — | `session` | generic | PLAN | OFF | `session` | `row.signal.trade` only, never the SMC fallback |
| — | `undervalue` | generic | LIST | OFF | `undervalue` | demand read computed (tab kind n/a) |
| — | `overnight` | generic | LIST | OFF | `overnight` | `direction == "up"` only |
| — | `earnings` | generic | LIST | OFF | `earnings` | REACTED group only; UPCOMING is never bought |
| — | `hot_sectors` | generic | LIST | OFF | `hot_sectors` | a sector view; not counted in the top 10 |

hot_sectors ranks 3rd by opens but is a sector view whose heat measured null, so it is skipped when picking the top 10; the 10 ON are the next ten long buy lists.

### Not a lane (7)

`klass = "not_a_lane"`: never dispatched, and `entries` refuses the tag in every mode.

| tab | reason |
|---|---|
| support | a one-ticker tool, not a list |
| holdings | his own positions |
| ema_frames | weekly/monthly chart view, kind n/a |
| news | no tickers |
| winners | a hindsight ledger selected by outcome |
| topping | bearish; the program is long-only |
| vcp | **OFF with Minervini**: it is the SEPA slice, whose lane is `auto_entry` |

`supply` is a legacy alias of `ict`.

### Legacy tags

Existing lanes keep writing their old ledger tags so journal and autopsy history stays joined. `strategy_tags.TAG_TO_SID` maps them, and **every `program_caps` function normalises first** (`strategy_tags.norm`), so the old tags hit the same caps and the same 0.25% sizing as the new ones:

| ledger tag | sid |
|---|---|
| `demand_zone` | `zones` |
| `breakout` | `breaking` |
| `quick_bounce` | `quick_bounce` |
| `catalyst` | `catalysts` |
| `hot_pullback` | `hot_pullback` |
| `zero_dte` | `signals` |

`minervini`, `options_zone` and `manual` are **non-roster**: they keep their own switches and rules.

**Tag fix.** Before this change `entries._strategy_tag` and `journal` coerced `hot_pullback` and `quick_bounce` to `manual`, so their history is journaled as `manual`. `STRATEGIES_ALL` fixes future rows only.

---

## Entry rules

### Every generic (new) lane

A generic lane buys only when all of these hold, in this order (`chart_maps_lanes.run_generic`):

1. The strategy is ON (`program_caps.strategy_on`), the market is open, and the time is before `zone_edge_entry.LAST_ENTRY_ET`.
2. The minute has not been taken by another lane (`program_caps.minute_taken`).
3. The snapshot is fresh (`snapshot_stale`, first reason wins):
   - built today (ET);
   - written at most `SNAPSHOT_MAX_AGE_SEC` ago;
   - the board's own build stamp (`source_as_of`) is known; **unknown fails closed**;
   - the board was built at or after the previous session's close (`prev_session_close`, which reuses `market_hours.gate.closed_reason`, so a Monday holiday means Tuesday uses Friday's close).
   A daily list (bonde, patterns, potus, and amd/keltner's post-close build) therefore trades on the previous close's list; the READY read on it is always the snapshot's own, at most `SNAPSHOT_MAX_AGE_SEC` old.
   **growth is a WEEKLY board** (rebuilt Sunday 09:00 ET by cron), so under this rule it is fresh on Monday only; Tuesday–Friday it reads "stale board (built … before the last close)". Whether a weekly board counts as fresh until its next rebuild is **HIS CALL** (open, 2026-09-27).
4. The strategy's own caps are not full (`program_caps.check(sid, "*")`).
5. Candidates are taken **in served board order**, skipping names that are held or pending, names already attempted today, and names that are not long (no served stop and no demand band).
6. The first remaining candidate is **re-confirmed on the live print**: `bounce_room.api_payload([sym], background=False)` must return coverage `store` or `ondemand` and verdict 🎯 READY (`enterable.READY`); for PLAN adapters the live band must match the snapshot band within `enterable.BAND_MATCH_TOL`. At most `MAX_CONFIRMS_PER_SID` confirms per sid per tick.
7. The stop (`stop_for`), **never invented**:
   - PLAN adapters (`deep_demand`, `ict`, `session`): the tab's served STOP, only when it is below the live print;
   - LIST adapters: the READY read's demand band floor × (1 − `zone_edge_entry.STOP_BUFFER_PCT`/100);
   - no served stop and no band → **no trade**.
8. `entries.enter(sym, stop_price=stop, strategy=sid, allow_earnings=False, reason={…})`. The chokepoint then applies the safety floors, the 10% stop limit, the earnings shield and the program caps.

🎯 READY is `supply_demand/enterable.py` `grade()`. It combines the two standing push gates (`alert_gates.room_gate`: at least `ALERT_MIN_ROOM_PCT` room to the first proven supply; `alert_gates.demand_proximity_gate`: within `ALERT_MAX_ABOVE_DEMAND_PCT` of demand), the floor held (`FLOOR_HELD_STATES`), and the two measured drags. So **every generic lane passes the standing alert gate.** WATCH is never bought.

### The LIST-lane sentence

For every LIST adapter (amd, bonde, growth, patterns, keltner, gnt, ipo, potus, gabbar, undervalue, overnight, earnings, hot_sectors):

> **Buys a 🎯 READY demand reversal on a name from this tab's list, not the tab's own setup.**

The tab chooses *which names*; the entry, stop and gate are the demand-reversal read. A LIST lane's result therefore measures "READY demand reversals on this tab's names", not "this tab's setup". The same sentence is `ROSTER.note` and prints under the row on the Trading page.

**patterns** adds: *"Confirmed patterns are bought only at demand, never on the breakout; most are cup-with-handle bases."* 11 of the 18 confirmed rows on 2026-09-27 were `cup_with_handle`, a Minervini-style base close to VCP. The pattern's own stop is not used: it is often more than 10% away (ARW: stop 187.96 against about 230), which `entries` refuses.

### Per strategy: the list, the filter, the stop

| sid | source of names (the tab's own builder) | kept only when | stop |
|---|---|---|---|
| deep_demand | `chart_maps.board.board(tab="deep_demand")` | READY, and the tile serves BUY and STOP with stop < print | served STOP |
| ict | `board(tab="ict")` | `plan.entry` and `plan.stop` present, `bias == "bullish"`, `state == "entry"`, stop < print, READY | served STOP |
| session | `supply_demand.session_board.cached_or_warm()` | row carries `signal.trade` (never the SMC fallback), READY | served STOP |
| amd, keltner, gabbar | `board(tab=…)` | READY on the served tile read | band floor |
| undervalue, ipo | `board(tab=…)` symbols → `bounce_room.api_payload` | READY | band floor |
| earnings | `board(tab="earnings")`, REACTED group | READY; UPCOMING never | band floor |
| bonde | `sepa.bonde.board(new_days=bonde.NEW_DAYS)` explosive/strong/steady | served `is_new`, READY | band floor |
| growth | `growth.tracker.board()` | READY | band floor |
| patterns | `patterns.scan.latest()` | `status == "confirmed"`, READY | band floor |
| gnt | `traders.feed.board(trader="gnt")` | served `fresh`, READY | band floor |
| potus | `political.api._board` | served `is_new`, READY | band floor |
| overnight | `daytrading.premarket.gappers("aggressive", False)` | `direction == "up"`, READY | band floor |
| hot_sectors | the hottest board's names | READY | band floor |

`board()` is called with `limit = board.LIMIT_MAX` (80, the page's `BOARD_LIMIT`), so the snapshot sees exactly the tiles he sees.

### Existing lanes

They stay the lane for their tabs. They are re-tagged and put under the program's caps, not rebuilt; their own rules and state collections are unchanged.

| sid | lane | its own rules (unchanged) | what the program adds |
|---|---|---|---|
| zones, quick_bounce | `zone_edge_entry.run(sides=("demand",))` | zone gate, `zone_edge_rules`, `MAX_ZONE_ENTRIES_PER_SIDE_PER_DAY`, `SIGNAL_MAX_AGE_SEC`, `LAST_ENTRY_ET` | the shared cheap-skip; `open_cap`; a transient program veto clears the band attempt instead of burning it for the day; `sid`/`tab`/`kind`/`stop_pct` in the reason |
| breaking | `zone_edge_entry.run(sides=("supply",))` | same | same |
| catalysts | `catalyst_entry.run` | `MAX_CATALYST_ENTRIES_PER_DAY`, its alert gates | same four edits |
| hot_pullback | `hot_pullback_entry.run` | `MAX_ENTRIES_PER_DAY`, `MAX_OPEN`, 09:30-10:00 window | the shared cheap-skip; **the standing alert gate** (below); one lane per name |
| signals | `zero_dte_lane.run` | `RISK_PCT_OF_EQUITY`, `PREMIUM_STOP_PCT` (premium at risk is already 0.25% of equity) | OFF while the program is ON unless switched on; check → claim → `record_entry` before submit |
| (options_zone) | `options_lane.run`, runs last | non-roster | open cap, pending check, one per minute; premium risk `min(RISK_PCT_OF_EQUITY, PROGRAM_RISK_PCT)` while the program is ON (HIS CALL #3) |

**The shared cheap-skip.** Before an existing lane writes any state or calls `entries.enter`, it runs `program_caps.check(tag, sym, …)`. A `program-cap:` reason or the minute-taken wait is written to `cm_lane_log` (deduped per ET day) and the lane moves on with no state, no race doc and no ledger row. A sid-level reason (OFF, daily cap, minute taken) stops the loop. So the page shows *why* zones or catalysts did not buy.

**hot_pullback's alert gate** (new, the standing rule that every S/D-type demand lane passes the gate). Before `TE.enter`, `bounce_room.api_payload([sym], background=False)` must return coverage `store` or `ondemand` with `enterable.gates.room_ok` True **and** `prox_ok` True, i.e. at least `ALERT_MIN_ROOM_PCT` room to the first proven supply and within `ALERT_MAX_ABOVE_DEMAND_PCT` of demand. An unreadable read refuses (fail closed). A refusal writes one `cm_lane_log` row (`"alert gate: …"`) and **no** `hot_pullback_skip` ledger row, which would otherwise repeat every minute of the window. This is the gate only, not the full READY; the floor and the drags stay a board read.

**Every existing lane runs every tick whatever its switch says**, because its exits live there. A program OFF gates **entries only**; it never flips a lane's own flag (`zero_dte_lane.run` and `hot_pullback_entry.run` return before managing positions when their own flag is off).

---

## Caps

All live in `trading/program_caps.py` and apply at the chokepoint (`entries.enter` / `_evaluate` for stocks; the two options lanes call them before submitting). Detail: [`trading_engine_inflight_cap.md`](trading_engine_inflight_cap.md).

| cap | constant | value | applies |
|---|---|---|---|
| Risk per stock trade | `PROGRAM_RISK_PCT` | 0.25% of `equity_used` | roster stock sids, program ON; **min-composed** with `risk_rules.position_size`, so the streak and progressive multipliers still bind |
| New buys per strategy per day | `PER_STRATEGY_MAX_ENTRIES_PER_DAY` | 1 | program ON; `cm_lane_caps` may only tighten |
| Open per strategy | `PER_STRATEGY_MAX_OPEN` | 2 | program ON; tighten-only |
| Program open | `PROGRAM_MAX_OPEN` | 15, stocks + options + pending | program ON, paper/sim only. Otherwise `risk_rules.MAX_POSITIONS` (5), untouched |
| Gross | `PROGRAM_MAX_GROSS_PCT` | 100% of `equity_used` (HIS CALL #1) | program ON |
| One new entry per ET minute | `ENTRY_CLOCK_ID` claim | 1 | **every mode, program ON or OFF**; manual exempt |
| One lane per name | check (c) | — | roster tags, every mode |
| In-flight open cap | check (a) | positions ∪ pending buys (spread legs counted) | every mode |

Unchanged underneath: `safety_floor.check` ($2 price, $700M cap), `risk_rules.ABS_MAX_STOP_PCT` (10%), never average down, the earnings shield (`entries.EARNINGS_SHIELD_DAYS`), and the bracket target `risk_rules.profit_target` (at least `MIN_REWARD_RISK`). **Stops and targets rest at the broker as a bracket for every stock.** A tab's served target is journaled, never traded (HIS CALL #4).

**Live is never a program.** `program_caps.enabled` is True only when `cm_program` is true and the broker mode is `paper` or `sim`.

**The dispatcher.** With the program ON, `chart_maps_lanes.run_program` runs every lane in **usage order**. After each slot it peeks at the minute; once another lane has claimed it, the remaining generic slots are skipped (logged once as `program-wait: minute taken`), and the remaining existing lanes still run for their exits but stop at the cheap-skip. Higher usage wins the minute. With the program OFF, `run_program` returns `exit_engine._run_lanes_fixed_order()`, today's lane code verbatim.

**$ will be tiny.** On 2026-09-27 the loss streak was 11, so `size_multiplier` is 0.25 and most trades risk **less** than 0.25% (a 3% stop gives about 0.19%). Judge in R.

---

## The SEPA sell rule runs on every position

Tick step (d1) runs `sell_discipline.evaluate(_distribution_read(sym), last)` on **every held stock, whichever lane bought it** (`exit_engine.tick`). `_distribution_read` is the symbol's row in the latest SEPA scan. Every verdict is an `auto_sell` at market: below the 200-day MA, Stage 4 under the 50-day, a climax, MVP exhaustion, Stage 3 with distribution. He chose AGGRESSIVE on 2026-06-25.

- Breakout-lane buys were sold 1-4 minutes after entry (LNG 1 min, ATI 2 min, SLAB 4 min).
- Of the 269 names on the zones / deep_demand / amd / quick_bounce / gabbar / keltner boards on 2026-09-27, 33 had a row in the latest scan, and **11 of those 33 would be auto-sold on the first tick after entry**, all as "Stage 3 topping". A name with no scan row is never sold by this rule.

So a program lane's result measures **the tab's entry, plus the bracket stop and target, plus the SEPA sell rule**. The journal labels these exits `distribution_exit` ("SEPA distribution sell: …") and the scoreboard counts them per strategy in `exits_by_kind`. Default: keep it (never loosen an exit); HIS CALL #4.

---

## Priors: every lane starts null, inverted or unmeasured

`strategy_tags.PRIORS`, shown as a chip on every row with its source in the tooltip.

| strategy | prior | source |
|---|---|---|
| zones (demand reversal) | reversal baseline 24% win / 75% stop-out; the 🎯 READY read's own replay **no_signal** (base R20 median −1) | `backend/scripts/entry_trigger_measured.json`, `enterable.MEASURED` |
| deep_demand | levels 2/3/4 **MEASURED NULL** | `backend/scripts/deep_levels_measured.json`, `docs/supply_demand/deep_levels_study.md` |
| amd, keltner | **INVERTED** vs placebo (~3,700 names) | `backend/scripts/turning_bullish_amd_study.py`, `backend/scripts/turning_bullish_keltner_study.py`, `docs/supply_demand/turning_bullish.md` |
| bonde | thesis **INVERTED** (2026-09-13) | the board's own `measured` block (`/bonde/board`) |
| growth | arrivals +7.49pp at 63 sessions (CI +0.52..+16.06); no entry, stop or cost model | `backend/scripts/board_growth_measured.json` |
| hot_pullback | **null**, +0.100R (−0.188..+0.405) | `backend/studies/hot_pullback_study.py` |
| breaking | tagged lane −0.70R; **−0.54R (−0.92..−0.10) outside the opening-bell clusters** | the 2026-09-27 Auto-Pilot autopsy (autopsy branch) |
| signals / 0DTE | first tag **inconclusive**: the sign depends on the placebo | the 2026-09-27 Auto-Pilot autopsy |
| ict | **no edge** vs placebo (+0.03R, 6,004 signals) | `backend/ict/backtest.py` |
| hot_sectors | sector heat **null** (−0.57pp) | `backend/studies/sector_heat_study.py` |
| gabbar | OOS 72% recovered, **no placebo** | Gabbar levels backtest 2026-08-31 |
| catalysts, quick_bounce, patterns, gnt, potus, ipo, undervalue, overnight, session, earnings | **UNMEASURED** as entries | — |

With 1 entry a day per strategy, a strategy reaches about 20 closed trades in a month or more. At n = 20 the 95% CI on expectancy is about ±0.5R, so **the realistic early output is the kill rule, not a winner.** Expect losses: the program measures, it does not predict.

---

## The journal

### What changed (the exit fix)

Before: `journal._EXIT_KINDS = ("trade_closed", "flatten", "flatten_all")`, and market exits never write a `trade_closed`. On 2026-09-27 `trade_journal` showed **13 open trades against 4 real positions** (AAT, EMR, IOSP, TGTX); the 9 stale rows (ASX, ATI, CNQ, LNG, MRK, PNTG, PR, SLAB, SM) had all closed through `distribution_exit` or `watchdog_exit`.

Now (`_MARKET_EXIT_KINDS`, `_is_exit_row`):

| ledger row | closes the trade when | exit reason shown |
|---|---|---|
| `watchdog_exit` | `detail.closed is True` | "watchdog stop (market)" |
| `distribution_exit` | `detail.closed is True` | "SEPA distribution sell: …" |
| `hot_pullback_exit` | always | "hot pullback exit: …" |
| `flatten_done` | no earlier exit row for the trade | "position gone (flatten)" |

- **The first such row closes the trade.** Later rows for the same symbol before its next `entry` are retries of the same close and are absorbed, never summed. `qty` on those rows is the position *remaining at that tick*: ASX's 608/608/124/1 would sum to 1,341 shares for a 608-share trade.
- **The price** is the VWAP of the broker's filled sells for that symbol (`journal_exit_fills`, written by `journal.resolve_exit_fills`), taken from `exit_ts − EXIT_FILL_BACK_SEC` to the next entry, capped at the entry qty. When no fill is known yet, it is the tick's last price, **marked approximate** (`price_source "tick_last"`, `approx True`). No price at all → closed but unpriced.
- **Dollars** use the broker-sold qty when fills are known (SLAB: 56 requested, 6 sold), otherwise the entry qty (`realized.qty_basis`).
- `reconcile()` stays broker-free. Fills are backfilled by the 17:00 review and by `python -m trading.lane_review --backfill-fills --since D [--dry]`.

**At deploy the Journal page numbers change**: the 9 stale "open" trades close, several as losses, and the win rate and analytics shift. The autopsy picks up the newly closed losers at up to `autopsy.MAX_PER_RUN` per tick.

### How to read the scoreboard

Per strategy (`lane_review.scoreboard`, counted from the day the program is switched ON, `cm_program_started`):

| field | read it as |
|---|---|
| `n_closed`, `n_open` | closed round-trips / open now |
| `win_pct` [`win_ci`] | win rate with a Wilson 95% CI; never judge on this alone |
| `exp_r` [`exp_r_ci`] | **the number that matters**: mean R per trade, seeded bootstrap 95% CI (`BOOT_SEED`) |
| `total_usd` | dollars, small by design |
| `open_risk_usd` | Σ qty × (entry − placed stop) over open trades, "risk at entry" |
| `n_approx` | exits priced at the tick's last, not a broker fill; shown as "≈ N" |
| `n_unpriced` | closed with no exit price; excluded from exp R, counted here |
| `exits_by_kind` | stop / take_profit / watchdog_exit / **distribution_exit (SEPA sell)** / hot_pullback_exit / flatten / premium_stop / time |
| `small_n` | n below `analytics.MIN_RECORD_N`: the CI is wide, do not act on it |
| `measured` | always False: this is a forward paper measurement |

Options lanes are scored from their own collections: 0DTE R = realized P&L / (fill × 100 × qty × `PREMIUM_STOP_PCT`/100); options_zone R = realized P&L / max loss.

A strategy with many `distribution_exit` rows is measuring the SEPA sell rule more than its own entry. A strategy with many `n_approx` exits is waiting on the fill backfill.

---

## The daily review routine

Full detail: [`trading_lane_review.md`](trading_lane_review.md).

1. **17:00 ET, weekdays** (cron, closed-day gated: `python -m market_hours.gate trading.lane_review`), after the 16:45 autopsy pass. A weekend or holiday writes nothing.
2. It backfills exit fills from the broker (paged `closed_orders_since`, which caps at 500 rows per call), then `journal.reconcile()`. A broker error leaves those exits approximate and the summary says so.
3. It scores every strategy, writes one Rule #9 loser line per losing trade (entry read, band, room, what the autopsy says happened, how it exited), and writes `lane_reviews` for the day.
4. It **proposes**, deterministically, and never applies:
   - **pause** a strategy (`cm_lanes: {sid: false}`) when `n_closed >= KILL_MIN_N` (20) and the exp-R CI upper bound is below 0;
   - a **class proposal** at `CLASS_PROPOSE_MIN` (3) losses of one autopsy class in a strategy: a config change where one exists (e.g. `zone_edge_rules.demand_residents=false` for `chased` on zones), otherwise a code TODO (entry-distance cap, band selection, index filter, stop buffer, time stop, entry width).
5. Each proposal is a card on `/trading?view=strategies`. **Confirm** on a config card applies exactly that change through the same validator as `POST /trading/config` and ledgers before/after (`lane_proposal_confirmed`). Confirm on a code card only adds it to Claude's TODO: nothing in the engine changes. **Dismiss** ledgers `lane_proposal_dismissed`; a dismissed card comes back only when its evidence count grows.
6. A Claude scheduled routine reads `GET /trading/review/latest?format=summary` and brings him the headline, losers and open proposals. The public host is behind oauth2-proxy; `X-User-Email` works only against the local API on the Mac mini, so the routine runs there.

**There is no auto-pause.** A losing strategy keeps trading until he confirms a pause.

---

## Switches

| key | set by | meaning |
|---|---|---|
| `cm_program` | master switch on the page (`POST /trading/config`) | program ON/OFF; the first True stamps `cm_program_started` |
| `cm_lanes` | per-row switch | `{sid: bool}` overrides of `DEFAULT_ON`; null resets |
| `cm_lane_caps` | review Confirm, or config | `{sid: {per_day, max_open}}`, **tighten-only** |

All four keys (`cm_program`, `cm_program_started`, `cm_lanes`, `cm_lane_caps`) must be in the `exit_engine.get_config` whitelist; a key missing there silently does nothing. Turning the master switch or a row ON asks for confirmation; OFF does not.

**What already ships at deploy with the master switch OFF** (HIS CALL #2): the in-flight cap with pending entries and spread legs, one new entry per ET minute across all lanes (manual exempt), one lane per name, the tag fix, hot_pullback's alert gate, and the journal exit fix. Generic lanes do not run until he flips the switch.

---

## Traps

- **Lane flags kill exit management** (zero_dte, hot_pullback). The program never flips a lane flag; OFF gates entries only.
- **Legacy tags must be normalised everywhere.** A function that used the raw tag would silently skip the 1/day cap and the 0.25% sizing for zones, breaking and catalysts.
- **The minute bucket has a residue.** A tick that runs past its minute can still claim its own older minute before the next tick claims the new one, allowing two entries seconds apart across a boundary. There is no tick lock; the `$lt` claim only blocks claiming backwards.
- **quick_bounce competes inside the zones slot** (the same zone-edge run). It can take the minute ahead of deep_demand when zones has no candidate. Documented, not fixed.
- **One lane per name has a residue.** A non-roster Minervini pyramid into a name hot_pullback holds, followed by hot_pullback's `close_position`, sells both. Minervini `auto_entry` is OFF now.
- **bonde's `scan_ts` was None on the weekend probe.** If a board has no build stamp on a weekday, that lane never trades ("stale board (build time unknown)") until the stamp is wired.
- **Api CPU in RTH.** The snapshot pass costs about 10 × 1.3-3.6 s every 5 min in the api process that serves his pages. Watch `built_ms`.
- **`positions()` mixes stocks and options.** Count by symbol/OCC strings, never by `asset_class`.
- **The crontab is host-mounted.** A deploy does not ship the two snapshot lines or the 17:00 review line; they are installed and checked in the cron container.
- **The container runs origin/main.** Verify branch code on the branch API (`:8001`), never through a `/trading/journal*` route (those call `reconcile()`, which writes).

---

## HIS CALL (open, defaults in bold)

His three answers of 2026-09-27 are above. These eight stay open for him; each ships at its default until he says otherwise.

| # | question | default |
|---|---|---|
| 1 | Caps: 15 paper-only; how a 2-leg spread counts; a gross cap | **15 paper-only (live stays 5); a spread counts 2; gross cap ≤ 100% of `equity_used`: YES** |
| 2 | What changes at deploy with the switch OFF | **YES to all**: in-flight cap, one entry per minute (manual exempt), one lane per name, tag fix, hot_pullback alert gate, journal exit fix |
| 3 | Sizing | **min-compose 0.25% with the streak and progressive multipliers; options_zone drops to 0.25% premium while the program is ON** (alternative: options_zone OFF); 0DTE is already 0.25% |
| 4 | Exits | **keep `risk_rules.profit_target` for every strategy (served target journaled only); keep the SEPA sell rule on every position; the review counts it** (alternative: SEPA sells only on `minervini` / manual) |
| 5 | The ON set | **his top 10 stands** (hot_sectors not counted; patterns ON as demand-only; signals/0DTE OFF once ON; breaking, hot_pullback and wide-rule zones ON against autopsy #5, #7, #4) |
| 6 | The entry read | **🎯 READY, not WATCH; LIST lanes buy a READY demand reversal on the tab's names; arrivals only via served flags (bonde/potus `is_new`, gnt `fresh`, overnight up); patterns `confirmed` only, band-floor stop** |
| 7 | Snapshot timing | **every 5 min 09:30-15:45; READY read ≤ 600 s; board built at or after the previous close; no build stamp = no trade** |
| 8 | Review and page | **kill proposal at n ≥ 20 with exp-R CI upper < 0; class proposal at ≥ 3 same-class losses; 17:00 ET; scoreboard from the day he switches ON; broker VWAP else tick last marked approximate; 🗺️ Chart Maps second on the Trading page** |

## Fix round 2026-09-27 (critic findings)

- **Switch vs buying now.** `GET /trading/strategies` rows serve `enabled` = the strategy's own switch (`program_caps.switch_on`: the `cm_lanes` override, else DEFAULT_ON), whatever the program's state, so the page shows the ON set that starts buying when the program is turned on. A new `buying_now` field (`program_caps.strategy_on`) says what the engine lets buy right now: with the program OFF the existing lanes run on their own switches and generic lanes never buy. The page prints a note when the two differ.
- **Not-a-lane tags are refused at the buy path.** `entries.enter(strategy=<vcp|topping|…>)` raises `program-cap: <sid> is not a lane (never buys)` in every mode. An unknown tag is still journaled as `manual`, but it takes the one-entry-per-minute slot; only an explicit `manual` (or no tag) is exempt.
- **A stale review card cannot loosen a zone rule.** Confirming a `zone_edge_rules` card keeps the stricter `min_touches` of the current config and the card (a card made at 1 → 2 leaves a later 3 at 3).
- **growth is weekly** (see step 3 above) — HIS CALL, unchanged in code.
