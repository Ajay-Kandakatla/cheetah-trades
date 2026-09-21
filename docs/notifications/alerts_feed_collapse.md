# Alerts feed — repeated rows collapse into one (2026-09-21)

## The ask, verbatim

Ajay 2026-09-21 ~15:40 ET, answering four questions after the price-alert latch
shipped: **"Yes to all.."** — item 4 was *"Collapse the 2,022 old rows on the
Alerts page?"*.

He is **not** asking to delete or hide history. The rows stay readable; they
stop filling the page one identical line at a time. His screenshot showed the
same ARM line twice and the same ON line twice inside a single 15:00 ET block.

This is **presentation only**. Nothing here gates, ranks, hides or scores a
kind. `ALERT_COOLDOWN_SEC`, the price-alert latch, `alert_gates` and every push
gate are untouched, and no number on this page is a measured edge claim.

## What changed

`GET /notifications/recent` (`backend/push/recent.py`) now folds **adjacent**
rows of the merged ts-desc list that share one identity into the **newest** of
them. The survivor carries a served `repeat` block; the others leave the served
list. `?collapse=false` returns the flat pre-2026-09-21 list.

### The identity

```
(source, kind, ticker, title, tuple(tickers))
```

- **`body` is OUT, on purpose.** Two of his presets (−7% and −12% on one name)
  firing on the same print produce two rows whose bodies differ only by
  `Note: −7% preset` / `Note: −12% preset`. Measured: with the body in the key
  the screenshot's duplicate does **not** fold at all. Consequence, stated
  plainly: the survivor shows the **newest** rule's Note; the older one is
  reachable with `?collapse=false`. (His call — see below.)
- **`tickers` is IN, as a guard.** Several digest titles carry a count and no
  name — `"🚀 3 growth names at demand"` (`backend/growth/alerts.py:189`), and
  the same shape in `hot_pullback_alerts.py`, `pattern_alerts.py`,
  `earnings_alerts.py`, `board_arrival.py`, `demand_alerts.py`. Without the
  name list, two such rows with the same count and different names would
  swallow each other. Measured on his feed in every window: **zero groups
  split** by adding it — it costs nothing today and is a pure guard.
- **`source` is IN**, so a push and a breakout row that happen to share a
  kind/ticker/title never fold together.
- `ticker` is normalised (`strip().upper()`, blank → `None`); nothing else is.
  The title is compared byte for byte.
- `user_email` is out — the read is already his own view.

### "Adjacent" means adjacent

A group is a **maximal run of neighbouring rows** in the served ts-desc list,
**after** the retired-kind filter and after the push/breakout merge. An
interleaved different alert splits a run, deliberately:

| served order | result |
|---|---|
| `ARM, ON, ARM` | **three** rows, none folded — three events |
| `ARM, ARM, ON, ON, ARM` | `ARM(2)`, `ON(2)`, `ARM(1)` |
| `price_alert, vb_workout, price_alert` | **one** row, count 2 — the retired row is removed first, so the two become adjacent |
| `price_alert, demand_alert, price_alert` | three rows |

Rejected alternatives (measured, not built): same-ET-day grouping (≈ −12%) —
a row folds across other rows and only accidentally stays inside its day;
whole-window grouping (≈ −31%) — `"🔔 Market closes in 15 min"` from 28 days
becomes one row drawn under today.

### What the survivor keeps

Everything of its own: `_id`, `ts`, `body`, `sent` / `failed` / `total` (so the
delivery line and the 🔔 alerted-today chips are unaffected), `url`,
`enterable`, `tickers`, `dismissed`. A folded group adds exactly one key.

A group of **1** is passed through as the *same object*, with no `repeat` key —
byte-identical to the old row. `collapse_repeats` never mutates its input.

### The `repeat` block

```json
{"count": 3, "first_ts": 1788616000, "first_ts_iso": "2026-09-05T13:46:40+00:00",
 "last_ts": 1788616120, "truncated": false,
 "line": "2 more like this · first 15:00 ET, last 15:00 ET"}
```

- `count` is the **group size, survivor included** — always ≥ 2. The sentence
  shows `count - 1`, because the survivor is already on screen.
- `last_ts` is the survivor's own stamp; `first_ts` the oldest in the group.
- `line` has two forms, and **every surface prints it verbatim** — no frontend
  recomposes the sentence, reads a clock or formats a date for this row:
  - same ET calendar day → `"1 more like this · first 15:00 ET, last 15:00 ET"`
    (24h, zero-padded — the page's own `etFromTs` style)
  - across days → `"12 more like this · first Jun 5 ET, last Sep 21 ET"`, with
    `Mon D` from `sepa.price_alerts._et_day_label`, the one engine that already
    writes those words in his price-alert messages. That import is lazy and
    wrapped; if it fails the day form falls back to `YYYY-MM-DD` rather than
    growing a second formatter, and the feed never blanks.
  - a missing/zero stamp → the head alone, `"1 more like this"`.
- `truncated` adds a `+`: `"40+ more like this · first Aug 31 ET, last Sep 21 ET"`.

## `limit`, the over-fetch, and the two truncation signals

`limit` counts **collapsed** rows, so the raw push fetch over-reads:

```
raw_limit = min(limit * COLLAPSE_OVERFETCH, MAX_LIMIT)     # 2, bounded by 500
```

`COLLAPSE_OVERFETCH = 2` is an engineering bound, not a trading number: it
covers the worst measured fold on his own feed (bell −12%). The default read
therefore calls `push.history.list_recent(email, **50**)` instead of 25, and a
kinds-filtered page read calls it with 400 instead of 200. The bell polls every
60 s from every open tab — 50 rows/min is bounded and cheap, but it is a
change, and the six moved positional pins in
`backend/tests/test_notifications_recent.py` say so.

Two separate signals, because they answer different questions:

| signal | measured on | what it means |
|---|---|---|
| `raw_truncated` (payload) | the **raw push fetch** — `len(pushes) >= raw_limit` | the window was cut; the page prints ` · newest 500 only — narrow the window` |
| `repeat.truncated` (one row) | the **last push group** at that cut | the `+` marker: this run may have more members past the boundary |

`repeat.truncated` lands on **the last push group, and only when that group has
≥ 2 members — a singleton tail closes every run above it**, so on a singleton
tail the `+` appears nowhere. A breakout run can sit older than every push in
the merged list (`all` mode + `since`; `BREAKOUT_SOURCE_CAP = 200` is its own
cap), so the `+` never lands there either. Top-level `raw_truncated` is what
covers the singleton-tail case, which is exactly why the payload has both.

**"first" is the oldest row in THIS read**, never "first ever": the `since`
window is the user's own filter and the raw fetch is capped at 500.

## The payload

```json
{"rows": [...], "count": 12, "collapse": true, "raw_truncated": false}
```

With `collapse=false`, `raw_truncated` is always `false` and no row carries
`repeat` — the flat read's own `rows.length >= 500` check behaves as before.
`?collapse=maybe` is a 422.

The page header prints an honest pair, `"320 rows · 336 alerts"`, computed
client-side as `visible.length + Σ (repeat.count − 1)` over the rows on screen.
There is deliberately **no server-side `events` total**: the page's
yesterday-only view is a client filter (`Alerts.tsx`), so a server-wide number
could not match what is visible, while the sum over `visible` is exact under
any client filter.

## Measured — HIS read, 2026-09-21 17:08 ET

Every number in this section is the printed output of
`backend/scripts/alerts_feed_fold_probe.py` run inside the api container
against the live Mongo — the shipped script is the source, nothing here is a
retyped read. (Pre-deploy the container still runs `main`, which has no
`repeat_key`, so the run was made with the branch's `backend/push` package
staged under `/tmp/foldprobe` and `PYTHONPATH=/tmp/foldprobe:/app`; after the
deploy the plain command below is the whole story.)

Visibility is `push.history.list_recent`'s own query,
`{"$or": [{"user_email": <owner>}, {"user_email": None}]}` — **his rows plus the
broadcasts**. The collection also holds the co-owner's, Karthik's and other
rows; an all-users read is a different, much larger number that his page never
serves and that is not quoted here.

| window (raw cap) | raw | after retired filter | served | removed | folded rows by kind |
|---|---|---|---|---|---|
| 90 days (all) | 13,589 | 11,692 | **10,813** | **879 (−7.5%)** | price_alert 735, autopilot 57, None 48, todo_reminder 16, rising_momentum 8, trade_flash 5, house_scrape_failed 4, stage_breakdown_2_3 2 |
| today since 00:00 ET (500) | 336 | 336 | **320** | 16 (−4.8%) | price_alert 14, todo_reminder 2 |
| last 5 ET days (500) | **500 (cut)** | 448 | **421** | 27 (−6.0%) | price_alert 22, todo_reminder 4, trade_flash 1 |
| bell default (raw 50) | 50 | 50 | 44 | 6 (−12%) | price_alert 6 |

Run lengths over 90 days: 2 ×512, 3 ×93, 4 ×39, 5 ×6, 6 ×2, 8 ×1, **24 ×1**
(one pre-latch rule re-firing on a cached print). `price_alert` rows 1,908 over
1,137 distinct titles — the title carries the fire price, so the twice-a-day
re-fires of a *moving* price do **not** fold; what folds is several presets on
one print and the same print re-fired inside one pass.

The 5-day row is why `raw_truncated` exists: the raw 500 hit the cap while the
served list was 421, so the old "newest 500 only" warning would have vanished
exactly when the window was cut.

**Re-run before quoting any of these numbers** (they move with the 90-day TTL):

```bash
docker exec -i -w /app cheetah-market-app-api-1 python -m scripts.alerts_feed_fold_probe
```

`backend/scripts/alerts_feed_fold_probe.py` is read-only, hard-codes that
visibility query, and imports `repeat_key` / `derive_tickers` / `known_symbols`
from `push.recent` rather than retyping the identity.

## Who reads this, and what did not change

Reads the collapsed feed for free: `/alerts` (`useAlertHistory` → `Alerts.tsx`),
the `NotificationBell` dropdown, the `PushHistoryPanel` on `/notifications`, and
the 🔔 alerted-today chips on `DemandReentryPanel` / `ZoneEdgeBoard` (those read
`sent` per ticker off a survivor, which keeps its own).

Unchanged: `push.history.list_recent`'s shape and its own 500 clamp,
`/push/history`, the SSE and mac streams, `kinds` / `since` / `ticker`,
`BREAKOUT_SOURCE_CAP`, `_retired_kinds`, `derive_tickers`, the merge order.

## Traps

- **The collapse runs AFTER the merge and the tagging, never on raw
  `list_recent` output.** `tickers` is part of the identity and is filled by
  `derive_tickers` (pushes) / `normalize_breakout` (breakouts) inside `gather`.
  A caller that folds untagged rows gets `()` for every row and the count-only
  digest guard is silently off.
- **The retired filter runs BEFORE the collapse.** Removing a retired row can
  make two identical rows adjacent — that is deliberate and pinned, and the
  inverse (a live row between them) is pinned too.
- **Adjacency depends on the served order within equal `ts`.** 1,916 rows in a
  recent window share a stamp with their neighbour (same-pass writes). Mongo
  returns ties in index order and Python's sort is stable; **do not add a
  tie-break key to `merged.sort`** — it would reorder the default read
  (push-before-breakout) and reshuffle which rows are adjacent.
- **The bell badge counts ROWS**, so a folded four-fire block is **one** unread.
  Deliberate and pinned; the alternative is `Σ repeat.count`.
- **`repeat_line` lazy-imports `sepa.price_alerts`**, which pulls
  `notify` / `prices` / `massive_keys`. Fine in the API process and in the test
  venv, but the import is wrapped: a failure falls back to `YYYY-MM-DD`, never
  to a blank line.
- **Two rules on one print become one line** (measured, deliberate) showing the
  newest rule's Note.
- Neither form of the line contains the word "bounce" or "reversal"; nothing
  here touches a surface's vocabulary.
- macOS bytecode cache defeats mutation tests here — purge
  `~/Library/Caches/com.apple.python` and `__pycache__` on every pytest run.

## HIS CALL — not decided here

1. **`body` out of the identity** — keep (two presets on one print fold into
   one line, newest Note shown), or put the body in (then only exact duplicate
   rules fold and the screenshot's duplicate stays two rows)?
2. **How much to fold on the 5-day / 30-day views** — adjacent-only ships
   (−4.8% today, −7.5% over 90 days). Same-ET-day ≈ −12%, whole-window ≈ −31%,
   and a price-blind identity for `price_alert` (drop the numbers from the
   title) would fold the twice-a-day re-fires of a moving price. Each is a
   semantic change; none is built.
3. **A flat-mode chip on the page** — not built. `?collapse=false` exists as a
   URL; a chip is cheap but it is one more control on a dense surface.
4. **The bell and the PushHistoryPanel print the line too** (built, one muted
   line each) — or keep the bell bare and let it fold silently?
5. **The `+` marker** ("40+ more like this") — built. If he would rather never
   see a `+`, drop `truncated` from the sentence and keep it in the block;
   `raw_truncated` and the page warning stay either way.
6. **`COLLAPSE_OVERFETCH = 2`** — an engineering bound. A bigger factor folds
   more per page and costs bell traffic.
7. **The bell badge counting rows, not fires** (see the trap above).

## Tests

- `backend/tests/test_notifications_recent_collapse.py` — the engine: the fold,
  the `[ARM, ON, ARM]` correctness pin, the body-out screenshot case, the
  count-only digest guard both ways, group-of-1 identity and non-mutation,
  push-vs-breakout, filter-before-collapse and its inverse, the cap counting
  collapsed rows, the over-fetch bound, `raw_truncated` with a short served
  list, the singleton tail, the `+` on the last push group only, both sentence
  forms, the broken-day-engine fallback, `collapse=false`, and `422` on
  `?collapse=maybe`.
- `backend/tests/test_notifications_recent.py` — the six positional-limit pins
  moved to the over-fetched values, plus the flat-mode read and the
  push-before-breakout tie order re-pinned on `collapse=false`.
