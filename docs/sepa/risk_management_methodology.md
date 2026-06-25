# Auto-Pilot Risk Management — book-faithful exits, automated

**Source:** Mark Minervini, *Trade Like a Stock Market Wizard* (2013),
Chapter 13 "Risk Management Part 2: How to Deal with and Control Risk",
printed pp.291–315 (`backend/sepa/minervini.pdf`, printed page = PDF page − 15).
Chapter 12 (pp.269–290) supplies the rationale (losses compound geometrically);
Chapter 13 supplies every number below.

**Why this exists (2026-06-11):** Ajay's indicators were right but the human
in the loop kept overriding them — watching positions minute-by-minute and
selling winners early / hesitating on stops. The fix is the book's own
prescription: decide everything **before** entry, then let standing orders
execute it. "The time to think most clearly about where you will exit a
position is before you get in. … There is no decision to be made; it's been
decided ahead of time." (p.301)

Implementation: `backend/trading/risk_rules.py` (pure math, this doc's
contract), `backend/trading/exit_engine.py` (reconciler), Alpaca bracket
orders (the stop and target legs **rest at the broker**, so they execute even
if this machine is off).

## The rules, page by page

| Rule | Value | Page |
|---|---|---|
| Initial stop set before entry, executed without hesitation | always | p.295, p.301–302 |
| Normal-market stop band | 7–8% (default **7%**) | p.311 |
| Difficult-market stop band | 5–6% | p.311 |
| Absolute maximum stop — never exceeded by any rule or override | **10%** | p.299, p.301 |
| Stop from real trade history (≥20 closed trades) | half the average gain, capped at 10% | p.299 |
| Reward:risk floor / stretch | **2:1** minimum, shoot for 3:1 | p.301 |
| Profit-taking band, normal / difficult | 15–20% / 10–12% | p.311 |
| Move stop to breakeven | when price reaches entry + **3×** initial risk | p.308 |
| Never widen stops for volatility | tighten instead | p.308–309 |
| Position count | 4–6 (engine cap **5**) | p.312 |
| Position size | **25%** of equity ("optimal for a true 2:1 trader") | p.312 |
| Losing streak governor | halve size after 3 consecutive stop-outs, halve again after 6; step back up one level per winner | p.304 |
| Never average down | adding allowed only above average cost | p.304–305, p.308 |
| Slippage / gap through the stop | sell at the next bid immediately | p.302–303 |

Verbatim anchors:

- p.299: "If your winning trades produce a gain of 15 percent on average, you
  should sell any declining stock at no more than 7.5 percent off the
  purchase price." / "…not allow any stock to fall more than 10 percent
  before selling."
- p.301: "My goal is to maintain at least a 2:1 win/loss ratio with an
  absolute maximum stop loss of no more than 10 percent. I shoot for 3:1."
- p.308: "When the price of a stock I own rises by three times my risk, I
  almost always move my stop up to at least breakeven." (Example: buy $50,
  stop $47.50, risk $2.50 → at $57.50 the stop moves to $50.)
- p.311: "If you normally cut losses at 7 to 8 percent, cut them at 5 to 6
  percent. … If you normally take profits of 15 to 20 percent on average,
  take profits at 10 to 12 percent."
- p.312: "If you're a true 2:1 trader, mathematically your optimal position
  size should be 25 percent (four stocks divided equally)."

## How the engine maps the rules to Alpaca

1. **Entry (user-confirmed, never self-initiated).** Every entry goes out as
   a **bracket order**: entry + stop-loss leg + take-profit (sell-into-
   strength) leg, GTC. The legs rest at Alpaca — a dead Mac cannot miss a
   stop. Shares = `position_size()` (25% × streak multiplier, whole shares).
2. **Earnings shield.** Entries are refused when earnings are ≤7 days out
   (the ATEX lesson — a stop cannot protect against an overnight gap;
   pp.296–297's disaster-plan logic). Explicit override flag exists.
3. **Reconciler tick (cron, market hours).** For every open position:
   - no protective stop on file → place one per `initial_stop()` and flag it
     (p.301–302: trading without a stop is "driving a car without brakes");
   - price ≥ `breakeven_trigger()` and stop still below entry → replace the
     stop leg at breakeven (p.308);
   - closed trades update the win/loss streak and the rolling average gain
     that feeds the p.299 half-average-gain stop.
4. **Never average down.** `/trading/enter` rejects adds below average cost.
5. **Regime.** The market-gauge verdict selects normal vs difficult bands
   (p.311). Difficult can only tighten, never widen (p.308–309).
6. **Armed/disarmed.** Disarmed, the engine logs what it *would* do
   (dry-run ledger rows) and places nothing. Paper vs live comes from env;
   the UI banners both.

## What the book says that we deliberately did NOT automate

- **Buying.** The engine never initiates a position. Stock selection stays
  with the SEPA scanner + Ajay's confirmation per entry.
- **Re-entry after a stop-out (p.295–296).** Surfaced as information (the
  stopped name goes back to the watch surfaces), not auto-executed.
- **Scaling in 2%+2%+1% (p.307).** v1 enters in a single tranche at 25%;
  pilot-buy scaling is a later phase.
- **Selling into weakness on technical breakdown (p.296).** v1's automated
  exits are the stop and the strength target; discretionary technical sells
  remain manual.

## Known limits (stated, not hidden)

- A stop order cannot protect against an **overnight gap** (ATEX −28% AMC).
  The earnings shield exists precisely for this; it is refusal-by-default,
  not a guarantee.
- Alpaca bracket stops trigger during regular sessions. Halts and locked
  markets fill where they fill (p.302–303 slippage rule: that's accepted).
- The half-average-gain stop (p.299) needs ≥20 closed trades; until then the
  engine uses the p.311 band default of 7%.

## Caution market → difficult-regime downshift (2026-06-22)

`exit_engine.regime()` maps the Market Gauge state onto the book's two regimes.
A **non-constructive** tape now runs the p.311 difficult-market playbook — BOTH
`risk_off` AND `caution` → `'difficult'`; only `constructive` (or a missing
gauge / error) → `'normal'`. Under `'difficult'` (`risk_rules.regime_bands`):

- **Stop tightens**: 7-8% band → **5-6%** (default 6%). Stops can only tighten,
  never widen (p.308-309), so this is strictly more conservative.
- **Profit target shrinks**: 15-20% → **10-12%** (still ≥ 2:1, p.301).

Rationale (Minervini p.311): in a tough/choppy market, gains are smaller and the
batting average lower, so cut losses shorter and settle for smaller profits.
Standing tighter on a caution day costs nothing here because the engine ticks
every minute — a later re-entry on a constructive turn is never missed
(TLSW p.288, "you don't have to involve yourself in every market movement").
Position-size reduction (the other half of p.311) is NOT yet wired — `position_size`
ignores the regime; the tighter stop already cuts per-trade risk (25% × 6% =
1.5% vs 1.75%). Locked: `tests/test_caution_regime.py`.

## Stop watchdog — the engine never trusts the broker stop alone (2026-06-24)

p.301–302 demands a stop **always resting** and a sale **the moment it's hit**.
We discovered that resting the stop at the broker is not sufficient: Alpaca can
leave a **bracket stop-loss leg stuck in `held`** after the entry fills, so it
never triggers even when price reaches it (a known Alpaca bug — confirmed in
their own community forums, 2026-06-24). The take-profit leg activates normally,
so a position ends up with an upside target but a **dead downside stop**, and the
old code couldn't see it: `open_orders()` queries `status=open`, which excludes
`held`, so the reconciler reported "UNPROTECTED" and its adopt-protect retry
failed silently (the held leg + working target reserve the share qty → the new
stop is rejected → the error was swallowed).

The fix does **not** change any stop math (`risk_rules.py` is untouched). It
makes the *enforcement* of the existing p.301–302 rule robust:

1. **Watchdog (the guarantee).** Each tick, for every open position, the engine
   computes the **committed stop** (`_effective_stop`: a live stop's price → the
   ledger's entry stop → `initial_stop()` recomputed). If price has reached/
   breached it **and no genuinely-working broker stop rests**, the engine
   **sells at market itself** (`watchdog_exit`, cite p.301–302). When a real
   working stop *does* rest, the broker is trusted (no double-sell). Disarmed →
   dry-run row only, as everywhere else.
2. **`held` is not protection.** `_find_working_stop` counts only genuinely-
   firing statuses (`new`/`accepted`/`partially_filled`), **not** `held` — so a
   stuck leg no longer masquerades as a resting stop.
3. **Failures are loud.** A swallowed adopt/watchdog error now persists to
   `trading_config.last_errors` and surfaces on the dashboard + an owner
   `position_alert` push — never a silent miss again.
4. **Honest status.** Each position reports `stop_status`: `working` (live broker
   stop), `watchdog` (engine-enforced backstop, shows the enforced price), or
   `none` (truly uncovered). The page reads "Stop 157.25 · engine" instead of a
   false "UNPROTECTED" scare.

**Limit (stated, not hidden):** the watchdog acts on the tick cadence
(market-hours, ~1 min), so it carries the same intra-tick slippage and overnight-
gap exposure as any stop (a stuck broker stop wouldn't fire overnight either).
A follow-up will additionally *replace* stuck `held` legs with standalone
working stops at the broker for intra-tick coverage; until then the watchdog is
the backstop. Terminology on the page is now **Stop / Exit** (was
Protection/Flatten), Ajay 2026-06-24.

Locked: `tests/test_trading_engine.py` (watchdog: fires on breach armed; held
leg ≠ protection; trusts a working stop; not above the stop; disarmed dry-run;
close-failure surfaced) + `frontend/src/lib/autopilotStop.test.ts` (badge wording).
