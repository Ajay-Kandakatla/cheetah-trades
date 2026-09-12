# 🚀 Explosive Growth tracker — the 100/100 screen

**Owner ask, 2026-09-11:** *"so now can you verify all the sectors and tell me
which new ones are blowing up? in Sales by 100% or more and 100 growth Quarter
over Quarter. Hot sector top growth stocks I need the same rules in demand zone
for these. I wanna know when ever these are in demand, separately just trackers.
I wanna keep adding during instituional orderblocks are present for these...
this is outside of regular supply and demand"*, plus *"remove the 700M rule for
this page"* and *"I want real growing stocks like AXTI and SABR with genuine
sales"*.

| | |
|---|---|
| Screen | [`backend/growth/tracker.py`](../../backend/growth/tracker.py) |
| Alerts | [`backend/growth/alerts.py`](../../backend/growth/alerts.py) |
| API | [`backend/growth/api.py`](../../backend/growth/api.py) — `GET /growth/board`, `POST /growth/refresh`, `GET /growth/at-demand` |
| Board | Chart Maps ▸ **🚀 Explosive Growth** |
| Push kind | `growth_demand_alert` |
| Tests | [`backend/tests/test_growth_tracker.py`](../../backend/tests/test_growth_tracker.py), `frontend/src/components/ExplosiveGrowth.test.tsx` |

---

## The screen

All four, on the latest reported quarter:

1. sales YoY **≥ 100%**
2. quarterly EPS YoY **≥ 100%**
3. **the PRIOR quarter's sales YoY > 0%**
4. a readable last price

**Leg 3 is the one that matters and it was not in the original ask.** One 100%
quarter off a collapsed year-ago base is a comparison artifact; two in a row is
a business. Without it the screen fills with names that lapped a bad quarter.

### Measured 2026-09-11 — **29 names**

*(An earlier mid-flight count of 25 was taken before the prior-quarter leg and the price-cache join were both in place; 29 is the shipped screen.)*

Run it yourself: `python -m growth build`.

The four sitting in a demand band with an **intact floor** on the day it was
built: **HHH, HNI, ARR, RKT**.

Two carry a ⛔ — on the board by his rule, refused by the engine: **PROP**
($0.45/share) and **FF** ($218M cap).

**AXTI is on it**, which is the point: sales **+145.9%** on a **+7.2%** prior
quarter, quarterly EPS **+185.0%**, cap **$3.95B**, $64.77.

## No market-cap floor — and what that costs

He asked for the $700M floor to be removed **on this page**, and it is:
`MIN_CAP_USD = None`, pinned by
`test_the_board_has_no_cap_floor` and by an AST guard that requires the constant
to be literally `None` so a reader sees the decision rather than an absence.

Every other board in the app filters to $700M+, **and so does the trading
engine** ([`docs/trading_safety_floors.md`](../trading_safety_floors.md)). So a
row can legitimately appear here and be unbuyable there. That is never silent:

| Row condition | Marker | Text |
|---|---|---|
| price < $2.00 | ⛔ | the engine will REFUSE to buy this |
| known cap < $100M | ⛔ | micro-cap, one buyer is the market |
| known cap < $700M | ⛔ | under the floor every other board uses |
| cap unknown | ⚠️ | the size floor could not be checked |
| $-volume < $20M/day | ⚠️ | below the institutional floor |
| $-volume < $5M/day | ⚠️ | one whale order moves this |
| promo-tagged | ⚠️ | the tag is promotion, never foresight |
| no zone bands | ⚠️ | outside the scan universe — blank, not empty |

The warning thresholds are **generated from `trading/safety_floor.py`**, never
retyped, and `test_warnings_quote_the_real_entry_floors` fails if they drift.

## The demand trigger

`growth_demand_alert` fires when a board name is **inside a tested demand band
whose floor has never been pierced**, and passes all three gates:

| Gate | Source | Why |
|---|---|---|
| `floor_held_gate` — **intact** | `alert_gates` | The ONE gate that measured: **+8.6pp win rate, n=31,861**. |
| `room_gate` — ≥5% overhead | `alert_gates` | His 2026-09-05 standing rule. |
| `demand_proximity_gate` — ≤1% above the band top, not under the floor | `alert_gates` | Same rule. An arrival, not a breakdown. |

**The standing phone gates apply even though the board is "outside regular
supply and demand."** The board is separate, the screen is separate, the kind is
separate — but *"Need only alerts on stocks that have atleast 5% to Supply and
also <1% bounce from demand zone"* is about what reaches his phone, and good
sales do not buy an exemption. A 100% sales grower with 2% of room overhead is
still a bad entry.

**Order blocks gate nothing.** He asked to *"keep adding during instituional
orderblocks"*, and the flag is carried in the push body and on the row — but the
2026-09-04 ICT study measured **+0.03R over 6,004 signals** against placebo, so
nothing may filter on it. `test_the_order_block_never_gates_anything` enforces
that by AST inside the *selecting* functions only, while
`test_the_order_block_IS_still_displayed` enforces that it survives as a read.
A name the engine refuses **still alerts**, labelled ⛔ in the body.

## Refresh

`0 9 * * 0` — **Sundays 09:00 ET**, right after the Sunday 08:00 weekly research
refresh writes the fundamentals it screens on. A Saturday rebuild would screen
last week's numbers. Deliberately **not** gated by `market_hours.gate`: Sunday is
a closed day and the gate would skip it forever.

`*/15 9-16 * * 1-5` — the alert pass, market days only, one push per symbol per
band per day.

That cadence is what answers *"make sure we are going to update this list as new
one come to the market.. Like getting added to russel 3000"* — new Russell
entrants reach the research cache on the weekly refresh and join the board the
same morning.

## Universe — and a correction

The board screens the weekly research cache (**3,738 rows**), which is the
`broad` universe: Russell 3000 ∪ micro-cap (IWC) ∪ ETFs, **3,703 names**.

**Earlier in this work I said ~5,300 ("massive").** That was wrong:
`load_universe("massive")` is **not a valid mode** — it falls back to the curated
**157** names and logs *"NOT the universe that was asked for"*. `broad` is the
widest real mode.

**Found while wiring this: AXTI was in no scanned universe at all.** It sits in
Russell 3000, so it reached `broad` — which only the 16:30 fast-scan runs — but
not `full` (2,651), which is what the hourly scan, `zone_store`, every board and
every alert actually use. Net effect: zero zone docs, so the name he named as
the shape he wants could never have fired a demand alert. It is now in the
curated list (2,651 → **2,652**), the same fix NTSK needed on 2026-09-10.

## The 🚀 chip — every Chart Maps tab

**Owner ask, same day:** *"I am hoping this new list will be considerd in all
chart maps. Like in Deep demand scan."* then, plainly, *"ALL TABS IN CHART
MAPS"*.

`GET /growth/tags` returns the board as a tiny `symbol → {sales, eps, refused}`
map, and [`GrowthChip`](../../frontend/src/components/GrowthChip.tsx) renders it
wherever a Chart Maps name appears. It is a **pointer** to the growth board,
never a second copy of the screen — the boards cannot drift into disagreeing
about what qualifies.

| Tabs | Renderer |
|---|---|
| zones, deep_demand, quick_bounce, breaking, gabbar, vcp, topping, ict, undervalue, zero_dte, earnings, winners | `PatternChart` (the one tile behind every board tab) |
| hot_pullback · patterns · session · signals · hot_sectors · catalysts · overnight · support | each board's own renderer |
| growth | none — it *is* the list |

The chip renders **nothing** for a name not on the board, so it costs a dense
surface nothing, and it takes the ⛔ tone when the trading engine will refuse the
name: good sales must never make an unbuyable row look clean. One fetch per page
load is shared by every tile through an in-flight promise; a failure is silent
and yields an empty map, because a growth-board outage must never blank a demand
board.

`test_the_growth_chip_reaches_EVERY_Chart_Maps_tab` (frontend contract) fails if
a new non-board tab is added whose renderer forgets the chip.

## The sector tree

Ajay 2026-09-11: *"I wanna see the secorts in the growth.. To show that only
some are growing.. I do need individual categories of these."*
Ajay 2026-09-12: *"What are these nymbers no headers"* ·
*"I need them to be clickable in to tickers and pick the top 10 in each sector."*

Built by `growth/api.py::_group()`, grouped on `companies.sector` / `.industry`
— the **GICS axis**, the same one the 🔥 Hottest tab uses. NOT the 24 curated
thematic sectors in `supply_demand/sectors.py`, and not the 13 themes in
`sepa/universe.THEME_UNIVERSE`; the three lists share no code path.

Four columns, each labelled since 2026-09-12:

| Column | Source | Meaning |
|---|---|---|
| **Sector** | `group` | GICS sector; a row with no tag lands in an explicit `(unmapped)` bucket rather than being dropped |
| **Qualified** | `n` **of** `n_scanned` | names clearing the screen / names of that sector in `sepa_research_cache` |
| **Hit rate** | `hit_rate_pct` | `n / n_scanned` — em-dash, never `0%`, when the denominator is unknown |
| **Med. sales** | `median_sales_growth_pct` | median YoY sales growth of the qualifiers |

The denominator is the whole point. `9` says nothing; `9 of 493` is the
statement he asked for.

**Med. sales is small-n by construction and the caption says so.** At 2 or 3
qualifiers a median is one name's number: Financial Services read `+8033.1%`
off 2 names on 2026-09-12 and Healthcare `+1842.7%` off 3 (PTGX alone
`+3749.2%`). Those are base effects on a collapsed year-ago quarter. **Hit
rate is the column with a real denominator** and the only one that supports a
sector-level read.

### Top 10, and why the cap is on the backend

`TOP_N_SYMBOLS = 10` in `growth/api.py`. `_top()` is the ONE place the list is
cut, at both the sector and the industry level — pinned by
`test_the_cap_is_one_named_constant_not_a_literal_in_the_loop`, because a
hand-typed `10` in one of the two levels is how they drift apart.

Two rules the tests hold:

- **The ten are the richest ten**, ranked by `sales_growth_pct` descending —
  the same axis the row's median is computed on, so the list and the number
  agree. A missing sales number sorts last, never crashes.
- **`n` stays the TRUE count.** The cap is display-only, so the row renders
  `+N more` instead of silently under-reporting the sector. Mutating `n` to the
  capped length is caught by
  `test_n_stays_the_true_count_so_the_row_can_say_plus_n_more`.

Every ticker renders through `<SymStrip>` → `<TickerLink>`, so Cmd-click /
middle-click open a new tab natively. `showWatchlist={false}` on these: ten ★
in one line is noise, and the star lives on the name's own page.

**Nothing on the 2026-09-12 board is actually capped** — the largest sector
carries 9 names. The cap is a guard for a wider list, not a change to what is
on screen today.

## Known limits

1. **Nothing here is backtested.** The 100/100 screen has never been measured
   forward. It is a discovery list; the board and the push both say so.
2. **The data is up to a week old.** Fundamentals come from the weekly research
   cache, so a fresh print can be missing. A blank renders as an em-dash, never
   as a zero.
3. **The board is WIDER than the alert path.** It screens `broad` (3,703) while
   zone bands are built from `full` (2,652) filtered to a known $700M+ cap. A
   row can qualify and have no zone read at all; `no zone bands` says so.
4. **710 scan-universe names (26.8%) have no cap in the shares cache** and are
   therefore invisible to every zone board — including **MU ($37.0B/day), TSM,
   LLY, SHOP, APH, AZO, CVNA, TGT**. 331 of them trade over $50M/day. This is
   NOT a growth-tracker bug; it is `big_cap_universe` treating "unknown" the
   same as "too small", on a cache that is warmed lazily and never swept.
   Measured but **not fixed here** — it is its own change.
