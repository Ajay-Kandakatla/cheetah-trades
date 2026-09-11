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

## The heat window moved to the week (2026-09-10)

Ajay, on the Aerospace & Defense popover: *"Actually this is red but it picked
up today so its the inverse… In general Aero was red but if you see 5 days to
today its green… Lately sector rotation is with in a week since its bear
market… Ignore the 21 day even if its read now recently market rotated that is
the actual truth to us."*

He was right, and the ranks are blunt:

| industry | 5d | 21d | 5d rank | 21d rank |
| --- | --- | --- | --- | --- |
| Aerospace & Defense | −1.86% | −14.25% | **41 / 73** | **71 / 73** |
| Semiconductor Equip & Materials | **+4.65%** | −9.61% | 1 | near bottom |
| Electronic Components | +2.06% | −9.29% | 3 | near bottom |
| Semiconductors | +1.73% | −7.57% | 5 | near bottom |

The semis complex was the live rotation and the 21-day window had all three
marked cold — the same thing he flagged that morning about AVGO.

**`heat.HEAT_KEY = "rel_5d"`** is the single place the window lives;
`build_index` and `read` both read it, and `HEAT_WINDOW` is what every label
prints. `rel_21d` / `rel_63d` stay on every row as context ("keep the other
days too") — they simply stop deciding the tone.

The group rows had **no short leg at all** before this: `group_row` computed
only `median_window` / `median_21d` / `median_63d`. `median_1d`, `median_5d`
and `pct_positive_1d` are new, computed over the same kept members.

### "Money in" must mean money in

`hot["in"]` was `ranked[:5]` unconditionally. On a red day that labelled the
five *least-red* groups as inflow — and it made "no group is hot"
arithmetically impossible, so the market-red line he asked for
(*"when there are none hot that day it helps to know overall market it red"*)
**could never fire**. The frontend test covering it passed only because its
fixture handed the component `in: []`, a shape the API cannot emit.

`in` is now sign-filtered. `out` is unfiltered — the cold end is always
information.

### NOT measured on this window

`studies/sector_heat_study.py` measured the **21-session** definition: hot 22.4%
vs cold 23.2% (−0.57pp, 95% −1.87…+0.71), and the backwards 5-session read
(COLD 30.8% vs 28.3%). **Those results do not describe what ships now.** The
ℹ️ Rules panel says so in place of quoting the old number, and re-running the
study on `HEAT_KEY` is outstanding work, not a settled question.
