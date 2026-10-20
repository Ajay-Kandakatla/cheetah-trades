# Auto-Pilot 🚩 Gajjala lane (paper) — his A+ ENTRY alerts, GG's trade math

Ajay 2026-10-20 (~09:4x ET), verbatim:

*"in the autopilot can you stop rest of the strategies and only use the Gajjalas strategies please."*

Code: `backend/trading/gajjala_entry.py`. Engine seam: `trading/exit_engine.py` tick step **(n)**, every minute in
RTH, after the 🔥 lane (m) and before the journal (g). Tab: `/trading?view=gajjala` (GET `/trading/gajjala`, admin).
**OWNER RULES — no book, no cites.** Paper only: the lane refuses a live broker. Not advice.

## READ THIS FIRST

- **UNMEASURED.** The 2026-10-14 study of his five setups read no edge (`docs/gajjala/study_2026_10_13.md`, run 2,
  push-fill row). This lane trades them on paper so the fills can be read — not because they are measured.
- The three-lane rule (never add a lane without his call) is satisfied by his 2026-10-20 ask.
- The other lanes were switched off live the same morning (`auto_entry`, `zone_edge_entry`, `catalyst_entry`,
  `options_entry`, `zero_dte_entry`, `hot_pullback_entry` all false; `armed` true). This lane is ON by default
  (`gajjala_entry`, code default true).
- The house safety floors still apply by default (`gajjala_floors` true) — most of his names are under $2 or small
  caps, so **most alerts are skipped and counted** (HIS CALL #0).
- The cron container runs the tick: the lane ships only when `cron` is redeployed with `api` and `frontend`.

## What it trades

| | |
|---|---|
| Signal | Today's 🚩 A+ ENTRY pushes that **reached his phone**: a live `GG:{date}\|{SYM}\|{setup}` claim in state `pushed` in `gajjala_alerts`, read through the 🏁 Track record's own reader (`ledger.alert_of(doc, "aplus")`, line `live`, date = today ET). Never a `SHADOW:` claim, a `#state` refusal, a `REPLAY:` doc, a 🧠 potential or another day's alert. All five setups. |
| Window | orders **09:45–15:30 ET** (`GC.LEDGER_FILL_FROM_ET` → regular close − `GAJJALA_ENTRY_CUTOFF_BEFORE_CLOSE_MIN` 30; 12:30 on a half day). After-hours A+ (16:00–20:00 ET) do push; the lane never trades them (HIS CALL #2). |
| Freshness | an alert first seen more than `GAJJALA_SIGNAL_MAX_AGE_MIN` = 20 min after it rang is refused `stale` (HIS CALL #3). |
| Caps | `GAJJALA_MAX_ENTRIES_PER_DAY` 3 orders a day (an unfilled one does not count, HIS CALL #11), `GAJJALA_MAX_OPEN` 3 in flight or open, one position per name (a name already held at the broker or by another lane doc is `held`, HIS CALL #10). The account's five-position ceiling (p.312, in `entries`) still applies (HIS CALL #7). |

## Entry / exit math (GG's trade math)

The 🏁 grader (`ledger.grade`) fills at **max(trigger, the open of the first minute whose high reaches the trigger)**
and wins at **fill + 1R**. A push recipient cannot fill at the trigger inside the entry bar, so the lane follows the
push-fill rule:

1. each tick, live last = `sepa.prices` last trade, else its price (never `prev_day_close`), else the broker's last;
2. last under the trigger → `waiting` (re-read every tick until the cut-off; at the cut-off `never_triggered`);
   last at or under the stop → `dead`;
3. **E = last × (1 + `GAJJALA_CHASE_PCT` 0.5 / 100)**, rounded UP onto the broker grid; E ≥ trigger + 1R → `missed`
   (HIS CALL #1, #9);
4. stop **SL = the alert's stop rounded DOWN** (never up into the structure); target **TP = E + `R_MULT` × R**
   (R = trigger − stop) rounded UP;
5. a grid that moves the stop or the +1R distance by more than `GAJJALA_MAX_ROUND_R_PCT` 10% of R → `rounding`;
   E − SL or TP − E under `MIN_STOP_GAP_USD` $0.01 → `broker_gap` (Alpaca refuses that bracket; the target side
   bites when R sits between $0.005 and $0.01);
6. size = min(⌊equity × 0.5% ÷ (E − SL)⌋, ⌊equity × 10% ÷ E⌋, ⌊cash ÷ E⌋) on ACCOUNT equity (HIS CALL #4);
   0 shares → `size`. No streak / progressive multiplier (HIS CALL #5);
7. ONE **day** limit bracket through `entries.enter` (the one chokepoint); not filled in `GAJJALA_FILL_WAIT_SEC`
   180 s → cancelled, `unfilled`, no retry; a partial fill on the cancel stays open with the filled quantity;
8. flat at **15:55 ET** (regular close − 5; 12:55 on a half day) through `exit_engine.flatten`; a position carried
   past its date is flattened at the next tick. The doc moves to `closing` only when the flatten closed the position
   or queued it; a broker error that did neither keeps it `open` and the next tick tries again.

Worked examples (equity 100,000, cash 100,000):

| Name | trigger / stop | R | last | E | TP | SL | qty | risk |
|---|---|---|---|---|---|---|---|---|
| SAIQ | 4.46 / 4.31 | 0.15 | 4.48 | 4.51 (4.5024 up) | 4.66 | 4.31 | 2,217 (the 10% notional cap; risk alone 2,500) | $443.40 · notional $9,998.67 |
| DRMA | 0.8744 / 0.861 | 0.0134 | 0.8790 | 0.8834 | 0.8968 | 0.8610 | 11,319 | $253.55 |
| HODO | 0.0753 / 0.0709 | 0.0044 | 0.0755 | 0.0759 | — | 0.0709 | — | `broker_gap`: E − SL = 0.005 < $0.01 |

The 2-decimal counter-example: before 2026-10-20 every stock price went to Alpaca as `round(x, 2)`. DRMA would have
gone out as 0.88 / 0.90 / 0.86 — the +1R distance 0.0134 becomes 0.02, **+49% of R**. Alpaca accepts 4 decimals
under $1.00 and 2 at or over (docs.alpaca.markets/docs/orders-at-alpaca, fetched 2026-10-20), so the broker layer
now sends every STOCK price on that grid (`broker_alpaca.price_decimals / round_price / price_str`, re-exported by
`trading/broker.py`; the sim stores the same decimals). Option orders keep their 2-decimal ticks.

Exits recorded on the lane doc: `target` (the bracket's limit leg), `stop` (its stop leg), `flatten` (15:55),
`owner` (the tab's Close), `carried` (past its session). P&L = (exit − fill) × qty; R multiple = (exit − fill) ÷ R,
half-up to 2 decimals.

## Floors (HIS CALL #0)

`gajjala_floors` ON (default): the house floors (`trading/safety_floor.py`: share price ≥ $2.00, a known market cap
≥ $700M) are checked at the plan's entry price before any order and again inside `entries.enter`; a blocked name is
`skipped` with skip kind `floor` and counted on the tab ("N skipped by the floors today"). OFF waives the two blocks
for this lane only — `entries.enter(floors="gg")` is refused from any other strategy — and records them as warnings
on the entry ledger row (`overrides.floor_blocks_waived`).

Flip it from the tab's floors switch (it asks first when turning them off), which sends
`POST /trading/config {"gajjala_floors": false}` (`{"gajjala_floors": true}` turns them back on) — the same line
the tab serves as `floors_flip`.

## Engine seams

- `exit_engine.get_config`: `gajjala_entry` (default true), `gajjala_floors` (default true),
  `last_gajjala_disabled_day`. POST `/trading/config` takes all three lane flags strictly (`gajjala_entry`,
  `gajjala_floors`, `hot_pullback_entry`; null → true; anything not a boolean → 400).
- Tick step (n): `summary["gajjala_lane"] = gajjala_entry.run(broker=broker, cfg=get_config())`, fenced like (m).
  `/trading/status` carries `gajjala_lane` = the tab's `status` block.
- State: Mongo `gajjala_lane`, one doc per alert, `_id` = the alert `_id`; the claim is `insert_one` (a duplicate key
  = already claimed) and every state change is conditional on the state it leaves (overlapping ticks cannot
  double-order). States: waiting → ordering → ordered → open → closing → closed; terminal unfilled / skipped / dry_run.
- `entries.enter(..., target_price=, sizing=, floors=, tif=, order_intent=)`: the lane plan bypasses only the book's
  stop / target / size; armed, the p.312 count, never-average-down, earnings and price stay. `tif="day"`,
  `order_intent="gg-" + setup` (the client order id never collides with another lane or setup on the name). The
  journal tag is `gajjala` (`entries` / `journal` STRATEGIES; `autopsy` has its own label).
- Ledger kinds: `gajjala_entry`, `gajjala_skip`, `gajjala_cancel`, `gajjala_exit`, `gajjala_disabled` (a live broker,
  once a day, dry run). Disarmed: the plan is recorded as `dry_run` on the lane doc — **no order, no ledger row, no
  cancel**.
- Tab: GET `/trading/gajjala` (admin) — `status`, `today` (today's pushed A+ LEFT JOIN the lane docs, every alert
  has a `fate_text`, an alert with no doc is `not_seen`), `recent` (last 40 of prior days), `journal`; POST
  `/trading/gajjala/close/{symbol}` (admin, armed) cancels the order or flattens the position; a close the broker
  refused answers `502` with the broker's errors joined as the `detail` (critic 2026-10-20 — the tab reads the HTTP
  status and prints the served detail; a `200` with `ok: false` left the row open with no error line).

## Tests

```bash
docker run --rm --network none -v /Users/ajay/clinet-test/cheetah-market-app:/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_gajjala_lane.py tests/test_entries_lane_plan.py tests/test_broker_price_precision.py
```

`test_gajjala_lane.py` (the lane: constants, gate, read, claim, plan math incl. the three examples, every refusal,
clock, fill wait, exits, caps, disarmed, floors, served text, tab payload, API), `test_entries_lane_plan.py` (the
chokepoint seam, the default path unchanged), `test_broker_price_precision.py` (the grid; options NEG). Pins moved:
`test_trading_contracts.py` (STRATEGIES, the enter signature, the new seams test), `test_autopsy.py`,
`test_safety_floor.py` (the lane buys through `entries.enter`), `test_rules_info.py`, `test_journal.py`, and the
explosive / short-interest source guards list the lane.

## Known limits (v1)

- The engine still acts on lane positions: SEPA distribution auto-sell, the 3R breakeven ratchet, the watchdog, and
  the streak step counts a lane stop into `consecutive_losses` (HIS CALL #6, #5).
- Legs are `day`: they expire at 16:00 ET; a 15:55 flatten that keeps failing leaves a position without broker legs
  overnight until the next tick's carried flatten / adopt-and-protect. A 403 "held for orders" is queued by
  `exit_engine.flatten` and the queue drains on the NEXT tick's step (a2), not the same tick.
- Same-day round trips need paper equity ≥ $25k (PDT) — not probed.
- `trade_closed` gain_pct in the engine stats reads the limit E, not the fill (small skew).
- A mid-day deploy makes the earlier alerts `stale` by design.
- Switched OFF (`gajjala_entry` false) stops NEW entries only (HIS CALL #13): on paper, armed and with the market
  open, the tick still manages what the lane holds — the fill-wait cancel, the 15:30 cut-off cancel, the 15:55 and
  carried flatten — and claims and buys nothing. While the market is closed the gate still returns first; the next
  open tick flattens anything carried.

## Fixes after the review (2026-10-20)

The critic's pass on the first build moved six things, each with a test in `tests/test_gajjala_lane.py`:

- A flatten that neither closed nor queued (a non-403 broker error) no longer moves the doc to `closing`; it stays
  `open` and is retried every tick (then as `carried`); the error lands in the tick's `errors`. A `closing` doc
  whose name is still in the account is flattened again at / past the flatten minute (or carried), unless the
  engine's flatten queue already holds it. The tab's Close answers `ok: false` (state `open`) when the broker
  neither closed nor queued.
- OFF stops new entries only (HIS CALL #13); the served `disabled_text` says so in one sentence.
- A disarmed tick's `gajjala_skip` ledger rows are written `dry_run: true`.
- `broker_gap` also refuses TP − E under $0.01.
- After a cancel the order is read again (else the name's position) before choosing `open` vs `unfilled`, so a
  partial fill landing between the read and the cancel is kept. The `ordering` move records the deterministic
  client order id; a doc still `ordering` after `GAJJALA_FILL_WAIT_SEC` (an overlapping tick may still be inside
  `entries.enter` before that) is reconciled by it: the broker has the order → `ordered`, a position → `open`,
  neither → `unfilled`, "the order never reached the broker — slot released".
- run()'s entry-window gate and the conditional state change (two overlapping ticks reading the same `waiting`
  doc send one bracket) now have tests that fail when either is removed.

## Differences from the 🏁 grader

The lane trades the alerts the 🏁 Track record grades, but it is not the same trade:

1. Target: the lane's target is E + R keyed off its LIMIT E; the grader's is fill + R with fill = max(trigger, the
   open of the first minute whose high reaches the trigger) (HIS CALL #14).
2. `dead` (last at or under the stop before any order) is final for the lane; the grader still fills on a later
   minute whose high reaches the trigger.
3. Thin-R alerts (R under `LEDGER_MIN_R_PCT` of the trigger) are refused by the lane; the grader still grades them.
4. The trigger test is the last trade at the tick, not the minute bar's high.
5. The lane is flat at 15:55 ET (regular close − 5); the grader marks to 16:00.

## HIS CALL (never decided here)

- **HIS CALL #0** Floors: `gajjala_floors` default ON → his $2 / $700M floors skip most A+ names (counted, one-line
  flip). OFF = the lane trades GG's own universe on paper.
- **HIS CALL #1** Entry: a day limit 0.5% over the last trade once the tape trades the trigger (the 🏁 / push-fill
  rule), one order per alert, cancelled after 180 s. Alternatives: (a) a limit AT the trigger (fills only on a
  pullback); (b) market; (c) retries.
- **HIS CALL #2** Horizon: same session (cancel 15:30, flat 15:55) vs hold into the next session (GG's "next" column,
  gtc legs); after-hours A+ never traded vs bought next morning.
- **HIS CALL #3** Stale line 20 min at first sight.
- **HIS CALL #4** Size off account equity (0.5% risk, ≤ 10% notional ≈ up to $10k a position on ~$100k) vs
  `equity_cap` like every other stock lane.
- **HIS CALL #5** Streak and progressive governors not applied to this lane.
- **HIS CALL #6** SEPA distribution exits still apply to lane positions (exempt the lane?).
- **HIS CALL #7** The p.312 five-position account ceiling still applies (existing holdings can block the lane).
- **HIS CALL #8** Thin-R refusal at `LEDGER_MIN_R_PCT` 0.5% (mine).
- **HIS CALL #9** "Missed" bound = trigger + 1R.
- **HIS CALL #10** One position per name (a second setup on a held name is skipped).
- **HIS CALL #11** Unfilled orders do not count toward the 3-a-day cap.
- **HIS CALL #12** Tab placement right after Dashboard; 🚩 first in the journal table.
- **HIS CALL #13** Switched OFF stops NEW entries only — an off lane still manages what it holds (the fill-wait and
  cut-off cancels, the 15:55 / carried flatten). Decided by the lead 2026-10-20; the served `disabled_text` says
  it. The alternative: OFF leaves held lane positions alone (the old behaviour; they then ride without broker
  legs past 16:00).
- **HIS CALL #14** Target from the fill (the grader's fill + 1R) instead of from the limit E + 1R (today's v1).

UNMEASURED — his setup, not a buy signal. Paper only. Not advice.
