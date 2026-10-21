# Auto-Pilot 🚩 Gajjala lane (paper) — his A+ ENTRY alerts, GG's playbook rules (v2)

Ajay 2026-10-20 (~09:4x ET), verbatim:

*"in the autopilot can you stop rest of the strategies and only use the Gajjalas strategies please."*

Ajay 2026-10-21 (on the tab's "skipped — house safety floors …" rows), verbatim:

*"Is the 700 M floor by Gajjala?"* / *"Follow full Gajjala and he doesnt care exactly about this.. Go through his rules
from play book and implement them exactly"*

Code: `backend/trading/gajjala_entry.py`. Engine seam: `trading/exit_engine.py` tick step **(n)**, every minute in
RTH, after the 🔥 lane (m) and before the journal (g). Tab: `/trading?view=gajjala` (GET `/trading/gajjala`, admin).
**OWNER RULES — GG's, no book, no Minervini cites.** Paper only: the lane refuses a live broker. Not advice.
Spec: BUILD_SPEC19 (v2, 2026-10-21); v1 was BUILD_SPEC17 (2026-10-20).

## READ THIS FIRST

- **UNMEASURED.** The 2026-10-14 study of his five setups read no edge (`docs/gajjala/study_2026_10_13.md`). This lane
  trades them on paper so the fills can be read — not because they are measured. Nothing here quotes an edge or a win
  rate.
- **The rule source is GG's**: `backend/chart_maps/gajjala/verified_rules.json` (`VR i.j` = `topics[i].verified[j]`) and
  the playbook's quoted lines. Every number in the code is his (`# GG <cite>`), mine (`# MINE — HIS CALL #n`) or a
  `None` placeholder that waits for his number (`# awaiting your number — <question>`); a placeholder keeps the lane
  running with that rule off.
- The $2 / $700M floors are the **house** floors (Ajay 2026-09-11, `trading/safety_floor.py`), not GG's: the switch
  `gajjala_floors` now **defaults OFF** (HIS CALL #0 decided 2026-10-21; the live config was flipped false at 11:05 ET).
- The other lanes stay off live (`auto_entry`, `zone_edge_entry`, `catalyst_entry`, `options_entry`, `zero_dte_entry`,
  `hot_pullback_entry` false; `armed` true). This lane is ON by default (`gajjala_entry`, code default true).
- The three-lane rule (never add a lane without his call) is satisfied by his 2026-10-20 ask.
- The cron container runs the tick: the lane ships only when `cron` is redeployed with `api` and `frontend`.

## GG's rules, as built

| Rule | GG (verified_rules.json) | Built as |
|---|---|---|
| Universe | VR 0.8 long only, stocks, intraday; VR 0.5 / 0.1 "the lower the float the better", no cutoff, $0.10 scanner floor; no cap floor | today's pushed live 🚩 A+ (all five setups); no floor, no cap gate while `gajjala_floors` is OFF |
| Catalyst / earnings | VR 0.7 "a must but never researched; 100% technical" — nothing on earnings | `allow_earnings=True`: no earnings shield (D2) |
| Window | VR 1.4 no trades in the first 15 minutes; VR 1.5 limit orders only outside regular hours | orders 09:45 → regular close − 30 min (15:30; 12:30 half day); RTH only (D12) |
| Entry | VR 11.0 "right at the break"; sometimes waits for the bar close · VR 11.1 market orders in regular hours | a **market** order (day) at first sight when the last trade ≥ the trigger; under it the doc **waits** (D7). Ajay's A+ needs the entry bar to CLOSE through the trigger, so the lane always sees the break after the close |
| Stop | VR 11.2 "low of the prior bar as the stop loss"; "a breakout back into its range = out" | the alert's stop rounded DOWN on the grid, the OTO order's stop leg (a market stop at the broker from the fill); the stop printing before the trigger trades = `never_triggered` |
| Size | VR 11.7 he STARTS at 0.25%; S8 56:27 "half size, then add" | full = ⌊equity × 0.25% × risk_mult ÷ (last − stop)⌋, capped by 10% of equity and the cash; the ENTRY is half (⌊full/2⌋, min 1) |
| Breakeven + add | VR 11.3 "breakeven once it moves … then I added half, double the size with zero risk" (S8 39:03) | the first CLOSED 5-minute bar ≥ 3 bars after the entry bar that closes ABOVE the fill → every stop of the name moves to the fill, the second half is bought at market with its stop at the same fill (D8a). The add = min(full − the first fill, full − held) — never a refill of shares sold since — and none while the drawdown half-off is due or done |
| Partial | VR 11.4 "peel off 1/3 or half … when strong" | `GG_PARTIAL_FRAC` 0.5; `GG_PARTIAL_R` = None → **off** until he gives the R |
| Trail | VR 11.4 "trail the remaining along the 9 EMA" (the 21 on Kiss & Fly "maybe") | after breakeven: out at market on a closed bar whose CLOSE is under the 9 EMA (`orderflow.signals.EMA_FAST`, the pass's `_masked_ema`); Kiss & Fly 21 = `GG_TRAIL_EMA_KF` None → 9 |
| Target | VR 11.6 no fixed targets | no take-profit leg, ever (Alpaca OTO) |
| Losers | S8 46:47 "$2,000 … next trade I cut to $1,000 … then $500" | `risk_mult` halves after a losing lane trade; back to 1 after a win (HIS CALL #18) |
| Drawdown | VR 11.7 "−10% / −15% drawdown → the next five trades ≤ −5% together"; VR 11.4 "in drawdowns take half off immediately" | at 10% under the equity peak the next 5 lane trades may risk 5% of equity together; on the turn into drawdown half of every open lane position is sold at market, once (HIS CALL #19) |
| Re-entry | VR 10.6 no re-entry on the next bar, "at least like couple of bars" | an alert on a name stopped out within the last 2 closed 5-minute bars is skipped `cooldown` |
| Halts | VR 10.1 "when it's clean, when it's calmer, then I enter" | `GG_HALT_CALM_MIN` None → **off**; today's halts are recorded on the row and shown in the fate text |
| Overnight | VR 0.8 no overnight holds in low floats | flat at 15:55 ET (regular close − 5) through `exit_engine.flatten` |
| Not his | VR 11.8 / 11.9 "exit within five minutes", "close below the 21 EMA" (Business Insider, Dollar Wisdom) | not built |

## Entry / management, step by step

1. Each tick the live last = `sepa.prices` last trade, else its price (never `prev_day_close`), else the broker's.
2. Last ≤ the stop → `never_triggered` (unfilled, final). Last under the trigger → `waiting` (re-read every tick until
   the cut-off; at the cut-off `never_triggered`). Last > trigger + `GAJJALA_MISSED_R` × R → `missed` (HIS CALL #9).
3. Stop SL = the alert's stop rounded DOWN; a grid shift over `GAJJALA_MAX_ROUND_R_PCT` 10% of R → `rounding`; last − SL
   under $0.01 → `broker_gap` (Alpaca refuses the stop leg).
4. Size as in the table; 0 shares → `size`. Then `held` (one position per name), `cap_open` (`GAJJALA_MAX_OPEN` 3, HIS
   CALL #17), `cooldown`, `halt` (off), `floor` (only while `gajjala_floors` is ON), disarmed → `dry_run`.
5. ONE market OTO order through `entries.enter` (the one chokepoint): `limit_price=None`, `stop_price=SL`,
   `sizing={qty: half, price: last, full_qty, …}`, `allow_earnings=True`, `ceiling="gg"`, `order_class="oto"`,
   `tif="day"`, `order_intent="gg-" + setup`. Not filled in `GAJJALA_FILL_WAIT_SEC` 180 s → cancelled, `unfilled`.
6. Open: every tick on **closed** 5-minute bars only (`bars.closed_only`; the bars come from the pass's own loader
   `bars.frames_for`, once per name per 5-minute bucket): breakeven + add (D8a); after it the 9 EMA trail (D8c); the
   partial once `GG_PARTIAL_R` is set (D8b). A failed stop replace keeps the old stop and adds nothing; it is retried
   next tick (`be_failed_n`, one `gajjala_be_failed` ledger row). The add goes through `entries.enter` too, so
   never-average-down refuses it when the tape is back under the average (the stop move stands).
7. A partial or the drawdown half-off: cancel the stop(s) → `close_position(sym, qty)` → a stop for the rest at the
   doc's stop (`exit_engine.lane_stop`): tick N cancels the stop(s); once none is pending_cancel, a later tick sells at
   market and re-stops the rest; adopt-and-protect skips the name in between. The gap is recorded as
   `{partial|dd_half}_naked_ms`. A refused
   sell restores a stop for every uncovered share. A lane position always has its stop: a shortfall of stop shares is
   re-stopped at the doc's stop; a lower house adopt-and-protect stop is raised to it.
8. Flat at 15:55 ET; a position carried past its date is flattened at the next tick; a flatten that neither closed
   nor queued keeps the doc open and retries every tick.

Worked examples (equity 100,000, cash 100,000, risk_mult 1):

| Name | trigger / stop | last | SL | full | entry (half) | risk on the half |
|---|---|---|---|---|---|---|
| SAIQ | 4.46 / 4.31 | 4.48 | 4.31 | 1,470 (the risk binds: 250 ÷ 0.17) | 735 | $124.95 |
| SAIQ-tight | 4.46 / 4.45 | 4.46 | 4.45 | 2,242 (the 10% notional cap) | 1,121 | — |
| DRMA | 0.8744 / 0.861 | 0.879 | 0.861 | 11,376 (the 10% notional cap) | 5,688 | $102.38 |
| HODO | 0.0753 / 0.0709 | 0.0755 | 0.0709 | — | — | `broker_gap`: last − SL = 0.0046 < $0.01 |

Exits recorded on the lane doc: `stop`, `trail`, `flatten` (15:55), `owner` (the tab's Close), `carried`; v1 docs
keep `target`. P&L = every filled sell since the fill (the partial, the stop legs, the trail / flatten) against the
average cost of the entry and the add; R = P&L ÷ (the first half's qty × (trigger − stop)), which equals
(exit − fill) ÷ R for one entry and one exit.

## Exemptions (strategy-gated)

- `entries._evaluate(ceiling="gg")` turns the p.312 five-position block into a warning — accepted only from a strategy
  in `FLOOR_WAIVER_STRATEGIES` ("gajjala"); any other strategy is refused (D3).
- `allow_earnings=True` is passed by this lane only; `zone_edge_entry` still passes `allow_earnings=False` (D2).
- `exit_engine.tick` (d): the SEPA distribution exit / alert step (d1) and the p.308 3R breakeven ratchet skip every
  symbol with a lane doc in `ordered` / `open` / `closing` (`GAJJALA_LANE_LIVE_STATES`, D9). The watchdog and
  adopt-and-protect still run, with one exception (fixed 2026-10-21, verifier): adopt-and-protect skips a lane name
  whose open doc is mid part-sell (`dd_half_state` / `partial_state` "cancelling", `gajjala_entry.part_sell_symbols`),
  the way it skips a flatten-queue name. The lane runs as tick step (n), after adopt-and-protect; a house stop placed
  between the lane's cancel and its sell re-held the shares, the lane cancelled it again every tick and the half-off
  never ran. The lane re-stops those shares itself after the sell. A closed or skipped lane doc exempts nothing.

## Floors (HIS CALL #0 — decided OFF 2026-10-21)

`gajjala_floors` OFF (default): the house floors are not checked for this lane; their two blocks ride as warnings on
the lane doc and on the entry ledger row (`overrides.floor_blocks_waived`). ON (his switch) brings them back exactly as
v1 (`floor` skips, counted on the tab). Flip from the tab, which sends `POST /trading/config {"gajjala_floors": true}`
(`false` turns them back off) — the line the tab serves as `floors_flip`.

## Engine seams

- `exit_engine.get_config`: `gajjala_entry` (default true), `gajjala_floors` (default **false** since 2026-10-21),
  `last_gajjala_disabled_day`. POST `/trading/config` takes the lane flags strictly (null → the code default:
  `gajjala_entry` / `hot_pullback_entry` true, `gajjala_floors` stored null = off; not a boolean → 400).
- Tick step (n): `summary["gajjala_lane"] = gajjala_entry.run(broker=broker, cfg=get_config())`, fenced like (m).
  `/trading/status` carries `gajjala_lane` = the tab's `status` block.
- State: Mongo `gajjala_lane`, one doc per alert (`_id` = the alert `_id`, `insert_one`; a duplicate key = already
  claimed); every state change is conditional on the state it leaves, and the breakeven / partial / half-off claims
  are conditional on their own `*_state` field (overlapping ticks act once). `gajjala_lane_state` (`_id` "state"):
  `risk_mult`, `equity_peak`, `in_drawdown`, `dd_window {trades, risk_used_pct}`.
- Broker (F5, both `broker_alpaca` and `broker_sim`): `submit_bracket(take_profit_price=None)` → no take-profit, order
  class `oto`; `close_position(symbol, qty=None)` (Alpaca `?qty=N`, the sim sells N; more than held is refused).
  `exit_engine.lane_stop(symbol, qty, stop_price, reason, protective_disarmed=False)` places the lane's resubmitted
  stop (armed only; `protective_disarmed=True` is HIS CALL #23's one disarmed sell stop, its `lane_stop` row noted).
- `entries.enter(..., ceiling=, order_class=)`: an OTO lane plan carries no target and may be a market entry
  (`sizing["price"]` = the planning price); the default bracket lane plan and the book path are unchanged.
- Ledger kinds: `gajjala_entry`, `gajjala_skip`, `gajjala_cancel`, `gajjala_exit`, `gajjala_disabled`,
  `gajjala_breakeven`, `gajjala_be_failed`, `gajjala_add`, `gajjala_partial`, `gajjala_restop_disarmed`, and the
  engine's `lane_stop`. Disarmed: `dry_run` on the lane doc — no order, no real ledger row (the drawdown-on row is
  `dry_run` too), no cancel, no management. One exception (HIS CALL #23, 2026-10-21): a doc whose part-sell cancel
  went out on an armed tick (`*_state` "cancelling") and the engine is then disarmed — the shares have no stop. The
  disarmed tick places ONE protective SELL stop at the doc's stop for every share without one (none while a cancel is
  still `pending_cancel`; none once they are covered) and writes a real `gajjala_restop_disarmed` row
  (`run()["restopped"]`). Never a buy, never a sell at market; the part-sell waits for an armed tick, which cancels
  that stop again and then sells. It also runs in the flatten window (from 15:55 ET; fixed 2026-10-21, verifier
  round 2): a disarmed flatten is a dry run, so a cancel at 15:54 followed by a disarm gets the same one stop through
  the close. Not covered: the lane switched OFF and disarmed together (the lane does not run).
- Served `status.rules` (D14, printed verbatim by the tab): `entry_text`, `stop_text`, `size_text`, `manage_text`,
  `risk_text`, `exempt_text`, `not_built[]`, `awaiting[] {key, question}` (only the placeholders still None).

## Awaiting your number (the rule is off while None)

- `GG_PARTIAL_R` — "peel off 1/3 or half … when strong": at how many R above the entry?
- `GG_TRAIL_EMA_KF` — 9 or 21 on Kiss & Fly ("the 21 on Kiss & Fly maybe")?
- `GG_HALT_CALM_MIN` — "when it's clean, when it's calmer, then I enter": minutes after the last halt resumed?
- `GG_CUSHION_DOUBLE_PCT` — the account cushion (% above the start of the month?) at which an A+ gets double size?
  A placeholder only: nothing reads it until the cushion's basis is his.

## Not built (Playbook text only)

Base counting (3rd base climax, 4th out); psychological $1 / $5 / $10 levels; "exit before the stop on hesitation";
mental stops; monthly risk re-basing.

## Differences from the 🏁 grader

The lane trades the alerts the 🏁 Track record grades, but it is not the same trade. The grader is untouched and still
grades **+1R before the stop** at max(trigger, the next minute's open) — a measurement, not the lane's exit.

1. The lane has no target: breakeven + add, then the 9 EMA trail; the grader wins at fill + 1R.
2. The lane's fill is a market order at the tick that first sees the last at or over the trigger.
3. The stop printing before the lane's order is final (`never_triggered`); the grader still fills on a later minute
   whose high reaches the trigger.
4. The lane is flat at 15:55 ET (regular close − 5); the grader marks to 16:00.
5. The lane's size moves (half then add; risk_mult); the grader counts alerts, not dollars.

## HIS CALL (renumbered 2026-10-21)

- **#0** Floors — decided OFF (Ajay 2026-10-21: "he doesnt care exactly about this"). ON stays his switch.
- **#1** Entry — decided: market at the break (VR 11.1). The v1 0.5% chase limit is gone.
- **#2 / #16** After hours — GG trades the last two hours and holds into after-hours squeezes with limit orders and
  less size (VR 1.5 / 1.7); the lane is flat at 15:55 ET and never trades the 16:00–20:00 pushes (Alpaca paper takes no
  market orders after 16:00). Mine, open.
- **#3** Stale line — removed (it was mine).
- **#4** Size basis — account equity (≤ 10% notional), not `equity_cap`. Mine, open.
- **#5** Streak governor — n/a: GG's own loss halving replaces it.
- **#6** SEPA distribution exits on lane names — decided by D9 (exempt).
- **#7** The p.312 ceiling — decided by D3 (waived for this lane).
- **#8** Thin-R refusal — removed (GG: tight risk-reward entries always).
- **#9** "Missed" bound = trigger + 1R at the tick. Mine, open.
- **#10** One position per name. Mine, open.
- **#11** Day cap — removed (GG has none; his only cap is the drawdown rule).
- **#12** Tab placement right after Dashboard; 🚩 first in the journal table.
- **#13** Switched OFF stops NEW entries (and the add) only; what the lane holds is still managed (fill wait, cut-off,
  stop moves, the trail, 15:55).
- **#14** Target — n/a (no target).
- **#15** The breakeven trigger = 3 closed bars after the entry bar + a close above the fill (my reading of "once it
  moves"; GG gave "give it 15 minutes, three bars").
- **#17** `GAJJALA_MAX_OPEN` 3. Mine, open.
- **#18** risk_mult back to 1 after a winning trade (my reading of "winning → bigger size"). Open: any loss halves it
  (a breakeven stop a cent under the fill too) and only a win resets it, so once the size is under one share the lane
  is locked — the `size` skip says so and names risk_mult. A floor on risk_mult, or counting only losses beyond a
  scratch, is yours.
- **#19** The drawdown half-off fires once on the turn into drawdown; a new 5-trade window opens while the account is
  still in drawdown after one is spent (my reading). The breakeven add is refused while the half-off is due or done.
- **#20** `GAJJALA_FILL_WAIT_SEC` 180 s — an order not filled by then is cancelled, no retry. Mine, open.
- **#21** `GAJJALA_MAX_ROUND_R_PCT` 10 — the broker grid may move the stop by at most 10% of R (else `rounding`). Mine,
  open.
- **#22** `GAJJALA_ENTRY_CUTOFF_BEFORE_CLOSE_MIN` 30 — last order 15:30 ET (12:30 half day), unfilled cancelled. Mine,
  open.
- **#23** Disarmed mid part-sell (the lead's call, 2026-10-21): while a doc is "cancelling" and the engine is
  disarmed, ONE protective SELL stop may be re-submitted for every unprotected share (never a buy, never a sell at
  market), ledger row `gajjala_restop_disarmed`; the part-sell itself waits for an armed tick. Before and after
  the 15:55 flatten time alike (the disarmed flatten is a dry run). The only order a disarmed engine places. Yours
  to keep or reverse.

## Tests

```bash
docker run --rm --network none --name cheetah-tmp-pytest-gglane2-a -v /Users/ajay/clinet-test/wt-gglane2:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_lane.py tests/test_gajjala_lane_gg_rules.py tests/test_entries_lane_plan.py tests/test_broker_price_precision.py tests/test_trading_contracts.py
```

`test_gajjala_lane.py` (v1's lane contract with the v2 pins moved in place: market OTO, half of 0.25%, no stale /
thin-R / dead / day cap, floors default OFF, earnings waived, the served `rules`), `test_gajjala_lane_gg_rules.py`
(every GG rule above with its NEGATIVE, the live-bar guard, the strategy-gated exemptions, the F5 broker changes in
both brokers, the grader's +1R untouched). Mutations proved on scratch copies (2026-10-21, 11 of 11 killed): the live
bar read, the D9 skips dropped / widened, the p.312 waiver not strategy-gated, breakeven after 2 bars or on a close at
the fill, the earnings shield kept, the trail before breakeven, the add past full_qty, floors default ON.

## Known limits (v2)

- The OTO legs are `day`: a 15:55 flatten that keeps failing leaves a position without broker legs overnight until the
  next tick's carried flatten / adopt-and-protect.
- Two stop legs after the add (one per half), both at the first fill; a resubmitted stop after a partial is one GTC
  stop for the rest.
- Alpaca: the shares under a working sell stop are not available, and a cancel is asynchronous (`pending_cancel` keeps
  them held). A partial / half-off takes two ticks (fixed 2026-10-21): tick N cancels the stop(s); tick N+1, once no
  stop is pending_cancel, sells at market and re-stops the rest. A stop is never resubmitted while a cancel is pending;
  the shares are without a stop for one tick (`*_naked_ms`). A refused sell restores the stop for every share.
  Adopt-and-protect skips the name in between (2026-10-21, verifier). A disarm in between → HIS CALL #23's one
  protective stop, in the 15:55 flatten window too; `*_naked_ms` then still counts from the first cancel (it
  includes the time under that stop). Still uncovered: the lane switched OFF and disarmed together.
- Same-day round trips need paper equity ≥ $25k (PDT) — not probed.
- The 🚩 bars are read once per name per 5-minute bucket from Massive (the pass's loader); a provider miss = no
  management that tick (the hard stop stands).

UNMEASURED — his setup, not a buy signal. Paper only. Not advice.
