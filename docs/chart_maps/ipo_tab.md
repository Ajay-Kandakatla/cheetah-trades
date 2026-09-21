# 🆕 IPOs ≤2y — Chart Maps tab

**2026-09-20.** Ajay asked for it in three lines: *"Can you build be an IPO tab
of the hot sectors please?"* · *"IPO of hot sector theme of stocks and then add
them as a tab in Chart maps"* · *"Also potential future IPOs coming up if
stocktwitz has"*. This paragraph is the record of what shipped, what it is
based on and what it is explicitly not.

The tab is a **list**, not a signal. The only cited thing on it is the recency
bound — TLSW Ch. 11, p. 260 (*"Eighty percent of the stock market winners that
drove the tech boom during the 1990s were IPOs within the prior eight years"*),
which this app already encodes as `sepa/ipo_age.py`'s
`is_recent_ipo = years <= 2`. `chart_maps/ipo.py::RECENT_YEARS` is pinned equal
to that bound by `tests/test_ipo_tab.py::test_RECENT_YEARS_equals_the_bound_ipo_age_actually_enforces`,
which reads the bound out of a real `ipo_age._block()` call rather than
retyping the number, so the two modules cannot drift apart silently. Nothing on
this board is measured; it gates nothing, orders nothing, alerts nothing and
enters no lane, and the served `note` says so on every request.

**Why every date is corroborated.** The listing dates come from Finnhub
`profile2.ipo`, cached in Mongo `ipo_dates` by `sepa/ipo_age.py`. On this
universe that field is ~21.4% corrupt, and the corruption has a shape: a
RECYCLED ticker — retired by one company, re-issued to a new listing — carries
the new listing's date while the price frame still holds the old company's
history. A naive tile would then print that other company's session as this
IPO's day one. So each claimed date is checked against two independent things:
a priced deal for the same symbol within `NEAR_DAYS` (30) in Finnhub
`/calendar/ipo`, and the price frame's own first bar.

| status | evidence | shown |
|---|---|---|
| `confirmed` | calendar prices it; bars agree or cannot say | yes |
| `recycled` | calendar prices it, but bars pre-date the listing | yes, `✳︎ recycled ticker`, every price stat blanked |
| `uncorroborated` | calendar silent; bars agree or cannot say | **no — dropped, counted in `counts.dropped_uncorroborated`** (2026-09-20, Ajay: *"Yes … #3"*); the calendar-outage build still shows it flagged |
| `bogus` | calendar silent **and** bars pre-date the listing | no — dropped, counted in `counts.dropped_bogus` |

**2026-09-20 — uncorroborated rows are DROPPED.** Until this date
`uncorroborated` was shown flagged rather than dropped, on the reasoning that
Finnhub's calendar does not reach back over the whole trailing window for every
venue and hiding a real listing is the worse error; dropping it was on the
owner's-call list. Ajay answered it: *"Yes for #1 and #2 and #3 and #4 and
#5"*, where **#3 was "DROP the IPO tab's uncorroborated rows"**. They now come
off the board and are counted in `counts.dropped_uncorroborated`, which the
🗓️ Coming up strip's basis line prints — *"· 22 uncorroborated dropped —
spin-offs and re-listings the calendar does not carry"* — so the drop is never
silent. On the live board that day **22** of the 66 candidates were
uncorroborated, and they were mostly spin-offs and re-listings the IPO calendar
has no reason to carry: HONA, FDXF, VSNT, GLIBA/GLIBK, RAL, MRP, ECG, CURB,
AMTM, Q, PSKY, SNDK, BULL, CEP. Expect the live counts to move to **42
confirmed / 2 recycled / 0 uncorroborated / 8 dropped_bogus / 22
dropped_uncorroborated**.

Two rules hold this honest. `counts.dropped_bogus` and
`counts.dropped_uncorroborated` are counted from `_evaluate`'s own verdict
— it returns `(row, dropped_as)` — never from `len(cands) - len(rows)`, because
one length gap with two causes is a number he cannot read. And the
CALENDAR-OUTAGE path is untouched: with no calendar to be silent,
"uncorroborated" says nothing about the listing, so every candidate is still
shown flagged, `dropped_uncorroborated` is `0`, and `counts.uncorroborated` is
the count of what is on screen. Bars that start AT a provider fetch cap are truncation, not a
listing (SAIC, 2026-08-31) — `ipo_age._at_fetch_cap` makes that call and this
module imports it rather than re-deriving it.

**2026-09-20, same day, corrected: bars before the claim are conclusive at
the fetch cap.** The first live board put **XOM** at the top of the tab —
"Listed 2026-07-02 · 80 days · uncorroborated". Finnhub's profile date for XOM
is garbage, the frame starts at the 2y cap (2024-09-19) with ~450 sessions
before the claim, and the first cut read "first bar at the cap → the bars
cannot say" and let the silent calendar decide. That guard was one-directional
and had been written as two-directional: a first bar at the cap cannot prove a
claim (SAIC), but bars that exist BEFORE a claim disprove it whether or not the
frame is truncated — truncation removes old bars, it never invents bars between
the cap and the claim. `corroborate` now checks "before" first and applies the
cap only to the "agree" direction. MKSI, RNA, VNOM and TEM were the same shape.
Regression: `test_bars_BEFORE_the_claim_are_conclusive_EVEN_AT_THE_FETCH_CAP_the_XOM_case`
(fails on the first cut).

**The two price stats say what they are.** `Day-1 open→close` is the first
session's open-to-close, and `Week-1 vs day-1 open` is the fifth session's
close against that same open. Neither is the pop off the **offer** price: this
app does not hold offer prices, and the labels are worded so the numbers cannot
be read as one. Both are blank on a recycled tile, on the backend and again in
`frontend/src/lib/ipoTab.ts::blankIfRecycled`.

**Coming up.** `IpoUpcomingStrip` is pinned above the grid like `IndexZones`:
it renders while the board is warming, while the board has failed and when the
calendar returned nothing (then: *"No priced listings in the next 30 days
(Finnhub calendar)"* — the sentence names the feed, so "none" can never read as
a claim about the market). Only `status == "expected"` rows inside
`FORWARD_DAYS` (30) appear. Every field is printed **verbatim**: `price`
arrives as a string like `18.00-20.00` and `numberOfShares` can be a string
too, and neither side parses either into a number. StockTwits has no IPO feed;
Finnhub's calendar is the source, and this app already holds that key.

**Flat, not grouped by sector.** Ten of this app's seventeen themes have no
recent listing at all, so a grouped board would be mostly empty headings. The
tab accepts the dispatcher's `themes_first` and `min_tier` and applies
**neither** — the served `criteria` says so out loud rather than leaving a
control that does nothing looking like one that did something.

**Failure behaviour.** A calendar outage does not change what the board is: it
still builds from `ipo_age` alone, every row becomes `uncorroborated`, nothing
is dropped — including under the 2026-09-20 drop rule, which fires only when
the calendar was actually read — and `corroboration.available` is `false` with
the reason attached, which the strip prints (without any drop count: that
sentence never rides on an outage line). Bars that pre-date a claim still blank the price stats
on that path, because another company's day one must never print whatever the
calendar says.

**Cost.** `finnhub_client` gained `ipo_calendar(from_d, to_d)` through the
existing `_cached_call`, keyed on the **window** (`__CAL__<from>_<to>`) since
this is not a per-symbol endpoint, with a 6h TTL (`cache._TTL_BY_ENDPOINT`) —
the same cadence as the earnings calendar. The trailing window is fetched in
`CAL_CHUNK_DAYS` (90) chunks so one 5xx costs a quarter, not the history; any
failed chunk makes the whole pass `ok: false`, because a half-fetched calendar
corroborates some names and silently fails to corroborate others.

**One fix carried along.** `finnhub_client/client.py` held a single
process-wide `httpx.AsyncClient`. That was safe while the only caller was the
FastAPI router on one app loop; this board calls the same endpoints from a
worker thread on its own short-lived loop, and a pool bound to one loop used
from another is the classic *"Event loop is closed"*. The client is now kept in
a `WeakKeyDictionary` keyed on the event loop. `chart_maps/ipo.calendar()` also
runs all of its chunks on **one** loop and restores the thread's previous loop
afterwards — `asyncio.run()` leaves the current loop set to `None`, which on
Python 3.9 breaks the next thing in that thread to ask for one (it broke
`tests/test_enterable_wiring.py` when run after this module's tests, and both
behaviours are now pinned in `tests/test_ipo_tab.py`).

## § Coming up → drill-in (2026-09-20)

> *"Can you gather similar info about these please like the ticket and make
> them clicable the onesin IPO tab that are future"* — Ajay, 2026-09-20, with a
> screenshot of the strip showing AMRO / BMB / PTT.

A ticker page shows a company's story and its numbers. An expected listing has
no price history, so the symbol on a 🗓️ **Coming up** row is now a button and
the drill-in shows what the ticker page would if it could. **It is a FACT
SHEET**: nothing on it is measured, nothing is a signal, there is no chip, no
verdict, no ranking and no score, and the served `note` says exactly that on
every payload.

`GET /chart-maps/ipo/upcoming/{symbol}` — `backend/chart_maps/ipo_upcoming.py`,
route appended to `backend/chart_maps/api.py`. Fetched on a CLICK and nowhere
else: `board()` does not import the module, because a cold open costs three to
four rate-paced EDGAR GETs plus a multi-megabyte download and a board may not
pay that per row.

### Sources, in order
1. **EDGAR full-text search** — `https://efts.sec.gov/LATEST/search-index`,
   `q="<company name>"`, `forms=S-1,F-1,S-1/A,F-1/A,424B4,424B1`,
   `dateRange=custom` over the last 365 days. Zero hits gets exactly ONE retry
   with the short company name (a phrase carrying punctuation, e.g.
   `"Bamboo Insurance Services, Inc."`, can come back empty). Two queries,
   never a third.
2. **Submissions** — `https://data.sec.gov/submissions/CIK{cik10}.json` for the
   confirmed filer: name, CIK, SIC + description, state of incorporation,
   fiscal year end. A pre-IPO filer's `tickers` and `exchanges` are EMPTY, and
   Finnhub's `profile2` is empty too, so EDGAR is the only fact source here.
3. **The primary document** —
   `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}`, the
   newest registration filing ranked by FORM first (424B4/424B1 > S-1/A, F-1/A
   > S-1, F-1) and then by filing date.
4. **Headlines** — `news_search.core.search`, keyword = the quoted short
   company name, 168 h window, `audit="ipo_upcoming"`.

Every EDGAR GET goes through `sepa.insider._edgar_get` — the ONE rate-paced
chokepoint that ended the 2026-06-17 429 storm — with `sepa.insider`'s own
`SEC_HEADERS` and `EDGAR_FTS`. No fifth user agent, no fourth pacer. The names
are bound BARE at import, which is the only reason a test stub can actually
stop the network; `test_edgar_get_is_insiders_before_patching` pins it.

### The resolver
`_source.ciks` and `_source.display_names` come back as **parallel lists** — a
filing with a co-registrant carries both filers — so the pairs are `zip`ped and
grouped by CIK before anything is confirmed. A hit whose two lists are
different lengths is skipped, never guessed.

* a ticker tag equal to the calendar symbol confirms the CIK it is printed on,
  and only that one → `method: "ticker_tag"`;
* else an exact name match, raw or short-name, confirms → `method: "name"`;
* `ticker_tag` beats `name`; a tie goes to the newest `file_date`;
* nothing else is confirmed. **The top hit is never taken on faith** — no
  confirmed CIK is the sentence *"no registration filing found for this name on
  EDGAR full-text search (S-1/F-1/424B4, last 365 days)"*.

A **name-only** match whose filing names a different trading symbol is hidden
with a sentence naming both. Both sides are normalised first: the cover prints
`under the symbol “AMRO.”` with the sentence's own full stop INSIDE the closing
quote, so the capture is `rstrip('.')`-ed and upper-cased before the compare.
Skip that and every Amaero-shaped filing looks like a different company.

### What is extracted — each one AS PRINTED
`overview`, `proposed_symbol_line`, `symbol_in_filing`, `shares_offered_line`,
`price_line`, `underwriters` (list), `revenue_line`, `revenue_units_line`,
`revenue_period_line`, `net_loss_line`, `net_loss_units_line`,
`net_loss_period_line`, `extracted_at`. A miss is `null` — never `""`, never
`0`; `underwriters` is the one field whose miss is `[]`, because it is a list.

The units and period header are read **per quote, from that quote's own
table**, at most `TABLE_HEADER_LOOKBACK_CHARS` (4,000) before it. On Amaero the
revenue line comes from the MD&A table (`(in thousands)`, *Year ended December
31, 2025*) and the net-loss line from the summary table (*in thousands, except
share and per share data*, *Six Months ended June 30, 2025*) — two different
tables with two different column orders. One shared units line would print the
wrong unit under one of them.

The underwriter segment anchors are Title-case and matched **case-SENSITIVE**.
A cover's bank list is typeset in Title case; Amaero's running text says
"…between us and the underwriters…" 2,140 characters before Stifel and Baird,
and a case-insensitive anchor opens the segment there and never reaches the
banks. A bank that is not in `UNDERWRITER_NAMES` is silently absent from the
list — the link to the cover is always there (§ his call).

### What is NEVER parsed
No number ever leaves the filing. `revenue_line` and `net_loss_line` are
SENTENCES carried verbatim with their own units and period lines beside them; a
thousands-vs-millions mistake on a sheet he reads before a listing is exactly
the invented number Rule #1 forbids. `test_wire_no_number_from_the_filing`
walks `filing` and `company` and fails on any int or float. The only numbers on
the wire are inside `calendar_row` (Finnhub verbatim), `headlines[].published`,
`headlines_window_days` and `resolution.hits`. There is no LLM anywhere in this
path — the Overview paragraph as printed IS the summary.

### The cache — Mongo `ipo_upcoming_cache`, one doc per symbol
* the filing block is keyed by **accession** and kept while the accession is
  unchanged **and `parse_note is None`**. A block carrying a parse note
  ("EDGAR answered 503", "prospectus larger than 15 MB; not parsed") is a
  failure, not a fact, and is re-fetched on the next resolve;
* a successful resolve and the headlines are fresh for 24 h (`CACHE_TTL_SEC`);
* **a failed resolve or a no-hit is NEVER cached — the next click asks EDGAR
  again.** `resolved_at` advances only on a resolve that actually read the
  filer, so a 30-second blip is a 30-second blip and never a day of stale
  answers;
* `cached: true` is served ONLY on the zero-network path;
* timestamps are **epoch floats in Mongo and ISO-8601 UTC on the wire**.

### Failure behaviour — every one of these is a sentence, never an exception
| What happened | What is served |
|---|---|
| EDGAR unreachable, no clean cached filing | `filing: null`, `error: "EDGAR could not be reached: …"`, `resolved_at` unchanged |
| EDGAR unreachable, a cached filing that parsed cleanly | that filing plus `error: "EDGAR could not be reached; showing the filing cached <iso>"` (`cached` stays `false`) |
| No confirmed CIK | `filing: null`, the no-hit sentence, `resolved_at` unchanged |
| Document over 15 MB, or a non-200 | the link, form and date still serve; every fact is `null` and `parse_note` says why; `resolved_at` DOES advance (the resolve worked, the parse did not) and the block re-fetches next time |
| Finnhub's calendar unreadable | **503** with a sentence naming the reason |
| Symbol not an expected listing in the window | **404** naming `FORWARD_DAYS` |
| Mongo down | the payload still answers; nothing is cached |

A deal Finnhub flips to `priced` leaves the strip and its drill-in answers
**404** — the drill-in is for expected rows only.

### Measured shapes (2026-09-20, from this machine)
* **AMRO** *Amaero Inc.* — 6 hits, all CIK 0002141616, display carries **no**
  ticker tag → `method: "name"`; newest S-1/A 2026-09-18; the cover prints
  `“AMRO.”` (stop inside the quote) and the ASX `“3DA.”` right beside it; no
  "between $X and $Y" sentence exists, so `price_line` falls to the printed
  "will be determined through negotiations" sentence — never a `0`;
  underwriters `["Stifel", "Baird", "Lake Street"]`.
* **BMB** *Bamboo Insurance Services, Inc.* — 15 hits, display carries `(BMB)`
  → `method: "ticker_tag"`; S-1/A 2026-09-14; a real price range on the cover.
* **PTT** *SIYATA PTT* — 21 hits on the quoted name (27 on bare `"PTT"`), some
  carrying `(PTT)` and older exhibits carrying none, which is exactly why the
  pairs are grouped by CIK; newest F-1/A 2026-09-18; F-1 wording ("ordinary
  shares", "ADSs") is carried in the regexes.

### Cost and mechanics
A cold open is 3-4 paced EDGAR GETs plus a 0.44 s parse of ~6 MB; warm is
**zero network**. HTML → text is BeautifulSoup with **`html.parser` only** —
lxml is installed in the api container but NOT in `backend/.venv`, and the two
parsers are measured identical on the 5.76 MB Amaero S-1/A (741,060 characters).
The parse is the one thing that leaves the event loop, via
`asyncio.to_thread(parse_filing, …)`: pure CPU, no lock, no network.
`lookup` itself must only ever be awaited on the app loop, because
`_edgar_get`'s pacing lock binds to the running loop.

### His call (nothing below is decided)
1. Headline window is 7 days; the app-wide default is 36 h. Keep, or match?
2. A two-sided read on the company name — not built (LLM, ~60 s).
3. A "days to listing" count — not shown (it would be a computed number on a
   fact sheet).
4. The same modal on the listed / recycled tiles — out of scope here.
5. `SEC_USER_AGENT` is **unset in the api container**, so EDGAR sees insider's
   placeholder `research@cheetah.local`. SEC asks for a real contact; setting
   it is host config, not code.
6. 24 h freshness on a successful resolve — a new amendment inside the day is
   missed until the next day. Shorter (6 h, the calendar's own TTL)?
7. Headline query is the quoted short name only. Append `IPO` to narrow it?
8. Finnhub unreadable → 503 with a sentence, vs a 200 with `calendar_row: null`.
9. EDGAR down with a stale clean filing → built to serve it with a sentence;
   the alternative is `filing: null`.
10. `UNDERWRITER_NAMES` (~95 banks) is a code constant. Move it to a data file
    he can edit?
11. No negative cache: a name EDGAR cannot confirm is asked again on every
    click (2 paced FTS calls). Built that way so a failure never becomes a
    fact. Want a short negative cache instead?

Files: `backend/chart_maps/ipo.py`, `backend/chart_maps/board.py`
(`TABS`, `ipo_tiles`, the `tab=ipo` dispatch), `backend/finnhub_client/client.py`,
`backend/finnhub_client/cache.py`, `backend/tests/test_ipo_tab.py` (50),
`backend/chart_maps/ipo_upcoming.py`, `backend/chart_maps/api.py`
(`GET /chart-maps/ipo/upcoming/{symbol}`),
`backend/tests/test_ipo_upcoming_drill.py` (56),
`backend/tests/fixtures/ipo_upcoming_excerpts.py`,
`frontend/src/lib/ipoTab.ts` (+ 20 tests),
`frontend/src/components/IpoUpcomingStrip.tsx` (+ 10 tests),
`frontend/src/components/IpoUpcomingModal.tsx`.
