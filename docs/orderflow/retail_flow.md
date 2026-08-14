# Retail order flow — identifying it from the tape

_Added 2026-08-14. Ajay: "Is there any way we can check orderbook with any
other API to know potential Retail orders sitting there waiting" → then "lets do
it so then we will sort our demand zone on the basis of # of retail flows?"_

## First, the question that was asked: no

Resting retail orders are not observable, and no vendor changes that:

- **The book is anonymous.** Even full L3/MBO (Databento, via Nasdaq
  TotalView-ITCH, ~$1,399/mo real-time) gives order IDs, sizes and queue
  position — never who placed them.
- **Retail marketable orders never reach the lit book.** They are sold to
  wholesalers and internalised. That is the ~39-60% off-exchange share we
  already measure. The lit book is precisely where retail *is not*.
- **Stops exist in no feed** until they fire.

So depth-of-book would buy a clear view of market-maker and institutional limit
orders — the opposite of the ask.

## What IS possible: identify EXECUTED retail flow

**Boehmer, Jones, Zhang & Zhang (2021).** Wholesalers internalising retail give
**sub-penny price improvement**. Reg NMS Rule 612 bans sub-penny *quotes* but
permits sub-penny *fills*, so:

    retail = off-exchange (FINRA TRF) AND sub-penny remainder
             (excluding .0 and .5 cent increments, which are not improvement)

Measured on our own tape, 2026-08-14: 8–17% of volume per name, matching the
~35%-of-retail-activity capture rate the literature reports.

## The correction, and why it is not optional

BJZZ signed the trade from the *direction* of the sub-penny. **Barber, Huang,
Jorion, Odean & Schwarz (2024, _Journal of Finance_)** validated that against
**85,000 known retail trades** in real brokerage accounts:

- identifies ~35% of retail trades
- **mis-signs 28% of the ones it finds**
- uninformative imbalances for 30% of stocks
- their fix — sign against the **quote midpoint** — drops signing error to ~5%

We reproduced the disagreement on SWKS, 2026-08-14:

| | buy | sell | imbalance |
|---|---|---|---|
| naive sub-penny sign | 34,004 | 39,998 | **−8.1%** |
| midpoint sign (the fix) | 51,296 | 37,351 | **+15.7%** |

**Opposite directions.** So `orderflow/retail.py` signs on the midpoint only,
and returns `signed: False` with **no imbalance at all** when NBBO is missing.
An unsigned count is honest; a wrongly-signed one is worse than nothing.
Locked by `test_retail_refuses_to_sign_without_nbbo`.

## On sorting demand zones by retail

Ajay asked to sort by *number* of retail flows. That metric is close to
useless on its own: a heavily traded name has more retail prints whatever else
is true, so it would mostly re-sort the board by volume. The sort menu
therefore offers **retail imbalance** (direction) and **retail % of volume**
(participation), not a raw count.

`divergence()` flags the configuration actually worth looking at — retail
leaning one way while large off-exchange blocks print in the same session.
Block *side* is not knowable from the tape, so it is explicitly a flag to go
look, never a verdict (`test_divergence_never_claims_to_know_the_block_side`).

## Bug found while wiring it

The caller passed `len(blocks)` where `divergence()` expected the block **list**,
so `len()` ran on an int and the retail read silently died — on every row that
*had* blocks, i.e. exactly the interesting ones. Rows with zero blocks worked,
which is why it looked like partial coverage rather than a bug.
`test_divergence_takes_the_block_LIST_not_a_count`.

## Surfaces

| Where | What |
|---|---|
| `/sepa/{sym}` → Tape | retail imbalance + participation alongside the venue split |
| `/supply-demand` → Back in Demand | `retail` column, ⚡ on divergence, sortable by imbalance or participation |

Costs nothing extra — reuses the tape and NBBO already fetched for the venue
split and the quote-rule delta.

## Does it predict anything? — first measurement (2026-08-14)

`orderflow/retail_backtest.py`, 60 S&P 500 names, 8 trading days, **475
symbol-day observations**, 88 minutes of fetching. Retail flow identified from
each day's COMPLETE tape and signed on the midpoint; return measured from that
day's close forward.

**Cross-sectional spread — most-retail-buying quintile minus most-retail-selling:**

| horizon | raw spread | demeaned by day | rank corr |
|---|---|---|---|
| 1 day | +0.81% | **+0.76%** | 0.063 |
| 3 days | +1.56% | **+1.54%** | 0.047 |
| 5 days | +2.44% | **+2.24%** | 0.081 |

The effect **survives demeaning within each day**, so it is cross-sectional,
not market beta — and the sign matches BJZZ's published finding (retail
imbalance positively predicts short-horizon returns), not the folk "retail is
dumb money" prior.

### Why it is NOT yet tradeable

| | |
|---|---|
| Distinct days | **8** — the effective sample, not 475. Same-day forward returns are heavily cross-correlated. |
| Days with a positive spread | 6/8 at 1d and 3d, **5/8 at 5d**. Binomial p ≈ 0.15 — not significant. |
| Concentration | The 5-day mean (+2.15%) drops to **+0.70%** with the two best days (2026-07-29, 2026-08-05) removed. Two-thirds of it is two sessions. |
| Rank correlation | 0.05–0.08 — near zero. The effect lives in the tails, not across the distribution. |

The automated verdict returns **"no usable signal"** because it requires
|rho| ≥ 0.1. Given the size of the quintile spreads that threshold is arguably
harsh — but its caution turns out to be right for a reason it did not know:
a low rank correlation means tail-driven, and the day-level breakdown shows
exactly that fragility.

**Verdict: promising, not established. Do not size on it.** This is the first
measurement all week that did not come back flat, which is precisely when it is
easiest to fool yourself.

### What would settle it

60+ trading days, which is ~11 hours of fetching at the current rate — an
overnight cron job, not an interactive run. Until then it is a hypothesis with
one encouraging look.
