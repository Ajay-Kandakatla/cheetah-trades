# Promo-circuit watch

**Shipped 2026-09-01.** Tracks the StockTwits alert/pump accounts we caught
seeding the 8/31–9/1 tiny-float movers, and turns their fresh tags into
(a) a SEEDING watchlist on the Catalysts page and (b) a −15 conviction
penalty on the predictions board. Includes the two EDGAR tells from the same
study. **Not book logic** — catalysts family, uncited market-structure
convention (no Minervini scope; see feedback_sepa_book_scope).

## Where it came from (measured basis)

The 2026-09-01 chatter-provenance study traced WHO called 11 board movers in
advance, with exact StockTwits message timestamps (global sequential IDs) and
EDGAR acceptance times:

- **The "predictions" were mostly the promotion itself.** @ShangVXO touted
  PETZ (8/19) and FLYE (8/20) via "_ProfessorGamma"; both went vertical the
  same Monday 8/31 on near-silent public tapes (FLYE: zero public posts
  8/29–9/1 premarket, 10,957× volume). @topstockalerts ran the NWGL alert
  loop from 8/19 into a 98.4M-share resale shelf. @beppels watchlisted RDAC
  8/21+8/25, re-flagged it premarket the day it ran +44%.
- **Chatter velocity LAGGED price in 5 of 10 cases** — crowds arrive after
  the candle. The only advance signals were **named accounts**, not volume
  curves.
- **The one genuinely predictive public signal was EDGAR**: Markiplier's
  GPRO 13G hit EDGAR six sessions before the +46% day; resale/shelf filings
  (NWGL, SSM 19.9% direct, LIDR ATM) marked the exit-liquidity setups.

Hence the two rules encoded here: **a roster tag is the promotion, never
foresight** (negative signal, early warning), and **13D/G + shelf filings
ride along** for every watched ticker.

## Architecture

`backend/catalysts/promo_circuit.py`

1. **Roster** — `PROMO_ACCOUNTS`, user-editable like
   `frontend/src/lib/fundTiers.ts`. Tiers: **S** documented pump-circuit
   tell (silent-tape verticals), **A** alert-room promoters (sell access,
   victory-lap loops), **B** watchlist reposters (context only — never
   penalize).
   **Maintenance recipe:** when Ajay says "add account X to the promo
   circuit", add one entry with tier + a *dated* evidence line, deploy
   `api cron`. No other change needed.
2. **Sweep** (cron, `python -m catalysts.promo_circuit`) — fetches each
   account's public user stream (`streams/user/{handle}.json`, ~14–20
   requests per run; paginated back past the previous sweep so overnight/
   weekend cron gaps can't drop a prolific account's early-evening seeds),
   extracts ticker tags, upserts per `(account, ticker)` into Mongo
   `promo_circuit_tags` with a **per-ticker** message-ID high-water mark
   (re-sweeps never re-count; an account-wide mark could bury a sibling
   ticker whose upsert failed). A dormant account re-tagging after ≥14 days
   resets `first_tagged_at` — a new campaign. Weekdays every 30 min
   7:00–19:30 ET; weekends every 2 h (the 8/31 movers were groomed on
   Saturday/Sunday). ETFs/megacaps/crypto symbols are excluded at
   extraction. StockTwits sits behind Cloudflare bot protection that 403s
   `requests` — the fetch uses **httpx + a browser UA** (measured
   2026-09-01), which is also the root cause of the chatter fetcher's
   0-message bug.
3. **Board** (`GET /catalysts/promo-circuit`, 10-min Mongo cache) — tags
   from the last 14 days grouped by ticker, joined with Massive daily bars
   since the first tag and EDGAR flags. Reads Mongo only; StockTwits is
   never fetched inline. `POST /catalysts/promo-circuit/sweep` = manual run.
4. **Predictions penalty** — `tags_for(tickers)` returns S/A-tier tags from
   the last 7 days (per-account override via `penalty_days`: ShangVXO's is
   **14d**, because his pumps land ~10 *sessions* after the tag — PETZ ran
   session 9, FLYE session 8, and 53% of his measured hits peaked after
   session 5); `predictions._extract_signals` adds `promo_circuit_tagged`
   (−15, **not** a hard veto, and only when `market_cap` is unknown or <
   **$2B** — the exit-liquidity thesis doesn't apply to a liquid name
   tagged in passing) plus a bear-thesis line. B-tier never penalizes.
   Tier is resolved against the **live roster** at read time, never the
   tier stamped at sweep time, so roster edits apply to existing tags
   immediately.

## Decision tables

Status per ticker (pure `classify_status`; price base = the last close
**before** the first session on/after the first tag — a weekend/premarket
tag must not measure the run against the run day's own close, or RAN/DUMPED
become unreachable for exactly the weekend-groomed movers):

| Status  | Condition |
|---------|-----------|
| RAN     | max gain since first tag ≥ **+30%** |
| DUMPED  | RAN and now ≤ **−40%** from the post-tag peak |
| SEEDING | **latest** tag ≤ **7 days** old, hasn't run — *the row that matters* (keyed to the latest tag so a campaign kept warm >7d still shows SEEDING the morning it's re-flagged) |
| QUIET   | no fresh tag, never ran |
| UNKNOWN | no daily bars |

EDGAR tells (pure `edgar_flags_from_filings`, off
`evidence._fetch_sec_filings(days=30)`):

| Tell | Forms | Window | Meaning |
|------|-------|--------|---------|
| owner_stake | SC 13D/G (+ /A) | 14 d | the study's one predictive public signal (GPRO) |
| shelf | S-1, S-3, F-1, F-3, 424B*, FWP (never S-8) | 30 d | dilution plumbing — exit-liquidity tell |

## Frontend

`PromoCircuit.tsx` — 🎪 tab on `/catalysts`. SEEDING table first, then
RAN/DUMPED ("how the last campaigns ended"), roster with evidence lines,
sweep freshness, method note rendered. Account chips carry the sample post
in the tooltip. Prediction cards need no changes — the penalty arrives
through the generic signal stack.

## Limits (stated on the board too)

- StockTwits-only. The study could not read Reddit directly (blocked +
  archive stale) and X at all; a group can groom elsewhere and stay
  invisible here until the tag hits StockTwits.
- Accounts get renamed/banned; roster handles are exact strings. A failed
  fetch shows in `sweep.accounts_failed` on the board.
- Selection: the roster is the accounts we CAUGHT once (2026-09-01). It will
  grow; absence of a tag is weak evidence of absence.
- Massive daily aggs may lack brand-new listings → status UNKNOWN, never a
  guess.

## Tests

`backend/tests/test_promo_circuit.py` — roster shape, tag extraction
(high-water mark, multi-symbol posts, excluded symbols, bad timestamps),
price-action math, full status decision table incl. the RAN boundary, EDGAR
windows (amendments count, S-8 excluded), predictions penalty wiring incl.
negatives (no signal / empty handles → no penalty; not a hard veto),
offline behavior, crontab + API source guards.
`frontend/src/components/PromoCircuit.test.tsx` — SEEDING render, table
split, EDGAR chips, no-flag dash, empty board + roster, HTTP failure.

## 2026-09-02 pm — the board reads live

Ajay: *"Is this page real time? I do not see realtime update… show me when it
was tagged with a date."*

- **Sweep every 10 min** on weekdays (was 30): a fresh tag reaches the board
  within 10 minutes.
- **Tag stamps:** every row shows *First tag* and *Last tag* as an ET
  date/time ("Sep 1 · 3:20p ET") next to the day count; rows carry
  `first_tagged_at` / `last_tagged_at`.
- **Live cells:** the one live fetch that feeds the ⚡ table (30 s while the
  tape is open) also feeds a *Today* column (live % vs prior close, PRE/AH
  badge) and a **live *Since tag*** (`pct_since_tag_live` = last print vs the
  board's own pre-tag base, `base_close`) on every SEEDING / RAN / DUMPED row —
  marked with a green dot; the daily-close read stays in the tooltip and is the
  fallback when nothing has printed.
- Status (SEEDING → RAN → DUMPED) is still classified on **daily closes** by
  the sweep, so a name that "blew up" intraday shows the move live but flips
  status at the next sweep.

## 2026-09-02 pm — 📈 tag tape: before or after the move?

Ajay: *"Small graph of price change from the time they said it and where the
price went… did they actually PSA it before the blow up or after?"*

Every board row has a 📈 toggle that opens `PromoTagTape`
(`GET /catalysts/promo-circuit/tape/{ticker}`, `backend/catalysts/promo_tape.py`):
5-minute closes incl. pre/post market (shaded) from the session before the
first tag to now (capped at 6 sessions), a marker at each account's first
(solid) and last (dashed) post with the price at that bar in the tooltip, and a
read from `analyze()` (pure, tested):

| verdict | rule (both measured from the price at the first tag) |
|---|---|
| BEFORE_THE_MOVE | < 3% in the hour before, ≥ 5% to the peak after |
| MID_RUN | ≥ 3% in the hour before and ≥ 3% more to the peak |
| AFTER_THE_MOVE | ≥ 5% in the hour before, < 3% more to the peak |
| NO_RUN / NO_TAPE_AFTER | neither / nothing printed since the tag |

The sweep keeps first/last per account, not every post, so a chatty account
shows two markers. In-process cache 60 s.

**Every post is kept (2026-09-02 pm).** Ajay: *"the reason I asked for this
graph is to find the actual announcement time vs the price action… TLYS
already went up 15% when they called it."* The sweep now stores each post
(`posts: [{id, at, body}]`, last 40 per account × ticker, `$push … $slice`);
the tape marks every one (first solid, later dashed) and lists them under the
chart with the price at that bar, the move in the hour before, and the peak
after — so a 9:23p watchlist mention and a 3:35p victory lap read separately.
`promo_circuit.backfill_posts(days)` fills history once (`$addToSet`, no
high-water-mark changes).

## 2026-09-02 pm — room to run, links, inline tape, recency order, early callers

Ajay: *"add the accurate names to the list. Add room to run. and also give me
the stocktwits link of the stock and our SEPA link along with and the small
graph of when they announced vs where it is. Sort by most recent announcement"*
+ *"when I go to the sepa page I wanna land on the sepa page with supply tab
open"* + *"default supply demand to 6 months in that tab"*.

- **Roster**: 8 early callers from the winner-provenance study (22 names that
  ran on 9/2; who tagged them BEFORE the move) added as **tier B** —
  `theblueflames`, `stock_catcher`, `blakecapital26`, `jmjtrading`,
  `birdseyetrader`, `davidscott`, `sadyk189`, `robbysinvestmentllc`. Each
  carries its measured Aug-2026 audit (entry = first close on/after the tag,
  hit = +30% touch within 15 sessions, dump = close ≤ 60% of the peak). Radar
  only: no conviction penalty, never a phone alert (`PROMO_ALERT_HANDLES` is
  still `topstockalerts`). Higher +30% touch = more volatile picks, not an
  edge — every one medians red by day 5.
- **Room to run** (`promo_live.room_read`): the Portfolio 🎯 read applied to
  every tagged name — first band overhead (supply at/above the print, or a
  demand band it already broke = `broken_support`) and the % from the live
  print to its bottom. States `UNPRICED / CLEAR / IN_BAND / NEAR (≤2%) /
  ROOM`, plus `PENDING` (zones not computed yet) and `UNAVAILABLE` (engine
  error). Zones come off daily bars (`price_zones.for_symbol(max_zones=None)`)
  and are cached 30 min in memory **and** Mongo `promo_zone_cache`, shared
  between the API and the cron; a live call never computes on its own clock
  (a cold container answered in 22 s when it did) — misses go to one
  background worker and read `PENDING` until the next 30 s tick, and the
  5-min `promo_live` cron warms every stale name after its alert pass
  (`warm_zones`). `CLEAR` = nothing found in the 1y read,
  **not** unlimited.
- **Links**: the symbol cell = `TickerLink` → `/sepa/<T>?tab=supply` (SEPA
  page landing on the Supply / Demand tab) + `ST↗` → the StockTwits stream +
  an explicit `SEPA` link. The SEPA page's Supply / Demand zoom now starts at
  **6 months** (`SEPA_SUPPLY_WINDOW`); Chart Maps keeps the engine's 3m.
- **Inline mini tape** (`MiniTape`, `?lite=1` on the tape route →
  `promo_tape.lite_payload`: every 3rd 5-min bar + the last one, `t/c/s`
  only, tags without bodies): a 120×30 sparkline per row, fetched once per
  ticker per page life and only when the row scrolls into view; marker = the
  first post, colored by the read (green before / amber mid-run / red after);
  click = the full tape row.
- **Order**: every board table is sorted by the latest announcement
  (`sortRecent`: `last_tagged_at`, else `first_tagged_at`, newest first). The
  ⚡ live table keeps today's move as its order.

Tests: `test_promo_live.py` (decision table incl. broken support, PENDING /
UNAVAILABLE, live rows attach `room`, budget + warm-only-stale, cron order),
`test_promo_tape.py` (lite stride + trim, route flag), `test_promo_circuit.py`
(early callers radar-only), `PromoCircuit.test.tsx` (recency order, links,
room cell states, mini tape per row + failure), `PromoTagTape.test.tsx`
(`miniLayout` geometry, once-per-ticker cache, error), and a source guard for
the 6-month default.

## 2026-09-02 pm — sticky column headers

Ajay: *"Keep the headers static on scroll until the end of the table."*
`.pcw .og__table thead th { position: sticky; top: var(--sticky-top, 0) }`
with the page background and an inset-shadow rule (collapsed borders don't
travel with a sticky cell). Two traps, both silent: (1) the phone-width
`.app` / `.main` rules used `overflow-x: hidden`, which makes the ancestor a
scroll container and disables every sticky descendant — now `overflow-x:
clip`; (2) the phone nav is itself sticky (`z-index: 100`), so `NavBar`
publishes its measured height as `--sticky-top` (`hooks/useStickyTop.ts`,
ResizeObserver) and the headers sit under it. Guarded by
`scripts/contracts.mjs` ("promo board column headers stick until the table
ends") and `useStickyTop.test.tsx`.


## 2026-09-02 pm — one sortable table, five tells per name

Ajay: *"add a new column to call out russell addition to the promo circuit.
Another column for sales and another for catalyst and another for any 8k or
SEC filings"* + *"I want both be the same with dates and new columns and give
me sort functionality on possible columns."*

**One table** (`PromoTable` / `UnifiedRow` in `PromoCircuit.tsx`): the ⚡ live
table and the three board tables share the same 17 columns — Symbol, Session,
Last, Tagged by, First tag, Last tag, Today, Since tag, Peak, Room, Tape,
Russell, Sales, Catalyst, 8-K, SEC, Status. A board row and a live row for the
same ticker merge (`unifyBoard` / `unifyLive`); a live-only row shows plain
handles (no tier claim). The live table defaults to today's move, the board
tables to the latest announcement. **Sorting** (`COLUMNS`, `sortRows`,
`nextSort`): 15 sortable headers (not Tagged by / Tape); click = the column's
natural order (numbers desc, text asc, Russell date / Catalyst verdict asc),
again = reverse, again = back to the default; empty cells always sort last;
`aria-sort` on the header.

**The five tells** live on the 10-min board (`promo_circuit.build`) and ride
onto the live rows unchanged (`promo_live.live_rows`):

| Column | Source | Shape | Cost |
|---|---|---|---|
| Russell | `russell_for()` — raw read of `russell_watch_cache` (never `build()`) | `{board, add_event{in_index, lists_published…}, as_of}` | free |
| Sales | `sales_for()` — `sepa.research.sales_snapshot` → `promo_sales_cache` (7d) → ≤40 `canslim.fundamentals_for` lookups per build inside 25 s | Bonde `{tier, growth_yoy_pct (YoY, never QoQ), prior_yoy_pct, accelerating, score, reason}` | one Mongo query + capped provider fill |
| Catalyst | `_catalyst()` — 48h Massive news + the evidence keyword tagger, `promo_news_cache` (30 min) | `{n_48h, n_bullish, n_bearish, top{title,url,publisher,published_utc,tone}, verdict REAL/THIN/NONE}`; `None` = fetch failed (unknown ≠ none) | one news call per name per 30 min, capped rows only |
| 8-K | `sec_flags_from_filings()` over the SAME submissions list `_edgar_bundle()` fetches once | newest 8-K ≤14d `{form, filing_date, url, items[], n_14d}` — `evidence._fetch_sec_filings` now carries the `items` codes | free (shared fetch) |
| SEC | same list, everything else ≤30d | `{n_30d, forms[], latest, n_form4, has_offering}` + the existing 13D/G / shelf chips (the old EDGAR column folded in) | free (shared fetch) |

`_edgar_bundle` replaces three would-be EDGAR fetches per row with one; the
capped pass (`EDGAR_ROW_CAP`, actionable statuses only) now runs `_enrich` =
bundle + catalyst.

Tests: `test_promo_circuit.py` (8-K window/items/roll-up, catalyst verdicts,
sales ladder with cap + cache, Russell raw join, one-fetch bundle),
`PromoCircuit.test.tsx` (17 shared headers, the five cells + dashes, click
sort tri-state with empties last, pure sort helpers, live-only rows).


## 2026-09-03 — valuation floor

Ajay: *"Filter out any company that its valuation is less than a billion."*
`promo_circuit.market_caps_for()` sizes every board name from the weekly
shares cache (`sepa.volume_movers`): shares_outstanding × the row's last
close, the provider's own market_cap when shares are missing, then ≤60
`shares_for` lookups per build inside 20 s for names the cache never saw.
`market_cap` rides on the board row and the live row. The FE hides
`market_cap < $700M` by default (`MIN_CAP_USD`; it was $1B for one afternoon —
Ajay 2026-09-03 pm: *"In the PROMO tab I do not want to see anything in less
then 700 million"*) (`passesCapFloor`, checkbox above the tables,
remembered in `localStorage pcw.capFloor`), keeps unknown caps visible with
"cap n/a" (hiding what we cannot size would hide real names), and prints
the cap under each symbol (red when it is under the floor and the toggle is
off). Tests: `test_market_caps_for_cache_then_capped_fetch`,
`test_build_rows_carry_market_cap_for_the_floor`, the FE "valuation floor"
describe.
