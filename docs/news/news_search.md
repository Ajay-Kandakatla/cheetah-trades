# `news_search` — the one reusable news routine

**2026-09-20.** Ajay, verbatim: *"A reusable backend routine"*.

`backend/news_search/core.py` is the single place a NEW backend surface asks
for headlines. One selector — a ticker, a sector, or a keyword — one window,
one undated policy, one dedupe, one relevance rule.

Nothing here is measured. A headline count is not evidence and a "fresh" stamp
is not a catalyst. `DEFAULT_WINDOW_HOURS` is a **scope knob**: it bounds what a
caller reads, it does not gate anything, and it is deliberately separate from
anything under `supply_demand/` or `trading/`.

## Using it

```python
from news_search import core

res = await core.search(ticker="NVDA")                       # async
res = core.search_sync(sector="Semiconductors")              # sync / cron
res = core.search_sync(keyword="CHIPS Act", audit="my_page") # audited
```

Exactly one of `ticker` / `sector` / `keyword`, or `ValueError("exactly one of
ticker/sector/keyword")`. A whitespace-only value counts as absent.

| Argument | Default | What it does |
|---|---|---|
| `window_hours` | `DEFAULT_WINDOW_HOURS` = 36 | older than this is not "today's news" |
| `now` | wall clock | pinned in tests |
| `relevance` | `"company"` | `"none"` skips the filter; only ever applies to the `ticker` selector |
| `limit` | `DEFAULT_LIMIT` = 12 | applied LAST, after every drop |
| `audit` | `None` | caller name; upserts the whole result into `news_search_audit` |

Returns `{"items", "selector": {"kind","value"}, "query", "window_hours",
"fetched_at", "counts": {"raw","undated_dropped","stale_dropped",
"irrelevant_dropped","deduped"}}`.

**It never raises past the selector check.** A provider that is down comes back
as `items: []` with `counts.raw == 0`, because every caller is a board that
still has to render.

## The four rules, and where each was lifted from

Nothing below was re-derived. Each rule is code that already shipped, moved:

1. **Window + undated + ms + future guards** — `rotation.sector_news_tags._fresh`,
   verbatim. An item with no timestamp is **DROPPED**, never assumed fresh. A
   13-digit stamp is read as milliseconds. A stamp more than 3600 s in the
   future is dropped (clock skew allowance).
2. **Dedupe** — `news.fetch_news`'s title key (`\W`-stripped, lowered, first 80
   characters), **plus** the url, so one leg serving the same url under a
   rewritten headline collapses too.
3. **Relevance** — `sepa.catalyst._fetch_google_news`'s post-filter: company
   name | its first word | `$TICKER` | bare ticker **only at 4+ characters**.
   That last clause is the USD trap: a bare three-letter ticker matches prose
   about the dollar.
4. **Query escaping** — `news.google_search` (new, additive) runs the query
   through `quote()`. The legacy `news._google_news` builds a raw f-string with
   `+` separators and no escaping; it is left alone because `fetch_news` is
   pinned by tests and three surfaces, and a ticker has no character that needs
   escaping. `quote()` encodes a space as `%20`, which Google accepts.

### Why the undated drop is load-bearing

Until 2026-09-19 `news._parse_rss_date` used `strptime("%z")`, which cannot read
a NAMED zone, and Google News emits exactly that. Every Google item raised and
was stamped with the **current time**. Measured: `fetch_news("NVDA")` returned
12 Google items, all 12 reporting an age of 0.00 hours, one of them genuinely
twenty-four days old. Every recency window in the app was filtering on a
constant. Undated now means undated.

## What delegated, and what did not change

`rotation/sector_news_tags.py`:

- `NEWS_WINDOW_HOURS` is now **re-bound** to `core.DEFAULT_WINDOW_HOURS` — one
  window in the app, not a copy per caller.
- `_fresh` → `core.fresh`. Proved byte-identical against a re-implementation of
  the pre-delegation body over eleven fixtures.
- `_news_for` → `core.search(..., relevance="none", audit="sector_day_tags")`.
  **`relevance="none"` is deliberate and behaviour-preserving**: these tags have
  never filtered a headline against the company name. Turning the filter on
  would change WHICH name gets the day's tag — **HIS CALL** (spec §7 item 8).

## The five undated policies this does NOT reconcile — HIS CALL

This module gives every **new** caller one policy. It does not rewrite the five
legs that already exist, each of which answers "what is an undated headline
worth?" differently. Reconciling them changes what shipped surfaces show, so
none of it was decided here:

| Leg | Window | Undated headline |
|---|---|---|
| `rotation/sector_news_tags._fresh` | 36 h | **dropped** (now via `core.fresh`) |
| `sepa/catalyst._fetch_google_news` | none | **kept**, `pub` carried raw |
| `catalysts/news_read` | none (Google) / 168 h (Massive fallback) | **kept** |
| `catalysts/evidence._fetch_massive_news` | `hours` cutoff | **KEPT** (`except: pass`) |
| `catalysts/product_launches._fetch_news` | `hours` cutoff | **DROPPED** (`except: continue`) |

The last two are the sharp one: **`catalysts/evidence.py` and
`catalysts/product_launches.py` read the SAME Massive endpoint and disagree on
the same row** — one keeps an unparseable date, the other drops it. Both are
untouched here; this is **HIS CALL**, as stated in the ask (spec §7 item 9).

### The must-not-move list, verbatim

> Do NOT touch `sales.py`, `canslim.py`, `buyable_verdict.py`,
> `episodic_pivot.py`, any tier threshold, `MEASURED`, or the verdict wording.

Nothing in this package touches any of them. `news.fetch_news` and
`news.market_news` are byte-identical in behaviour — `google_search` is
additive and the legacy Google URL for `NVDA` is pinned by a test.

## Comment-vs-code corrections shipped with this (comments only, no behaviour)

Three comments in the codebase stated a time window the code has never passed:

| File | Said | Truth |
|---|---|---|
| `backend/catalysts/api.py` | "pulls the last 72h of headlines" | Google leg passes **no window**; Massive fallback is `hours=168` (7 days) |
| `backend/catalysts/premarket.py` | "Overnight news mentions (last 12h)" | **no hour bound** — the 100 most recent Massive articles |
| `backend/supply_demand/news.py` | "co-mentioned NVDA + TSM in 30 days" | **no date bound** — 30 is a COUNT OF ARTICLES, not days |

## The audit collection

`audit="<caller>"` upserts the whole result into `news_search_audit` under
`_id = "{caller}|{kind}|{value}|{ET date}"` — one row per caller, selector and
**ET session date**, so what a surface was shown on a given day is readable
after the fact. A Mongo failure is logged and never reaches the caller.

## Tests

`backend/tests/test_news_search_2026_09_20.py` — 71 tests, no network, every
provider leg faked. Negatives carry the file: undated dropped from both ends,
window boundary ±1 s, future beyond the skew allowance, NaN stamps, empty and
whitespace queries, zero / two / three selectors, provider failure, a failing
name lookup, a Mongo write failure, a non-200 and a raising transport, and the
hostile query `AT&T stake? #1 C++ 100% "x"` asserted to leave no raw space, `&`,
`?`, `#` or `+` in the URL's query segment and to decode back exactly.

`tests/test_sector_news_tags_2026_09_19.py` (50) and
`tests/test_news_rss_dates_2026_09_19.py` (10) pass unchanged.
