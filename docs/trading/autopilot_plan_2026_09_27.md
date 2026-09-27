# Auto-Pilot: where the money went, and the plan (PLANNER SPEC, rev 2, 2026-09-27)

Everything in this document is a proposal for Ajay to decide. Nothing here is enabled, flipped or ordered.
Worktree `/Users/ajay/clinet-test/wt-autopsy`, branch `feat/autopilot-autopsy-2026-09-27`.
Rev 2 applies the verifier's 11 findings; the changelog is §12. Rev 1 is kept at `scratchpad/plan_rev/autopilot_autopsy_plan.rev1.md`.
Template map: 0 ask = §0 · 1 facts = §2, §3, §7 · 2 decision + alternatives = §1, §4, §8 · 3 design = §5 · 4 work packages = §9 · 5 verification = §10 · 6 risks = §11 · 7 HIS CALL = §6.

**Source tags. Every number carries one.**
- **[AJ:key]** `backend/scripts/autopilot_autopsy_2026_09_27_measured.json`, produced by `backend/scripts/autopilot_autopsy_2026_09_27.py`. This is broker-fill truth and reconciles to the account to $0.00 (verifier re-ran it: 0 key differences).
- **[SJ:key]** the scratchpad file `spy/result.json`, produced by `backend/scripts/autopilot_autopsy_spy_options_feasibility.py`. WP-B moves it into the repo. **[SM]** is its memo, `docs/trading/autopilot_spy_options_feasibility_2026_09_27.md`, and holds the broker facts with their URLs.
- **[PA-CI]** planner arithmetic over `[AJ].trades[]` plus a read-only `trade_ledger` probe of entry SEND order, with CIs: scratch script `scratchpad/plan_rev/pa_ci.py` (output `pa_ci.out`; Wilson for rates, seeded bootstrap seed 20260927, B = 5,000, trade-level; day-clustered where shown). **WP-A must re-emit every [PA-CI] number from a repo script before it is shown to Ajay.**
- **[LIVE]** read-only probe on 2026-09-27 of `exit_engine.get_config()`, `trade_ledger`, `options_positions` and `price_cache`. No writes, no keys.
- **[ST:script]** a prior study together with its script.
- Do NOT quote the engine-map `journal.summary` table (for example "minervini −$2,643"). It covers only the post-reset journal, not broker truth.
- **Order matters.** A cap decides at SEND time. Every cap counterfactual below uses the ledger send order (`trade_ledger`, `kind == "entry"`, non-dry, sorted by `epoch`), never the fill order.

## 0. The ask (verbatim, Ajay 2026-09-27)
"We are losing a lot of money in autopilot reasearch and make to understand the where we are losing money and why and create a better plan to make money and use our data logic in autopilot please.. not sure whats missing but find ways to make it better. Also try and do SPY options buying please? in the auto pilot daily, high frequency trades with monitoring min to min to make sure it sell on time? I would like to execute atleasst 5 trades if possible on SPY. based on the demand entries with a minimum of at least one trade based on volatility of the market."

## 1. VERDICT (3 lines)
1. **Paper account: −$11,061 (−11.06%) since 06-12** [AJ:account.total_change]. **−$12,732 came from 14 stock entries on two opening bells**: 9 on 09-09 sent within 61 seconds, and 5 on 07-06 [AJ]. The other 21 stock trades made +$2,309, but **two winners are +$1,864 of it** (PNTG +1,196, IRDM +669); their mean is **flat: R −0.02 (−0.36..+0.35)** [PA-CI].
2. By lane ($): Minervini **−5,094**, breakout **−4,694**, demand **−1,473**, 0DTE −513, options_zone −325, pre-tag zone_edge +838 [AJ:tables."lane (all)"].
3. **WHY: on those two days the engine broke its own written caps.** The position cap ignores in-flight orders (a1 would have refused **8 entries, −$7,259**), and paper lifts Minervini's live 2-a-day cap (**4 entries, −$3,060**; the two overlap) [PA-CI]. That is **n = 2 bad days**, so the fixes are rule enforcement and a concentration limit, **not a measured gain**. And no lane shows an edge on the other days either: every lane trades a signal that is unmeasured or measured null, so none can be expected to make money yet.

## 2. The loss table (sources inline)

| where | n | win % (95% CI) | exp R (95% CI) | total $ | source |
|---|---|---|---|---|---|
| **Account** equity $88,938.60 (from $100k) | — | — | — | **−11,061.40** | AJ:account |
| All closed round-trips | 76 | 27.6 (18.8–38.6) | −0.18 (−0.35..−0.01) | −11,260.91 | AJ:overall.all |
| Stocks | 35 | 28.6 (16.3–45.1) | −0.35 (−0.61..−0.07) | −10,422.91 | AJ:overall.stocks |
| Options | 41 | 26.8 (15.7–41.9) | −0.04 (−0.22..+0.17) | −838 | AJ:overall.options |
| **Cluster 2026-09-09** (9 entries sent 09:30:03–09:31:04) | 9 | 0 | −0.97 (−1.25..−0.71) | **−8,947** | AJ:tables."entry ET day (stocks)"; ledger send times [LIVE] |
| **Cluster 2026-07-06** (5 entries sent 09:31:14–09:32:22) | 5 | 0 | −0.61 (−1.19..−0.10) | **−3,785** | same |
| Entries a1 would have refused, **send order** (positions() counts stocks + options: 2 open at the first send on both days) | 8 | 0 (0–32.4) | −1.01 (−1.39..−0.60) | **−7,259.12** | PA-CI. n = 2 days: the CI is not an EV estimate |
| same, stocks-only count (1 open on 09-09; IBKR and CNQ sent in the same second) | 7 | 0 (0–35.4) | — | −6,487.51 .. −6,939.73 | PA-CI |
| Stock entries filled while > `MAX_POSITIONS` were open (**fill order, descriptive only**) | 7 | 0 (0–35.4) | −1.09 (−1.30..−0.93) | −7,859 | AJ:tables."concurrent open stock positions…" |
| Minervini entries past the LIVE 2/day cap, **send order** (LAMR, UFPT, EIX on 07-06; SABR on 09-09) | 4 | 0 (0–49.0) | −0.68 (−1.30..−0.16) | **−3,059.70** | PA-CI; overlaps a1 on UFPT, EIX |
| a1 + b1 together, send order | 9 | 0 (0–29.9) | — | −7,912.66 .. −8,364.88 (IBKR/CNQ tie) | PA-CI |
| Stock trades on every other day | 21 (11 days) | 47.6 (28.3–67.6) | **−0.02 (−0.36..+0.35)**; day-clustered (−0.40..+0.34) | +2,309.36 | PA-CI |
| same, without PNTG and IRDM | 19 | 42.1 (23.1–63.7) | −0.09 (−0.45..+0.33) | +444.92 | PA-CI |
| Stock first-30-min entries, outside the two cluster days | 14 (6 days) | 64.3 (38.8–83.7) | +0.24 (−0.18..+0.67) | +1,714.35 | PA-CI |
| Other fan-out days (fill times): 09-04, 4 fills in 36 s / 09-08, 4 fills in 3 min 21 s | 4 / 4 | — | — | **+837.90** / −6.98 | PA-CI |

| lane | n | win % (CI) | exp R (CI) | total $ | outside the two clusters [PA-CI] | entry signal evidence |
|---|---|---|---|---|---|---|
| minervini (`auto_entry.py`) | 16 | 31.2 (14.2–55.6) | −0.21 (−0.60..+0.20) | −5,094 | n=8, 5 wins, +$2,014; R +0.25 (−0.29..+0.78) | UNMEASURED (no placebo) |
| breakout (`zone_edge_entry`, supply side) | 13 | 7.7 (1.4–33.3) | **−0.70 (−1.04..−0.32)** | −4,694 | n=9 (4 days), 1 win, −$542; **R −0.54 (−0.92..−0.10)** | ENTERABLE/entry-trigger **no_signal** [ST:entry_trigger_study.py] |
| all zone breakouts incl. 4 pre-tag (`zone:breakout/broke`) | 17 | — | −0.39 (−0.78..+0.04) | −3,856 | n=13, +$296; R −0.18 (−0.62..+0.29) | same |
| demand_zone | 2 | 0 | −1.09 | −1,473 | 0 (both on 09-09, both tier `in`, non-arrival) [LIVE] | same-day demand = coin flip; reversal baseline 24% win / 75% stop [ST:bounce_quality_study.py] |
| zero_dte (`zero_dte_lane.py`) | 31 | 25.8 (13.7–43.2) | −0.03 (−0.27..+0.23) | −513 | n/a | Signal Lab first tag **inconclusive: the sign depends on the placebo**. +0.233R (−0.018..+0.483); vs uniform placebo **+0.239 (+0.009..+0.466)**; vs ±15-bar placebo **−0.170 (−0.333..−0.006)**. SPY only, stock R, 123 sessions; both 95% CIs end within 0.01R of zero, so neither survives the 99% rule. Every tag: −0.015R (−0.086..+0.059), 62.3% stop-out [SJ:part_B] |
| options_zone (`options_lane.py`) | 10 | 30.0 (10.8–60.3) | −0.05 (−0.21..+0.14) | −325 | n/a | same zone touch as demand |
| catalyst / hot_pullback | 0 fills | — | — | 0 | — | hot pullback **null** +0.100R (−0.188..+0.405) [ST:studies/hot_pullback_study.py] |

## 3. Root causes

### CONFIRMED (with data)

| # | cause | evidence (file:line / data) | $ impact |
|---|---|---|---|
| C1 | **The position cap ignores in-flight orders.** `_evaluate` counts `len(broker.positions())` only, so an entry order that has been sent but not yet filled is invisible | `trading/entries.py:167-176`; peak of 10 concurrent against `risk_rules.MAX_POSITIONS = 5` (`risk_rules.py:76`) [AJ:execution.max_concurrent_stock_positions] | a1 in send order: **8 entries, −$7,259** [PA-CI]. ASX (the biggest loser) filled 2nd but was sent 7th, so only a send-order count catches it |
| C2 | **Paper lifts the live Minervini guardrails.** `_never_auto_stop()` returns True off-live, so `entry_cap` = inf (live `MAX_AUTO_ENTRIES_PER_DAY = 2`) and the risk-off gauge halt is bypassed. This is Ajay's own 2026-06-26 standing choice | `trading/auto_entry.py:61, 478-501`; ledger sends: 07-06 CSX 13:31:14, CACC :22, LAMR :32, UFPT 13:32:13, EIX :22; 09-09 SM 13:30:03, NWL :05, SABR :06 [LIVE] | **4 entries, −$3,059.70** (LAMR, UFPT, EIX, SABR) [PA-CI]; overlaps C1 on UFPT and EIX |
| C3 | **Every lane fans out in the same minute.** The tick runs the lanes one after another, each lane checks only its own caps, and names first seen pre-market all fire at 09:30 (ASX `first_seen 04:11`) | `trading/exit_engine.py:1222-1290`; 09-09 sends 09:30:03–09:31:04 [LIVE] | the two clusters, −12,732 [AJ]. **Confounded:** fan-out on 09-04 made +$838 and on 09-08 −$7 [PA-CI]. Fan-out magnifies whatever the day does; n = 2 bad days |
| C4 | **Zone lanes run the WIDE owner rules.** Live config is `{'demand_residents': True, 'breakout_any_band': True, 'min_touches': 1}`; the strict defaults are False, False, 2 | `trading/zone_edge_entry.py:148, 155-157, 552, 559`; 16 of 20 breakout entries had `new_highs=False` and both demand entries were residents [LIVE] | breakout −4,694 and demand −1,473 [AJ]. The tagged breakout lane is still −0.54R (−0.92..−0.10) outside the clusters [PA-CI] |
| C5 | **The lane's gate has drifted from the phone gate.** The lane docstring says "PHONE GATE = ENTRY GATE", but the lane checks only room and proximity. The pushes also require `floor_held_gate`, `knife_gate` and `reversal_mood_gate`, added 09-09 | `trading/zone_edge_entry.py:699-760` against `supply_demand/zone_edge.py:1011-1025` | not separable (n=2) |
| C6 | **The 0DTE PINNED skip never fires.** `read_symbol()` returns `regime` as a DICT, and `contract_for` compares `str(dict)` against the skip list. The tests pass only because their fixture uses a plain string | `trading/zero_dte_lane.py:65, 186-191`; `options/zero_dte.py:521, 539`; `tests/test_zero_dte_lane.py:34`; 22 of 39 orders were placed on PINNED days [SJ:part_A.entered_while_regime_in_skip_list] | PINNED −1,425 against AMPLIFYING +912 (CIs overlap) [SJ:part_A.closed_by_regime] |
| C7 | **0DTE loses mostly on direction (approximate split).** The delta part is −$728 and the residual +$215. The underlying moved the trade's way in 10 of 31 (32.3%, 18.6–49.9). **Approximate:** `stock_move_pct` runs from the signal price to the close-DETECTION time, not fill to fill (`zero_dte_lane.py:540-545`), and the 12 signal-stop exits are direction losses by construction | [AJ:zero_dte_decomposition] | −513 |
| C8 | **0DTE closes are never re-priced.** A close is re-sent only when the broker cancels it | `trading/zero_dte_lane.py:491-500, 517-536`; 5 of 31 closes took over 60 s, the worst **4,340 s** [SJ:part_A.close_send_to_fill_sec] | unmeasured |
| C9 | **SPY 0DTE entries miss.** The limit is set once at the ask and cancelled after `ENTRY_FILL_WAIT_SEC = 180` | `trading/zero_dte_lane.py:64, 475-486`; SPY filled 2 of 6 (CI 9.7–70%) against 79.5% for all names [SJ] | opportunity only |
| C10 | **Stock winners are too small.** Payoff is 0.63, and only 1 of 35 reached its target. The distribution exit closed 11 trades for −$174 | [AJ:overall.stocks; tables."exit reason (stocks)"] | the whole stock expectancy; the cause is unknown |

### SUSPECTED (no $ attribution yet)
- **S1 Stuck `held` bracket stop legs.** When the leg sticks, the position is protected only by the watchdog, once per tick (`exit_engine.py:576-590, 1000-1036`). `last_errors` now shows "adopt AAT … held_for_orders" [LIVE].
  - **Correction to the autopsy doc (WP-A applies it):** the ASX slip was mainly an opening gap, not an execution failure. On 09-14 it opened at 37.41 against a stop of 38.86 [LIVE price_cache], and its broker stop leg shows `canceled`. About $882 of the −$1,135 slip is the gap, which a resting stop would also have paid. About $255 came from four watchdog market sells over 5 minutes [PA-CI; single trade, no CI].
- **S2 The expected-move and regime reads use a 15-minute-delayed spot.** The Massive snapshot's `underlying_asset` is DELAYED on 1500/1500 contracts [SM §3].
- **S3 Minervini `close_confirm` buys at the open.** All 5 post-reset Minervini entries were at 09:30–09:31 [LIVE]. Payoff 0.10, n=6, small n [AJ doc §2].
- **S4 Tick overlap.** `tick()` stores only its start (`last_tick_iso`, `exit_engine.py:1216-1219`), records no duration, and takes no lock (`:906`). A tick longer than a minute can overlap the next and double-evaluate. Unmeasured; a6/P0 measures it.

### Checked and rejected (not a cause)
- Per-trade size: 0 entries over `MAX_POSITION_FRACTION`; mean risk is 0.41–0.99% of equity [AJ:risk_by_lane].
- Slippage: +14 bps (−12..+38) [AJ:execution.entry_slippage_bps].
- Regime, VIX, SPY trend, weekday, price and cap: every bucket is negative and the CIs overlap [AJ:tables].
- Opening hour as such: not shown either way. Outside the clusters, first-30-min entries are R +0.24 (−0.18..+0.67), n=14 [PA-CI].
- "options exit_reason empty": the lane writes `close_reason`, which is filled on 10 of 10 [LIVE].

## 4. The plan (each item is HIS call)

### (a) Bug fixes that enforce rules already written (no strategy change; they ship only on his nod)
| id | fix | where | expected effect |
|---|---|---|---|
| a1 | **In-flight cap.** Count `|position symbols ∪ pending-BUY-entry symbols|` against `MAX_POSITIONS`, where pending = `status ∈ {new, accepted, pending_new, partially_filled}`. The union counts a partly filled buy once (its symbol is already in `positions()`). Refuse a second entry for a symbol that already has a pending buy. Fail CLOSED on a broker read error | `trading/entries.py:167-181`, reusing `broker.open_orders()` (`broker_alpaca.py:120`, `broker_sim.py:344`) | enforces the written cap of 5. On the two cluster days it would have refused 8 entries, −$7,259 [PA-CI]. This is rule enforcement, not an EV claim |
| a2 | **PINNED skip reads the dict.** `name = r.get("regime") if isinstance(r, dict) else r` | `trading/zero_dte_lane.py:190` (also the `narrative` at :267) | the lane's own rule runs; 0DTE entries roughly halve (22 of 39 were PINNED) |
| a3 | **0DTE close re-price.** A close still open after one tick is cancelled and re-sent at the current bid (`round_down_tick`), every tick until filled | `trading/zero_dte_lane.py:491-500` | exits land within about one tick, **if** the tick itself runs every minute (a6) |
| a4 | **0DTE spot.** Use the real-time stock last price when the snapshot's underlying is DELAYED | `options/zero_dte.py` (`chain_for`/`read_symbol`) | correct expected move, regime and delta×spot |
| a5 | **Docs.** Strike the "0DTE cannot be backtested" claim, which is false because Massive serves option minute bars and NBBO history back to 2023-09 [SM §3]. Correct the ASX attribution | `options/zero_dte.py`, `options/zero_dte_history.py` docstrings; `docs/trading/autopilot_autopsy_2026_09_27.md` (WP-A) | truth |
| a6 | **Tick telemetry (no behavior change).** Every `tick()` writes one `engine_tick_log` doc: started, finished, duration, seconds per lane, and `overlapped` (the previous doc has no `finished` and started < 60 s ago) | `trading/exit_engine.py:906` (`tick`), wrapping the lane block `:1222-1290` in try/finally | proves or disproves "monitoring minute to minute" before anything relies on it |

### (b) STOP-DOING list: lanes trading null, inconclusive or relaxed rules (each his call)
| id | stop | evidence | recommended |
|---|---|---|---|
| b1 | **Paper's lifted Minervini caps** (`entry_cap` = inf, gauge bypass) | C2: 4 entries past the live cap by send order, −$3,059.70 [PA-CI]. Paper should rehearse the rules he will run live | **Restore the live caps in paper** |
| b2 | **0DTE Signal Lab trigger** | first tag inconclusive (the sign flips with the placebo); every tag −0.015R (−0.086..+0.059), 62.3% stop-out [SJ:part_B] | **Pause new 0DTE entries as a precaution** (`zero_dte_entry` false, flipped by him) until WP-B reads. Not because the trigger is proven inverted |
| b3 | **Hot Pullback lane** | measured null, +0.100R (−0.188..+0.405) | **OFF** |
| b4 | **Demand residents** (`demand_residents: True`) | both demand losses were residents; reclaims hit the stop 66% of the time vs 11% for arrivals (n=286 pushes) [ST:sd_autopsy_2026_09_08] | **Strict: arrivals only** (config) |
| b5 | **Breakout wide rule** | tagged lane −0.70R (−1.04..−0.32) overall and still **−0.54R (−0.92..−0.10) outside the clusters** (n=9, 4 days) [PA-CI]. WP-D computes V2's baseline in the replay, so a live baseline arm is not needed | **Pause the breakout side (P5).** Until P5 ships: strict `breakout_any_band: false` (existing key, his flip) |

### (c) Named paper variants (pre-registered; each replaces the arm named; nothing runs without his yes)
| variant | rule (existing engines only) | why (study, effect, CI) | n needed | success / failure | replaces |
|---|---|---|---|---|---|
| **V1 `demand_phone_parity_v1`** | Zone demand arrivals (strict) plus the full phone gate: room ≥ `ALERT_MIN_ROOM_PCT` 5, `demand_proximity_gate`, **`floor_held_gate` (intact)**, `knife_gate`, `reversal_mood_gate`. Stop at band floor −`STOP_BUFFER_PCT` 0.5 | intact floor: **+8.60pp win (+6.39..+11.06)**, stop-out −9.58pp, 31,861 events over 192 dates [ST:bounce_quality_study.py]. Knife and mood measure flat but are his rule. Expectancy is UNKNOWN (median R −1) → WP-D | ~170 trades for ±0.15R. That is about a year at the current fire rate, **so the replay (WP-D) is the proof and paper is the execution check** | Pass: WP-D R CI lower bound > 0, AND paper at n ≥ 30 inside the WP-D CI. Kill: paper n ≥ 20 with R CI upper bound < 0 | demand residents (b4) |
| **V2 `breakout_lastlid_near_high_v1`** | Break of the LAST lid (the `supply_demand/lid_break.py` event) where the prior 52-week high is ≤ 5% above the lid. Target = the prior 52-week high. Stop = lid floor −0.5%. Time stop 21 sessions | at distance ≤5%, **89.6% (n=1,835)** reached the prior high within 21 sessions [ST:`docs/supply_demand/lid_break_study.md:50`]. **No distance-matched placebo exists yet.** The 24.0%/26.4% placebo (`:43`) is all-distance and is NOT comparable, because a high ≤5% away is touched often at random. The 75.2% close-back-under-the-lid (`:46`) covers all 3,967 breaks; the ≤5% subgroup is unmeasured. Both → WP-D. A touch rate, not P&L | replay first (WP-D) | same rule as V1 | the paused breakout side (b5) |
| backlog (study-first, no lane) | Growth/Bonde ARRIVALS, hold 63 sessions | +7.49pp at 63 sessions, date-clustered (+0.52..+16.06); no entry, stop or cost model [ST:board_growth_measured.json] | — | needs a P&L replay | — |
| backlog | the BOX (≤10% under the 52-week high, ≥75% above the low) | 3.2× lift on ≥+200% in 12 months, n=137; 12-month horizon; memory only | — | not a swing trigger | — |
| not ready | Gabbar levels | OOS 72% recovered, n=43 resolved; **no placebo**; 66 hand-drawn tickers | — | — | — |

### (d) Risk and sizing
| id | change | why | recommended |
|---|---|---|---|
| d1 | **One new stock entry per tick across all lanes, all day.** Pyramid top-ups count; manual entries are exempt | C3, as a **concentration limit that enforces one decision per minute, not an EV gain** (fan-out on 09-04 made +$838; n = 2 bad days). Its counterfactual is not reconstructable: blocked names can re-fire on later ticks, and first-in-tick would still have entered ASX (−$2,435) and UFPT (−$1,583) [PA-CI] | yes |
| d2 | Keep per-trade risk as it is | sizes are within the book. `consecutive_losses = 11` [LIVE] already makes `size_multiplier` **0.25** (`risk_rules.py:166-172`), and the progressive pilot is 0.5 (`progressive.py:57`) | no change |
| d3 | Keep counting option positions inside `MAX_POSITIONS` (`positions()` returns every `/v2/positions` row, `broker_alpaca.py:116-117`) | counting stocks only would be a loosening | no change |
| — | Rejected: portfolio-heat cap (redundant once a1 holds: 5 × about 1%); blanket no-entry for the first 30 minutes (no evidence either way: R +0.24, −0.18..+0.67, n=14 [PA-CI]) | | |

## 5. SPY options lane: draft (UNMEASURED, PAPER-ONLY)

**Feasibility: yes on the plumbing, no on the evidence.**
- **PDT is retired.** SEC approval 2026-04-14; Alpaca live 2026-06-04. The PDT fields are null on our account [SM §1].
- **Account and approvals:** equity $88,938.60, options buying power $76,699.79, options level 3 [SM §1].
- **Data:** SPY has same-day expiries. SPY 1-minute bars are real-time from Massive. Option quotes are real-time for picking the contract. The snapshot spot is **15 minutes delayed** (a4). Exits are priced off Alpaca's *indicative* feed, which is not OPRA [SM §2-3].
- **Minute-by-minute monitoring is scheduled, not proven.** `exit_engine tick` is scheduled `* 9-16 * * 1-5` (`backend/crontab:914`) and the 0DTE lane runs inside it. But the tick records only its start (`exit_engine.py:1216-1219`), no duration, and has no overlap lock (`:906`). a6/P0 measures it. **P4 does not ship until P0 shows p99 tick < 60 s and 0 overlaps over ≥ 5 RTH sessions.**
- **Hard broker limits:** no options stop orders and no brackets (the stop lives only in our tick). SPY expiry-day orders are refused **from 15:30 ET**, and Alpaca auto-liquidates at **15:45** [SM §2].
- **What blocks it today:**
  - The caps: `MAX_ENTRIES_PER_DAY = 3` and `MAX_OPEN = 3` (`zero_dte_lane.py:60-61`), with one entry per name per day, give SPY **at most 1 trade a day**.
  - The standing S/D buy gate passes on SPY on only **10 of 247 closes (4.0%, 2.2–7.3)**; the median room is 1.19% against the 5% required [SJ:part_D].

**Design: extend the ONE 0DTE engine (`trading/zero_dte_lane.py`) with two named variants. No new lane module.**
| part | spec (reuses existing constants by name) |
|---|---|
| **DT `spy0dte_demand_v1`** (the "demand entries") | Bands from `price_zones.for_symbol("SPY", tf="15m")`, off bars closed before the session. Trigger: a 1-min bar whose low ≤ band.hi while the prior 1-min close was > band.hi (an **arrival from above, never a reclaim**), the band floor not traded through earlier today, and `demand_proximity_gate(last, band)`. Room gate per HIS CALL #16 (default: the standing gate applies). **Long call.** At most 4 a day, and one per band per session |
| **VT `spy0dte_vol_v1`** (the "volatility" trade) | Candidates, measured separately in WP-B and chosen by Ajay only if one clears: **VT1** the ORB break (`signal_lab` `orb_up`→call / `orb_dn`→put, `ORB_MINUTES = 15`) on sessions whose prior VIX close ≥ `iv_read.NORMAL_BELOW` (20). Prior: in-sample ORB on elevated-VIX days is n=12 (9 sessions), **−0.583R (−1.0..0.0)** [SJ:part_B.orb_by_vix_regime.elevated], small n and unfavourable. **VT2** a continuation once SPY has moved ≥ 1.0 × the chain's own expected move (`zero_dte.expected_move_pct`) from the open. **VT3** the dealer regime reads AMPLIFYING; this cannot be replayed (0 SPY docs in `gex_history`), so it is forward-only. At most 1 a day, in its own slot |
| contract | Same-day expiry via `zero_dte.pick_contract`: `TARGET_DELTA` 0.35, `MAX_SPREAD_PCT` 25, `MIN_DAY_VOLUME` 500, `MIN_ASK` 0.20 |
| window | `ENTRY_OPEN_ET` 09:45 → `LAST_ENTRY_ET` 14:30 |
| exits, checked every tick | Premium −`PREMIUM_STOP_PCT` 50 on the bid. Premium +`PREMIUM_TAKE_PCT` 100. Underlying 1-min close < band floor × (1 − `STOP_BUFFER_PCT`/100) for DT, or the opposite side of the ORB for VT. Underlying reaches the first supply band. **Flatten at 15:25 ET** (his call, before Alpaca's 15:30 cutoff); if still unfilled at 15:27, send a market order |
| selling on time | a3 re-prices the close every tick. Entries re-quote to the current ask each tick until `ENTRY_FILL_WAIT_SEC` (his call, SPY/QQQ/IWM only) |
| size | Existing `min(RISK_PCT_OF_EQUITY 0.5% × equity, MAX_PREMIUM_PER_TRADE $500)` = **$444.69 per trade today** [SM §5]. Five a day = about $2.2k of premium at risk |
| caps | SPY-variant counters are kept apart from the 13-name caps: **≤5 SPY entries a day (4 DT + 1 VT), 1 SPY position open at a time.** **Daily loss cap:** stop new SPY entries once there have been **2 premium-stop exits today, OR** the realized SPY day loss ≥ **2 × (`PREMIUM_STOP_PCT`/100) × the per-trade budget** (= 2 × 0.5 × $444.69 = $444.69 today). The count leg catches stops that sell slightly above −50%; the "2" is his call (#15) |
| gate | The standing rule is "demand lanes pass the alert gate". DT is a demand lane, so by default the gate applies. **With the gate, DT fires only on sessions where the daily gate passes (4.0% of closes), so "≥5 SPY trades a day on demand entries" is unreachable.** Exempting DT is HIS call (#16); the default is NO |
| journal | `strategy: "zero_dte"`, `variant: <name>`; the zero-DTE tab shows a variant badge |

**Quota vs cap: the honest line.** "At least 5 a day, at least 1 on volatility" is a **quota**, so it forces entries. The existing trigger fires 12.7 times a session, which makes a quota *mechanically* reachable. But every tag of that trigger is **−0.015R (−0.086, +0.059) with 62.3% stop-outs** [SJ:part_B]. Our same-day demand reads are a **coin flip** (52% close above the print) [ST:sd_autopsy_2026_09_08]. A quota therefore buys losses at a fixed rate. **The alternative is a CAP of 5 that enters only when a rule fires, with the vol slot firing only on a VT rule.** Recommended: CAP.

**How it gets measured.** WP-B runs an option-P&L replay of SPY 0DTE from 2023-09-11 to 2026-09-25: buy at the NBBO ask, sell at the bid, with live regulatory fees as a column and a time-matched ±15-min placebo. It covers T0 (the current first tag), T1 (every tag), DT (with and without the room gate), VT1 and VT2, and applies the daily loss cap.
- **Pre-registered pass:** the mean R CI lower bound > 0 AND the difference vs placebo has a CI lower bound > 0, at ≥ 300 trades. Report 99% CIs as well (5 comparisons).
- **No pass:** the lane does not run, unless he chooses the 1-contract measurement lane (#17).
- **Pass:** paper at the budget; kill when n ≥ 20 and the R CI upper bound < 0; about 170 trades (≈7 weeks at 5 a day) before any promotion.

## 6. HIS CALL (numbered; recommended default in bold)
1. Ship the bug-fix batch (a1–a6; a6 is telemetry only) on a fresh `fix/` branch. **YES**
2. Restore the live Minervini caps in paper (`MAX_AUTO_ENTRIES_PER_DAY` 2 plus the risk-off halt); 4 entries past the cap by send order lost −$3,059.70. This reverses the 2026-06-26 "never auto-stop in paper" rule. **YES**
3. One new stock entry per engine tick across all lanes (d1): all day, or only for the first `autopsy.FIRST_MINUTES` (30)? It is a concentration limit, not a measured gain (n = 2 bad days). **All day**
4. Demand lane back to the strict rules, arrivals only (`demand_residents: false`, `min_touches: 2`). He flips it through `POST /trading/config`. **YES**
5. Breakout wide rule: pause the breakout side, switch to strict, or keep it as a live V2 baseline arm? It is −0.54R (−0.92..−0.10) even outside the clusters. **Pause (P5); strict `breakout_any_band: false` until P5 ships** (changed from rev 1 "keep")
6. Pause new 0DTE entries on the Signal Lab trigger until WP-B reads. The trigger's sign is inconclusive, not proven inverted. **PAUSE (precaution)**
7. Hot Pullback lane OFF (measured null). **OFF**
8. Apply the full phone demand gate (floor held, knife, mood) to the demand, options and catalyst lanes, per his 09-05 rule "phone gate = entry gate" (V1). **YES, as a tagged variant**
9. V2 last-lid near-high breakout: build it only after the WP-D replay passes against a distance-matched placebo. **YES (study first)**
10. 0DTE flatten time: 15:25 ET for SPY/QQQ/IWM and 15:10 for single names, with a market-order fallback 2 minutes later (Alpaca refuses orders from 15:30 / 15:15). **YES**
11. 0DTE entry re-quote to the current ask each tick until `ENTRY_FILL_WAIT_SEC` (this is chasing). **YES for SPY/QQQ/IWM only**
12. SPY: quota ("≥5, ≥1 vol, forced") or cap ("≤5, rule-only")? **CAP**
13. Which volatility trigger: VT1 (ORB on VIX ≥ 20; in-sample prior −0.58R, n=12), VT2 (a 1× expected move from the open), or VT3 (AMPLIFYING, forward-only)? **None until one clears WP-B**
14. SPY trade side: calls at demand only, or also puts at supply? **Calls only (his "demand entries")**
15. SPY daily loss cap: stop after 2 premium-stop exits OR a realized loss ≥ 2 × (`PREMIUM_STOP_PCT`/100) × budget ($444.69 today). The "2" is new. **YES, 2**
16. Exempt the SPY demand variant (DT) from the ≥5%-room alert gate? The standing rule says demand lanes pass the gate. With the gate, DT fires on about 4% of sessions and ≥5 SPY a day on demand entries is unreachable. Without it, DT trades a same-day demand touch that is unmeasured until WP-B. **NO (standing rule; WP-B measures both so he can decide on data)**
17. If WP-B shows no pass, run the SPY lane anyway as a 1-contract measurement lane? Yes gives him SPY trades and forward data at 1-contract cost, on a trigger with no measured edge; no keeps "study first". **No recommendation. HIS call.**
18. Kill/promote rule for every variant (kill: n ≥ 20 with R CI upper < 0; promote: replay CI lower > 0 AND paper within the replay CI). **YES**
19. Stuck-`held` stop repair (cancel the held leg, then place a standalone stop): investigate only for now. **Investigate**
20. Tick overlap lock (skip a tick that starts while the previous one is still running): only if a6 shows any tick ≥ 60 s or any overlap. **Decide after a6 data**

---

## 7. Facts and constants (file:line, reuse by name)
- `trading/risk_rules.py:76` `MAX_POSITIONS = 5`; `:77` `MAX_POSITION_FRACTION = 0.25`; `:80-81` `STREAK_HALVE_AFTER = 3`, `STREAK_MULTIPLIERS = (1.0, 0.5, 0.25)`; `:166` `size_multiplier`.
- `trading/entries.py:125` `_evaluate`; `:167-176` the cap check (`len(positions) >= MAX_POSITIONS`); `:199` safety floors; `:369` `enter`.
- `trading/broker_alpaca.py:116-117` `positions()` = every `/v2/positions` row (stocks AND options); `:120-127` `open_orders()` (nested legs).
- `trading/auto_entry.py:61` `MAX_AUTO_ENTRIES_PER_DAY = 2`; `:478` `_never_auto_stop`; `:494` `entry_cap`; `:499` `gauge_allows`.
- `trading/exit_engine.py:906` `tick()` (no lock, no duration); `:1216-1219` `update_config(... last_tick_iso=tick_started_iso ...)` (start only); `:1222-1290` lane order: auto_entry (f), zone_edge (h), qb_eod (h2), catalyst (j), options (k), zero_dte (l), hot_pullback (m); `:576` `_STOP_LIVE_STATUSES`; `:1000-1036` watchdog; `:1345` `_engine_liveness`. The `get_config` key whitelist (`:130-145` onward) is a trap: a new key dies silently unless it is added.
- `trading/zone_edge_entry.py:133-134` per-side caps 4/8; `:137` `STOP_BUFFER_PCT = 0.5`; `:148` `MIN_TOUCHES = 2`; `:155-157` `RULES_DEFAULT`; `:501` `active_rules`; `:699` `alert_gate`.
- `supply_demand/alert_gates.py:81` `ALERT_MIN_ROOM_PCT = 5.0`; `:434` `demand_proximity_gate`; `:838-842` `FLOOR_HELD_STATES`, `floor_held_gate`.
- `trading/zero_dte_lane.py:54-65`: `ENTRY_OPEN_ET 09:45`, `LAST_ENTRY_ET 14:30`, `FLATTEN_ET 15:45`, `SIGNAL_MAX_AGE_SEC 180`, `RISK_PCT_OF_EQUITY 0.5`, `MAX_PREMIUM_PER_TRADE 500`, `MAX_ENTRIES_PER_DAY 3`, `MAX_OPEN 3`, `PREMIUM_TAKE_PCT 100`, `PREMIUM_STOP_PCT 50`, `ENTRY_FILL_WAIT_SEC 180`, `SKIP_REGIMES ("PINNED",)`; `:186` `contract_for` (`:190` the str() compare); `:446` `_manage`; `:517` `_send_close`; `:536-545` `_finish` (`stock_move_pct` = signal price → close-detection time); `:560` `_try_entries`.
- `options/zero_dte.py:80` `UNIVERSE`; `:90-94, 123` delta, spread, volume and ask rules; `:271` `expected_move_pct`; `:312-314` regime names; `:317` `regime_from_gex` (returns a dict); `:501` `read_symbol`.
- `trading/options_lane.py:80` `MAX_OPTIONS_ENTRIES_PER_DAY = 1`; options_zone INTC position 09-08→09-10 was a single-leg long call (`INTC261009C00100000`) [LIVE options_positions], so it was one `positions()` row on 09-09.
- `trading/hot_pullback_entry.py:57-62`.
- `sepa/iv_read.py:33-35` `CALM_BELOW 15`, `NORMAL_BELOW 20`, `ELEVATED_BELOW 30`; `:65` `classify`.
- `daytrading/signal_lab.py:37` `ORB_MINUTES = 15`; `:40` `TARGET_R = 2.0`; `:46` `events_from_frame`.
- `supply_demand/price_zones.py:219` `compute`; `:332` `for_symbol(tf=)`.
- `docs/supply_demand/lid_break_study.md:43` 57.5% vs placebo 24.0/26.4 (all distances); `:46` 75.2% closed back under the lid (all breaks); `:50` ≤5% bucket 89.6% (n=1,835).
- `trading/autopsy.py:107` `FIRST_MINUTES = 30`.
- `backend/crontab:914` tick cadence `* 9-16 * * 1-5`.
- Ledger entry send times [LIVE]: 07-06 CSX 13:31:14Z, CACC :22, LAMR :32, UFPT 13:32:13, EIX :22; 09-09 SM 13:30:03, NWL :05, SABR :06, IBKR :08, CNQ :08, ZM :09, ASX 13:31:03, ASML :04, FSLR :04. Open at the first send: 07-06 WST, PNTG; 09-09 TECK + the INTC call.
- Live config [LIVE]: `armed` True; every lane True; `equity_cap` 100000; `consecutive_losses` 11; `zone_edge_rules` wide.

## 8. Alternatives rejected (one line each)
- **A new `trading/spy_0dte_lane.py`:** it would be a parallel engine to `zero_dte_lane` (same tick, broker helpers and journal).
- **Raise `MAX_ENTRIES_PER_DAY` to 5 on the Signal Lab trigger:** every tag is −0.015R (−0.086..+0.059) with 62.3% stop-outs, and the first tag's sign flips with the placebo.
- **Use the daily S/D alert gate as the only SPY entry rule:** it fires on 4% of sessions (kept as the DT default only because the standing rule says so, #16).
- **Blanket no-entry for the first 30 minutes:** no evidence either way (R +0.24, −0.18..+0.67, n=14).
- **Portfolio-heat cap:** redundant once a1 enforces 5 positions.
- **Cut per-trade risk:** no entry was oversize, and the streak multiplier is already at 0.25.
- **Keep the breakout side live as V2's baseline arm:** WP-D computes the baseline in the replay, and the live arm is −0.54R (−0.92..−0.10) outside the clusters.
- **Count a1 by fill order or by `concurrent_stock_positions`:** the broker cap decides at send time and `positions()` includes options.
- **Wire in Gabbar, the BOX or growth arrivals now:** none has a P&L replay with a placebo.
- **Re-quote entries on all 13 names:** single-name spreads are wide, and on a null trigger that is just chasing.

## 9. Work packages
**NOW (this worktree; new files under `backend/scripts/autopilot_autopsy_*` and `docs/trading/` only; read-only; parallel, disjoint).**

| key | files owned | steps | tests (in `--selftest`, negatives mandatory) |
|---|---|---|---|
| **WP-A autopsy-cuts** | `backend/scripts/autopilot_autopsy_2026_09_27_cuts.py`, `…_cuts_measured.json`, `docs/trading/autopilot_autopsy_2026_09_27.md` (add §7 cuts; apply the corrections below) | Read [AJ] plus read-only `trade_ledger` / `price_cache` / `options_positions`. Emit, with Wilson and seeded bootstrap CIs (seed 20260927, 5,000; day-clustered where ≥ 5 days, else flagged `few_days`): **every [PA-CI] number in §1–§4** (must equal `scratchpad/plan_rev/pa_ci.out`: −7,259.12; −6,487.51/−6,939.73; −3,059.70; −7,912.66/−8,364.88; +2,309.36; +444.92; +1,714.35; +837.90; −6.98; the lane-outside-cluster rows). **Send-order engine:** entries sorted by ledger `epoch`; open count at send = broker positions (stocks + options round-trips open at that instant) ∪ earlier same-day sends; same-second ties reported as a range. Also: lane × cluster-day; Minervini sends past `MAX_AUTO_ENTRIES_PER_DAY` per ET day; breakouts by `new_highs`; demand by tier/arrival; fan-out days (≥ 3 entries within 5 min) with $ and R each; stop exits split into gap-at-open (open < stop) vs intraday slip; zone `first_seen` pre-market vs RTH; the gauge state per entry day if a gauge history exists, else "not reconstructable"; C7 split labelled `approximate_window`. **Doc corrections:** §5 class line → "opening-bell cluster day: 12 of 15; filled while over the cap (fill order): 7 (CACC, UFPT, NWL, SABR, ASML, IBKR, FSLR); refused by a1 in send order: 7 of the 15 (ASX, UFPT, ASML, IBKR, FSLR, ZM, CNQ)", and label the per-row "Nth open position" notes "by fill"; §3 ASX → gap (open 37.41 vs stop 38.86), stop leg `canceled`, ≈$882 gap + ≈$255 watchdog sells, not an "execution failure"; §6 zero_dte row → cite part_B with the placebo-dependent sign instead of "no placebo study"; line 221 "Bounce-gate" → "Reversal-gate"; drop "not signals"-type causal claims. **Reconcile gate:** every cut sums to [AJ] totals to the cent, else exit non-zero | a trade with no `et_day` lands in `unassigned`, never dropped; n<10 → `small_n`; n<2 → CI `[None, None]`; an injected mismatch → raises; re-run → byte-identical JSON; a same-second send tie → both orderings reported, never one picked silently; an option position open at send time IS counted; a position closed before the send is NOT counted; fill order ≠ send order on a synthetic pair → the send-order count wins |
| **WP-B spy0dte-replay** | `backend/scripts/autopilot_autopsy_spy0dte_replay.py`, `…_spy0dte_replay_measured.json`, `backend/scripts/autopilot_autopsy_spy_options_feasibility_measured.json` (re-run output), `docs/trading/autopilot_spy0dte_replay_2026_09_27.md`, `docs/trading/autopilot_spy_options_feasibility_2026_09_27.md` (repoint to the repo JSON; state the first-tag result as "inconclusive, sign depends on the placebo") | Pre-registered as in §5. SPY 1-min bars from Massive for 2023-09-11 → 2026-09-25 (cached in the scratchpad, never Mongo). Expired contracts via `/v3/reference/options/contracts`. Contract minute bars via aggs. NBBO at entry and exit minute+1 via `/v3/quotes` (one read each). Delta by BS from the NBBO mid, fed to `pick_contract`. 15m bands via `price_zones.compute` on a **closed=left** resample of prior bars. VIX via `prices._fetch` (NOT `load_prices`; the 501-bar trap). **Repro gate first:** T0 on the 123 cached sessions must equal [SJ:part_B.composite_first_tag_only]. **Realism check:** replay the lane's 31 real trades and report the replay-minus-actual gap with its CI. Output per trigger: n, the distribution of trades per session (share of sessions with ≥5), win% (Wilson), $ and R with a session-clustered CI, stop-out %, minus BOTH placebos (uniform and ±15-bar), 95% and 99% CIs, flatten at 15:25 vs 15:45, DT with and without the room gate, and the day-loss-cap rule of §5 applied | a trigger bar at 14:31 is rejected; bands built with any bar ≥ the session open raise (lookahead guard); a reclaim (prior close < band.lo) is rejected; ask < `MIN_ASK` is rejected; a missing quote drops the trade into `skipped_no_quote` (never a guessed fill); the placebo is never outside the window; the resample label check runs on a synthetic frame; 2 stop exits → a 3rd entry that day is refused; one stop that sold at −48% plus a small loss under the cap → the next entry is allowed |
| **WP-D variant-replays** (V1, V2) | `backend/scripts/autopilot_autopsy_variant_replays.py`, `…_variant_replays_measured.json`, `docs/trading/autopilot_variant_replays_2026_09_27.md` | V1: the `bounce_quality_study` event set, restricted to arrivals + intact floor + knife + mood + room + proximity; exits: stop at floor −0.5%, target the first supply, 21-session time stop; baseline = all events; date-clustered bootstrap (192 dates). V2: `lid_break` events with distance ≤5%; entry at the next open; stop lid floor −0.5%; target the prior 52-week high; 21 sessions; **distance-matched placebo** = the study's any-day and up-day draws restricted to days whose close is ≤5% under the 52-week high; baseline = all lid breaks; emit the ≤5% fail-back rate (close back under the lid within 21 sessions); date-clustered | future-bar leakage → raises; distance >5% excluded from both the event set AND the placebo; a gap-through open fills at the open, not at the stop; a draw with no events → reported, not zero; an all-distance placebo passed to the V2 comparison → raises |
| **WP-C plan-doc** (MAIN session, after A/B/D) | `docs/trading/autopilot_plan_2026_09_27.md` | Sections 1–6 of this spec with the [PA-CI] numbers replaced by WP-A output and §5 filled from WP-B | — |

**AFTER HIS CALL (fresh `fix/` / `feat/` branch; disjoint; sequenced where a file is shared: P4 after P3, P5 after P0).**

| key | files owned | steps | tests incl. negatives | docs |
|---|---|---|---|---|
| P0 tick-telemetry (a6; #20 later) | `trading/exit_engine.py`, `tests/test_exit_engine_tick_telemetry.py` (new) | In `tick()` (`:906`) record `started`, per-lane seconds around each lane call in `:1222-1290`, and in a `finally` write `{started_iso, finished_iso, duration_s, lanes, overlapped}` to a new `engine_tick_log` collection (TTL index; retention named `TICK_LOG_TTL_DAYS`, value his call, not a trading threshold). `_engine_liveness` (`:1345`) adds `tick_p50_s`, `tick_p99_s`, `overlaps_today`. No order path changes | a lane that raises → the doc still has `finished_iso` and `duration_s`; the telemetry write raising → the tick result is unchanged and the error lands in `summary["errors"]`; the previous doc lacking `finished_iso` and < 60 s old → `overlapped: true`; older than 60 s → false; the tick summary is identical with telemetry on and off | `docs/trading_engine_liveness.md` (append a section) |
| P1 entries-guard (a1, d1) | `trading/entries.py`, `tests/test_entries_inflight.py` (new) | Add `_inflight(broker)` → (set of position symbols, set of pending-BUY entry symbols); count the UNION. Block "portfolio full: %d positions + %d pending entries / %d (p.312)". Block "entry already pending for SYM". Throttle: refuse when a non-dry `entry` ledger row is < 60 s old ("one entry per tick") | 4 positions + 1 pending → blocked; a `partially_filled` buy for a symbol already in `positions()` counts ONCE; an option position counts; SELL stop/target legs not counted; `held` legs not counted; a pending buy on the same symbol → blocked; `open_orders` raises → blocked (fail closed); a second enter in the same tick → blocked; a manual entry is exempt from the throttle | `docs/trading_engine_inflight_cap.md` (new) |
| P2 paper-live parity (b1) | `trading/auto_entry.py`, `tests/test_autoentry_never_stop.py` (rewrite) | `_never_auto_stop()` → False in every mode (no new config key, which avoids the whitelist trap) | paper: 3rd entry blocked; paper + risk_off → blocked; live unchanged; broker-mode read fails → capped | `docs/trading/autopilot_paper_live_parity.md` (new) |
| P3 zero-dte-fixes (a2, a3, #10, #11) | `trading/zero_dte_lane.py`, `tests/test_zero_dte_lane.py`, `docs/trading_zero_dte_lane.md` | Read the regime dict (plus `narrative`). Close re-price each tick. Per-class flatten plus market fallback. SPY/QQQ/IWM entry re-quote | fixture regime = **the dict shape `read_symbol` returns**; PINNED dict → skip; UNKNOWN dict → no skip; None → no skip; legacy string "PINNED" → skip; a close open for > 1 tick → cancel + resend at the new bid; a close filled → no resend; flatten at 15:25 for SPY, 15:10 for a single name; no entry re-quote on single names | same |
| P3b zero-dte-data (a4, a5) | `options/zero_dte.py`, `options/zero_dte_history.py`, `tests/test_zero_dte.py` | Real-time spot when the snapshot underlying is DELAYED; fix the docstrings | DELAYED → real-time used; real-time missing → snapshot kept and flagged `spot_delayed`; REAL-TIME snapshot → untouched | — |
| P4 spy-variants (§5; only after WP-B, P0's p99 < 60 s gate, and his yes) | `trading/zero_dte_lane.py` (after P3), `tests/test_zero_dte_spy_variants.py` (new), `frontend/src/components/ZeroDteLaneTab.tsx` + `.test.tsx` | `VARIANTS` registry; DT/VT triggers; DT room gate per #16; SPY counters; daily loss cap (count leg OR $ leg, both from constants); `variant` on the doc and the ledger | 6th SPY entry blocked; a 2nd open SPY blocked; 2 premium-stop exits → blocked; realized loss ≥ 2 × 0.5 × budget → blocked; 1 stop at −48% + a small loss under the cap → allowed; DT with room < `ALERT_MIN_ROOM_PCT` and #16 = NO → blocked; a reclaim → no entry; a vol slot left unused never forces a trade; the variant badge renders; a missing variant → no badge | `docs/trading_zero_dte_lane.md` |
| P5 zone-kind switch (if #5 = pause; after P0) | `trading/zone_edge_entry.py`, `trading/exit_engine.py` (the `get_config` whitelist line only), `tests/test_zone_edge_entry.py` | New `zone_edge_kinds` key | kind off → skipped with a reason; junk value → strict default; key missing from the whitelist → test fails | `docs/supply_demand/zone_edge_autopilot.md` |
| MAIN | `tests/test_trading_contracts.py`, `frontend/src/lib/newFeatures.ts`, lane `rules_list()` lines / `supply_demand/rules_info.py`, config flips (**Ajay only**) | pin the new constants; add a ✨ entry for the SPY tab badge and the tick-health line | — | — |

## 10. Verification plan
- **WP-A:** run in the api container read-only (pipe the script in on stdin; nothing written there). The reconcile gate passes; a second run gives an identical JSON; every [PA-CI] figure equals `pa_ci.out`. Quote to Ajay only from `…_cuts_measured.json`.
- **WP-B:** run in a throwaway `cheetah-api:latest` container (`--network cheetah-market-app_default`, `MONGO_URL=mongodb://mongo:27017`, `MONGO_DB=cheetah`, `--memory 1.5g`), detached, **outside RTH** (today is Sunday; otherwise after 16:00 ET), polling no faster than once a minute. The repro gate must pass before the full run.
- **WP-D:** the V2 comparison must use the distance-matched placebo; the doc quotes no all-distance placebo beside the 89.6%.
- **After the code packages:** run the hermetic backend suite with caches purged, plus FE vitest/tsc/contracts. **On HIS surface** (https://pounce.ajaykandakatla.dev/trading):
  - P0 first: after ≥ 5 RTH sessions, `GET /trading/status` → `engine.tick_p50_s / tick_p99_s / overlaps_today`. "Minute-by-minute" is claimed only if p99 < 60 s and overlaps = 0; P4 waits on it.
  - After the next open, the ledger shows at most 1 entry per tick, and the "positions + pending entries" block reason appears on a busy open.
  - The 0DTE tab's attempts show "dealers PINNED — no 0DTE entry" on PINNED days.
  - `GET /trading/status` `rules_list` carries the new lines.
  - Journal-by-strategy shows the `variant` split.
- **Pins that will break (MAIN updates them):**
  - `tests/test_trading_contracts.py:1137` (FLATTEN_ET) and `:1140` (only if caps change).
  - `tests/test_zero_dte_lane.py:111, 114`.
  - `tests/test_autoentry_never_stop.py` (P2).
  - `test_trading_contracts.py:91` stays green (MAX_POSITIONS unchanged).

## 11. Risks and traps
- **The container runs origin/main.** Branch code is not loaded there; probes must re-implement and be pinned by a repo test.
- **Fill order ≠ send order.** Caps decide at send time; ASX filled 2nd but was sent 7th. Any cap counterfactual uses ledger `epoch` order, and `positions()` includes options.
- **Two-day counterfactuals are accounting, not estimates.** Their CIs span 2 clusters and say nothing about expectancy. Never present a1/b1/d1 as an EV gain; d1's counterfactual is not reconstructable (re-fires on later ticks).
- **`load_prices(period=…)` returns about 501 bars on a cache hit.** Use `prices._fetch` read-only for 2023+.
- **Resampling must be `closed=left`.** Massive stamps can be ns or ms; check which before converting.
- **`intraday_cache` holds only 123 SPY sessions**; older bars come from Massive. `gex_history` has **0 SPY docs**, so PINNED/AMPLIFYING is not replayable.
- **Paper fills are optimistic** (NBBO, no size, no slippage, no fees). The replay prices ask/bid and adds a live-fee column.
- **Multiple comparisons** (5 triggers, 2 placebos): print 99% CIs. A result whose sign flips with the placebo is "inconclusive". Never rank on win rate; always show R and stop-out beside it.
- **Placebo must match the conditioning.** A distance-filtered event set needs a distance-filtered placebo (V2).
- **Don't sum overlapping buckets** (a1 and b1 overlap on UFPT, EIX; use the combined row).
- **Variant $ results will be tiny** at the 0.25 streak multiplier; judge them in R.
- **A new config key must be added to the `get_config` whitelist** or it silently does nothing.
- **Tick duration is unmeasured.** Nothing in the SPY design may assume a one-minute exit until P0 data exists.
- **Config flips, arming and orders are Ajay's alone.** No executor POSTs to `/trading/*`.
- **Heavy replays never run during RTH.**

## 12. Changelog, rev 1 → rev 2 (verifier findings)
1. **High, C2 $ by fill order → FIXED.** Recounted by ledger send order: LAMR, UFPT, EIX, SABR = **−$3,059.70** (CACC and NWL were within the cap). Updated §1, §2, C2, b1, HIS CALL #2.
2. **C1 $ by fill order → FIXED, refined.** Send order gives the verifier's −$6,487.51..−$6,939.73 on a stocks-only count. But the live cap reads `positions()`, which includes the INTC long call open on 09-09 (single leg, `options_positions`), so 2 were open at both first sends and a1 refuses **8 entries, −$7,259.12**. Both are shown; the fill-order −$7,859 is kept as descriptive only.
3. **Fan-out confounded → FIXED.** Verdict line 3 drops "not signals" and says n = 2 bad days; a1/d1 are justified as rule enforcement and a concentration limit; 09-04 (+$838) and 09-08 (−$7) added; every [PA] number now has a CI ([PA-CI], `pa_ci.py`). Outside-cluster mean R is −0.02 (−0.36..+0.35); without PNTG and IRDM +$445. Knock-on: the breakout lane stays −0.54R (−0.92..−0.10) outside the clusters, so b5/#5's default changes from "keep as baseline" to "pause" (planner self-correction).
4. **0DTE "INVERTED" selective → FIXED.** Now "inconclusive, sign depends on the placebo" with all three numbers (§2, b2, §8, #6). The pause stays, labelled a precaution. Added the in-sample VT1 prior (elevated-VIX ORB −0.583R, n=12).
5. **V2 placebo mismatch → FIXED.** The 24/26% placebo is labelled all-distance and not comparable; 75.2% labelled all breaks; WP-D must build a distance-matched placebo and emit the ≤5% fail-back, with a test that refuses an all-distance placebo.
6. **#16 / #17 defaults → FIXED.** #16 default is now **NO** (standing rule; never loosen a gate), with the consequence stated; #17 is "no recommendation, HIS call".
7. **Loss-cap arithmetic → FIXED.** Cap = 2 premium-stop exits OR realized loss ≥ 2 × (`PREMIUM_STOP_PCT`/100) × budget ($444.69 today); the "2" is his call (#15); tests added in WP-B and P4.
8. **a1 double count → FIXED.** a1 counts the union of position symbols and pending-buy symbols; P1 test "partially filled counts once" added.
9. **Minute monitoring unmeasured → FIXED.** §5 now says "scheduled, not proven"; new a6/P0 tick telemetry; P4 gated on p99 < 60 s and 0 overlaps over ≥ 5 RTH sessions; overlap lock is #20, decided after data.
10. **Autopsy doc contradictions → FIXED (assigned to WP-A, which owns the doc).** §5 "12 of 15 over the cap" → 12 cluster-day / 7 over the cap by fill / 7 refused by a1 by send; §3 ASX → gap, not execution failure; §6 zero_dte "no placebo study" → part_B cited; line 221 and plan line 42 "Bounce" → "Reversal" (plan fixed here).
11. **C7 window mismatch → FIXED.** C7 labelled approximate, with `zero_dte_lane.py:540-545` and the by-construction note; WP-A tags the split `approximate_window`.
Rejected: none.
