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
| structure | long call by default. **IV ≥ 45 % → short put spread under the band floor** (2026-09-06): short put = highest listed strike at or under the floor, long put = highest strike at or under short × 0.95, credit ≥ 15 % of the width, risk = width − credit; no liquid put spread → **bull call spread** (short strike = lowest listed strike at or above the first supply band = the room target); no liquid short strike → long call | `structure_for`, `_plan_put_spread`, `pick_put_short_strike`, `pick_put_long_strike`, `credit_ok`, `call_spread_fallback`, `pick_short_strike` |
| liquidity | open interest ≥ 200, two-sided quote, bid-ask ≤ 10 % of mid or ≤ $0.15 | `liquidity_ok` |
| size | $ at risk = min(1 % of equity, $1,500) → whole contracts; premium for debit structures, width − credit for the put spread | `size_contracts` |
| pace | 1 entry per ET day, 3 open underlyings, one position per underlying | caps |
| orders | marketable limits rounded to the option tick ($0.05 under $3, $0.10 above): buy at the ask, call spread at long-ask − short-bid (`mleg`, net debit), put spread at short-bid − long-ask as ONE `mleg` package with a **negative** limit (Alpaca: "a negative value signifies a credit") — never a naked short leg | `_place` |

Put-selling was out of v1; Ajay approved it 2026-09-06 ("ok please all 3").
Only the defined-risk put **spread** is placed, never a naked put.

## Stop-loss and exit rules (on the underlying, never on the premium)

| exit | rule |
|---|---|
| thesis failed | underlying prints under the band floor − 0.5 % (same buffer as the stock lane) → close |
| target | underlying reaches the first supply band (the short strike on a spread) → close |
| time | DTE ≤ 7 → close |
| earnings | earnings within 2 days → close |
| take profit (put spread only) | the spread can be bought back for ≤ 25 % of the credit received → close (`take_profit_reason`, quotes read once per tick per open credit position) |
| max loss | the premium paid (long call / debit spread); width − credit (put spread) |

Closes are marketable limits: long leg sold at the bid, short leg bought
back at the ask, **short leg first** so there is never a naked short. The
quotes come from the position's own option type (`otype` call / put). A
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
- Put-spread P&L: the position stores `debit = -credit`, so the same
  `(close net − debit) × 100 × qty` realises both structures; the journal's
  expectancy divides by `max_loss` (the $ actually at risk).

## Builder defaults (2026-09-06, put spread) — change on Ajay's word

`PUT_SPREAD_WIDTH_PCT` 5, `MIN_CREDIT_PCT_OF_WIDTH` 15, `TAKE_PROFIT_PCT_OF_CREDIT`
25. Pinned in `tests/test_trading_contracts.py`.

## The why line (2026-09-08)

Ajay: *"There was no journal on why we entered INTC."* Every open and closed options position now
carries `narrative` — built on read by `options_lane.narrative(doc)` from the position doc alone
(nothing invented; a missing field drops its sentence), in the stock lanes' journal voice:

> Bought INTC — 1 × Oct 9 call ($100 long) @ $9.7 ($970 at risk). Options lane entry (paper
> Auto-Pilot, owner rules): the stock printed 101.2 in the demand band 100.61–104.19 (1 touch);
> room +39.8% to 141.45 (the first supply band); alert gate passed. Expiry 2026-10-09, 31 DTE
> inside the 28–60 window; earnings 2026-10-22, after expiry. Long $100 call = highest strike at
> or under the band top with delta 0.61 (0.55–0.75). IV 64% ≥ 45% asked for a put spread under
> the floor — INTC261009P00100000: open interest 137 < 200 — then a bull call spread: no liquid
> strike at or above the target 141.45 — so a long call. Size: 1 contract, $970 at risk inside
> the $992.57 budget. Exits on the stock, never the premium: under 100.11 → close; at 141.45 →
> close; DTE ≤ 7 (by 2026-10-02) → close; earnings within 2 days → close.

Closing / closed positions append the exit and the realized result. To say *why this
structure*, the entry now keeps `structure_reason` (`put_spread_fallback`, `spread_fallback`
from the plan) and `budget` on the doc; INTC's were backfilled from its `options_entry` ledger
row. The Auto-Pilot ▸ Options tab prints the line under each position row
(`data-testid="options-why"`). Tests: `test_options_lane.py` (the INTC doc word for word, closing /
closed / sold put spread / cheap-IV variants, NEGATIVE empty doc; the entry keeps the reasons;
`_public` carries the narrative), `OptionsLaneTab.test.tsx` (one why row per position that has
one).
