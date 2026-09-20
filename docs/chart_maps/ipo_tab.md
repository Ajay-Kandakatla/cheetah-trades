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

Files: `backend/chart_maps/ipo.py`, `backend/chart_maps/board.py`
(`TABS`, `ipo_tiles`, the `tab=ipo` dispatch), `backend/finnhub_client/client.py`,
`backend/finnhub_client/cache.py`, `backend/tests/test_ipo_tab.py` (44),
`frontend/src/lib/ipoTab.ts` (+ 20 tests),
`frontend/src/components/IpoUpcomingStrip.tsx` (+ 10 tests).
