# 🎢 High Beta — Chart Maps tab (2026-10-14)

**Ask (Ajay 2026-10-14, verbatim, in order):**

1. "Can you build me a category or filter for High Beta stocks in Resilient and make a scan there were all down today especially a qqq series. Can you please make sure you do a full scan. I wanna see whcih stock have high potential to bounce back aggressively.. I need a tape burst notification specific for High Beta stocks from the reselinet separately and also other tape bursts from the Chart Maps page"
2. "I am rethinking the ask now, I think Resielient and high beta will not go hand in hand. Can you create a new tab for High Beta stocks"
3. "in the High Beta tab.I wanna able to sort my most volatile stocks"

His knob answers: "give me all 3 categories" (the cut), "a lot of AI stocks are down like 5 to 10% today like NBIS, IREN. Yeah look at historically but today after the CPI it was all down" (down today), "Show both sorts, you pick" (the order), "High-Beta tab names + all Chart Maps names" (the tape bursts — see `docs/alerts/tape_burst_kinds_2026_10_14.md`).

The first message says "bounce back". Every served string (the tab blurb, the ✨ entry, the Notifications rows, every `.py` string literal) quotes the other sentences and leaves that one out; only this doc quotes it in full. A wording test walks the AST of `high_beta_tab.py` and of the ℹ️ section.

URL: `https://pounce.ajaykandakatla.dev/chart-maps?tab=high_beta[&sort=hb_swing|hb_drop|hb_vol|<any header sort key>][&hb_dir=asc|desc][&hb=b15,b20,top20,qqq,d5][&hb_mode=all][&hb_all=1][&hb_view=sales]` (`hb_view` is FE-only URL state, never sent to the server)

**Status: UNMEASURED.** Display only. Nothing here gates a scan, sizes a position or enters a lane, and nothing gates on it. It is read by the two tape kinds' watch lists (🎢 watches it, 🗺️ subtracts it from its own) and by the Chart Maps membership snapshot (`chart_maps/membership.py`, the ✨ arrivals "also on" links). The tape pushes describe prints, not this order.

## Why a tab, not a 🛡️ box

He withdrew the 🛡️ version ("will not go hand in hand"). 🛡️ is about names that held on a red day; this tab is about names that move most with the market. A box inside 🛡️ would also have broken six 🛡️ pins.

## The universe

- `full` (Russell 3000 ∪ S&P 1500 ∪ curated ∪ themes ∪ traders ∪ promo) **∪ the Nasdaq-100**: "especially a qqq series", "make sure you do a full scan".
- The Nasdaq-100 comes from `universe.fetch_nasdaq100()`, the Wikipedia list with its fresh → live → stale cache ladder. Members carry a **QQQ** badge, and the `qqq` box (`QQQ · Nasdaq-100`) keeps only them.
- If the list cannot be read (an exception or `[]`), there is no badge, the box is shown OFF with the reason, and a ticked box passes no name. The tab never falls back to a curated list.
- NBIS and IREN are in the static layers of `full`: NBIS in the curated `UNIVERSE`, and both in `THEME_UNIVERSE["ai_power"]`. A test pins this.
- ETFs are counted, never rated (`INCLUDE_ETFS = drop10_tab.INCLUDE_ETFS`, False). Leveraged and inverse ETFs would otherwise own the top 20%. Delisted fates are counted too.

## β, one engine

- β = the house `sepa/beta.py` formula: cov/var of daily **log** returns against SPY (`universe.BENCHMARK`) over the last `BETA_LOOKBACK` (252) common bars. It is read through the pure `beta.beta_from_frame` on frames already in memory, with no fetch.
- Only bars strictly **before** the session are used (`zone_store.drop_today`), never today's in-progress bar.
- A name with too short a history has β None. It is counted as `short_history` and never listed.
- 🛡️ Resiliency keeps its own β (% returns on the SPY calendar, None on any hole), so one name can print two β values. Unifying them is HIS call (spec §7 #13). The card says which engine it used.

## The three categories ("give me all 3 categories")

| key | box label | rule | constant |
|---|---|---|---|
| `b15` | 🎢 β ≥ 1.5 | β ≥ `B15_MIN` | `B15_MIN = 1.5` # Ajay 2026-10-14 |
| `b20` | 🎢 β ≥ 2.0 | β ≥ `B20_MIN` | `B20_MIN = 2.0` # Ajay 2026-10-14 |
| `top20` | 🎢 Top 20% by β | the `ceil(n × TOP_PCT / 100)` highest of the rated stocks; ties at the cut included | `TOP_PCT = 20.0` # Ajay 2026-10-14 |

The tab lists the **union**. Each name is badged with every category it is in (`🎢 β 2.34 · ≥1.5 · ≥2.0 · top 20% · QQQ`). The boxes follow the 🏎️ Dual Momentum pattern: **ANY** by default; "must match all" (`hb_mode=all`) keeps only names passing every ticked box. A box with no read (None) never passes.

Two more boxes: `qqq` (above) and `d5` = 📉 Down 5%+ today, today's move ≤ −`DOWN_CHIP_PCT` (`DOWN_CHIP_PCT = 5.0` # Ajay 2026-10-14). `d5` is None when the name has no read today, so a ticked box hides it.

## Today's move (the official prior close)

- **Which session:** the 🔻 clock (`drop10_tab.mode_for`). `live` in RTH (snapshot re-read on `LIVE_TTL_SEC` = 60 s), `after_close` 16:00–20:00 ET (the regular-session close), and `closed` before the open, overnight, weekends and holidays (the last closed session off the cached bars, basis `last_session`).
- **Prior close:** 🛡️'s official rule (`resiliency_tab.official_prev_close`). The snapshot's `prev_day_close` is used when its day bar is dated the session AND it sits within `drop10_tab.PREV_CLOSE_TOL_PCT` (1%) of the cached close; otherwise the cached close is used.
- **Held out** (state `suspect`, move None, named under the grid): a live prior close more than 1% off the cached one, or a move the price layer's 5× guard flags (`drop10_tab.suspect_reason`).
- **Not read:** `no_print` (the snapshot row is not dated the session; this is the overnight `date` trap, read only through `drop10_tab.day_from_snapshot`), `no_snapshot` (no answer after asking twice), `stale` (closed mode with no cached session bar). A name with no read is **never** `+0.00%`.

## What the tab shows (AMENDMENTS A1)

- **Default view = the names red today** (his ask: "all down today"). `hb_all=1` (`VIEW_LABEL` "include green names") lists every High-Beta name; green names sort after the red ones because their drop is 0.
- `rows`: a compact row for **every** listed name, in the active order: symbol, β, categories, QQQ, move, state, β × drop, σ, prior close, basis. They render as a dense table above the charts (the Bonde density pattern).
- **Liquidity floor — the tab opens with "No floor"** (Ajay 2026-10-14, a screenshot of the Liquidity menu: *"Give me all option and default to all in this please"*): `board.TAB_DEFAULT_MIN_TIER["high_beta"] = "any"`, read through `board.default_min_tier(tab)` by `board()`, the API (`min_tier` omitted) and the FE (`defaultMinTier(tab)`); every High-Beta name can take a chart (still the top `LIMIT_MAX` 80 by the sort) and a thin name keeps its `thin` flag in the table. Deep / Tradeable / Thin stay in the menu and an explicit `min_tier` applies. Every other tab keeps `DEFAULT_MIN_TIER` "ok". The membership snapshot's writer rule (`membership.is_default_request`) treats the tab's own default (or `None`) as the default request, a chosen floor as a filtered view.
- `tiles`: chart cards for the top 80 only (`board.LIMIT_MAX`). The header says "{n_red} red of {n_listed} High-Beta names · charts for the top 80".
- Every card: the category pill, the 📅 today pill (🛡️'s `TODAY_PLAIN_FMT` / `TODAY_LAST_FMT`), the β / Today / β × drop / σ (50d) stats, and the 🏎️ demand band and room.

## Orders (served, tab-scoped — "Show both sorts, you pick" + "sort my most volatile stocks")

| key | label | order |
|---|---|---|
| `hb_swing` (also `default`) | 🎢 β × today's drop | red names by `β × |move|`, largest first; then up/flat by smallest move; then unread names |
| `hb_drop` | 📉 Today's drop | deepest first; then up/flat; then unread |
| `hb_vol` | 🌊 Most volatile (σ 50d) | σ = sample stdev of the last `SIGMA_BARS` (= `resiliency_tab.VOL_AVG_BARS`, 50) daily % returns — the σ the 🛡️ cards print — largest first; no σ sits last |

β × drop is an order, not a forecast (AMENDMENTS A2: β × drop, never drop ÷ β). The default is MY pick (spec §7 #4). The 50-session σ window is his open call (DECISIONS K3a). Any other sort key on this tab (and `default`) → `hb_swing`, and `hb_drop` / `hb_vol` on any other tab → `default` (the 🔻 precedent).

## Header sorts (2026-10-14 b)

**Ask (Ajay 2026-10-14, verbatim):** "Can you add sort function on the headers and also 5 day and 21 days columns to show how they were reacting in price like hot sectors and also add sales tab make it like hot sector with some important metrics like EPS, QUAlity and other colums that show the strength of the stock"

His knob answers (DECISIONS2): **K1** a Price | Sales toggle inside 🎢 (same names, same `hb_all` switch; Sales = the 🔥 Hottest fundamentals columns through Hottest's own functions). **K2** "Both (4 columns)": own 5 / 21-day move AND the same vs RSP; SPY's and RSP's own once in a header line. **K3** the strength column on Sales = "RS vs SPY (63-day)" only. **K4** every column of both views sorts on a header tap (first tap = the column's first direction, tap again flips, like 🔥); the top-80 chart cards follow the active (server) sort; the three presets stay and become their columns' header sorts.

One server-side engine with two paths. A preset (`hb_swing` / `hb_drop` / `hb_vol`) in its own first direction runs the old `sort_key` verbatim — byte-identical orders, golden-tested on the old fixture's captured orders. Every other (key, direction) runs 🔥 Hottest's engine: `HOT._rank_names(rows, lambda r: HOT._sorter(col, dir)(sort_fields(r)))` — missing values LAST in both directions, exact ties A→Z, a NaN dropped by `HOT._num` (sorts as missing). The direction rides `hb_dir` (`DIR_PARAM`; `asc` | `desc`; absent, blank or junk → the column's first direction, never a 4xx). The FE sends `hb_dir` only when it differs from the column's first direction and drops `sort` for β × drop desc, so the default page request stays the default (`membership.is_default_request` True — the 2026-10-14 trap). The cards follow because `board.high_beta_tiles` builds the tiles in `rank` order; `out["sorts"]` stays the three presets.

| sort key | column | first | value read |
|---|---|---|---|
| `hb_swing` | β × drop | desc | `swing`, red names only (preset: legacy `sort_key` when desc) |
| `hb_drop` | Today | **asc** | today's move when read (preset: legacy when asc) |
| `hb_vol` | σ | desc | `sigma_pct` (preset: legacy when desc) |
| `hb_symbol` | Symbol | **asc** | the ticker, A→Z / Z→A |
| `hb_levered` | 🔗 | desc | the number of tagged leveraged ETFs; untagged = missing (AMENDMENTS2 B3) |
| `hb_ret_5d` / `hb_rel_5d` | 5 days / 5 days vs RSP | desc | the row legs |
| `hb_ret_21d` / `hb_rel_21d` | 21 days / 21 days vs RSP | desc | the row legs |
| `hb_beta` | β | desc | `beta` |
| `hb_cats` | 🎢 | desc | the number of categories |
| `hb_qqq` | QQQ | desc | member 1 / not 0 / None when the Nasdaq-100 list was not read |
| `hb_sales_yoy` | Sales YoY | desc | `fund.sales_yoy` |
| `hb_sales_tier` | Sales trend | desc | `fund.sales_tier` (🔥 `TIER_RANK` via `_sort_value`) |
| `hb_q_eps_yoy` | Q EPS | desc | `fund.q_eps_yoy` |
| `hb_net_margin` | Margin | desc | `fund.net_margin` |
| `hb_eq_score` | Quality | desc | `fund.eq_score` |
| `hb_next_earnings` | Next ER | **asc** | `fund.next_earnings` (🔥's date rule; asc = soonest) |
| `hb_rs_spy_63d` | RS vs SPY (63d) | desc | the row legs |

`TAB_SORTS = tuple(HEADER_SORTS)`, the three presets first in their old order. The block serves `sort_dir`, `sort_preset` (the preset key iff the active order is a preset in its first direction, else null) and an order line naming the column and how it runs ("Order: the 5-day move, lowest first." + how many with no value sit last). A flipped preset is NOT the exact mirror of the preset: the presets keep `sort_key`'s ties (−β, then symbol, the red / green / unread buckets), every other order ties A→Z. The header UX is 🔥's (`button.hs-sort`, `th.is-sorted`, `aria-sort`, the sticky first column, `useHScrollCue`'s "more columns →"); the table never sorts rows itself.

## 5 days / 21 days

- **Formula:** the tracker engine, never a port. Own move = `RT.trailing_return(bars, n)` (percent, `bars[-(n+1)]` close → `bars[-1]` close) for n = `LEG_FAST` 5 / `LEG_SHORT` 21 / `RS_WINDOW` 63 (= `rotation/tracker.py` `WINDOW_FAST` / `WINDOW_SHORT` / `WINDOW_MED`), rounded 2 dp (the `member_stats` rule). "vs RSP" = `RT.traction_row` — the stock's move minus the bench's over the same sessions, in percentage points; None when either side is missing, so a raw move never lands in a vs column. RS vs SPY = the same against SPY over 63 sessions.
- **Closed bars, three modes:** the windows END at the last CLOSED session. `live` (RTH) → through the prior close; today's live move stays in the Today column, and the served line says so. `after_close` / `closed` → the session's own close (= the Today print) is the last bar.
- **No new fetch:** each listed name keeps its last `TAIL_BARS` 64 closes (`close_tail`) from the frames the base build already reads (the closes dict `rate_one` builds for σ). SPY and RSP keep theirs only when their prior date is the prior market day.
- **The bench rule:** vs columns use RSP (`EW_BENCH`, the 🔥 basis). When RSP has no read for the windows they use SPY (`REL_FALLBACK` = `tracker.BENCHMARK_FALLBACK`, the tracker's own rule) and the labels say "vs SPY"; when neither was read the vs columns are blank. `returns_line` prints SPY's and RSP's own 5 / 21, the close they end on and which bench the vs columns use.
- **Precision:** cells print `LEG_TEXT_DP` 1 decimal ("+12.3%", "+4.1 pp"), like 🔥 Hottest's `pct()` (AMENDMENTS2 B8); the served numbers and the sort stay the tracker's 2-dp values.
- DISPLAY only: nothing gates, sizes or alerts on them. Compare 🎢 and 🔥 5-day numbers only in closed mode (🔥's come from the rotation snapshot built after 16:30).

## Sales view

- **Toggle:** `?hb_view=sales` (`TABLE_VIEW_PARAM`, `VIEW_PRICE` / `VIEW_SALES`, labels "Price" / "Sales"). FE-only: it never reaches `board()`, a switch fires no fetch, and the active sort survives the switch. The server serves both column sets every time (`table.columns`, `table.sales_columns`, `table.views`).
- **Columns:** Symbol, 🔗, Today, Sales YoY, Sales trend, Q EPS, Margin, Quality ⓘ, Next ER (the six heads and three titles = 🔥 `HS_COLS` byte for byte, contract-pinned), then RS vs SPY (63d).
- **Hottest's functions, one read per build:** ONE `HOT._decision_map` + ONE `HOT._earnings_map` over the listed names (~600), rows via `HOT._fundamentals_row` (the YoY pair guard blanks Sales YoY / Q EPS on a mismatched pair and keeps the tier), served as `rows[].fund` with exactly `FUND_ROW_KEYS`; the ⓘ explainer via `HOT._quality_info`, served as a copy with `group_rows` None (🎢 has no group rows; the memo's dict is never touched). The FE draws every cell with 🔥's own `HsFundCell`, exported from `HottestSectors.tsx` (golden: 🔥's DOM unchanged).
- **Memo:** `_fund_memo[(session, universe)]`, `FUND_TTL_SEC` = `BASE_TTL_SEC` 1 h (MINE — cache freshness, not a rule), read by `build()` AFTER `_base_for` — the 8 s base build does not grow. A newly listed name forces a re-read.
- **not_read:** a failed or empty read is never memoised; the block serves `fundamentals.state = "not_read"` with the reason, and the Sales cells stay blank — never zero, never "—" invented — until the next refresh (60 s live / 30 min closed). The research cache's "disabled until restart" latch (`sepa/research.py`) is left as is (his call).
- **UNMEASURED** (`FUND_NOTE`): Quality is a description (ⓘ), not a tested edge; nothing ranks a name as better, or gates, sizes or alerts on Sales, EPS, margin, Quality or RS. Not advice.

## Memo and cost

- The 🔻 memo pattern verbatim: an in-process memo keyed by (mode, session, universe), stale-while-revalidate, one warm thread per key, a `FAIL_RETRY_SEC` back-off, and a late older-session build dropped. There is no cron and no Mongo store. The request path never parses or scans; a cold read answers `warming`.
- Base half (once per session, `BASE_TTL_SEC`): ONE `prices.bulk_cached_frames` over the universe + SPY/RSP/QQQ (never a fetch), then β, σ and the categories per name.
- Live half: one snapshot fan-out over the listed names only.
- Build time, **measured** 2026-10-14 22:1x ET (prereg Data section) in a throwaway read-only container (`--cpus 2`), closed mode, session 2026-10-14: base half **8.1 s** on 2,742 scanned (2,621 rated, 601 listed; top-20% cut at β ≥ 1.60); live half **0.0 s** (closed mode reads no snapshot). The live-session snapshot over ~600 names is not timed.
- That run's top-20% cut (β ≥ 1.60) sat above `B15_MIN` 1.5, so every `top20` name was also `b15`: on that day `top20` added no names to the union.

## The study ("look at historically")

Pre-registered in `docs/research/high_beta_2026_10_14_prereg.md` before any outcome run. The script is `backend/scripts/high_beta_study.py`, the artifact `backend/scripts/high_beta_measured.json`, and the literal `backend/chart_maps/high_beta_measured.py` (`{"state": "unmeasured"}` until pasted).

- **Question:** after a name's own red close of 5%+ (ALL sessions, any SPY direction), do names with β ≥ 1.5 close differently from same-session, same-β-tercile names that did not fall 5%+, over the next 3 sessions (1 and 5 reported)? "SPY-red days only" is reported on the line beside it, never the verdict (AMENDMENTS A13; prereg Q1 step 6).
- **CI:** a moving-block bootstrap over sessions (block 5), also clustered by symbol; 2000 draws; seed 20261014 (all MINE, AMENDMENTS A6). Plus a leave-top-5-sessions-out line.
- **Survivors-only cohort** (today's list, AMENDMENTS A7). The served line says so.
- What the result may change: ONLY the served study line. The default order, every box and both push kinds stay as built; changing them is HIS call.

## Watch list for the 🎢 tape kind

`GET /chart-maps/high-beta/watch` returns the listed names biggest drop first, at or above the house $2 share-price floor (`trading.safety_floor.MIN_SHARE_PRICE`, AMENDMENTS A13), uncapped (the kind caps at 150). A `warming` answer means an empty list for that poll only. The cron process reads it over HTTP and never warms in-process (AMENDMENTS A9).

## ℹ️ Rules panel

`rules_info._high_beta_section()`, key `high_beta`, sits right before `gajjala`. Every number in it is read from `high_beta_tab` (and the 🔻 / 🛡️ / tape modules it reuses), never typed; a test walks its AST for numeric literals and forbidden words. The study line is the tab's own `study_block()` text, and the note says UNMEASURED until the literal reads `measured`. The alerts list carries both tape kinds (see the alerts doc).

## Numbers

| constant | value | whose |
|---|---|---|
| `B15_MIN` / `B20_MIN` / `TOP_PCT` | 1.5 / 2.0 / 20 | Ajay 2026-10-14 |
| `DOWN_CHIP_PCT` | 5 | Ajay 2026-10-14 |
| σ window (`VOL_AVG_BARS`) | 50 | Ajay 2026-10-14 (K3a), the house value |
| `BETA_LOOKBACK` | 252 | house (`sepa/beta.py`) |
| `PREV_CLOSE_TOL_PCT` | 1% | house data guard (🔻) |
| memo TTLs | 60 s live / 30 min closed / 1 h base | house cache freshness (🔻), not rules |
| top-20 = ceil, ties included; study draws / seed / horizons / block; `SESSIONS_MAX` 250 | — | MINE (AMENDMENTS §8) |
| `LEG_FAST` / `LEG_SHORT` | 5 / 21 sessions (= `tracker.WINDOW_FAST` / `WINDOW_SHORT`) | Ajay 2026-10-14 (the ask, K2) |
| `RS_WINDOW` | 63 sessions (= `tracker.WINDOW_MED`) | Ajay 2026-10-14 (K3) |
| `RS_BENCH` SPY · vs bench RSP (`EW_BENCH`) | — | Ajay 2026-10-14 (K3, K2) |
| `REL_FALLBACK` SPY | — | house (the tracker's fallback rule) |
| `TAIL_BARS` | 64 = `RS_WINDOW` + 1 | derived |
| `FUND_TTL_SEC` | 3600 s (= `BASE_TTL_SEC`) | MINE — cache freshness, not a rule |
| research staleness | 16 d (`research.CACHE_TTL_SEC`, through `HOT._decision_map`) | house |
| `LEG_TEXT_DP` | 1 decimal; own "%", vs / RS " pp" | MINE (= 🔥 `pct()`, AMENDMENTS2 B8) |
| first directions | Today asc, Symbol asc, Next ER asc, every other column desc | MINE / K4 |
| 🎢 / QQQ / 🔗 ordinals | category count / member 1, not 0, unread None / tagged-fund count | MINE |
| column order | Price and Sales, as listed above | MINE (his call) |
| view labels | "Price" / "Sales" | MINE wording |

## His calls (open)

1. The label "🎢 High Beta", the emoji and the slot right after 🔻 Down 10%+.
2. Red-only default with an "include green names" toggle.
3. The QQQ box (the badge is always on).
4. The β × drop order as the default.
5. The 50-session σ window.
6. Two β engines (🎢 house log-return β vs 🛡️'s own).
7. Today's move against the official prior close (🛡️'s rule) with 🔻's 1% hold-out.
8. The study design: the 3-session horizon primary; primary = all sessions, SPY-red-only line beside it; β terciles; the bootstrap.

2026-10-14 b (header sorts · 5 / 21 days · Sales view), defaults shipped as listed:

9. 5 days, 21 days and RS end at the last CLOSED session (in market hours through yesterday's close, today stays in Today) — vs ending at today's live print.
10. First tap: Today deepest drop first (= 📉 `hb_drop`), Symbol A→Z, Next ER soonest first (🔥), every other column highest first.
11. The generic "Sort" dropdown is hidden on 🎢 (the three buttons and the headers own the order).
12. Column order: Price = Symbol, 🔗, Today, 5 days, 5 days vs RSP, 21 days, 21 days vs RSP, β, β × drop, σ, 🎢, QQQ; Sales = Symbol, 🔗, Today, the six 🔥 columns, RS vs SPY (63d) last.
13. The active sort survives the Price ⇄ Sales switch (the order line names it).
14. RS vs SPY = the 63-session move minus SPY's, in percentage points (the house `rel_` rule) — not a ratio, an RS line or a percentile; UNMEASURED.
15. Sales numbers re-read hourly; a failed read waits for the next refresh (≤ 30 min closed); the research cache's "disabled until restart" latch is left as is.
16. The Quality header keeps 🔥's "Minervini Ch.8" hover on a non-SEPA tab (the SEPA-scope rule).
17. Next ER prints a past date as 🔥 does (no past-date guard).
18. The cards get no new stat (5 / 21 days and the fundamentals live in the table).
19. One sort key (no 🔥 shift-click tie-breaks on 🎢).
20. Cells print 1 decimal like 🔥 Hottest, while the sort reads the 2-dp number (AMENDMENTS2 B8).

(The 🔗 column sorts — by the number of tagged funds — because K4 said every column; it is not a his-call any more, AMENDMENTS2 B3.)

## Files

- `backend/chart_maps/high_beta_tab.py`, `backend/chart_maps/high_beta_measured.py`, `backend/sepa/beta.py` (`beta_from_frame`, `log_returns`)
- `board.high_beta_tiles` / `board.high_beta_watch`; `chart_maps/api.py` (`hb`, `hb_mode`, `/chart-maps/high-beta/watch`); `chart_maps/membership.py` (`MEMO_BLOCK_KEY`, TTL)
- `backend/scripts/high_beta_study.py`, `docs/research/high_beta_2026_10_14_prereg.md`
- `rules_info._high_beta_section`, `backend/tests/test_rules_info_high_beta.py`, `backend/tests/test_high_beta_tab.py`, `backend/tests/test_high_beta_study.py`
- FE: `lib/highBeta.ts`, `components/HighBetaBoardNote.tsx`, `lib/chartMaps.ts` (`CM_TABS`, `TAB_META.high_beta`, `boardQuery`), `pages/ChartMaps.tsx`, `lib/cardLadder.ts`
- 2026-10-14 b: `backend/chart_maps/high_beta_tab.py` (`HEADER_SORTS`, `TABLE_COLUMNS` / `SALES_COLUMNS`, `sort_fields` / `order_rows`, the legs, `fund_read` / `_fund_for`, `returns_line`, `fundamentals_block`, `table_block`), `board.high_beta_tiles` / `board.board` (`hb_dir`), `chart_maps/api.py` (`hb_dir`); tests `backend/tests/test_high_beta_table_2026_10_14.py`, `backend/tests/test_high_beta_board_sort.py` (+ pin updates in `test_high_beta_tab.py`, `test_high_beta_levered.py`)
- 2026-10-14 b FE: `components/HottestSectors.tsx` (`HS_FUND_KEYS`, `HsFundRow`, `HsFundCell`) + `HottestSectors.fundcell.test.tsx` + `__fixtures__/hottest_fund_cells_golden_2026_10_14.json`; `components/HighBetaBoardNote.tsx` (`COLUMN_KEYS`, the header sorts, the view toggle) + `HighBetaBoardNote.sales.test.tsx`; `lib/highBeta.ts` (`HB_DIR_PARAM`, `HB_VIEW_PARAM`, `parseHbDir`, `parseHbView`, `hbHeaderNext`); `lib/chartMaps.ts` (`boardQuery` `hbDir`); `pages/ChartMaps.tsx`; `styles.css` (`.cm-hb-scroll`, the 🎢 `.hs-sym` override); `scripts/contracts.mjs` ("🎢 header sorts + Sales view"); `lib/newFeatures.ts` (`chart-maps-high-beta-table-2026-10-15`); fixture `__fixtures__/high_beta_board_2026_10_14.json` recaptured

Deploy `api frontend` (and `cron` for the tape kinds).
