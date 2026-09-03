# Chart Maps — sorting, liquidity, and what a daily bar cannot tell you

Ajay 2026-08-17, two messages:

> *"in the chart maps do you have the same logic as In demand page from supply
> demand such as volume sort and you gave a dedicated dropdown can you add them"*

> *"Did verify that volume is retailer and dark pool exactly what you did in the
> other place same with SEPA we want to make that average turn over is high for
> these"*

The second message caught a real mistake in the first attempt, and the check it
prompted turned up two more defects. All three are fixed here.

Code: `backend/chart_maps/board.py`, `backend/orderflow/tape.py`,
`backend/supply_demand/demand_reentry.py`.
Tests: `backend/tests/test_chart_maps.py` (37 new).

---

## 1. I mirrored the wrong dropdown

The first attempt copied the **Breakouts** dropdown — today's volume, $ turnover,
conviction, RS. The one he meant is on `DemandReentryPanel.tsx`:

```
🎯 R:R (default) · 🧍 Retail imbalance · 🧍 Retail % of volume
🟣 Off-exchange % · 📊 Relative volume · 🕐 Freshest re-entry
```

Retail and off-exchange **are** that dropdown. `SORTS` in `board.py` now leads
with those three, then relative volume, then the four that come free from a scan
row and have no equivalent there.

## 2. Retail and dark pool are not in a daily bar

A daily aggregate is one consolidated volume number. It **includes** off-exchange
prints — Massive's `/v2/aggs` is SIP-consolidated — but it does not **split**
them, and SEPA scan rows carry no `venues` or `retail` key at all (checked
2026-08-17: both absent).

That data comes from a per-symbol **intraday tape pull** (`/v3/trades` →
`darkpool.split_venues` + `retail.identify`). So the three tape sorts trigger
`attach_tape()`, which reuses `demand_reentry._enrich_one` unchanged — the two
surfaces cannot disagree about what "retail" or "dark" means.

**It enriches a pool, not the universe.** `TAPE_POOL_MULT * limit` (72 for a
24-tile board) taken by the ordinary ranking, then re-sorted. That is a real
limit — the demand page has the same one, enriching its top 15 by R:R — and the
page states the pool size rather than implying a full-scan ranking.

### "Retail imbalance" genuinely cannot be answered off-session

Measured on USB, off-session:

```
venues: dark_pct 16.3, dark_shares 1.6M of 9.9M total    ← works
retail: retail_pct_of_volume 2.3                          ← works
retail: imbalance_pct null, lean null                     ← cannot work
```

Telling a retail **buy** from a retail **sell** needs the NBBO, and
`orderflow.retail` refuses to guess: *"Retail prints identified but unsigned —
no NBBO for this session, and sub-penny signing mis-signs 28% of trades."*

A sort over an all-null column silently returns the default order, which looks
like a working sort and is not one. The board now reports `sort_unavailable` and
the page says so.

## 3. The one-calendar-day tape fallback — a bug in the existing board too

Every consumer walked back exactly **one calendar day** when today was empty. On
a Monday pre-open that lands on Sunday. Measured 2026-08-17 (a Monday, ~00:30 ET):

```
USB 2026-08-17 (Mon, pre-open)  0 rows
USB 2026-08-16 (Sun)            0 rows
USB 2026-08-15 (Sat)            0 rows
USB 2026-08-14 (Fri)       53,075 rows   ← dark 16.3% of 9.9M shares
```

So **all weekend and every Monday pre-open**, the Back in Demand board's
off-exchange and retail columns came back empty and its dark-pool sorts ranked a
column of nulls. The data was always there; nobody asked for the right day.

`orderflow.tape.last_session_trades()` walks back by **trading** days — skipping
weekends without a request, and continuing past a holiday because a holiday
simply returns no prints. `_session_venues` and `_enrich_one` both route through
it, so the fix lands on the existing Back in Demand board as well as here.

---

## 4. The liquidity floor — "average turn over is high for these"

He was right. The board inherited SEPA's gate, and that gate is an **OR**
(`sepa/adr.py:45`):

```python
liquid = avg_dollar_vol >= 20_000_000 or avg_shares >= 200_000
```

The shares branch exists so a genuinely tradeable low-priced name is not excluded
for its price. It also admits names nowhere near institutional turnover.
Measured on the live board — **7 of 17** strong-VCP names passed on shares only:

| symbol | 50-day avg $ vol | tier on the Back in Demand scale |
|---|---|---|
| ANTX | **$1.5M** | **illiquid** |
| BOLD | $4.1M | thin |
| WEST | $5.4M | thin |
| EGBN | $8.5M | thin |
| DIN | $11.2M | ok |
| UHAL | $15.0M | ok |
| CADL | $15.4M | ok |

The same stock was reading differently on two of his surfaces. The thresholds are
now **imported** from `demand_reentry`, never re-declared, so they cannot drift:

| tier | floor | |
|---|---|---|
| deep | ≥ $50M/day | institutional tape |
| **ok** | **≥ $10M/day** | **default** — comfortably tradeable in retail size |
| thin | ≥ $2M/day | small size only, wider spreads |
| any | — | no floor |

Effect on the live board:

```
any   17 tiles   dropped 0
thin  16 tiles   dropped 1     (ANTX)
ok    13 tiles   dropped 4     ← default
deep   8 tiles   dropped 9
```

Two decisions:

* **An unknown turnover FAILS a real floor.** Letting it through means the one
  name whose liquidity we could not measure is the one that shows up unfiltered.
* **The floor runs before the ranking**, so the 24 slots are filled with names
  that clear it rather than leaving gaps where thin names were cut.

### Still open: the Back in Demand board itself has no floor

`is_reentry = band.is_reentry and trend_ok and quality_ok` — liquidity is
computed, rendered as a tier badge, and **gates nothing**
(`demand_reentry.py:584`, filtered at `:977`). An illiquid name that passes the
zone rules ships to that board with an amber border and nothing more.

Deliberately **not** changed here: that board is used daily with real money and
adding a filter to it silently shrinks his list. It is a one-condition change
whenever he wants it.

---

## Where the honesty is enforced

| Decision | Guard |
|---|---|
| The dropdown mirrors Back in Demand | `test_the_dropdown_mirrors_the_back_in_demand_one` |
| Tier scale imported, never re-declared | `test_the_tier_scale_is_imported_from_the_demand_page_not_redeclared` |
| ANTX at $1.5M is illiquid | `test_the_real_ANTX_case_is_illiquid` |
| Unknown turnover fails a real floor | `test_an_UNKNOWN_turnover_FAILS_a_real_floor` |
| Unsigned retail stays null, never 0 | `test_tile_metrics_reads_the_venue_and_retail_blocks` |
| Sort runs backend-side, before the cut | `test_the_per_theme_cap_does_not_apply_to_an_explicit_sort` |
| Missing metric sorts last, never first | `test_a_tile_with_NO_value_sorts_LAST_not_first` |
| Every offered sort has a comparator | `test_every_offered_sort_actually_orders` (parametrised off `SORTS`) |
| Winners tabs offer no sort they cannot answer | `test_the_winners_tabs_offer_no_sort_because_they_have_no_volume` |


---

## Update 2026-08-17 — the declutter, and what "turnover" was

> *"Remove default themes checked and AI sector from drop down… Volume instead
> or turn over. What is turn over is it average volume?"*

**No — turnover was never average volume.** The dropdown carried three
volume-ish entries across two different units:

| key | was labelled | what it actually is | example (SWKS) |
|---|---|---|---|
| `volume` | 📈 Today's volume | today's **shares** | 3.8M |
| `turnover` | 💵 $ turnover | today's **dollars** (shares x price) | $265M |
| `avg_turnover` | 🏦 Liquidity (avg $ vol) | **50-day average** dollars/day | $370M |

One ambiguous word spanning all that is why the question had to be asked. The
fix is subtraction plus units in the labels:

* **`turnover` removed.** It ranks nearly the same names as today's volume,
  differing only by share price, so it was the least informative of the three.
* **`volume` → "📈 Volume today (shares)"**.
* **`avg_turnover` → "🏦 Avg daily volume ($)"**. Kept: it is the number behind
  the liquidity floor he asked for the same morning, and `passes_liquidity`
  reads its key.

### "AI sectors" was two claims wearing one hat

`theme` was both `DEFAULT_SORT` **and** a dropdown entry labelled
"🤖 AI sectors (default)". Those are different things:

* the **theme lead** is the *Themes first* checkbox
* the **default order** is the tab's own score — base tightness on VCP, R:R on
  Back in Demand

Splitting them (`DEFAULT_SORT = "default"`, labelled "⭐ Best setup first") is
what allows `THEMES_FIRST_DEFAULT = False` without deleting the concept of a
default order. The checkbox still turns the AI-ecosystem lead back on in one
click.

This is narrower than the standing "breakout lists lead with AI sectors" rule:
/chart-maps is a study surface, not a breakout list, and the forced lead was also
reshuffling the per-theme spread cap underneath every other control on the page.

| Decision | Guard |
|---|---|
| No label says "turnover" | `test_the_word_TURNOVER_is_gone_from_every_dropdown_label` |
| Both volume sorts state their unit | `test_the_two_surviving_volume_sorts_state_their_UNIT` |
| Today's $ volume is not offered, but the metric survives | `test_todays_dollar_volume_is_no_longer_OFFERED_as_a_sort` |
| AI sectors is not a dropdown entry | `test_AI_sectors_is_not_a_dropdown_ENTRY_any_more` |
| Themes do not lead by default | `test_themes_no_longer_lead_by_DEFAULT` |
| Every entry point honours that default | `test_every_board_entry_point_honours_that_default` |
| The checkbox still works | `test_the_checkbox_can_still_turn_the_theme_lead_back_ON` |

## Update 2026-09-03 — default order per demand tab, read at the live print

> *"make sure in our other demand and deep demand keep the closest one to
> demand zones on the top. Of course CMF inflow too considered."*

Two things changed on the demand boards. The **order** is now one shared key
(`supply_demand/demand_order.proximity_key`: inside the band → nearest in 0.5%
buckets → inflow > neutral > distribution > missing → stronger CMF → exact
distance; full rationale in `docs/supply_demand/demand_reentry_methodology.md`),
and it is applied **at read time on the live print** rather than trusting the
scan's order. The demand scan cache is warmed at 9:25 and 16:55; by mid-session
the name that was 2% out may be inside the band, and the 7% bounce gate that
shipped earlier the same day already fetches the live prices for exactly that
reason — the board now fetches them **once** and reuses them for both the gate
and the rank, falling back to the scan's `last_price` per symbol when the tape
has no print.

`_score` on those boards is the **position** in that order (`float(len(rows) -
rank)`, the supply-tab pattern pinned by `test_into_supply.py`) — one definition
of the order, not a second weighted number. `_finish` still ranks `_score`
descending, so *Themes first* (when on) and an explicit dropdown metric override
it exactly as before.

| Tab / cell | Default order | Read-time | Gate |
|---|---|---|---|
| Back in Demand · **reached · zone** | R:R (measured floor), then the cheetah composite flow × velocity × R:R — **unchanged** | none (rows are all inside the band) | 7% bounce |
| Back in Demand · **approaching · zone** | closest to the band first, flow/CMF inside a 0.5% bucket, drift then symbol | live print | 7% bounce |
| Back in Demand · **approaching · order block** | same, over the block | live print | 7% bounce |
| Back in Demand · **reached · order block** ("In the order block") | **youngest block first**, then the proximity key inside an age tie | live print | 7% bounce |
| Deep Demand · reached | inside the second band first, flow/CMF inside a bucket, stronger band | live print | Bonde sales + 7% bounce |
| Deep Demand · approaching | nearest the second band first, same tie-breaks | live print | Bonde sales + 7% bounce |
| Into Supply | nearest lid first (unchanged, `into_supply.sort_key`) | — | — |
| VCP / Topping / Gabbar / Under Value / others | their own metric (unchanged) | — | — |

The Deep Demand board's weighted score (flow 100k / CMF 10k / in-band 100 /
sales ×0.05, 2026-08-26) is gone: sales **gate** (Bonde) and are said on the
badge; they do not rank. The note strings say the order out loud ("inside the
second band first on the live print, money flow (CMF) ranking within a 0.5%
distance bucket") instead of "inflow names sort first".

Flow badges now read `demand_order.inflow_of(row)` (top-level `inflow`, else
`deep_demand.inflow`), so order-block and deep tiles wear the 💰 / 🔻 badge the
Back-in-Demand tiles already had — the scan attaches `inflow` to those rows
since the same change.

Order-dependent consumers to remember: the API's default `limit=60` and
`catalysts/signal_watch.py` both truncate the **reached** `rows` by position;
neither reads the re-ranked boards.

| Decision | Guard |
|---|---|
| Shared key on every non-reached list | `test_every_non_reached_demand_list_sorts_with_the_shared_key` |
| Position score, live re-rank, reached composite intact | `test_chart_maps_reranks_on_the_live_print_with_a_position_score` |
| Live prices fetched once per board | `test_approaching_reranks_on_the_live_print_not_the_scan_price` |
| Board order == the key's order with themes off | `test_approaching_board_score_is_the_position_in_the_shared_key` |
| Same age → CMF, missing flow last | `test_in_the_block_same_age_ranks_by_cmf_and_missing_inflow_last` |
| Deep: in before near, nearest near first | `test_deep_demand_in_band_leads_and_the_nearest_near_row_leads_its_phase` |
