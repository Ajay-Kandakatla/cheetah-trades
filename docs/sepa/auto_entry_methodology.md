# Auto-Entry Methodology — `backend/trading/auto_entry.py`

The Auto-Pilot's buy side: the engine enters Ajay's own picks — the output of
the app's Minervini SEPA funnel — automatically, paper account first
(started 2026-06-12, "assume you have 5k, will observe next week").

Companion docs:
- `docs/sepa/risk_management_methodology.md` — stop / target / sizing /
  streak math (TLSW pp.291-315). **FROZEN** with `trading/risk_rules.py`.
- `docs/SEPA_CONTRACTS.md` — the scanner gates that produce the candidates.

---

## 1. Where the book lives (and where it doesn't)

Auto-entry deliberately re-derives **no** book formula. It composes three
layers that are already book-cited and contract-locked elsewhere:

| Layer | Book rules | Where they are implemented |
|---|---|---|
| Candidate funnel | Trend Template (p.79, all 8 checks), Stage 2 (pp.71-72), VCP / Power-Play pivot (pp.198-205), volume-confirmed breakout (p.203), not extended past the pivot (p.224) | `sepa/scanner.py` `_is_buyable` — the scan row's `is_buyable` flag |
| Risk math | Initial stop (pp.299/301/311), profit target ≥2:1 (p.301/311), breakeven ratchet at 3R (p.308), 25% position size (p.312), losing-streak multiplier (p.304), never average down (pp.304-305) | `trading/risk_rules.py` (frozen) via `trading/entries.py` — the **only** buy path |
| Trigger timing | The book says buy the breakout "as close to the pivot point as possible" (p.224) on expanding volume (p.203); it does not prescribe tick-level automation mechanics | `trading/auto_entry.py` — the hybrid trigger below (**engine parameters**, §4) |

## 2. The candidate funnel

Per tick (market hours only), candidates are the rows of the **latest
completed SEPA scan** — read with the exact same reader `GET /sepa/scan`
uses (`sepa.scanner.load_latest()`, the file-persisted
`~/.cheetah/scans/latest.json`; Mongo holds the separate scan *history*)
— filtered to:

- `is_buyable == true` (the scanner's strict book gate, see table above),
- `score >= 70` (the scanner's BUY rating tier — owner choice, §4),
- `entry_setup.pivot` present (VCP / Power-Play base-high pivot),

sorted by `score` descending.

## 3. The hybrid trigger

For each candidate, cheapest checks first:

1. **Skip** if already held at Alpaca; entered/attempted today (per
   symbol + ET day, `auto_entry_state`); positions ≥ `risk_rules.MAX_POSITIONS`
   (5, p.312); auto entries today ≥ `MAX_AUTO_ENTRIES_PER_DAY`.
2. **Skip** if the Market Gauge **raw state** is `risk_off` (the raw verdict,
   not the normal/difficult band mapping the exit engine uses), or earnings
   are ≤ 7 days out (`sepa.earnings_watch`, same helper as manual entries —
   **no `allow_earnings` override exists in auto mode**).
3. Live quote via **one** batched `sepa.prices.bulk_live_prices` call for all
   surviving candidates. Then two entry paths:

   **a. Intraday** — all of:
   - live > pivot;
   - the **first tick we ever observed** live > pivot today landed in the
     first half of the session (`session_fraction ≤ FIRST_HALF_FRACTION`;
     the fraction is persisted as `cleared_at_frac` per symbol + ET day so a
     late-day clear can never retro-qualify);
   - projected full-session relative volume ≥ `AUTO_RELVOL_MIN`
     (`sepa.live_gate` — today's pace ÷ session elapsed vs the 50-day
     average; computed only for names that passed every cheap check);
   - live ≤ pivot × (1 + `MAX_EXTENSION_PCT`/100) — not chasing (p.224).

   **b. Close-confirmation** — if not entered intraday: the **previous
   regular-session close** finished above the pivot AND live > pivot AND
   still within the same extension cap → enter on next-morning ticks.
   No after-hours machinery; the close itself is the confirmation, so no
   RelVol floor on this path.

4. **The buy goes through `entries.enter()`** — the only order path in the
   codebase. Armed gate, equity-cap sizing, never-average-down, the earnings
   shield and the 0-share floor all re-apply there. If the scan row's
   `entry_setup.stop` sits between 1% and `risk_rules.DEFAULT_STOP_PCT` (7%)
   below the live price, that distance is passed as the requested stop — a
   *structure* stop tighter than the band default is allowed; a wider one is
   ignored (stops never widen, pp.308-309) and the band default applies.
5. Every evaluated candidate gets a per-symbol `last_eval` snapshot in
   `auto_entry_state` (`checks: {name: {pass, value}}`) so the UI can answer
   "why didn't it buy X". Ledger rows are written only for actual entries
   (`auto_entry`, with full trigger detail `{path, pivot, live, relvol,
   cleared_at_frac, prev_day_close}`) and for the **first** veto of the day
   of an otherwise-triggered name (`auto_entry_blocked`, dry-run-style) —
   not for every skip on every tick.

## 4. Engine parameters vs book numbers — the honest list

These five constants (top of `trading/auto_entry.py`) are **owner (Ajay)
choices**, not book-cited values. Minervini defines the setup and the risk
math; he does not give an entries-per-day cap, a relative-volume floor, a
session-half cutoff, or a dollar cap for a paper trial. They are locked in
`tests/test_trading_contracts.py` ("engine params" block) so any change is a
deliberate signed-off decision:

| Constant | Value | What it is | Provenance |
|---|---|---|---|
| `MAX_AUTO_ENTRIES_PER_DAY` | 2 | Max auto buys per ET day | Owner choice — observation-friendly pace for the paper week |
| `AUTO_RELVOL_MIN` | 1.5 | Projected full-session RelVol floor, intraday path | Owner choice — "expanding volume" (p.203) is the book concept; the 1.5 number is ours |
| `FIRST_HALF_FRACTION` | 0.5 | First observed pivot clear must land in the first half of the session | Owner choice — no book equivalent |
| `MAX_EXTENSION_PCT` | 3.0 | Buy-zone ceiling above the pivot | **Mirrors `sepa.scanner.BUYABLE_MAX_EXT_PCT`** — book p.224 gives the concept ("without chasing … more than a few percentage points") but no number; 3% is the user-approved (2026-06-09) house value. Cross-locked with the scanner token in the contract test |
| `DEFAULT_EQUITY_CAP` | 5000.0 | Sizing-equity ceiling (trading_config.equity_cap default) | Owner instruction verbatim: "assume you have 5k" |

(`AUTO_MIN_SCORE = 70.0`, the funnel score floor, is likewise an owner choice
matching the scanner's BUY rating tier.)

## 5. The equity cap

`trading_config.equity_cap` (default `DEFAULT_EQUITY_CAP`). For **all**
entries — manual and auto — `entries.py` sizes off
`min(Alpaca equity, equity_cap)`. Alpaca paper accounts default to $100k;
the cap is what makes the $5k trial real. `GET /trading/preview` surfaces
`{"equity_used", "equity_cap"}`. Adjustable via
`POST /trading/config {"equity_cap": ...}` (validated 100..100000, admin).

## 6. Enable flag, wiring, safety

- `trading_config.auto_entry` (default **false**). `run()` no-ops — writing
  at most one `auto_entry_disabled` ledger row per ET day — unless
  configured AND **armed** AND auto_entry AND market open.
  `armed=false` never places orders anywhere (house invariant, unchanged).
- `exit_engine.tick()` calls `auto_entry.run()` **after** exit
  reconciliation, inside try/except: an auto-entry crash can never break
  stop protection.
- `auto_entry.py` contains **no direct broker order call** — contract test
  greps the module source; buys must flow through `entries.enter()`.
- Push: `push.hooks.notify_autopilot(kind, ticker, detail)` fires to the
  owner's devices (send_to_user, no pref/scope filter — his own trades) for
  every auto entry and for trade closes (`stop_filled` / `target_filled`)
  detected by the exit engine. Push failures are logged and swallowed.

## 7. API surface (all admin-gated, GETs included — /trading house rule)

- `POST /trading/auto-entry?enabled=true|false` — flip the flag.
- `POST /trading/config` — `{"equity_cap": float}` (100..100000).
- `GET /trading/status` — gains `auto_entry: {enabled, equity_cap,
  entries_today, max_per_day, candidates: [per-symbol last_eval snapshots]}`.

## 8. Tests

- `tests/test_auto_entry.py` — behavioral: both trigger paths, every veto,
  structural-stop pass-through, daily cap (including same-tick slot
  consumption), dedupe, disabled/disarmed no-ops, equity-cap sizing math.
- `tests/test_trading_contracts.py` — "engine params" source locks for the
  five constants, the scanner mirror cross-lock, and the
  no-direct-broker-order invariant.

## 9. Built-in SIM broker (paper trading without an external account)

`trading/broker_sim.py` is a simulated broker with the **same duck-typed
surface** as the Alpaca client, returning Alpaca-shaped dicts — the exit
engine, risk rules, entries, auto-entry, ledger and pushes run **unchanged**.
Selection lives in `trading/broker.py`:

- `TRADING_BROKER=sim` or `=alpaca` — explicit choice always wins;
- otherwise **Alpaca** when `ALPACA_KEY_ID`/`ALPACA_SECRET_KEY` are set;
- otherwise the **sim**. Switching to Alpaca later = set the env keys (or
  `TRADING_BROKER=alpaca`) and restart — no code change.
  `GET /trading/status` reports `mode: "sim" | "paper" | "live"`.

State: Mongo `sim_account` (cash, starts at `SIM_STARTING_CASH = 5000.0` —
mirrors `DEFAULT_EQUITY_CAP`), `sim_positions`, `sim_orders`.

**Fill semantics** — `process_fills()` runs at the top of every
`exit_engine.tick()`, matching pending orders against ONE batched live
Massive quote call (`sepa.prices.bulk_live_prices`):

- market buy → fills at the live print; limit buy → fills once live ≤ limit;
- bracket legs are `held` until the entry fills, then go live (Alpaca
  semantics); OCO — one leg fills, the sibling is canceled;
- sell stop → triggers at live ≤ stop, **fills at
  `stop × (1 − SIM_SLIPPAGE_PCT/100)`** (`SIM_SLIPPAGE_PCT = 0.1`,
  deliberately pessimistic);
- sell limit (target) → fills at the limit once live ≥ limit;
- `account().equity` = cash + Σ(qty × live); `buying_power` = cash.

**Coarseness caveat (honesty):** fills are evaluated once per engine tick
(~1/minute) against the last trade — between-tick moves resolve at the NEXT
tick. A stop touched-and-recovered inside a minute may not fill; a real gap
through a stop fills far worse than 0.1% slippage. The clock has **no
holiday calendar** (weekday 9:30–16:00 ET only). Sim results are a
plumbing/process trial, not an execution-quality measurement.

**Reset:** `POST /trading/sim-reset?confirm=yes` (admin; 400 unless the
active broker IS the sim) or `python -m trading.broker_sim reset` — drops
the three collections and restores starting cash.

## 10. SIM → brokerage cutover (Ajay 2026-06-19)

When the engine switches venue from the sim to a paper/live brokerage, three
accounting seams matter. None of them is a book number; they are about keeping
the **track record continuous and honest** across the boundary.

**Account P&L baseline (`exit_engine.account_starting_cash`).** The sim reports
`starting_cash` on its account; a brokerage account does not — its API only
knows equity *now*. So the first time the engine sees a brokerage account it
**snapshots equity** and persists it in `trading_account_baseline` (keyed by
account id), reading that snapshot forever after. The dashboard's "started $X →
made $Y" header then reads as gain *since the engine connected to this account*.
Seed it while the account is pristine (right after the cutover) so the baseline
is the true starting equity. Degrades safely (no Mongo → P&L shows $0, never a
crash); delete the doc to re-baseline.

**Venue label on every fill.** `entries.enter()` stamps the active broker
`mode` (`sim`/`paper`/`live`) into the entry ledger row. `journal` surfaces it;
`analytics.compute()` adds a `by_source` breakdown beside `by_trigger`. The
headline batting/expectancy stays the **combined** record across the cutover
(the continuous "rodeo"); `by_source` lets the live-paper accuracy accrue in
parallel. Fills predating the cutover carry no `mode` and bucket as `sim`.

**Open-position handover (`trading/sim_handover.py`).** The sim's still-open
paper positions cannot move to the brokerage account. Left alone they linger as
ghost "open" round-trips marking to live prices forever. `sim_handover.run()`
books each one **closed at its last simulated mark** — a labelled
`trade_closed`/`sim_handover` ledger row — so the sim chapter becomes realized
history and the only open trades going forward are the real brokerage ones.
Properties: pure journal history (never a broker order; the sim is no longer the
active venue); does **not** feed the consecutive-loss streak (that reads broker
fills, not the ledger), so sim results never penalise live-paper sizing; the
journal recomputes the realized gain against each entry's recorded price (single
basis); idempotent (a symbol already booked is skipped). Run once after the
switch: `python -m trading.sim_handover` (`--dry-run` to preview). The handover
mark is **not** an engine exit signal — it is just "where the sim stood when we
handed over," and is labelled as such in the journal narrative.

Invariants unchanged: `armed=false` places nothing anywhere (sim included);
buys only via `entries.enter()`; constants locked in
`tests/test_trading_contracts.py` (SIM tokens + the factory invariant: no
direct `broker_alpaca` import in engine modules); behavior locked in
`tests/test_broker_sim.py`.
