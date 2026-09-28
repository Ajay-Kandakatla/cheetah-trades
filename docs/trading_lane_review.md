# Chart Maps lanes — the daily loss review (2026-09-27)

Ajay 2026-09-27: "analayze losses everyday with a routine or something and restategize and
confirm with me". His answer on pausing: **no auto-pause** — a daily review plus
Confirm / Dismiss cards.

Code: `backend/trading/lane_review.py`. Program: `docs/trading_chart_maps_lanes.md`.
UNMEASURED forward paper measurement — every prior is null, inverted or unmeasured; judge in
R, not dollars.

## What runs

`python -m trading.lane_review [--day YYYY-MM-DD] [--dry]` after the close (17:00 ET on
session days; weekends and NYSE holidays return `{"skipped": ...}` and write nothing):

1. **Broker fills first.** Market exits (watchdog stop, SEPA distribution sell, hot pullback
   exit, flatten) have no fill price in the ledger. The job pages the broker's closed orders
   (`closed_orders_since`, 500 per page, `after` = the last row's `submitted_at`) and
   `journal.resolve_exit_fills` caches each trade's sell VWAP in `journal_exit_fills`. THEN
   `journal.reconcile()`. If the broker cannot be read, the review still runs and its summary
   says the market-exit prices are **approximate** (the tick's last print, marked `~`).
2. **Score** every strategy since `cm_program_started`: stock round-trips from the journal,
   0DTE from `zero_dte_positions`, options from `options_positions`.
   - win % with a 95% **Wilson** interval (percent);
   - expectancy in R with a **seeded percentile bootstrap** (B = 2000, seed 20260927);
   - R: stocks = realized $ / (qty x (entry - placed stop)); 0DTE = realized $ / (fill x 100
     x qty x PREMIUM_STOP_PCT); options = realized $ / max_loss;
   - an unpriced close counts in `n_unpriced` and stays out of win % and expectancy; an
     approximate one counts in `n_approx`.
3. **Loser lines** (Rule #9), one per losing close today:
   `SYM −1R −$50 · in: 🎯 READY, band 9.37–9.59, room +6.2% → 11 (Quick Reversal, cm-lanes-v1)
   · what happened: shakeout: … · out: stop` — the entry read comes from `cm_lane_entries`
   (the snapshot the lane bought from), the class from the trade autopsy. Every line he
   reads says "reversal", never the other word.
4. **Proposals** — written as `proposed`, never applied here:
   - **pause** (`cm_lanes: {sid: false}`) only at n ≥ 20 closed trades with the WHOLE
     expectancy interval below zero (autopsy plan rule #18);
   - **loss class** at ≥ 3 losses of one autopsy class for one strategy: `chased` on the
     zone lanes → `zone_edge_rules.demand_residents: false` only when it is on (default is
     already strict: nothing proposed); `band_failed` → `min_touches: 2` only when below 2;
     everything else is a code-level card (index filter, stop buffer, time stop or
     confirmation wait, entry width vs band, entry-distance cap, band selection);
   - a dismissed card comes back only when its evidence count grows; a confirmed / TODO card
     never comes back.

One `lane_reviews` doc per day (`_id` = the day), cards in `lane_proposals`. `--dry` writes
nothing at all (no fills cache, no reconcile, no review, no cards).

## His decision

- **Confirm** a config card: applies exactly that change — only `cm_lanes`, `cm_lane_caps`,
  `zone_edge_rules`, validated by the same validators as `POST /trading/config`
  (`program_caps.validate_updates`, `zone_edge_entry.validate_rules`) — and ledgers
  `lane_proposal_confirmed` with `before` / `after` / `by`.
- **Confirm** a code card: status `todo`, a ledger row, and nothing in the engine changes.
- **Dismiss**: status `dismissed`, ledgered `lane_proposal_dismissed` with the evidence.
- A decided card cannot be decided again (409).

The review itself never writes `trading_config` and never touches an order.

## Routes (admin only)

| Route | Returns |
|---|---|
| `GET /trading/review/latest?format=full` | the newest review + `proposals_open` + `link` |
| `GET /trading/review/latest?format=summary` | the compact read the Claude routine consumes: `day, built_at, headline, strategies[{sid, label, n_closed, win_pct, win_ci, exp_r, exp_r_ci, total_usd, today{entries, losers}}], losers, proposals_open[{id, sid, title, level}], summary_lines, link` |
| `GET /trading/review?day=YYYY-MM-DD` | that day's doc, 404 when none |
| `POST /trading/review/proposals/{id}/confirm` | `{id, status: confirmed\|todo, applied}`; 404 unknown, 409 already decided, 400 invalid |
| `POST /trading/review/proposals/{id}/dismiss` | `{id, status: dismissed}`; 404 / 409 as above |

Proposal fields: `id, sid, kind (pause | class:<name>), level (config | code), change {key,
value} | null, todo, title, evidence, status, created_day, updated_day`.

## Tests

`backend/tests/test_lane_review.py` (26): Wilson edges, the seeded bootstrap, a closed day
writes nothing, fills resolve before the reconcile, 500-order paging, an unreadable broker
says approximate, a dry build writes nothing, n 19 vs 20 for a pause, 2 vs 3 for a class,
dismissed cards return only on more evidence, demand_residents only when on, the loser line
reads `cm_lane_entries` and never says the other word, the 0DTE R formula, SEPA-sell exits
counted and unpriced closes kept out of expectancy, Confirm config / code / twice, Dismiss,
and the routes (403 / 404 / 409 / 400).
