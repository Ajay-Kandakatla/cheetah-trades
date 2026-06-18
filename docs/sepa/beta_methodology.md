# Beta (volatility vs the market) — methodology

_Added 2026-06-17. Ajay: "add a Beta column to the breakout [page] and sort table
by low-volatility stocks."_

## What it is

**Beta** measures how a stock moves relative to the market (SPY):

```
beta = cov(stock daily log-returns, SPY daily log-returns) / var(SPY daily log-returns)
```

over the trailing **252 common bars (≈ one trading year)**.

- **β < 1** — *less* volatile than the market (defensive / "low volatility")
- **β ≈ 1** — moves with the market
- **β > 1** — *more* volatile; amplifies market swings (e.g. high-beta semis)

`backend/sepa/beta.py`. This is the **canonical app beta** — the same
cov/var-of-log-returns formula already used by `portfolio/drop_attribution._beta`
(itself "verbatim from the original `sepa.ravi._beta`"). One year of daily returns
is the conventional window for a published "beta" figure.

## Window caveat (don't read it as the textbook number)

It's a **1-year daily** beta, so it reflects the *recent* regime, not the long-run
"textbook" value. In a year dominated by semis/AI, defensive staples can print a
beta near 0 (or slightly negative) because their day-to-day moves barely correlate
with the index — that's correct for the window, just not the 5-year figure a broker
might quote. Verified on real data 2026-06-17: KO ≈ 0, JNJ/PG ≈ 0, SPY = 1.00
(sanity), NVDA 1.83, TSLA 2.03, MRVL 2.67, MU 2.95.

## Where it shows

A **Beta** column on the `/breakouts` table (between Stage and → R1/R2). Tapping
the header sorts **ascending = low-volatility first** (the requested "sort by low
volatility"). Color: β<1 green (calmer), β>1.3 red (jumpy). Missing history → "—".

## How it's computed (and why there)

Computed in `breakout.board()` for the **displayed names only** (≤ top), not in the
scan hot path:

- SPY's return series is loaded **once** per board build; each name's beta is a
  per-symbol **daily cache** (`beta.betas_for` → `beta.beta_for`), so repeat loads
  are instant.
- Prices come from `prices.load_prices` (the same date-indexed 2-year frames the
  rest of SEPA uses), so the join is **date-aligned** (not row-position aligned).
- The board endpoint is already `asyncio.to_thread`-wrapped, so the per-name price
  reads don't block the event loop.

## Contract

**Display-only / informational** — beta never feeds the SEPA score, the
qualifier/buyable gates, or the buy verdict. It's a risk lens for sorting. Every
path **soft-fails to `None`** (a stock with < ~1 yr of history, or a failed price
read, shows "—" — never a crash, never a wrong number from a short window: the
252-bar guard returns `None` rather than computing on too few bars).

## Tests

- `backend/tests/test_beta.py` — the 2×/1×/0.5× formula identities, the 252-bar
  window guard, date-alignment, zero-variance guard, per-day cache, batch, and the
  soft-fail negatives.
- `backend/tests/test_breakout_board.py` — the board attaches beta to each row
  (and `None` when unavailable).
- `frontend/src/pages/Breakouts.test.tsx` — the Beta column renders, sorts
  low-volatility first, and shows "—" for a missing beta.
