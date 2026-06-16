# Volume Movers + turnover — methodology

_Added 2026-06-15. Ajay: "page with highest volume and price change… track total
stocks of a company… INTC has the highest volume but it did not get a price push,
I don't understand why it did not deplete the stocks." Display-only — never feeds
the scanner score._

## The misconception this corrects

"Heavy volume depletes supply → demand → price gets pushed" is intuitive but not
how it works:

1. **Volume is two-sided.** Every share traded has a buyer *and* a seller. High
   volume means lots of shares changed hands — not net buying. Price moves on the
   **imbalance** (who's more aggressive), not the count.
2. **Float isn't "used up."** The same shares trade over and over (turnover). A
   stock can trade 50% of its float in a day without any supply being "consumed."
3. **Raw share count scales with float and inverse price.** A low-priced mega-cap
   needs *millions* of shares to move meaningful dollars, so it always looks like
   a "volume leader" even on a quiet day.

## The honest reads (what the board shows)

| Metric | Formula | What it tells you |
|--------|---------|-------------------|
| **Volume** | shares traded today | raw activity (misleads on its own) |
| **RVOL** | today's volume ÷ 50-day avg | *unusual* volume — is today actually busy **for this name**? |
| **$ Vol** | volume × price | where the real money flowed |
| **Shares** | float (tradeable shares) | the company's total supply |
| **Turnover %** | volume ÷ float × 100 | **how much of the supply actually changed hands** |

Turnover and RVOL are the supply/demand reads. A real supply/demand event is a
**high RVOL + high turnover** name (a thin float overwhelmed by buyers, price
rising) — not the biggest raw share count.

## Worked example — why INTC didn't get pushed (2026-06-15)

| | Volume | RVOL | Float | Turnover |
|--|--------|------|-------|----------|
| **INTC** | 128.7M | **0.93×** | 5.0B | **2.6%** |
| **NVDA** | 148.7M | 0.93× | 23.2B | **0.6%** |
| **NIXX** (thin float) | 94.6M | **33.7×** | 22.3M | **424%** |

INTC's 128M shares *look* huge, but that's **2.6% of its 5-billion-share float**,
and today's volume was actually **below** its own average (RVOL 0.93×). Almost no
supply changed hands relative to what's out there → no push. NVDA traded even more
raw shares yet only **0.6%** of its float. NIXX, by contrast, turned over **4× its
entire float** on 33× normal volume — *that's* a genuine supply/demand event.

## Where to get "total shares of a company"

`sepa.volume_movers.shares_for(symbol)` → `{shares_outstanding, float_shares,
market_cap}` from yfinance, cached weekly in Mongo (`shares_cache`). Float
(tradeable supply) drives turnover; we fall back to shares-outstanding if float
is missing, and show "—" for ETFs (no float).

## Where it lives

- `sepa/volume_movers.py` — `movers(top, sort)` builds the board from the latest
  scan (volume/RVOL/$vol/change are free) and enriches the shown rows with
  float + turnover. Sorts: `volume` (default), `rvol`, `dollar_vol`, `change`;
  the FE can re-rank the loaded rows by `turnover`.
- `GET /sepa/volume-movers?top=&sort=`.
- `VolumeMovers.tsx` on the Leaderboard.

## What it is NOT

Not a buy signal and not part of the SEPA score. High turnover says supply met
heavy demand; whether that's *accumulation* (price rising) or *churning /
distribution* (price stalling on volume — a Minervini warning after an advance)
is read off the price action, which the SEPA card already grades.
