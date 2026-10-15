# 🎢 High Beta — Chart Maps tab (2026-10-14)

**Ask (Ajay 2026-10-14, verbatim, in order):**

1. "Can you build me a category or filter for High Beta stocks in Resilient and make a scan there were all down today especially a qqq series. Can you please make sure you do a full scan. I wanna see whcih stock have high potential to bounce back aggressively.. I need a tape burst notification specific for High Beta stocks from the reselinet separately and also other tape bursts from the Chart Maps page"
2. "I am rethinking the ask now, I think Resielient and high beta will not go hand in hand. Can you create a new tab for High Beta stocks"
3. "in the High Beta tab.I wanna able to sort my most volatile stocks"

His knob answers: "give me all 3 categories" (the cut), "a lot of AI stocks are down like 5 to 10% today like NBIS, IREN. Yeah look at historically but today after the CPI it was all down" (down today), "Show both sorts, you pick" (the order), "High-Beta tab names + all Chart Maps names" (the tape bursts — see `docs/alerts/tape_burst_kinds_2026_10_14.md`).

The first message says "bounce back". Every served string (the tab blurb, the ✨ entry, the Notifications rows, every `.py` string literal) quotes the other sentences and leaves that one out; only this doc quotes it in full. A wording test walks the AST of `high_beta_tab.py` and of the ℹ️ section.

URL: `https://pounce.ajaykandakatla.dev/chart-maps?tab=high_beta[&sort=hb_swing|hb_drop|hb_vol][&hb=b15,b20,top20,qqq,d5][&hb_mode=all][&hb_all=1]`

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
- `tiles`: chart cards for the top 80 only (`board.LIMIT_MAX`). The header says "{n_red} red of {n_listed} High-Beta names · charts for the top 80".
- Every card: the category pill, the 📅 today pill (🛡️'s `TODAY_PLAIN_FMT` / `TODAY_LAST_FMT`), the β / Today / β × drop / σ (50d) stats, and the 🏎️ demand band and room.

## Orders (served, tab-scoped — "Show both sorts, you pick" + "sort my most volatile stocks")

| key | label | order |
|---|---|---|
| `hb_swing` (also `default`) | 🎢 β × today's drop | red names by `β × |move|`, largest first; then up/flat by smallest move; then unread names |
| `hb_drop` | 📉 Today's drop | deepest first; then up/flat; then unread |
| `hb_vol` | 🌊 Most volatile (σ 50d) | σ = sample stdev of the last `SIGMA_BARS` (= `resiliency_tab.VOL_AVG_BARS`, 50) daily % returns — the σ the 🛡️ cards print — largest first; no σ sits last |

β × drop is an order, not a forecast (AMENDMENTS A2: β × drop, never drop ÷ β). The default is MY pick (spec §7 #4). The 50-session σ window is his open call (DECISIONS K3a). Any other sort key on this tab (and `default`) → `hb_swing`, and `hb_drop` / `hb_vol` on any other tab → `default` (the 🔻 precedent).

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

## His calls (open)

1. The label "🎢 High Beta", the emoji and the slot right after 🔻 Down 10%+.
2. Red-only default with an "include green names" toggle.
3. The QQQ box (the badge is always on).
4. The β × drop order as the default.
5. The 50-session σ window.
6. Two β engines (🎢 house log-return β vs 🛡️'s own).
7. Today's move against the official prior close (🛡️'s rule) with 🔻's 1% hold-out.
8. The study design: the 3-session horizon primary; primary = all sessions, SPY-red-only line beside it; β terciles; the bootstrap.

## Files

- `backend/chart_maps/high_beta_tab.py`, `backend/chart_maps/high_beta_measured.py`, `backend/sepa/beta.py` (`beta_from_frame`, `log_returns`)
- `board.high_beta_tiles` / `board.high_beta_watch`; `chart_maps/api.py` (`hb`, `hb_mode`, `/chart-maps/high-beta/watch`); `chart_maps/membership.py` (`MEMO_BLOCK_KEY`, TTL)
- `backend/scripts/high_beta_study.py`, `docs/research/high_beta_2026_10_14_prereg.md`
- `rules_info._high_beta_section`, `backend/tests/test_rules_info_high_beta.py`, `backend/tests/test_high_beta_tab.py`, `backend/tests/test_high_beta_study.py`
- FE: `lib/highBeta.ts`, `components/HighBetaBoardNote.tsx`, `lib/chartMaps.ts` (`CM_TABS`, `TAB_META.high_beta`, `boardQuery`), `pages/ChartMaps.tsx`, `lib/cardLadder.ts`

Deploy `api frontend` (and `cron` for the tape kinds).
