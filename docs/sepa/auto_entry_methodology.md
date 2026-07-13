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
- `score >= AUTO_MIN_SCORE` (85 default — owner choice, §4; `auto_min_score`
  config override),
- `rs_rank >= AUTO_MIN_RS` (80 default; `auto_min_rs` config override) —
  TLSW **p.79, Trend Template criterion 8**, verbatim:

  > "The relative strength ranking (as reported in Investor's Business
  > Daily) is no less than 70, and preferably in the 80s or 90s, which will
  > generally be the case with the better selections."

  The scanner's `is_buyable` already enforces the hard 70 floor inside
  `trend.pass_all`; the engine's own floor sits at the book's *preferred*
  band because an unattended engine should only take "the better
  selections". A row with **no `rs_rank` at all fails closed**. See the
  2026-07-12 audit below for the evidence.
- `entry_setup.pivot` present (VCP / Power-Play base-high pivot),

sorted by `score` descending.

**Scan trust (2026-07-12):** before any candidate is considered, the scan
itself must pass `scan_trusted()`:

- **Fresh** — the scan's ET date is today or the previous trading day
  (weekday-walk; the book's evening-scan → next-day-pivot routine, never
  older). A dead scanner cron can no longer leave the engine trading
  last week's setups.
- **Sized** — `universe_size >= MIN_RS_UNIVERSE` (500). `rs_rank` is a
  percentile **within the scanned universe** (`sepa.rs_rank.rs_ranks`), so a
  small manual scan (curated mode) that overwrites `latest.json` produces
  distorted ranks — EIX read RS 64–75 across same-day runs depending on the
  scan's pool. Only market-sized scans (the 16:30 `--mode broad` cron writes
  ~3,700 names) are tradeable.

Both fail **closed**: an untrusted scan means the engine sits out
(`reason: untrusted_scan`, one `auto_entry_skipped_scan` ledger row per ET
day, and `status.auto_entry.scan.trusted=false` renders a ⏸ banner on the
Trading page).

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
   - the **volume gate** (TLSW p.229 "Extrapolating Volume Intraday",
     reworked 2026-07-09 after the failure autopsy):
     - PASS if **actual** today's volume already ≥ `AUTO_RELVOL_MIN` × the
       full 50-day average — the tape proved itself, any time of day; or
     - PASS if session elapsed ≥ `VOL_CONFIRM_MIN_FRAC` AND the **projected**
       full-session RelVol (`sepa.live_gate` intraday curve) ≥
       `AUTO_RELVOL_MIN` — the p.229 extrapolation, trusted only once there
       is tape to extrapolate FROM. Minutes into the open the denominator is
       near zero and ANY opening print projects as huge RelVol — the hole
       that fired 12 of 18 entries at 9:30-9:32 (4 of 6 closed trades
       stopped out). Missing volume data **fails closed**.
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
| `VOL_CONFIRM_MIN_FRAC` | 60/390 ≈ 0.1538 | Minimum session elapsed before a **projected** RelVol may trigger the intraday path (actual volume ≥ floor passes any time) | TLSW p.229 demonstrates the extrapolation "two hours into the trading day"; the book mandates no minimum — 60 min is the house value (Ajay sign-off 2026-07-09, failure autopsy) |

(`AUTO_MIN_SCORE = 85.0`, the funnel score floor, is likewise an owner
choice — raised from 70 on 2026-07-09 after the failure autopsy: winners
scored 87–94, no loser above 84, the two lowest-scored entries ever taken
both stopped out. n=6, so this is a **hypothesis being enforced**, reviewed
as the sample grows; the `auto_min_score` trading-config key overrides it
live without a deploy.)

Two more (2026-07-12 low-RS audit):

| Constant | Value | What it is | Provenance |
|---|---|---|---|
| `AUTO_MIN_RS` | 80.0 | Funnel RS-rank floor (`auto_min_rs` override; missing `rs_rank` fails closed) | **TLSW p.79 criterion 8** gives the 70 floor and the "preferably in the 80s or 90s" preference; setting the engine's floor AT the preferred band is the owner-tightening (Ajay sign-off 2026-07-12) |
| `MIN_RS_UNIVERSE` | 500 | Minimum scanned-universe size for `rs_rank` to be trusted | Owner rule — `rs_rank` is universe-relative (IBD ranks vs the whole market; we approximate with the broad ~3,700-name scan); no book equivalent |

### 2026-07-12 low-RS audit changes, summarized

Ajay observed the engine picking weak stocks and narrowed it to RS. The
audit of all 18 auto-entries against `candidate_snapshots` confirmed it:

- **Both closed winners were RS 87+** (ARM 98 → +15.0%, ILMN 87 → +12.0%).
- **Three of the four closed losers were RS ≤ 82** (UFPT 76 → −8.5%,
  IRM 79 → −6.1%, CACC 82 → −6.0%; NESR 95 → −7.1% is the counterexample).
- **7 of 18 entries went in below RS 80**, and EIX entered with same-day
  snapshots reading RS 64–75 — sub-book-floor readings caused by
  universe-relative rank variance across scan runs, plus scan staleness
  (the engine trades whatever `latest.json` last said, with no age check).

Hence the three fixes: the RS-80 floor, the scan freshness gate, and the
universe-size gate. Same honesty note as the score floor: n=6 closed
trades is a **hypothesis being enforced**, tunable live via `auto_min_rs`.

The audit also found and fixed a real bug: `exit_engine.get_config()`
whitelists its return keys and was **stripping `auto_min_score`** — the
documented live override never actually reached the engine. Both floor
overrides now pass through the whitelist (regression-locked in
`test_trading_contracts.py`), and `POST /trading/config` accepts
`auto_min_score` / `auto_min_rs` (number to set, `null` to reset).

## 4b. X-anchored entry rules (2026-07-12 research sweep)

Two rules added from **Minervini's own recent public statements** (primary
source: his X posts, found in the 2026-07-12 internet research Ajay asked
for). Honesty note: the CONCEPTS trace to him verbatim (one also has a book
anchor); the NUMBERS are owner choices, locked in the contract tests like
every other engine parameter.

### Progressive-exposure governor (`trading/progressive.py`)

Book anchor — TLSW pp.307-308, verbatim:

> "You should start off with 'pilot buys' by initiating smaller positions
> than normal; if they work out, larger positions should be added to the
> portfolio soon thereafter. … If you're not profitable at 25 percent or 50
> percent invested, why move up to 75 percent or 100 percent invested or
> use margin? Wait for confirmation and require that at least a few trades
> work out before getting more aggressive. Conversely, if your trades are
> not working as expected, cut back."

Recent restatements (his X account):
[the standing "last 4 or 5 stocks" rule](https://x.com/markminervini/status/1331694910899179524)
— *"are your last 4 or 5 stocks profitable on balance. If no, then you have
no business increasing your exposure"* — and a
[January 2025 dated ledger](https://x.com/markminervini/status/1884705597402059074)
showing pilot → quarter/half → full builds across two weeks.

Mechanization: **every entry (manual + auto — both flow through
`entries.enter`) sizes at `PILOT_MULTIPLIER` (0.5×)** unless the last
`PROGRESSIVE_WINDOW` (5) closed trades are profitable **on balance** (net
`gain_pct` > 0) — then full size. Fewer than `PROGRESSIVE_MIN_TRADES` (3)
closed trades = unproven = pilot. Composes with the p.304 streak governor
**via `min()` inside `risk_rules.position_size`** — the most conservative
governor wins; the two never multiply. `GET /trading/preview` surfaces the
read as `progressive: {basis, net_pct, gains, …}`. The
`progressive_exposure` config key (default **ON**; `POST /trading/config`
accepts a boolean, `null` resets) disables it live. Unreadable ledger reads
as unproven → pilot (fail conservative).

### Leaky-pivot suppressor (`sepa/pivot_leakage.py`, shared)

> Moved to `sepa/pivot_leakage.py` (stdlib-only) the same day so the
> SCANNER stamps the identical read on every scan row as `pivot_leakage`
> — SEPA Global demotes a leaky "Buy now" to Watch (plain-English reason),
> the general SEPA card shows a 🚱 chip on affected buyable/setup-ready
> names, and the engine imports the same function (a single rule, three
> surfaces, zero drift — locked in `test_leaky_pivot_cited_and_intraday_only`
> + `test_pivot_leakage.py`).

Primary source — [Minervini on X, 2026](https://x.com/markminervini/status/2029213943428698253):

> "…the dominant theme is right-side volatility — which often starts as
> pivot leakage… for truly low-risk buy points to emerge, that volatility
> needs to subside. Patience is key. Let the setups come to you."

Mechanization: a **leak** = a completed daily bar whose high poked above
the pivot but whose close fell back below it. When ≥ `PIVOT_LEAK_MAX` (2)
leaks exist in the last `PIVOT_LEAK_LOOKBACK` (10) completed bars AND the
latest is ≤ `PIVOT_LEAK_COOLOFF_DAYS` (5) bars ago, the **intraday path is
suppressed** (`pivot_not_leaky` check in the per-symbol snapshot). The
**close-confirmation path is exempt** — a full close above the pivot IS the
volatility subsiding. Missing/garbage bar data **fails OPEN**: this is a
veto heuristic layered on top of the required book gates (trend, stage,
setup, volume), not a book gate itself, so a price-cache hiccup must not
block otherwise-valid entries.

## 4c. Pyramid adds — top up to full at the next valid buy point (2026-07-12)

Book anchors, verbatim:

> **TTLAC §3, "Adding Exposure Without Adding Risk" (the Add and Reduce,
> Figure 3-5):** "I buy 1,000 shares of a stock at $16.50 and set a stop at
> $15.50 … The stock then rallies and sets a new buy point. I then add an
> additional 1,000 shares as the stock moves through the new buy point at
> $17.50 … What I'm doing is letting my profits finance additional risk."
>
> **TTLAC §5:** "I usually start off with a quarter position … On the heels
> of each win, I double my position size until I'm trading full-size
> positions. I scale up on winners and scale back on losers."
>
> **TLSW pp.307-308:** "start off with 'pilot buys' … if they work out,
> larger positions should be added to the portfolio soon thereafter."

Mechanization: a **held** name that reads `is_buyable` again in the current
trusted scan is no longer skipped — it becomes an **add candidate** and runs
through the SAME trigger machinery as a new entry (live > pivot, ≤ 3%
extension, first-half clear + volume gate + leak-free intraday, or
close-confirm), plus:

- `add_pivot_above_cost` — the fresh pivot must sit **above our average
  cost** (§3: the new buy point is higher; profits finance the added risk).
  Never-average-down (pp.304-305) re-applies inside `entries` on top.
- **Top-up sizing** (`entries.enter(top_up=True)`) — the add is
  `full-position shares − shares held`: it **completes** the position
  toward the p.312 25% ceiling and can never exceed it. A position already
  at full size is vetoed ("already at full size").
- **Progressive compose** — while the account is unproven, "full" IS the
  pilot size, so a pilot can only top up after the last-5 read turns
  positive: §5's "on the heels of each win", with zero extra machinery.
- Adds **re-use their own position slot** (no MAX_POSITIONS consumption)
  but **do consume the daily cap** (conservative pace), ledger as
  **`auto_pyramid`** (violet on the page), and stamp `top_up: true` on the
  entry ledger row.
- `pyramiding` config key (default **ON**; boolean/`null` via
  `POST /trading/config`) turns adds off live.

**Deferred (documented, not built):** §3's constant-dollar-risk stop raise
(after an add, lift the stop on the ENTIRE position so total $ risk stays
put). V1 places the add as its own bracket — its stop/target legs protect
the tranche and the p.308 breakeven ratchet keeps operating — because
rewriting resting stops on a live position belongs to the exit engine and
needs its own Rule #4 round.

### 2026-07-09 failure-autopsy changes, summarized

Multi-agent autopsy of the first 6 closed engine trades (4 stops, 2 targets):
zero losers gapped through their stop (exits worked); every loss was an
idiosyncratic intraday grind with SPY flat/up; distribution-day counts did
NOT discriminate (the best winner had the most); the score did (see above);
and 12 of 18 entries had fired within 2 minutes of the open on
meaningless volume projections. Hence: the p.229 projection trust floor +
the score floor. Verified adversarially before shipping.

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
- `POST /trading/config` — any subset of `{"equity_cap": float (100..100000),
  "auto_min_score": float|null (0..100), "auto_min_rs": float|null (1..99)}`;
  `null` resets a floor to its code default.
- `GET /trading/status` — gains `auto_entry: {enabled, equity_cap,
  entries_today, max_per_day, min_score, min_rs,
  scan: {trusted, scan_date, universe_size, fresh, sized, min_universe},
  rules: [{rule, value, source}], candidates: [per-symbol last_eval
  snapshots]}`. `rules` is built by `rules_list()` from the live
  constants/config — the Trading page ⓘ panel renders it verbatim, so the
  page can never drift from what the code enforces.

## 8. Tests

- `tests/test_auto_entry.py` — behavioral: both trigger paths, every veto,
  structural-stop pass-through, daily cap (including same-tick slot
  consumption), dedupe, disabled/disarmed no-ops, equity-cap sizing math,
  the RS floor (below/at/missing + config override), scan trust (fresh /
  stale / small / missing-meta fail-closed + the sit-out ledger row), and
  the status-block rules payload.
- `tests/test_trading_contracts.py` — "engine params" source locks for the
  constants (now including `AUTO_MIN_RS` + `MIN_RS_UNIVERSE`), the scanner
  mirror cross-lock, the p.79 cite + fail-closed RS check shape, the
  scan_trusted-wired-into-run() lock, the get_config whitelist pass-through
  regression, and the no-direct-broker-order invariant.
- `frontend/src/lib/autopilotRules.test.ts` — the ⓘ panel's cleaning +
  scan-warning copy, including garbage-payload negatives.

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
