# Demand-zone re-entry — methodology

_Added 2026-08-13 (Ajay: "update my Supply and demand page with stocks that
entering back in to demand zones and give me a scan button … scan only S&P 500
stocks for this", plus a hand-marked SNDK TradingView chart for the per-stock
drawing)._

> **METHOD HONESTY.** This is a **configured, pragmatic price-structure read —
> NOT a named book methodology.** Every threshold below is a house value chosen
> from measurement, not a Minervini (or any author's) number. Two things are
> borrowed rather than invented: the **trend gate** reuses the contract-locked
> `sepa.trend_template` (the 8 Stage-2 criteria), and the **stop sanity cap**
> reuses `trading.risk_rules.ABS_MAX_STOP_PCT`. Decision-support only — not a
> buy signal and not advice.

## What the signal actually is

A **transition**, not a snapshot:

1. price is **inside** a demand band today, and
2. price traded **≥ `MIN_RISE_ABOVE_PCT` above that band's top** inside the last
   `REENTRY_LOOKBACK_BARS` sessions (it *left*, then came back), and
3. the band is real support — **≥ `MIN_TOUCHES` tests** and
   **≥ `MIN_ZONE_STRENGTH`** strength, and
4. the **trend still holds** — not a falling knife
   (`sd_liquidity.is_falling_knife`: swing lows stepping down **and** a falling
   50-day. This replaced the `sepa.trend_template` ≥ `MIN_TREND_CHECKS` gate on
   2026-08-13 — see the module docstring for the CIEN case that forced it), and
5. the band is **not broken** — no bar has CLOSED below its floor since price
   was last above it (added 2026-08-17;
   **docs/supply_demand/broken_band_guard.md**).

A name that has simply sat inside a band for months is **not** "entering back
in" and is excluded (`test_not_a_reentry_when_price_never_left_the_band`). A
name **below** the band has broken support — the opposite signal — and is also
excluded (`test_not_a_reentry_when_price_is_below_the_band`), as is one that
closed below the floor and bounced back inside
(`test_a_close_below_the_floor_disqualifies_the_reentry`).

## Parameters (all house values)

| Constant | Value | Why |
|---|---|---|
| `SWING_WINDOW` | 5 | bars each side for a swing point |
| `MERGE_PCT` | 4.0 | swings within 4% merge into one band |
| `HALF_WIDTH_PCT` | 1.75 | width given to a single-swing band |
| `REENTRY_LOOKBACK_BARS` | 40 | window the run-up must sit inside |
| `MIN_RISE_ABOVE_PCT` | 5.0 | how far above the band it must have traded |
| `MIN_TOUCHES` | 2 | an untested band is not support |
| `MIN_ZONE_STRENGTH` | 40 | 0–100, tests + volume at the band |
| `STRUCTURE_SWING_WINDOW` / `MA_SLOPE_LOOKBACK` | 5 / 10 | the falling-knife guard (replaced `MIN_TREND_CHECKS` 6-of-8) |
| `STOP_BUFFER_PCT` | 1.5 | stop sits under the floor, not on it |
| `STOP_HIT_LOOKBACK_BARS` | 10 | how far back a proposed stop is checked against bars that already traded (warns, never gates) |

### Why the bands are WIDER here than on the /zones page

The `/zones` defaults (`ZONE_MERGE_PCT` 1.75, `ZONE_HALF_WIDTH_PCT` 0.6) produce
**~1%-wide bands**. Measured across the S&P 500 on 2026-08-13, those produced 21
"re-entries" — almost all utilities (AEP, DTE, LNT, AEE, DUK, ED, ATO), most of
them 1 bar after price crossed a band **0.5–0.8% wide**. Example: AON, band
`348.00–350.83`. That is price wiggling inside a line, not demand absorbing
supply.

Widening to merge 4.0 / half-width 1.75 and adding the trend gate produced 9
hits from the same 200 names — CMI, FIX, CIEN, COHR, GOOG — real pullbacks into
multi-tested bands (COHR fell **23.9%** from its high into a 3×-tested band).

The geometry is passed **per call** into `price_zones.compute(...)`. It must
**never** be applied by mutating the module globals — that would silently change
the `/zones` page and `orderflow.signals`, which share the module. Locked by
`test_price_zones_defaults_are_untouched_by_this_module`.

## The written entry / exit

`trade_plan()` (pure, unit-tested):

- **Entry band** = the demand band itself — buy *into* support, not through it.
- **Stop** = `STOP_BUFFER_PCT` under the band floor. Below the floor the reason
  for the trade is gone.
- **Target** = the **low of the first band of either origin above the entry
  band's top** — the first place sellers are known to be waiting. A demand-kind
  band overhead counts: broken support acts as resistance (see "documented
  decisions" below). When there is no band above, **`target` is `None`** and no
  R:R is shown. We do not invent a target
  (`test_trade_plan_without_overhead_supply_has_no_target_or_rr`,
  `test_trade_plan_targets_the_first_band_of_EITHER_origin_above_the_entry_band`).
  The OB reads' `target_basis` label says which it was — "next supply band" or
  **"broken demand band overhead"** (`_label_target_kind`, 2026-09-05).
- **`risk_exceeds_max`** flags a stop wider than `ABS_MAX_STOP_PCT` — the plan
  is surfaced as undefendable rather than silently handed over.

Display note: actionable levels use `level()` on the FE, which always keeps
cents. `money()` rounds $98.50 → "$99", which would show a **tighter stop than
the one computed** — never round a risk level
(`zonePlan.test.ts › level — actionable risk levels must never round`).

## Universe — "S&P 500 only" must mean the S&P 500

**Bug found + fixed 2026-08-13.** `sepa.universe.fetch_sp500()` fetches from
Wikipedia, which now answers **403** to the container. The old fallback returned
`UNIVERSE` — the **158-name curated momentum list**, a completely different
universe. Anything asking for "S&P 500 only" silently scanned 158 mega-caps.

The on-disk cache held the real **503 constituents** but was 76 days old, past
the 30-day TTL, so it was ignored.

### Root cause of the 403 (found 2026-08-13, same day)

`pandas.read_html(url)` **fetches the page itself**, via urllib, with urllib's
default `User-Agent`. Wikipedia blocks that agent. Measured inside the api
container:

| User-Agent | Result |
|---|---|
| urllib default (what `pd.read_html(url)` sends) | **HTTP 403**, 126-byte error page |
| `cheetah-market-app/1.0 (+https://pounce…)` | **HTTP 200**, 568 KB article |
| a browser UA string | HTTP 200 |

So it was never a hard block — just UA filtering. The fix is `_read_html_ua()`:
fetch with `requests` + a descriptive UA (per Wikimedia's UA policy), then hand
pandas the *already-fetched markup*. **Never pass a URL to `pd.read_html`** —
`test_sp500_never_hands_a_bare_url_to_pandas` locks that.

Two other candidate sources were measured and rejected:

- **Massive API** — has no index-constituents endpoint (404 on every path), and
  `I:SPX` returns `NOT_ENTITLED` on the stocks key anyway.
- **iShares IVV holdings CSV** — returns the 2.2 MB Cloudflare/JS disclaimer
  interstitial, not CSV, exactly like the IWB/IWV URLs already documented in
  `universe.py`. The Russell fetchers only work because they parse a
  **manually downloaded** `.xls`; there is no working automated iShares path to
  mirror.

### Resolve order

**fresh cache → Wikipedia (UA'd) → datahub CSV mirror → stale cache → curated.**

- `datahub` is `datasets/s-and-p-500-companies` on GitHub raw. Honest caveat:
  it is *derived from the same Wikipedia table*, so it is not an independent
  source of truth — but it is an independent **delivery path**, which is the
  exact failure mode that took Wikipedia out.
- A live source only wins if it also passes a **count sanity gate**
  (`_EXPECTED_COUNTS`: sp500 450–530, sp400 350–430). A parse that "succeeds"
  into 12 names is rejected and not cached, so a reshaped table degrades to the
  stale snapshot instead of silently truncating the scan.
- The expired snapshot of the real index still beats a fresh list of the wrong
  universe. Curated is the true last resort.

`fetch_sp400()` had the same 403 and the same 76-day-old cache; it now shares
the ladder, but falls back to `[]` and **never** to curated — leaking large-caps
into the mid-cap layer of a union would corrupt `broad`.

### Reporting which list was used

`universe.last_source(name)` records how each list resolved
(`cache` / `wikipedia` / `datahub` / `stale-cache` / `curated` / `empty`).

- Falling through to curated sets `universe_is_sp500: false` and the page
  renders a red warning — it must never quietly claim "S&P 500" over the wrong
  names (`test_scan_reports_when_the_universe_is_not_actually_sp500`).
- **A stale cache is the silent case, and it is the one that actually bit.**
  It holds the *real* constituents, so `universe_is_sp500` stays `true` and the
  warning above never fires — the list sat 76 days out of date with nothing on
  the page saying so. `universe_stale_days` now reports the age, and
  `DemandReentryPanel` shows a muted note that escalates past 120 days
  (`test_scan_reports_how_stale_the_constituent_list_is`,
  `DemandReentryPanel.test.tsx`).

## Surfaces

| Where | Component | Endpoint |
|---|---|---|
| `/supply-demand` → 🟢 Back in Demand tab | `DemandReentryPanel` | `GET /supply-demand/demand-reentry`, `POST …/scan` (the Scan button) |
| Individual stock → Setup tab | `ZoneMap` | `GET /supply-demand/zone-map/{symbol}` |

The zone map draws red supply bands, green demand bands, the entry band outlined
**BUY**, and dashed **STOP** / **TARGET** rules — the plan reads off the picture.
It renders for **any** symbol, including names sitting in overhead supply (the
SNDK case in Ajay's screenshot), not only re-entry hits.

Caching: 3h in-process, `force=True` on the Scan button.

## What it is NOT

Not a buy signal, and it feeds **no** scanner score and **no** Auto-Pilot gate.
It is a structural "where would I buy this, and where am I wrong" read. The
strict `is_buyable` gate still decides buyable-now.


## Universe expansion — beyond the S&P 500 (2026-08-13)

_Ajay: "expand the scan to best companies beyond S and p 500 increase in to
1000 others."_

The page now takes a `universe` parameter:

| Key | Names | What it is |
|---|---|---|
| `sp500` (default) | ~503 | S&P 500 |
| **`sp1500`** | **~1,506** | S&P 500 + 400 MidCap + 600 SmallCap |
| `sp400` | ~400 | MidCap only |
| `sp600` | ~603 | SmallCap only |

**Why S&P 400+600 and not a Russell slice.** They add ~1,000 names *outside*
the S&P 500 that still clear S&P's index-committee bar — including a
positive-earnings requirement. A raw Russell 1000/3000 slice is a
capitalisation cut with no quality screen, and overlaps the S&P 500 heavily.
"Best companies beyond the S&P 500" is a fair description of the mid/small
S&P indices; it is not a fair description of Russell.

`fetch_sp600` was added alongside the existing `fetch_sp500`/`fetch_sp400`,
sharing the same resolve ladder (fresh cache → Wikipedia with a real UA →
stale cache → last resort) and the same count sanity gate (540–650).
Like sp400 it falls back to `[]`, **never** to the curated list: leaking
large-caps into the small-cap layer would corrupt the union.

`fetch_sp1500` unions the three, deduped and order-stable (large → mid →
small). Each layer resolves independently, so one failing layer **shrinks** the
universe rather than silently mixing in wrong names, and the payload reports
per-layer provenance plus the WORST layer's staleness.

Each universe is cached separately — a single slot would have served an sp500
result to an sp1500 request for up to 3 hours
(`test_each_universe_is_cached_separately`).

**First run (2026-08-13):** 1,506 names, 1,482 scanned, **6.7 s**, 40 hits, of
which 7 cleared R:R ≥ 1.5 — the only cohort that backtested positive.


## Sorted by R:R, with liquidity + venue columns (2026-08-13)

_Ajay: "Sort the list by [R:R] … Also Dark pool rating. Give me some indication
of the Volume and entry becuz if there are no order flow or book map or volume
no point buying."_

**Sort is now R:R descending.** The walk-forward backtest found R:R ≥ 1.5 was
the only cohort with positive expectancy, so the number that decides whether a
row is worth reading leads the list. Ties break on freshness.

Each row also carries:

| Field | Meaning |
|---|---|
| `breakeven_win_pct` | `100 / (1 + R)` — the win rate needed just to break even. 4R → 20%; 1R → 50%; 0.03R → **97%**. |
| `liquidity.avg_dollar_vol_50` | average 50-day dollar volume |
| `liquidity.tier` | `deep` ≥ $50M · `ok` ≥ $10M · `thin` ≥ $2M · `illiquid` below |
| `venues.dark_pct` / `.blocks` / `.rating` | off-exchange share, large off-exchange block count, `heavy` ≥45% · `normal` ≥30% · `light` |

**Why liquidity is a first-class column.** A 4R setup on tape too thin to cross
is not a trade — the spread alone can exceed the edge, and the backtest models
only 2bp/side, which small caps will not honour. Rows below the `thin`
threshold get an amber border rather than the usual green.

**Dollar volume is not a spread measurement.** It is the honest proxy computable
for free from bars already in hand. A $5 stock at $3M/day still costs more to
cross than its tier implies.

**Venue detail is top-N only.** It costs one tape fetch per name
(`VENUE_DETAIL_TOP_N = 15`), so only the rows worth acting on get it. A dash in
the dark column means *no tape was pulled*, *not* 0% off-exchange — the UI
tooltip says so explicitly, locked by
`zonePlan.test.ts › explains the dash rather than implying zero dark volume`.

The off-exchange bucket still mixes dark-pool crossing with retail
wholesaler internalisation and the tape cannot separate them, so the copy says
"printed off-exchange" and never "institutional accumulation".

**First run (S&P 1500, 52 hits, 33.9 s):** every one of the top 12 by R:R came
back `ok` or `deep` — none were untradeable. HOOD printed **49.9%** off-exchange
(heavy, 15 blocks); LNN printed 19.6% with **zero** blocks.


## Defaults (2026-08-14)

_Ajay: "make the in demand page a default tab to load on S/D page.. and make it
default scan 1500."_

- `/supply-demand` now lands on **🟢 Back in Demand**, and that tab leads the
  row (a default tab sitting second reads like a mistake).
- **`DEFAULT_UNIVERSE = "sp1500"`**, on the API query default and the page's
  own selector. The S&P 500 alone surfaced ~3 names at a tradeable R:R; the
  full 1500 surfaces ~12.
- A **cron warm at 16:55 ET weekdays** keeps that default instant. The scan is
  ~7 s, but venue detail on the top rows costs a tape fetch each (~35 s total)
  and the cache is only 3 h — without the warm, the first view after an expiry
  pays the whole wait. It runs after the 16:50 pullback-scan, so the price
  cache is already hot.

Note for future edits: six tests exercise the single-layer sp500 path
(provenance, staleness, curated fallback, per-symbol errors). They now pass
`universe="sp500"` explicitly, because a bare `scan()` resolves three layers
and would call fetchers those tests do not stub.

---

## R:R is measured at spot, but the card instructs a band (2026-08-31)

Ajay: *"there is a problem with setup tab and Supply demand tab.. Can you make
sure logic is intact"*.

`trade_plan` reports `rr` at `entry_ref`, which is spot. The card renders
`Buy $entry_low–$entry_high`. Those are different trades whenever the first
objective sits close above the band, and on the live board that day they
disagreed on **41 of 96 rows** — every one of which passed the 1.0R floor at
spot and failed it at the top of its own buy range.

The worst was QBTS:

| | |
|---|---|
| entry band | $16.92 – $17.41 |
| stop | $16.67 |
| target | $17.42 |
| R:R at spot ($16.99) | **1.34R** — passes the floor |
| R:R at the band top ($17.41) | **0.01R** |

This is the VRT defect of 2026-08-13 in a new costume. That fix required the
target to clear the entry band's top (`lo > max(hi, last_price)`); it did not
require it to clear by anything worth trading, so a band sitting one cent above
still produces a plan whose reward is spent before the entry range ends.

### What changed

* `plan.rr_at_entry_high` — R:R at the worst fill the plan permits. **`None`
  when there is no target**, because "not computable" and "measured, fine" are
  different claims.
* `plan.thin_across_band` — true when that number is under `THIN_BAND_RR` (1.0,
  the same number as the floor: the claim is "this stops being a trade", not a
  second opinion on how good one is).
* `zonePlan.oneRCeiling(plan)` — the highest entry that still pays 1R, from
  `(target + stop) / 2`. When a plan is thin, `planLine` quotes **that** as the
  top of the buy range instead of the band top, and appends *"above $X this
  stops being 1R"*. QBTS's advertised band shrinks from `$16.92–$17.41` to
  `$16.92–$17.05` — three quarters of it was never buyable.

### What deliberately did NOT change

The R:R floor still gates on `rr`. Enforcing the band-top number would drop 43%
of the board overnight; that is Ajay's call, not a side effect of adding an
annotation. `test_thin_flag_does_not_change_which_rows_the_floor_keeps` locks
this.

Also unchanged, and **not** bugs — both are documented decisions that this audit
re-confirmed rather than "fixed":

* **The target may be a demand-kind band.** `price_zones.nearest_resistance` is
  the first band of any origin above price, because broken support acts as
  resistance. Origin is kept for colour only.
* **The target may not appear in the drawn zone lists.** Those are truncated to
  the four NEAREST per side (the strongest four until 2026-09-02); `nearest_resistance` is computed over all of
  them. Searching only the drawn lists is what gave KLAC an implausible 11.8R.

*Decision-support only. Not investment advice.*

---

## Reaching vs already reached (2026-08-31)

Ajay: *"What I am seeing in Demand zones and Deep Demand zones are already
reached Demand zones and bouncing.. I need the ones that are about to reach
and catch them"*, then *"Be the UX expert and find a way to show me both and
give me toggle reaching vs already reached."*

Both demand boards now carry a segmented toggle — **Already reached** (default,
the historical behaviour) vs **Approaching** — URL-backed as `phase=approaching`.

### Back in Demand: a fourth in-scan predicate

`approaching_read` (pure, `demand_reentry.py`) qualifies a scan record when:

* price is strictly **above** the entry band's top (inside = reached board's
  territory; below = breakdown),
* the band top is within `APPROACH_NEAR_PCT` (5%) below price,
* price has **fallen** ≥ `APPROACH_MIN_DRIFT_PCT` (0.5%) over the last
  `APPROACH_DRIFT_BARS` (5) sessions — the load-bearing half. Distance alone
  cannot tell an approach from a departure: a name 3% above its band that
  bounced yesterday sits at the same distance as one falling into it, and
  showing it as "about to reach" would put the bounce he already missed on the
  catch-it-early board (`test_a_name_rising_away_from_the_band_is_departing…`),
* the **same quality bar** as the reached board (MIN_TOUCHES,
  MIN_ZONE_STRENGTH) and the falling-knife guard — a weaker standard here
  would make the toggle a knife catalogue,
* with no close series the answer is None: "could not measure the drift" must
  never render as "approaching".

Captured in the same scan loop as `deep_rows`/`supply_rows` (fourth predicate,
zero extra price loads), served as `approaching_rows` on the payload.

**Ranking**: nearest band first, harder drift breaking ties. The cheetah
composite (flow × velocity × R:R) deliberately does **not** apply — the
approach board's question is *which band gets hit first*, and a strong-flow
name 4.8% out ranking above a neutral one 0.3% out would answer a different
question than the toggle promises. The R:R floor is also not applied to this
list: `rr` at spot describes a fill the board's whole premise says has not
happened yet.

### Deep Demand: a filter along an existing line

`deep_demand.read` already classified every row `in` (inside the second band)
vs `near` (falling toward it within NEAR_PCT), and the old board interleaved
them. The toggle splits along that existing line — reached = `in`,
approaching = `near`. A filter, not a new predicate: nothing about what
qualifies changed, and the second band's label says which moment it shows
("entering" vs "approaching"). Three tests that locked the mixed board were
updated to the split contract, per phase.

*Decision-support only. Not investment advice.*

### Approaching order blocks (2026-08-31, same day)

Ajay: *"Now find stocks closer to orderblocks. Now that we have orderblocks in
there from charts.. Add another switch to distinguish.. Approaching order
block vs Approaching Demand Zone."*

The Approaching phase on Back in Demand gains a target switch: **Demand zone**
(default, the tested swing-cluster band) vs **Order block** (`target=
order_block`). Same near (5%) / drift (−0.5%/5d) / knife standards; the LEVEL
differs — `approaching_ob_read` finds the nearest **fresh bullish order
block** below price on the DAILY frame (`smc.order_blocks`: last down candle
before a ≥1.2×ATR up-impulse). Two rules of its own:

* **Fresh only** — no bar's low has re-entered the block since it formed
  (checked from two bars after the block, so the displacement bar is not a
  visit). A mitigated block already had its first touch; listing it as "about
  to be reached" would describe an event that already happened. Locked by
  `test_a_mitigated_block_is_spent_and_never_listed`.
* **Age-capped** at `OB_APPROACH_MAX_AGE_BARS` = 90 daily bars — CONVENTION,
  like all SMC numbers here; every payload carries `cited: false` and the tile
  wears an "SMC · uncited" badge.

Trade geometry comes from `patterns.trade_levels` on the block itself (entry
at the top, ATR-buffered stop under the bottom, nearest overhead band as
target 1) — the tile draws the block in the SMC purple and prices the BLOCK's
trade, never the zone plan's. Computed inside `decide_from_frame` alongside
the zone read (same wiring lock — the empty-board bug must not be repeatable),
served as `approaching_ob_rows`, ranked closest-first. Deep Demand takes no
switch: its second band IS its level.

### The 2×2, and the phase lens on every tab possible (2026-08-31, same day)

Ajay: *"hit the 'In the orderblock' to see all the stocks"* + *"I need it in
all the tabs possible to implement"*.

**Back in Demand is now a 2×2**: the PHASE gives the moment, the TARGET the
level. `phase=reached & target=order_block` = price INSIDE a fresh bullish
block on its **first touch** (`in_ob_read`): the first bar whose low entered
the block is within `OB_FIRST_TOUCH_BARS` (5) — a name camped in its block for
weeks is a block that already failed to bounce, not an arrival — and no close
below the floor since the visit began (a close through the floor is the block
failing, not being tested). Youngest block first. Same knife guard, same
`cited: false`.

**Every other tab, honestly:**

| Tab | What it gets | Why |
|---|---|---|
| Back in Demand | full 2×2 | its rows carry both levels |
| Deep Demand | phase only | its second band IS its level; its names fail the trend gate the OB reads require, so an OB switch would render empty |
| Under Value | 3-state phase lens (All default) | a FILTER on its valuation screen: reached = inside a demand band, approaching = the demand scan's own near/drift constants (imported — one definition of "approaching" everywhere) |
| Gabbar Levels | 3-state phase lens (All default) | filters the in/near/away state it already computes against the hand-drawn bands |
| Into Supply | nothing | it IS an approaching board by construction — rallying into the lid |
| VCP / Topping / Session / 0DTE / Earnings / Winners / Support | nothing | their levels are pivots, chains, ledgers or on-demand reads — "approaching a demand zone" is not their question |

Route plumbing: the `phase` Query default became `""` = "the tab's own
default" — reached for the demand boards, All for the lens tabs — so every
pre-existing URL renders byte for byte. Locked by
`test_lens_tabs_default_all_while_demand_boards_default_reached`.

## Ordering — closest to the level first, money flow breaks ties (2026-09-03)

Ajay: *"make sure in our other demand and deep demand keep the closest one to
demand zones on the top. Of course CMF inflow too considered."*

One key, `supply_demand/demand_order.proximity_key`, now orders every demand
list **except** the reached Back-in-Demand board. Measured on the 17:22 UTC
scan that day, the three lists disagreed with the ask in three different ways:

| list | old key | what it did wrong |
|---|---|---|
| `deep_rows` | flow group → −CMF → in-band → dist | NOG, **2.53% above** its second band, ranked over 52 names already inside theirs because its CMF (+0.36) was the largest |
| `approaching_rows` / `approaching_ob_rows` | `dist_pct or 99.0` → drift | raw distance: LECO 0.01% sat over ITRI 0.07% on one tick of noise while the flow read was ignored; a true `0.0` distance sorted **last** |
| `in_ob_rows` | `bars_ago or 999` | 41 of 82 rows were 2 bars old and sat in universe order |

### The key

```
( state,            0 inside the band · 1 above · 2 below · 3 unknown
  bucket,           floor(prox_pct / 0.5)  — distance in 0.5% steps
  flow rank,        inflow 0 < neutral 1 < distribution 2 < missing 3
  −CMF-20,          stronger inflow / milder selling first; None → +inf (LAST)
  prox_pct,         exact distance
  *tail )           per-board tie-breaks: drift, band strength, symbol
```

`prox_pct` = (px − hi) / px × 100 above the band, 0 inside, (lo − px) / px × 100
below it. Below-band sorts **after** above-band: falling through the level is a
different event from arriving at it.

**`PROXIMITY_BUCKET_PCT = 0.5`** — house value. A raw-distance sort never lets
CMF speak (two floats are almost never equal); 0.5% on a $96 stock is ~$0.48,
inside one session's noise, while the CMF spread it yields to (−0.04 vs −0.28)
is a real difference in who is buying. The bucket edge is a step (0.49% and
0.51% are different buckets) — documented, tested
(`test_bucket_boundary_0_49_vs_0_51_is_documented_behaviour`), intended.

Worked example (live rows that day): Deep — COTY inside CMF +0.248 / APPF 0.81%
out CMF +0.282 / NOG 2.53% out CMF +0.364 → **COTY, APPF, NOG**. Approaching,
all in bucket 0 — MP 0.26% inflow / HIMS 0.18% neutral −0.031 / ITRI 0.03%
neutral −0.044 / VLTO 0.11% distribution −0.144 / EXR 0.08% distribution −0.275
→ **MP, HIMS, ITRI, VLTO, EXR** (raw distance gave the accumulated name last).

### Per list

* **Approaching (zone)** — `approaching_key`: proximity over `approaching.band`,
  tail = (drift_pct, symbol). The 2026-08-31 "harder fall first" tie-break is
  kept, but now only breaks an *identical* distance.
* **Approaching (order block)** — `approaching_ob_key`: the same over
  `approaching_ob.block`.
* **In the order block** — `in_ob_key`: block **age still leads** (youngest
  first, Ajay 2026-08-31), then the proximity key over the block — so inside an
  age tie flow and CMF decide. Missing age sorts last.
* **Deep Demand** — `deep_demand.sort_key` → `deep_key`: proximity over the
  **second** band, tail = (−strength, symbol). **Supersedes** the 2026-08-26
  *"rank these by highest CMF on the top"* order. A row carrying only the read
  (no `last_price`) ranks from its own state/dist_pct — same formula.
* **Back in Demand (`rows`)** — **unchanged**, R:R-first (`rr_floor.md`). Every
  row is inside its band; proximity is a constant there and cannot rank.

### Flow on every list

The order-block collectors never attached `inflow` (3/82 and 7/83 live rows
had one, by accident of also being reentry rows). They now run the same
`deep_demand.inflow_read(volume.analyze(...))` warm re-read the approaching
collector uses, time-boxed by **`OB_INFLOW_BUDGET_SEC = 30`** (each read is
milliseconds over a frame the pass just cached; the ceiling exists so a slow
cache can never stretch the 3-minute scan — past it rows ship `inflow: None`,
which sorts last, never first; counts are logged). Deep rows also copy
`deep_demand.inflow` to the top-level `inflow`, so `demand_order.inflow_of`
reads one place for every board and the Chart Maps flow badge renders on deep
and order-block tiles.

### Deep cap, per state

Until now one `MAX_ROWS = 80` slice ran after the sort. Closest-first puts
every in-band row ahead of every near row, so a day with 80+ in-band arrivals
would have emptied the Chart Maps *approaching* toggle. The cap is now
**`MAX_IN = 60` + `MAX_NEAR = 40`** (`deep_demand.cap`, order-preserving;
`MAX_ROWS` is the derived ceiling). Measured 2026-09-03: `deep_n` 242, the
kept sample 49 in / 31 near (~61/39) → ~148 in / ~94 near, both caps fill.
`deep_n` still reports the uncapped total.

### Order-dependent consumers

* `_apply_limit` — the API default `limit=60` truncates `rows` **by position**.
* `catalysts/signal_watch.py` — takes the first N symbols of the cached `rows`.
* Chart Maps re-ranks the non-reached boards at read time on the **live**
  print (see `docs/sepa/chart_maps_sort.md`), so the scan order is the order
  only when the tape is unreachable.

Guards: `test_demand_order.py` (the key), `test_deep_demand.py` (deep key +
cap), `test_chart_maps.py` (board wiring), `test_supply_demand_contracts.py`
(source guards: shared key on every non-reached list, no `or 99.0`, `rows.sort`
still R:R-led, position score on the boards).

*Decision-support only. Configured house ordering, not a book method.*

---

## 2026-09-05 review fixes — the re-entry read

Ajay 2026-09-05, on the S/D zone review: *"yes please fix the bugs"*. Four
findings against `demand_reentry.py`; the broken-band one is written up in
`broken_band_guard.md` §4. The other three:

* **One price basis.** `zones["last_price"]` and every band edge are 2dp quotes;
  the closes fed to `reentry_read` were raw. A Massive close 0.4c above the band
  top was INSIDE for the membership test and ABOVE for the read at the same
  time — `is_reentry True`, `bars_since_above 0`, "dropped in today" on a bar
  that never left. `decide_from_frame` now rounds the closes to 2dp, the basis
  every other number in the record already used (the alternative — raw closes
  for membership — would have shown a `last_price` inside the band on a row that
  said it was outside).
* **Deep Demand's break evidence is live.** `top_band_read` was `reentry_read`
  on the top band, asked only when price was BELOW it — and that read is the
  empty shape whenever price is outside the band, so `bars_since_top_break` and
  `fell_from_pct` were dead on every deep row (the module docstring's "None on
  older cached rows" was false). It is now `demand_reentry.band_break_read`
  (the same scan, no in-band requirement). **`bars_since_top_break` = age of the
  FIRST close under the top band in the current leg** — when it fell through;
  the most recent close under it is always today for a name still under its
  floor. `fell_from_pct` = how far above the top band the run-up before that
  break reached. None only on rows cached before 2026-09-05.
* **The target label.** `patterns.trade_levels` names target 1 "next supply
  band" for any opposing band; `approaching_ob_read` / `in_ob_read` hand it
  `nearest_resistance`, which is the first band of EITHER origin above price.
  A demand band overhead is a valid target (documented above) and now prints as
  **"broken demand band overhead"**. `trade_plan`'s docstring said "supply band"
  while its math never did; the docstring now matches.

No new thresholds: the answer rule reuses `MIN_RISE_ABOVE_PCT`, the price basis
reuses `price_zones`' 2dp rounding. Guards: `test_supply_demand_contracts.py`
block "reentry fixes 2026-09-05".

*Decision-support only. Not investment advice.*
