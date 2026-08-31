# Hot sectors strip + sector × cap-tier cohorts

Shipped 2026-08-31. Ajay: *"make sure this scan you did today to be on top of
the chart maps or some section where it says Hot sectors"* + *"Feel free to
categorize more sectors in a similar faction.. Like Health care small caps or
something please feel free to reinvent the wheel"* + *"I need this component
market guage tab too"*.

## Cohorts

`rotation/tracker.py` now crosses each sector with a **cap tier**, where tier
is **S&P index membership** — large = S&P 500, mid = S&P 400, small = S&P 600.
Membership, not a computed market cap, because the S&P committee already
maintains the split, the lists are cached 30 days in `sepa.universe`, and it
costs zero API calls (a shares × price cap would cost one Massive reference
call per name). Every cohort label carries its index so the tier is auditable.

Methodology is IDENTICAL to the sector grid — the four pinned decisions apply
unchanged (RSP benchmark, strict-before anchor, median member, dead tickers
dropped):

* tiering happens **before** sampling, on the full sector membership —
  sampling first would starve small-cap cohorts by whichever names the sector
  stride kept;
* deterministic stride sample, `COHORT_SAMPLE = 25` per cohort;
* `MIN_COHORT_N = 8` **kept** members or the cohort is dropped — a median over
  three names is noise wearing a number; re-checked after dead tickers drop;
* missing tier lists → no cohorts, never a crash, sector grid untouched.

Measured 2026-08-31: 32 cohorts, +4s on a warm build. First live read:
Technology **large caps** +5.7 rel 21d (money returning) while Technology
overall is −13.9 on the summer window — exactly the split the sector table
could not see. Real Estate small/mid and Consumer Cyclical small/mid led the
outflows.

## The hot ends

`build()` adds `cohorts` (full rows) and `hot` — top/bottom 5 **ranked by
`rel_21d`**: "where is the money flowing right now" is a 21-day question,
while the tables stay sorted by the window like everything else. Rows with no
computable 21d are excluded from the ranking — None must not sort as hottest.

## Surfaces

* `GET /rotation/hot` — slim payload for the strip; shares the same 30-minute
  cache entry as `/rotation` (same key), so the two can never disagree.
* `HotSectors.tsx` — one strip component mounted on **Chart Maps** (above the
  tabs, so every board is read against the rotation backdrop) and **Market
  Gauge** (the gauge says HOW MUCH exposure; the strip says WHERE). Renders
  nothing on error or empty — a decorative strip must never break its page.
  Links to `/rotation` for the full tables.

Measurement of what moved — not a forecast and not advice. The rotation
backtest's own finding stands: acting on leaders did not beat owning the
market (see `/rotation/backtest`).
