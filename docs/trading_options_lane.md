# Auto-Pilot options lane (paper)

**Ask (Ajay 2026-09-06):** "create a new tab on the Auto pilot on options
trading and paper trade with it please. Include our supply demand rule we
defined and any others that you think may be needed."

**Basis:** owner rules from the 2026-09-06 chat (KLAC bounce discussion). No
book. Supply & Demand scope only — no Minervini cites anywhere in this lane
(`feedback_sepa_book_scope`). Paper account: Alpaca paper, options level 3
(verified 2026-09-06: `options_approved_level 3`, options buying power
~$79.7k). Decision support, not advice.

Code: `backend/trading/options_lane.py` (rules + lane), Alpaca helpers in
`backend/trading/broker_alpaca.py` (`option_contracts`, `option_snapshots`,
`submit_option_order`, `submit_option_spread`, `option_positions`), engine
hooks in `backend/trading/exit_engine.py`, routes in `backend/trading/api.py`,
tab in `frontend/src/components/OptionsLaneTab.tsx`.

## Stock-pick rules (what it buys)

| rule | value | where |
|---|---|---|
| signal | the SAME demand-zone touch the stock lane buys: a zone-edge `near_demand` row (tier in / near) | `zone_edge_entry.read_candidates` |
| gate | ≥ 5 % room to the first band overhead, print ≤ 1 % above the band top, cap ≥ $1B, signal ≤ 3 min old, no new entry after 15:45 ET | `zone_edge_entry.alert_gate`, `alert_gates` |
| underlying | price ≥ $20 | `MIN_UNDERLYING_PRICE` |
| expiry | nearest listed expiry with 28–60 days; skipped if an earnings date sits inside [today, expiry] | `MIN_DTE`, `MAX_DTE`, `sepa.earnings_watch` |
| long strike | highest listed strike **at or under the band top** whose delta is 0.55–0.75 (in the money the moment the bounce starts); falls back to the highest liquid strike under the top when the feed carries no greeks | `pick_long_strike` |
| structure | long call; **bull call spread** when the chosen call's IV ≥ 45 % (short strike = lowest listed strike at or above the first supply band = the room target); no liquid short strike → long call | `structure_for`, `pick_short_strike` |
| liquidity | open interest ≥ 200, two-sided quote, bid-ask ≤ 10 % of mid or ≤ $0.15 | `liquidity_ok` |
| size | premium at risk = min(1 % of equity, $1,500) → whole contracts | `size_contracts` |
| pace | 1 entry per ET day, 3 open underlyings, one position per underlying | caps |
| orders | marketable limits rounded to the option tick ($0.05 under $3, $0.10 above): buy at the ask, spread at long-ask − short-bid (`mleg`, net debit) | `_place` |

Put-selling (short put / put spread under the band floor) is **not** in v1:
assignment and margin need the owner's separate yes.

## Stop-loss and exit rules (on the underlying, never on the premium)

| exit | rule |
|---|---|
| thesis failed | underlying prints under the band floor − 0.5 % (same buffer as the stock lane) → close |
| target | underlying reaches the first supply band (the short strike on a spread) → close |
| time | DTE ≤ 7 → close |
| earnings | earnings within 2 days → close |
| max loss | the premium paid (long call / debit spread) |

Closes are marketable limits: long leg sold at the bid, short leg bought
back at the ask, **short leg first** so there is never a naked short. A
position is `closing` until every leg is gone at the broker, then the fill
prices from the closed orders realise the P&L (`options_exit` row, push).

## Engine seams

- Tick step **(k)** after the catalyst lane: manage open contracts, then at
  most one new entry. Fenced: a failure here never touches stock protection.
- The stock protect / ratchet / watchdog loop and `status()` **skip
  `asset_class == "us_option"` rows** — a contract never gets a stock stop.
- Flag `options_entry` (default OFF, strict boolean on `POST /trading/config`);
  arming still gates every order; disarmed → dry-run ledger rows only.
- A broker without the options helpers (the sim) gates the lane off.
- State: Mongo `options_positions` (one doc per position: legs, debit,
  expiry, DTE, IV, delta, band, stop / target underlying, order ids, status
  open → closing → closed, realized_pnl) and `options_lane_state` (one row
  per symbol per day: entered / blocked / dry_run / error).
- Ledger kinds: `options_entry`, `options_blocked`, `options_close_sent`,
  `options_exit`, `options_disabled` (once a day, only when the lane is ON
  but gated).
- Journal: `GET /trading/journal` → `summary.by_strategy.options_zone`
  (n / open / closed / wins / losses / win rate / expectancy on premium /
  realized P&L) merged from `options_lane.journal_block()`.

## Endpoints

- `GET /trading/options` — `{status, armed, mode, recent_closed}`; `status`
  = `status_block()` (enabled, caps, rules, settings, open positions,
  today's attempts, journal).
- `POST /trading/options/close/{underlying}` (admin, armed) — close now.
- `POST /trading/config {"options_entry": true|false|null}`.

## Rules panel

`GET /supply-demand/rules` carries an `options` section built from the same
constants, so the ℹ️ Rules pill on the tab can never drift from the code.

## Tests

`backend/tests/test_options_lane.py` (pure rules, entries, exits, engine
integration, journal merge, close_now), the `test_options_lane_2026_09_06_*`
guard in `backend/tests/test_trading_contracts.py`,
`frontend/src/components/OptionsLaneTab.test.tsx`.

## Known limits (v1)

- Quotes come from Alpaca's **indicative** options feed; weekend / pre-open
  quotes are wide, which the liquidity rule rejects until the session is live.
- One close order per leg per tick; an unfilled close is re-sent by the
  next minute's tick with a fresh quote (no market orders on contracts).
- IV is the chosen contract's implied volatility, not an IV rank.
