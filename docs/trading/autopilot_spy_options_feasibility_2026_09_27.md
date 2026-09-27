# SPY options on Auto-Pilot: feasibility memo (2026-09-27)

**The ask (Ajay, 2026-09-27):** "try and do SPY options buying please? in the auto pilot daily, high frequency trades with monitoring min to min to make sure it sell on time? I would like to execute atleasst 5 trades if possible on SPY. based on the demand entries with a minimum of at least one trade based on volatility of the market."

**Short answer:** the broker, the account and the plumbing can all do it. The existing `trading/zero_dte_lane.py` already trades SPY 0DTE on paper, with a check every minute. What's missing is **evidence**. No SPY intraday trigger in the app beats a placebo. The standing S/D buy gate passes on SPY about **1 session in 25**. So "5 a day" and "1 volatility trade a day" would be quotas, which means forced entries. Four code or rule defects also need his call first (see Blockers).

Every number below comes from `backend/scripts/autopilot_autopsy_spy_options_feasibility.py`, which is read-only. It was run 2026-09-27 18:56 UTC. The result JSON was saved to the session scratchpad `spy/result.json`. Rerun it with:

```bash
docker exec -i -w /app cheetah-market-app-api-1 python - < backend/scripts/autopilot_autopsy_spy_options_feasibility.py
```

---

## 1. Pattern Day Trader rule

| Question | Answer | Source |
|---|---|---|
| Is PDT still enforced? | **No. It has been retired.** The SEC approved the FINRA Rule 4210 amendments on 2026-04-14. Alpaca put its new Intraday Margin Framework in place on **2026-06-04**. It removed "the Pattern Day Trader designation and all PDT-based account restrictions", the $25,000 minimum, and "day trade counting". | [Alpaca blog](https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/), [WilmerHale](https://www.wilmerhale.com/en/insights/client-alerts/20260423-sec-approves-amendments-to-finra-rule-4210-replacing-day-trading-margin-requirements-with-a-modernized-intraday-margin-standard), [FINRA RN 26-10](https://www.finra.org/rules-guidance/notices/26-10) |
| What replaces it? | Intraday buying power, based on real-time margin excess. "Pre-Trade Checks will reject orders" that would create a margin deficit. A deficit leads to an intraday margin call, which must be met within 2 business days. | [Alpaca intraday margin](https://docs.alpaca.markets/us/docs/the-intraday-margin-rule) |
| Options day trades | They are no longer counted. There is no day-trade count at all. Long premium is paid in full from `options_buying_power`. | same |
| API fields | `pattern_day_trader`, `daytrade_count` and `daytrading_buying_power` are deprecated; integrations had to stop using them by 2026-07-06. **Our paper account returns `null` for all three.** No app code reads them (checked with grep). | Alpaca blog; live read |
| Our paper account (read-only `broker_alpaca.account()`, 2026-09-27) | mode **paper**, ACTIVE; **equity $88,938.60** (last_equity $88,950.60; the 2026-09-14 memory figure of $91,958 is stale); cash $66,482.98; **options_buying_power $76,699.79**; **options_approved_level 3 / options_trading_level 3**; multiplier 4; trading_blocked false. `/v2/account/configurations` has no `pdt_check`. | live read |

**Not a blocker.** A 5-a-day SPY lane cannot trip PDT. The only per-order limit is buying power.

## 2. Alpaca options on paper

| Item | Fact | Source |
|---|---|---|
| Approval level to BUY calls or puts | **Level 2** (L1 = covered call and cash-secured put; L3 = spreads). Paper accounts get **L3 by default**. Ours is L3. | [Options overview](https://docs.alpaca.markets/docs/options-trading-overview), [L3 in paper](https://docs.alpaca.markets/changelog/multi-leg-level-3-options-trading-in-paper) |
| SPY 0DTE / 1DTE | Available. On Monday 2026-09-28 the live Massive chain lists 314 SPY contracts expiring that day and 310 expiring 09-29. | script Part C |
| Order types | **Market and limit only**, `time_in_force=day` only, whole-contract qty. **No stop or stop-limit, no extended hours, no notional orders.** Multi-leg (`order_class=mleg`) is supported, and `options_lane.py` already uses it. **No bracket or OCO on options**, so there is no stop resting at the broker. The stop exists only inside our tick. | Options overview |
| Expiry-day cutoffs | Orders on expiring **SPY/QQQ** contracts must be in **before 15:30 ET** (15:15 ET for other names). Later orders "will be rejected". Expiring positions are **auto-liquidated at 15:45 ET** for broad-based ETFs (15:30 ET for others). The docs don't say whether sell-to-close orders are exempt. **Don't rely on it.** | [0DTE cutoffs](https://alpaca.markets/support/what-are-the-cutoff-times-for-trading-0dte-options-on-alpaca), [0DTE guide](https://alpaca.markets/learn/how-to-trade-0dte-options-on-alpaca) |
| Paper fills | Paper fills are matched against the NBBO once an order is marketable (a buy limit needs to be ≥ the ask). Order size is **not checked against NBBO size**. Partial fills happen on a random 10% of orders. **Not simulated:** slippage from latency, market impact, queue position, price improvement, regulatory fees. | [Paper trading](https://docs.alpaca.markets/docs/paper-trading) |
| Fees (live) | $0 commission. Regulatory fees still apply: ORF $0.02295 per contract (buy and sell), OCC $0.025 per contract, TAF $0.00329 per contract (sells only). Paper does not charge them. | [Regulatory fees](https://docs.alpaca.markets/us/docs/regulatory-fees) |
| Options data feed | `broker_alpaca.option_snapshots` uses `feed="indicative"`. An Alpaca staff member says of that feed: "the quotes are not actual OPRA quotes", and "trades are delayed by 15 minutes". Real OPRA data needs the paid Algo Trader Plus plan. | [Indicative feed](https://forum.alpaca.markets/t/what-is-the-indicative-pricing-feed-for-options/14595), [paper pricing](https://forum.alpaca.markets/t/paper-trading-options-pricing/17795) |

## 3. Data for checking positions every minute

- **Engine cadence:** cron runs `* 9-16 * * 1-5 python -m trading.exit_engine tick` (backend/crontab:914), so there is one tick per minute from 09:00 to 16:59 ET. The 0DTE lane is tick step (l). That means minute-by-minute monitoring **already exists**.
- **SPY 1-minute bars:** these come from Massive Stocks at real-time. `daytrading/data.py` caches finished days in Mongo `intraday_cache`: **123 full SPY sessions, 2026-04-01 → 2026-09-25**. Today's bars are fetched again on every call. Signal Lab reads them through `TF.intraday_raw(sym, "15m")`, which returns 1-minute RTH bars.
- **SPY option quotes used to choose the contract:** these come from the Massive Options Advanced snapshot (`opex._fetch_contracts`). `last_quote.timeframe` is **REAL-TIME on 1500/1500** contracts. However, **`underlying_asset.timeframe` is DELAYED on 1500/1500**. So the `spot` used for expected move, walls and delta×spot is **15 minutes stale**.
- **Quotes used for exits:** the premium mark and the close limit price come from Alpaca's indicative feed, not OPRA. The stock-stop check uses `broker_alpaca.latest_trade`, with no `feed` parameter, so it uses the account's default feed. The Alpaca data plan wasn't checked.
- **Measured lane latency** (39 orders, Part A): signal→seen median **6.5 s** (max 90.7). Seen→order median **6.4 s** (max 59.7). Order→fill median **0.2 s** (max 125). **Signal→fill median 15.1 s.** Median hold **25.3 min**.
- **Sell on time:** close send→fill has a median of **0.2 s**, but **5 of 31 closes took over 60 s**: 73 s, 98 s, 134 s, 726 s, and **4,340 s** (QQQ 2026-09-16). The reason: the close is a day LIMIT at the (indicative) bid. It is sent again only if the broker cancels it. It is **never re-priced**, so on a falling contract it can sit above the market.
- **Option price HISTORY exists.** This corrects the docstrings in `options/zero_dte.py` and `options/zero_dte_history.py`, which say "no intraday option price history on this plan … cannot be backtested". That is **false today**. The Massive options key returns 1-minute bars for expired SPY 0DTE contracts on 2026-09-25 (405 bars), 2025-09-10 (395) and **2023-09-11 (405)**. It also returns `/v3/quotes` NBBO history, `/v3/trades`, and the expired-contract reference (330 contracts for 2026-09-10). **A real 0DTE option-P&L backtest, priced at the bid and ask, can now be done** (Part C).

## 4. SPY "demand entries" and volatility triggers the app already has

**What already exists** (no new method needed):

| Read | Where | Fit for SPY 0DTE |
|---|---|---|
| Signal Lab composite BUY/SELL (sweep → BOS/CHoCH, stop at the trap wick, 2R target) | `daytrading/signal_lab.py` | This is the lane's current trigger. |
| 15-minute opening-range break (ORB), Crabel/Raschke | `daytrading/signals/orb.py` (+ `signal_lab` orb_up/dn) | 0–2 per day |
| Daily index zones (board + fine) | `supply_demand/index_zones.py`, `GET /supply-demand/index-zones` | Bands are 1–4% wide (SPY board supply 749.53–779.37). The module says it "gates nothing, alerts nothing, orders nothing". |
| 15m / 60m zones + FVG + entry, stop and target | `GET /supply-demand/price-zones/SPY?tf=15m\|60m` | The 15m demand band 763.25–773.68 has a stop 1.45% away. That is about 2× SPY's daily expected move, so the premium would be gone before that stop is hit. 5m is not served (`available: false`). |
| Key levels (PDH/PDL, PMH/PML on 5m, week/month/52w) | chart key levels | Close-only alerts. No study behind them. |
| S/D buy gate (≥5% room + ≤1% above demand) | `supply_demand/alert_gates.py` | See below. |
| Volatility: VIX level/regime (15/20/30), VIX change, 252-day percentile, SPY IV term 9d/30d/90d | `sepa/iv_read.py`, `sepa/iv_term.py`, `GET /market/iv` | Latest: VIX 14.87 (calm, 7.5th percentile). SPY IV 11.7 / 13.1 / 14.4, contango. |
| 0DTE ATM expected move, dealer regime PINNED/AMPLIFYING, walls, flip | `options/zero_dte.py`, `options/opex.py` | Live only. `gex_history` holds 8,015 docs, **none of them SPY**. |

**Measured on SPY's own 1-minute tape** (Part B, 123 sessions, lane window 09:45–14:30, stock exits only, flat at 15:45). The placebo uses the same side and the same stop distance at a random time, and the CI is a session-clustered bootstrap. **These are underlying R values, not option P&L.**

| Trigger | Count | Mean R (95% CI) | vs placebo | Stop-outs |
|---|---|---|---|---|
| Composite, every tag | **12.7 per session** (median 13, min 7; 100% of sessions have ≥5) | **−0.015** (−0.086, +0.059) | −0.062 (−0.123, +0.001) | **62.3%** (59.9–64.7) |
| Composite, first tag of the day (what the lane actually takes) | 1 per session | +0.233 (−0.018, +0.483) | whole-window +0.239 (+0.009, +0.466), but **time-matched ±15 bars −0.170 (−0.333, −0.006)** | 56.1% (47.3–64.6) |
| ORB | 1.02 per session | +0.131 (−0.104, +0.378) | +0.047 (−0.191, +0.294) | 54.8% (46.1–63.2) |

- Composite stops sit a median **0.089%** from entry (about $0.69 on SPY), which is inside 1-minute noise. SPY's median session range is 0.79%.
- The first tag's apparent lift comes **from the time of day**, not the tag. Against a random entry in the same ±15 minutes, the tag does **worse**.
- VIX splits are too thin to read: only 12 calm sessions and 9 elevated ones, no stress sessions.
- **Standing S/D buy gate on SPY** (Part D, 247 daily closes, demand-engine geometry): it passed on **10/247 closes = 4.0% (2.2–7.3%)**. It passed on 6.5% (4.0–10.3%) using the day's low as an upper bound. The median room to the first supply at the close was **1.19%**, far short of the gate's 5%.

**Verdict:**
- **Every SPY entry trigger we have: NO SIGNAL.** The composite is flat and slightly inverted when time-matched. ORB is flat.
- The demand gate almost never fires on SPY.
- **No volatility read has ever been measured as a trigger.**

## 5. Risks and what "at least 5 a day" implies

- **Theta:** measured on the SPY 0DTE chain on 2026-08-24, a 764 call's theta was **7.8× its own ask** (`options/zero_dte.py` docstring). Late in the day, a trade with no edge loses to theta.
- **Spread:** SPY entries paid a spread of 1.2–1.7% of premium at the ask (journal). The close is at the bid, so every round trip pays the spread in full.
- **Flatten time:** `FLATTEN_ET = 15:45` equals Alpaca's **15:45 auto-liquidation** for SPY. It is also **after the 15:30 order cutoff**, so a flatten close sent at 15:45 may be rejected. For single names on Fridays, 15:45 is after both their 15:15 cutoff and their 15:30 liquidation. This has not bitten yet: every entry so far was at 09:46–10:55 ET and every exit was by 14:20 ET.
- **Caps:** the lane allows **one entry per name per day**, `MAX_ENTRIES_PER_DAY = 3` across all 13 names, and `MAX_OPEN = 3`. A missed fill uses up a slot. **Today SPY can get at most 1 trade a day.**
- **What 5 a day means:** the composite fires about 13 times a day, so 5 SPY entries is mechanically possible. But with no edge, each one is a forced trade. The lane's own journal gives the expected result: **31 closed, 8 wins, 25.8% (13.7–43.2%)**, avg win +$446, avg loss −$178, **mean −$16.55 per trade (−$111, +$90), sum −$513**.
- **Sizing at today's equity:** min(0.5% × $88,938.60, $500) = **$444.69 of premium per trade**. At 5 a day that puts about $2.2k of premium at risk every day.

## Blockers (his call on each)

1. **No SPY trigger has an edge.** The composite is null or inverted, ORB is null, and the S/D gate fires about 4% of sessions. "≥5 a day" and "≥1 volatility trade a day" are quotas, not signals. Under Rule #10 and "ship the backtest", a named paper variant needs his yes.
2. **The PINNED skip never fires in production (bug).** `contract_for()` checks `str(row["regime"]).upper() in SKIP_REGIMES`, but `read_symbol()` returns `regime` as a **dict**. The tests pass only because their fixture uses a string. As a result, **22 of 39 orders were placed on PINNED days**. PINNED closed trades: 16, win rate 18.8%, **−$1,425** (mean −$89, CI −171..+14). AMPLIFYING: 15, win rate 33.3%, **+$912** (mean +$61, CI −107..+261). The CIs overlap, so this is not a measured edge, but it is the lane's own written rule failing to run.
3. **The flatten time collides with Alpaca's SPY 15:30 cutoff and 15:45 auto-liquidation.** A new flatten time is an owner number, so it's his call.
4. **The caps allow only 1 SPY trade a day** (one per name, 3 per day in total). New caps are his call.
5. **Execution quality:**
   - SPY entry fills were **2 of 6 (33%, CI 9.7–70%)**, against 79.5% (64.5–89.2%) for all names. The limit is set once at the Massive ask and cancelled after 180 s without a new price.
   - Closes are never re-priced (the 4,340 s case above).
   - Exits are priced off Alpaca's indicative feed.
   - The Massive snapshot's spot is delayed.

**Removed as a blocker:** "a 0DTE rule cannot be backtested". Option minute bars, NBBO history and expired contracts are all on the plan (Part C).

## Reusable as-is

- `trading/zero_dte_lane.py`: tick step (l), the paper-only gate, latency stamps, limit closes at the bid, re-send on cancel, the journal and the `/trading?view=zero_dte` tab.
- `broker_alpaca` option helpers (contracts, snapshots, single-leg and mleg orders).
- `options/zero_dte.pick_contract`: delta 0.35, spread ≤ 25%, volume ≥ 500, ask ≥ $0.20.
- `daytrading/signal_lab`, `daytrading/signals/orb.py`, `price_zones` at `tf=15m|60m`, the IV read, the dealer-gamma regime, and the `intraday_cache` tape.

## Recommended next step (not done)

Run `/measure` as a real **option-P&L replay** of the lane's rules on SPY 0DTE. Use Massive minute bars plus `/v3/quotes`, entering at the ask and exiting at the bid. Cover the first-tag and every-tag variants, split by PINNED vs AMPLIFYING, with a time-matched placebo, over 2023-09 → now. Only a positive result there should unlock a ≥5-a-day SPY variant.
