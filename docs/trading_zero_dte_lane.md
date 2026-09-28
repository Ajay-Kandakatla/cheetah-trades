# Auto-Pilot 0DTE lane (paper) — same-day options on Signal Lab tags

Ajay 2026-09-08: *"Can you also help me with doing options ODTE and Same day expire
day trading options please? I would like to see the accuracy and quick ness with
everything we have setup"* … *"Did you start the ODTE options"*.

Code: `backend/trading/zero_dte_lane.py`. Engine seam: `trading/exit_engine.py` step
**(l)**, every minute in RTH, after the options lane (k). Tab: `/trading?view=zero_dte`
(`frontend/src/components/ZeroDteLaneTab.tsx`). **OWNER RULES — no book, no cites.**
Day-trading options scope, never Minervini. Paper only: the lane refuses a live broker.

## What it trades

| | |
|---|---|
| Names | the 0DTE tab's universe (`options/zero_dte.UNIVERSE`: SPY QQQ IWM NVDA TSLA AAPL AMD META MSFT AMZN GOOGL AVGO MU). **Only a name with a same-day expiry trades** — SPY/QQQ/IWM every day, the single names on their Friday. No same-day chain = a journaled skip, never a 2DTE contract on a board called 0DTE. |
| Signal | Signal Lab's composite 1-minute **BUY / SELL** tag on today's session (`daytrading/signal_lab.events_from_frame`: a sweep, then the opposite-side structure break; stop = the trap wick, target = 2R). The tag's bar must have closed ≤ `SIGNAL_MAX_AGE_SEC` = 180 s ago. |
| Contract | BUY → the tab's **call** pick, SELL → its **put** (`options/zero_dte.pick_contract`: delta ~0.35, spread ≤ 25 %, day volume ≥ 500, ask ≥ $0.20). Massive's `O:` ticker → the OCC symbol Alpaca trades. Dealers **PINNED** (`regime_from_gex`) → skip. |
| Window | entries **09:45–14:30 ET**; everything flat by **15:45 ET**. |
| Size | premium at risk = min(**0.5 %** of equity, **$500**) → whole contracts at the ask; one contract over budget = skip. |
| Caps | **3** entries a day, **1** per name per day, **3** open. An entry limit not filled in **180 s** is cancelled and journaled `missed`. |

## Exits (in this order, every minute)

1. the clock — at/after 15:45 ET, whatever the P&L;
2. the **stock** through the signal's stop (call: ≤ stop; put: ≥ stop);
3. the **stock** at the signal's 2R target;
4. the **premium** at −50 % / +100 % off the fill (mark = bid).

Closes are `sell_to_close` **limit at the bid** (tick-rounded), never a market order on a
contract. A close order that expires/rejects is re-sent with a fresh quote.

## Accuracy and quickness — what every row records

- **Latency** (seconds): signal bar close → seen by the tick → order sent → broker fill.
  The tab shows the chain per row and the medians in the journal strip. The tick is once a
  minute and the bar closes a minute after its stamp, so ~60–120 s signal→seen is the floor
  of this design; order→fill is Alpaca paper.
- **P&L next to the stock**: `realized_pnl`, `premium_return_pct` and `stock_move_pct`
  (signal price → stock at the close of the trade). A lane that is right on the stock and
  wrong on the premium is a contract-selection problem, and this splits the two.
- The why line (`narrative`) on every row: contract, delta, spread, moves needed to double,
  dealer regime, fill time, exit reason.

## Engine seams

- `get_config()["zero_dte_entry"]` — **default ON**; `POST /trading/config
  {"zero_dte_entry": bool|null}` (null → ON). `armed` still gates orders (not armed = dry-run
  rows, no order).
- Gate: configured broker + switch + broker has `submit_option_order` / `option_snapshots` +
  **paper** (`broker.mode() != "live"`) + market open. Gated with the switch ON writes one
  `zero_dte_disabled` ledger row a day.
- State: `zero_dte_positions` (one doc per trade — the journal), `zero_dte_lane_state` (one
  attempt per `(symbol, day, signal bar)` so a tag is tried once). Ledger kinds:
  `zero_dte_entry`, `zero_dte_filled`, `zero_dte_missed`, `zero_dte_close_sent`,
  `zero_dte_exit`, `zero_dte_disabled`.
- Endpoints: `GET /trading/zero-dte` (tab payload), `POST /trading/zero-dte/close/{symbol}`
  (owner, armed). `GET /trading/status` carries `zero_dte_lane` (status block).
- Rules panel: one ⏱️ line under Auto-Pilot (`supply_demand/rules_info.py`).

## Tests

`backend/tests/test_zero_dte_lane.py` (22): owner numbers; `fresh_signal` (age window,
sweeps are not entries, naive-UTC index); sizing; `contract_for` (call/put, PINNED, no
chain, no ask, `O:` strip); `exit_reason` order incl. the clock beating a target and
the −49.6 % hold; latency + narrative; journal medians; gates (switch, live, closed market,
not armed); entry (order shape, doc, state, ledger, no double order); put side; skips;
window/caps; broker rejection; stock-stop close at the bid; close fill → P&L + stock move;
flatten; premium take/stop; fill read + stale limit cancelled; put exits; status/tab shape;
`close_now`. `test_trading_contracts.py` pins the numbers and the seams.
`frontend/src/components/ZeroDteLaneTab.test.tsx` (6) + `Trading.views.test.tsx`; frontend
contract "Trading page carries the 0DTE paper lane tab".

## Known limits (v1)

- One tick a minute: a tag is acted on 60–120 s after its bar closes. A faster loop is a
  separate decision (cost: a Massive read per name per tick).
- Same-day expiries only. Mon–Thu that is SPY/QQQ/IWM; the single names ride on Fridays.
- No placebo yet: `stock_move_pct` is the stock's own outcome, not a random-entry control.
  Two weeks of rows first, then the study.
- Quotes for exits come from Alpaca's indicative options feed; entries are priced off the
  0DTE tab's Massive read. Both are what the tab already shows.

Decision support on a paper account — not advice.

## 2026-09-27 — inside the Chart Maps lane program

The 0DTE lane is the `signals` strategy of the Chart Maps lane program
(`trading/program_caps.py`, `docs/trading_chart_maps_lanes.md`). With the program OFF (the
deploy state) nothing changes: the lane enters on its own `zero_dte_entry` switch, exactly as
before. With the program ON, `signals` is OFF by default (it is not in the frozen top ten), so
the lane stops ENTERING — `entry_reason` reads `program: signals OFF` and a `cm_lane_log` row
says why — while `_manage` still runs every tick, so open contracts keep their stops, targets
and the 15:45 flatten. In every mode an entry now passes the shared chokepoint before it is
sent: the in-flight open cap (positions + pending entries), one lane per name, and the atomic
one-entry-per-ET-minute claim. A TRANSIENT refusal (`program-wait:` — minute taken, portfolio
full) records no attempt, so the signal is retried next tick; a day cap (`program-cap:`) is
recorded as a `skipped` attempt. A filled entry is written to `program_entries` (sid `signals`,
the OCC symbol). The daily loss review scores the lane in R = realized $ / (fill x 100 x qty x
PREMIUM_STOP_PCT). UNMEASURED. Tests: `test_lanes_program_adoption.py` (program OFF still
submits; program ON + signals OFF manages but never enters; a refused claim never submits; a
day cap records a skipped attempt), `test_lane_review.py` (the R formula).
