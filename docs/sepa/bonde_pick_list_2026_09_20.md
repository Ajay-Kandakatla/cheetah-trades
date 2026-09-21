# 📋 The Bonde PICK LINE — his STATIC criteria, each one cited

**2026-09-20.** Ajay: *"I need bonde for stock picks rather than deciding to
enter. I decide based on supply and demand and also based on Momentum, but show
me other things like EPS, Sales and other things"*, corrected the same day to
*"momentum does not need to be a criteria for his pics … i look at momentum and
others as dynamic info. I am looking fro static info"*.

So the 📈 Bonde tab now carries, on every row, a **pick line**: the set of
STATIC facts Pradeep Bonde has published about what goes on his list, each one
shown with the verbatim sentence, its URL and its date. Entries stay his — S&D
and momentum — and **no momentum, relative-strength, return or persistence leg
is on the pick line**, by his own correction.

Engine: `backend/sepa/bonde_picks.py`. Wired in `backend/sepa/bonde.py`
(`_row` → the scan legs, `board()` → the cache legs + the served legend).

---

## What this is NOT

- **Not measured.** No leg here is a signal, none has a placebo, none has a CI.
  The board's own thesis measured INVERTED (`sepa/bonde.py::MEASURED`); the pick
  line is newer than that measurement and has not been measured at all.
- **Not a gate, a sort or a filter.** Nothing on this line changes which rows
  the board draws or in what order. No count, ratio or score over the legs is
  rendered anywhere — `n_pass` / `n_fail` / `n_unknown` are served for this doc
  and for `coverage()` only.
- **Not sourced from the YouTube summary.** The third-party summary was never a
  source and nothing from it is cited. The INTERVIEW itself now IS one — Words
  of Rizdom, published 2026-02-18, recorded ~June 2025, received 2026-09-20 —
  and it is quoted by timestamp, each link opening at the second the sentence
  starts (§ The interview). Every other quote comes from a post on
  `stockbee.blogspot.com` or from his own X account, with its date.
- **Not an entry decision.** He decides entries; so does Ajay.

## Tri-state, always

Every leg is `{"ok": true|false|null, "value": …, "why": …}`.

`ok: null` is **UNKNOWN and never a fail.** A cold cache, a fiscal pair that is
not a year apart, a year-ago loss and a Yahoo frame that could not be read are
all "we cannot say". A ✗ beside his sentence is a claim about the company.

`stale` and `age_days` are **labels** (Rule #7: check the reported PERIOD, not
the cache age) and they never flip `ok`.

---

## The 18 computed criteria

Four of them are FACTS (`report_age`, `turnaround`, `growth_streak`, `theme`),
joining `fund_holding`: his words name the thing and publish no level, so the
leg carries a value and `ok` stays `null` — never a ✓, never a ✗. They are built
through one `_fact()` helper that cannot be handed an `ok`.

| leg | his sentence (verbatim, abridged here — the served quote is complete) | post | data on this board |
|-----|------------------------------------------------------------------------|------|--------------------|
| `eps_5c` | "…the earnings should be at least 5 cents." | 2007-03-30 | latest quarterly EPS, `sepa/qoq.compute` |
| `eps_yoy_100` | "a significant earnings acceleration compared to last year same quarter … 100% plus" | 2010-02-12 | `qoq.yoy_pct` slot 0 vs slot 4, positive year-ago base required |
| `eps_seq_100` | "earnings are up 100% or more quarter over quarter" | 2007-03-30 | `qoq.compute().income_qoq_pct`, refused on a non-adjacent pair |
| `eps_accel` | "Now what one is looking for is earnings acceleration." | 2007-03-30 (+2010) | this quarter's y/y EPS growth vs the previous quarter's |
| `sales_5` | "Sales/revenue should be up 5% or more." | 2007-03-30 | the pillar's own rounded seam vs `sales.SALES_FLOOR_PCT` |
| `surprise` | "Beats analyst estimate" (+2007 "An earnings surprise … will lead to breakout next day.") | 2010-02-12 | `earnings_calendar.last_report.surprise_pct` (a PERCENT) |
| `float_25m` | "Float below 25 million is ideal … best moves … below 10 million … 100 million plus float tend to have pullbacks." | 2010-02-12 (+X 2024-06-13) | yfinance `floatShares` via `board_metrics` |
| `short_dtc_5` | "high short interest ( 5 plus days to cover)" | X 2024-06-13 | FINRA short interest via Massive, `short_interest_latest` |
| `neglect_analysts` | "no analyst coverage and is neglected" | 2007-03-30 (+2010) | analyst count on Yahoo's estimate row, via `analyst_pulse` |
| `fund_holding` | "…float, fund holding" (+2025 "low fund ownership") | 2014-07-30 | institutional ownership off the scan row — a 13F LEVEL, never a flow |
| `ipo_10y` | "Gone Public in the last 10 years" | 2025-09-01 | `ipo_dates` (Finnhub profile), **uncorroborated** |
| `cap_10b` | "a capitalization of less than $ 10 billion" | 2025-09-01 | yfinance `marketCap` via `board_metrics` |
| `rev_39_x2` | "two quarters of revenue growth of 39% plus" | 2025-09-01 | this quarter's and last quarter's revenue growth, read y/y |
| `sector_3` | "focus on three sectors: technology, healthcare, and consumer discretionary" | X 2023-01-25 | the scan row's sector, in yfinance vocabulary |
| `report_age` **FACT** | "And I opened the newspaper. It used to have the list of stocks which are released earnings last night." | tape [0:49:23] | days from today to the `date` of the last reported quarter in the `earnings_calendar` cache — the SAME doc the `surprise` leg reads, so it costs no extra read. His words name no window; the `stale` label past 157 days is this app's |
| `turnaround` **FACT** | "I have a specific setup of turnaround stocks where I know based on their history that it can be held for a little longer than the growth stock" | tape [0:11:22] | year-ago quarter EPS ≤ 0 and latest quarter EPS > 0, on the same fiscal-pair guard the y/y legs use (`sepa/qoq`, slot 0 vs slot `Q.YOY_GAP`). This is the cohort the y/y EPS legs mark `year_ago_loss`; the SEQUENTIAL flip (`qoq.income_turn`) rides beside it as `seq_turn` and is never confused with it |
| `growth_streak` **FACT** | "which is based on projecting how many quarters in a row that stock is likely to have a growth" | tape [0:13:00] | `sales.compute`'s own `consecutive_growth_q`, read off `fundamentals.sales` and never recomputed here. Three things it does not say on its face, all carried on the leg: the counter stops at **4**, so a 4 means *four or more* (`capped`); the count can end because the revenue HISTORY ran out rather than because growth did (`history_ended`, with `n_pairs_available`); and only the latest two year-ago pairs are period-checked. His sentence is a FORWARD projection this app does not make |
| `theme` **FACT** | "there is 100 times more money on story stocks EP … Understanding what theme is working and finding story EP in them is now my major focus" | X 2023-11-12 (+ tape [0:14:33]) | the app's OWN theme map (`supply_demand/sectors.sectors_for_ticker`), in memory, no network. His word is *theme*; the map is ours. It names 167 tickers across 26 themes and is S&P-heavy, so a miss reads `not on the app's map` — **unmapped, never themeless** — and about 84% of this board misses it |

### The cite mapping that matters

He names BOTH earnings bases, in two different posts, and the legs cite the post
that carries the leg:

- **`eps_yoy_100` cites 2010** — "compared to last year same quarter as well as
  quarter over quarter … earnings acceleration of 100% plus".
- **`eps_seq_100` cites 2007** — "earnings are up 100% or more quarter over
  quarter".

The 2007 sentence names **no base for sales** ("Sales/revenue should be up 5% or
more"); this app reads sales year over year, for parity with `canslim`.

### Two notes on his own numbers

- **$10B vs $11B.** His 2025 prose says "less than $ 10 billion"; his scan line
  in the same post says "below 11 billion". `cap_10b` passes at the prose bound
  and the legend states both. Which one to use is **his call**.
- **The two-quarter revenue figure is read as y/y.** His post does not say which
  base. The leg says so on the row.

## The 9 criteria that are his and are NOT computed here

| leg | why not |
|-----|---------|
| `run_up_65d` | a PRICE read over 65 days — the correction asked for static information only |
| `story_ep` | no feed decides whether a name is a story stock; inventing one is this app's judgement in his voice |
| `pead` | the anomaly his whole method rests on, not a per-name screen |
| `reactor_watchlist` | a watchlist kept over weeks, and the reaction is a price read |
| `top_sector` | no sector RANK feed reaches this board |
| `earnings_40` | one entry in his catalogue of EP catalyst CATEGORIES — he writes that he only focuses on the 100%-plus names |
| `ep_origin_300` (tape [0:48:59]) | the book paragraph that STARTED EP, quoted by him — not his screen. His published screen is 100% (2007, 2010) and nothing here moves off it |
| `valuation` (tape [0:12:54]) | he names valuation and no metric and no number; a chip would be this app choosing a ratio and wearing his word for it. The quarters-in-a-row half of that sentence is the `growth_streak` fact |
| `volume_9m` (tape [1:05:52]) | unit and window are unstated, and volume is DYNAMIC — the class his own correction removed from this line. His 2010 construct is relative ("ten times or more compared to average volume"), not an absolute floor |

They are printed in the legend anyway, with the reason, so the list on screen is
never shorter than his list.

---

## `WHY_CODES` — the ONE vocabulary

Every served `why` is a member of `bonde_picks.WHY_CODES` (25 codes). The
frontend's `WHY_TEXT` keys are pinned equal to it by the contract sweep, so a
code with no sentence beside it cannot reach the page.

| code | what it means |
|------|---------------|
| `no_eps_series` | no quarterly EPS filings on the scan row, or the series does not reach back a year |
| `year_ago_loss` | the year-ago quarter lost money; `yoy_pct` divides by \|base\|, so a loss would print as a doubling |
| `pair_not_a_year_apart` | the fiscal pair was CHECKED and is not four quarters apart — every y/y leg refuses |
| `no_period_keys` | the pair could NOT be checked (no keys on file). The number IS computed; the chip says `unverified` |
| `prior_hole` | the PRIOR quarter is absent — costs the acceleration read and the two-quarter read, nothing else |
| `no_sales_read` | no revenue growth on the row |
| `no_inst_read` | no institutional-ownership figure on the scan row |
| `no_sector` | the scan row carries no sector |
| `no_symbol` | the scan row carries no symbol, so the theme map cannot be asked about it |
| `no_threshold_in_his_writing` | he names the criterion and publishes no number — the leg is a FACT and never a pass or a fail |
| `seq_base_non_positive` | the previous quarter lost money (from `qoq.BASE_NON_POSITIVE`) |
| `seq_base_too_small` | the previous quarter is positive but too near zero to carry a ratio (`qoq.BASE_TOO_SMALL`, `MIN_EPS_BASE`) |
| `seq_base_unknown` | the two quarters are not both on file (`qoq.BASE_UNKNOWN`) |
| `seq_not_adjacent` | the two newest filings skip a quarter (`qoq.BASE_NOT_ADJACENT`) |
| `not_on_calendar` | no `earnings_calendar` doc, or no past reported row on it |
| `no_surprise_in_report` | the last report carries no surprise figure |
| `no_metrics_doc` | no `board_metrics` doc within its TTL |
| `no_float_in_doc` | the doc exists and carries no float (cached before 2026-09-20, or yfinance had none) |
| `no_cap_in_doc` | the doc exists and carries no market cap |
| `not_warmed` | no `short_interest_latest` doc — the warm has not run |
| `no_si_record` | a doc exists with no settlement date: a REMEMBERED miss, not an un-run warm |
| `no_analyst_doc` | no `analyst_pulse` doc |
| `no_estimate_read` | a doc exists and the analyst count is unset (property raised, frame `None`, or the doc predates 2026-09-20) |
| `no_listing_date` | no date in the `ipo_dates` cache |
| `future_listing_date` | the profile date is in the future — a corrupt row, never "the youngest name on the board" |

The `qoq` base states are mapped **by name** through `INCOME_BASE_TO_WHY`, so a
rename in `sepa/qoq.py` is an ImportError here, not a silently wrong sentence.

---

## Cost: ZERO network on the board path

`legs_from_scan_row` is pure and reads the scan row it is handed.
`attach(rows, db)` makes **five bulk Mongo reads** over the distinct symbols and
nothing else:

| reader | collection |
|--------|-----------|
| `sepa.board_metrics.snapshot` | `board_metrics` |
| `sepa.earnings_watch.last_report_map` | `earnings_calendar` |
| `short_interest.client.short_interest_map` | `short_interest_latest` |
| `sepa.analyst_pulse.coverage_map` | `analyst_pulse` |
| `sepa.ipo_age.listing_dates_map` | `ipo_dates` |

They are imported **inside** `attach()`: `short_interest.client._main` imports
`sepa.bonde`, which imports this module, so a top-level import in either
direction closes the cycle. `attach` never raises — a reader that is missing,
empty or throwing leaves its legs UNKNOWN and the board is served, because
`board()` runs inside crons.

`analyst_pulse.get_map` makes a bulk LIVE price call and is **never** on this
path; `ipo_age.age()` loads prices and `listing_date()` can call Finnhub —
neither is on this path either.

## Coverage on the 199 shown names, 2026-09-20 (before the warms)

| leg | known |
|-----|-------|
| EPS series (all four earnings legs) | ~95% of scan rows carry `eps_q_series` |
| institutional ownership | 22% of scan rows |
| market cap | 169 of 199 (a `board_metrics` doc exists) |
| float | **0** until `python -m sepa.board_metrics warm --all` re-fetches (the key is new) |
| earnings surprise | 53 of 199; 63 of the 885 stored reports app-wide are older than the stale bound |
| analysts | 134 docs exist; the count itself is unset until `python -m sepa.analyst_pulse refresh --force` |
| listing date | 199 of 199 |
| short interest | **0** until `python -m short_interest.client warm-si` has run |

The board serves a `pick_coverage` block and the page prints one sentence from
it, so an unwarmed leg reads as "not warmed", never as a silent wall of dashes.

> Short interest reads unknown on every row until
> `python -m short_interest.client warm-si` has run in the api container; a
> crontab line does not ship with a deploy.

## Freshness labels — this app's numbers, never his

- `SURPRISE_STALE_DAYS = QUARTER_DAYS (91) + FILING_LAG_DAYS (45) + GRACE_DAYS (21) = 157`
  — built from the Rule #7 constants in `observability/period_freshness.py` by
  name. `QUARTER_DAYS` is a new app label.
- `SI_STALE_DAYS` (owned by `short_interest/client.py`) — FINRA settles mid- and
  end-month and publishes ~9 business days later.

Neither is his, and **neither ever changes an `ok`.**

## The one caveat on `ipo_10y`

21.4% of Finnhub profile dates on this universe are recycled tickers
(`chart_maps/ipo.py`), which reads as a RECENT date on an OLD company — a falsely
young ✓. The leg is labelled `uncorroborated` on the row.
`chart_maps.ipo.corroborate()` reaches back ~130 days only, so it cannot check a
10-year claim. Whether the leg stays among the chips is **his call**.

## The one caveat on `neglect_analysts`

Yahoo never prints a zero. An **empty** `earnings_estimate` frame is the only
evidence of no coverage there is, and reading it as his "no analyst coverage" is
a reading — labelled `Yahoo carries no estimate rows` on the leg, with the
pending-nod sentence in the legend. A frame with rows but no current-quarter row
is UNKNOWN, not zero. Whether a small count (≤2) should also read as neglected
is **his call** — his words give no number.

---

## § The interview (2026-09-20)

Ajay sent the video after the pick list had shipped, with his standing
instruction for this tab: *"look for thing she said from a stock pic pov …
momentum does not need to be a criteria for his pics … I am looking fro static
info"*. So the tape is a SECOND cite beside his posts. It replaces nothing: the
primary quote, URL, date and source of every criterion that existed before today
are unchanged.

**Source.** <https://www.youtube.com/watch?v=fjox2hapu98> — *"Trading Legend:
His Strategy Has Made the MOST Millionaire Traders - StockBee"*, Words of
Rizdom, with Riz and Pradeep Bonde. Published 2026-02-18; recorded ~June 2025,
by his own sentence at [1:05:11] (*"the last month is over May"*); received
2026-09-20. Frozen extract:
`backend/tests/fixtures/bonde_video_captions_2026_09_20.json`.

Manual en-GB captions, no speaker labels; the host's turns are never cited.

Every tape link opens at the second the sentence starts. The `&t=` suffix is
written in exactly one place in the module (`_tape`), so a hand-typed second
cannot reach the page.

### Covered — the tape agreeing with something already on the line

Each row below adds a CITE and nothing else: no leg, no threshold, no chip and
no ordering moved.

| leg | ts | his words on tape, verbatim | it agrees with | what changed |
|---|---|---|---|---|
| `sector_3` | [1:07:04] | "I have seen that over any time period of last 24 years 25 years right there are three sectors where the biggest money is in the market. Technology, biotechnology or healthcare related stock and third is consumer discretionary." | his X post of 2023-01-25 naming the same three | cite only |
| `sector_3` | [1:07:17] | "You can get rid of everything else if you really want to make money." | the same post, which says *focus on* | cite only — see Contradictions |
| `sector_3` | [1:07:22] | "once in a while you'll have gold stocks making money. once in a while you're a uranium stock making money but just trading technology stock is where the money is." | the same post, which ranks nothing | cite only — see Contradictions |
| `story_ep` | [0:14:33] | "that reason must be might be theme That might be sector that might be whatever earnings catalyst story but the that particular stock should have a reason to go up" | his X post of 2023-11-12 on story EP | cite only |
| `story_ep` | [1:06:50] | "today if you have to make money what is in play AI uh robotics humanoid robotics or like crypto wallets or things like that" | the same post | cite only, and printed as DATED — what was in play when this was recorded, never a standing rule |
| `top_sector` | [1:04:32] | "So take the first point right and which is you have to trade what is in the market likes right" | the existing legend-only reason | cite only |
| `pead` | [0:49:55] | "And that changed how that became the EP kind of an idea then." | his X post on post-earnings drift | cite only — the origin: he systematised the search after one trade |
| `surprise` | [0:49:23] | "And I opened the newspaper. It used to have the list of stocks which are released earnings last night." | his 2010 surprise sentence | cite only — his origin universe was last night's reporters |
| `run_up_65d` | [0:27:04] | "Now I tended to believe this when I was new in the market right till I actually checked it out and when I checked it out I found that actually the stock which make the biggest move are the one which were written down the most right" | the existing legend-only reason | cite only — it agrees in DIRECTION only and is still a price read, so it stays off the line |
| `eps_yoy_100` | [0:49:28] | "And there was this small stock called USLB. At that time it was called US laboratories. And that had come out with earnings and the sales growth was some 900% and the profit was 2,600%." | his 2010 earnings sentence | cite only — a worked example, direction only, carrying no threshold |
| `eps_seq_100` | [0:49:28] | the same USLB sentence | his 2007 sequential sentence | cite only — no threshold, no number moved |
| `rev_39_x2` | [0:49:28] | the same USLB sentence, in which sales is named FIRST | his 2025 scan line, "two quarters of revenue growth of 39% plus" | cite only; the leg keeps his published number |

One phrase in that table is a mishearing on the caption track: where he says
*beaten down*, the captions have *written down*. Every quote is carried exactly
as captioned, mishearings included, and the frozen extract pins it that way.

### New facts — four legs, plus the one that already existed

All five carry `ok: null` **by construction**: they are built by `_fact()`, which
cannot be handed an `ok`. A FACT shows a value and a dash, never a tick and
never a cross, because his words give no line for any of them.

| leg | built from | reads UNKNOWN when | his call |
|---|---|---|---|
| `report_age` | `earnings_calendar`, through `sepa/earnings_watch.last_report_map` — the same bulk read the `surprise` leg already makes, so the board still makes five | there is no calendar doc, no past reported row, or the row carries no readable past date (`not_on_calendar`) | what recency reads as *in play*; the 157-day label stays this app's and flips nothing |
| `turnaround` | the scan row's EPS series through `sepa/qoq` — the year-ago slot vs the latest, the same guard the y/y legs use; `qoq.income_turn` (the SEQUENTIAL flip) rides beside it as `seq_turn` | there is no EPS series (`no_eps_series`) or the fiscal pair was checked and is not a year apart (`pair_not_a_year_apart`) | whether a turnaround reads as a pass or stays a fact |
| `growth_streak` | `sepa/sales.compute`'s `consecutive_growth_q`, read off `fundamentals.sales` — never off the pillar copy, whose `or 0` would turn *no read* into a zero streak | the pair was refused (`pair_not_a_year_apart`) or there is no sales read (`no_sales_read`) | what count reads as a pass; his words give none |
| `theme` | the app's own map, `supply_demand/sectors.sectors_for_ticker` — in memory, no network, no I/O | the scan row carries no symbol (`no_symbol`) | whether the app's map is the right reading of his word *theme*, and whether a miss should read UNKNOWN instead of a fact about the map |
| `fund_holding` (already shipped) | institutional ownership off the scan row — a 13F LEVEL, never a flow. Unchanged; it is now built by the same `_fact()` helper, with byte-identical output | there is no ownership figure on the row (`no_inst_read`) | he names fund holding and publishes no level |

Where the fiscal pair could not be checked at all, the `turnaround` and
`growth_streak` legs say **unverified** on the row — the number is computed and
the pair is simply not on file.

**On the theme map.** It names 167 tickers across 26 themes and is an S&P-heavy
roster, not a small-cap theme map. On the 2026-09-20 board, 167 of the 199 rows
— about 84% — are not on it. A miss therefore reads `not on the app's map` with
`mapped: false`: **unmapped, not themeless.** Reading it as "none" would be a
claim about the company off an absent roster row, which Rule 2 of the module
forbids.

### Legend-only — his words on tape, printed and not computed

| what | ts | why it is legend only |
|---|---|---|
| the second header line, *"a good chart itself is not a setup … they don't go up just because there is a pretty good chart or support or resistance"* | [0:14:17] | it frames the whole list; it is not a per-name criterion and it is served beside the header, never inside it |
| `ep_origin_300` — *"the earnings is like phenomenally good 300 400 500%. Then those stocks can double or triple."* | [0:48:59] | the paragraph that started EP, quoted by him from a book — not his screen |
| `valuation` — *"I will base lot of my longerterm trading on a setup which is very very analysis based, which is based on valuation, which is based on projecting how many quarters in a row that stock is likely to have a growth."* | [0:12:54] | he names valuation and no metric and no number |
| `volume_9m` — *"that is why I use the 9 million volume because I know volume is a object effective way to find where the crowd is"* | [1:05:52] | unit and window are unstated, and volume is dynamic |

### Contradictions — both sides stay exactly as published

| on tape | in a post | how it is handled here |
|---|---|---|
| "300 400 500%" as the earnings figure, [0:48:59] | 100% in 2007 and in 2010 | the tape figure is the origin PARAGRAPH he quotes; the post figure is his screen. The legs keep the post number and the tape sentence is legend only |
| "the 9 million volume", an ABSOLUTE figure, [1:05:52] | his 2010 construct is RELATIVE: "will have huge volume surge, typically of 10 times or more compared to average volume" | neither becomes a leg; both are printed, and which one is meant is his call |
| "You can get rid of everything else", [1:07:17] | the X post says *focus on* three sectors | exclusion versus focus. The `sector_3` pass line does not change; a filter would be a real decision and is his |
| technology ranked first, gold and uranium named "once in a while", [1:07:22] | the X post names the three equally, with no rank | no rank goes on the row; legend note only |
| his tenure, given as 24 and 25 years at [1:07:04], 25 and 26 at [0:52:00], 26 at [0:21:56] | — | the numbers stay as he said them; nothing on the board reads tenure |

### Out of scope — said on tape, and nowhere near the pick line

Entries are Ajay's, and the correction that shaped this tab asked for static
information only. Every line below is recorded so it is on the record, and none
of it touches the module.

| what he says | ts | why it is off the line |
|---|---|---|
| a move of 10 to 20% in two or three days, then sell 80% of the position and keep 20% | [0:30:36]–[0:30:42] | an EXIT rule |
| start with five or 10 shares, "then go to 40 shares 100 shares 300 shares" | [0:37:25]–[0:37:40] | position SIZING |
| wait for the stock to revisit the pre-market low, then buy near it | [0:28:49]–[0:29:08] | an ENTRY rule — and see the note under this table |
| a scan for a stock making 60 new highs in less than 3 minutes | [1:06:07]–[1:06:12] | a live intraday scan: dynamic, and dynamic is what the correction removed |
| a stop at the 10-day or the 20-day moving average | [0:13:13]–[0:13:19] | an exit and a price read |
| shorting small caps as the edge in day trading | [0:27:50]–[0:27:55] | day trading, and the short side is not this line |
| "less than like 6 weeks I made more money than I had ever imagined in my life in one trade" | [0:49:47] | a performance claim — never printed here as measured |
| "$1 million to over $100 million" | [0:00:00] | a performance claim in the opening — never printed here as measured |

**Whose voice.** Two of the lines in that table are not in his own voice: the
opening claim belongs to the show's introduction, and the rule about revisiting
the pre-market low is one he is repeating back from a trader he had been talking
to. Neither is ever presented as his. The show's own turns are never cited
anywhere in this doc or in the module, and the only citable voice on this tape
is his.

Their timestamps: [0:00:00], [0:07:34], [0:13:30]–[0:14:11],
[1:03:45]–[1:04:27]; and the repeated entry rule at [0:28:49]–[0:29:08].

### His call — nothing here was decided

The default is what ships if he says nothing.

| # | question | default |
|---|---|---|
| 1 | the origin figure at [0:48:59] — a second, higher tier, or legend only | legend only; it is the book paragraph, not his screen |
| 2 | the sector EXCLUSION at [1:07:17] — the pick line's first FILTER, or a fact only | fact only. The board's own thesis measured INVERTED, and a gate off an unmeasured sentence is a real decision |
| 3 | technology ranked first at [1:07:22] — print a rank inside the three, or a legend note | legend note |
| 4 | the volume figure at [1:05:52] — shares or dollars, which window, and whether a dynamic liquidity floor belongs on a static line at all | legend only, no leg |
| 5 | `turnaround` at [0:11:22] — a pass or a fact | fact |
| 6 | `growth_streak` at [0:13:00] — what count reads as a pass | fact, no pass |
| 7 | `valuation` at [0:12:54] — which metric, if any | legend only |
| 8 | the recency window at [0:49:23] — how fresh the last report must be to be *in play* | fact, no window; 157 d stays this app's LABEL |
| 9 | the exit, sizing, entry and scan sentences | doc only; entries stay his |
| 10 | the theme map as the reading of his word *theme* | ship the fact, labelled *the map is ours*; a miss reads unmapped, not themeless. The alternative is an UNKNOWN leg, so a miss prints no value at all |
| 11 | the turnaround tokens beyond loss → profit | serve all four; only loss → profit is his word |
| 12 | the streak display, *4+ q* | ship it as a display truth. LIFTING the counter's cap is a change to `sepa/sales.py`, which is book-cited and is not touched here |
| 13 | the stale hover on the `surprise` chip now printing the bound rather than the row's own age | ship the correction; the label semantics and the tick are untouched |
| 14 | `coverage()` counting a FACT leg as *known* — a value that was served, or a pass/fail verdict as today, where `fund_holding` reads 0 of N | a served value counts as known; it is a served-count semantic and no surface reads it for these keys |
| 15 | a theme lookup with no symbol — a new why code `no_symbol`, or reuse `no_sector` | add `no_symbol`, on both sides |
| 16 | the old ✨ entry's sentence *the video itself was never received* | leave it as history; it is contract-pinned and the new entry supersedes it. The alternative is amending one clause |
| 17 | the tape cite's `date` — every other cite's `date` is when he wrote it, while the tape's is the show's publish date for words spoken about a year earlier | keep `date` = publish and carry `recorded` beside it. The alternative is making `date` the recording estimate |

---

## Tests

`backend/tests/test_bonde_picks.py` — the quotes are frozen verbatim
(`ALLOWED_QUOTES`), every branch of every leg has a negative, a stubbed board is
walked end to end asserting every served `why` is in `WHY_CODES`, `requests` is
monkeypatched to raise to pin the zero-network rule, and
`n_pass + n_fail + n_unknown == 18` on every row (the five FACT legs always land
in `n_unknown`).

Every tape sentence is pinned against a frozen extract of the caption track,
`backend/tests/fixtures/bonde_video_captions_2026_09_20.json`, so a quote that
drifts by one word stops the suite. `STREAK_CAP` is pinned equal to
`sales.compute`'s own behaviour rather than read out of `sepa/sales.py`, which
is book-cited, contract-pinned and untouched here.
