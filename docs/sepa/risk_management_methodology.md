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
