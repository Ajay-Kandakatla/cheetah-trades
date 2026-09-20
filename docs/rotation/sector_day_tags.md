# 📰 Sector day-tags — a bull case AND a bear case, off the day's news

**Shipped 2026-09-19.** Not measured. Not a signal. Gates nothing.

Ajay, verbatim:

> "Also for the hot sectors if you see any postive news I would like you to see
> a bullish and bearish case result for a stocks and add it to the sector as a
> tag for that day."

and, on automating it:

> "But I need you pull those scanned stuff in to our app but automate this
> daily morning and over the weekend."

---

## What it does

Once a day, for the top `SECTORS_PER_RUN` sectors on the 🔥 Hottest board:

1. Read the news on each sector's `NAMES_PER_SECTOR` leading names.
2. Pick the one name that actually **has a story** today (≥ `MIN_HEADLINES`).
3. Hand the model the headlines **and the numbers already on that board row**.
4. Get back a bull case, a bear case, and a positive/not read.
5. Store one document per `(date, sector)` in Mongo `sector_day_tags`.

`GET /rotation/hottest` then attaches each sector's tag as `day_tag`. The board
renders a 📰 chip beside the sector name; clicking it opens a row with the
trigger headline and the two cases.

## The decisions worth knowing

### Both sides, always

A tag ships only when **both** cases are written (`_usable`). A bull case with
an empty bear case reads as a recommendation, which is the one thing this is
not. Half a tag is suppressed, not shown.

The frontend gives the two cases the same width, the same type and the same
container, and a test asserts it. The moment the bear case looks like a
footnote, this stops being a briefing.

### The name is picked by news, never by return

`_pick_name` orders by **headline count**, then by the board's own ranking.
Deliberately not by move: a tag chosen by return is a momentum read wearing a
news label, and the board already sorts by return. There is a test named
`test_THE_BIGGEST_MOVER_DOES_NOT_WIN_ON_ITS_MOVE`.

### There is no sentiment score

Because we do not have a measured one. No lexicon was invented, no numeric
threshold was fitted, nothing counts "positive words". A fitted score would
look like evidence and be worth nothing.

`positive` is the **model's read of the headlines**, and the tile says so in
those words. Every tag carries `measured: false` and `read_by`.

### The app owns numbers, the model owns prose

The same split `desk.report` established. `_facts` builds the block — the
sector's move against RSP, the name's own legs, sales and EPS growth, the zone
state, the next earnings date — from the hottest payload. The system prompt
forbids the model from stating any number not in that block, and forbids
recommendations, ratings and price targets. Whatever it writes, the numbers a
reader sees are rendered by the frontend from `facts`, never parsed back out
of the prose.

Absent values are **omitted** from `_facts` rather than passed as `None`, so
the model is never handed a hole to hallucinate around.

### Scope knobs, not signal thresholds

| constant | value | what it bounds |
|---|---|---|
| `SECTORS_PER_RUN` | 6 | sectors tagged per pass |
| `NAMES_PER_SECTOR` | 5 | names whose news is read |
| `NEWS_WINDOW_HOURS` | 36 | what counts as "today's news" |
| `MIN_HEADLINES` | 2 | one loose headline is not a story |

None is fitted to an outcome. Moving one changes how much gets summarised,
never what a number means. A test asserts the module never imports
`supply_demand`, `trading`, `alert_gates` or `entries`, and never pushes.

36 hours, not 24, so a Monday run still sees Friday's close-of-day story.

### Undated headlines are dropped

The three feeds merge Finnhub, Yahoo RSS and Google RSS, and Google's is the
one that most often omits the timestamp. Letting those through would quietly
turn a 36-hour window into "whatever the cache holds". Millisecond stamps are
understood; far-future stamps are dropped.

### Local model first, hosted second

`provider="local"`, then `provider="anthropic"` if local is unusable — **not**
`provider="auto"`, which resolves to Anthropic whenever a key exists and would
send every call off-box even with LM Studio running.

Measured on the cron container the day this shipped: the local server was
refusing connections on `host.docker.internal:1234` while Anthropic answered.
A job that only tried local would have shipped as a feature that silently
never fires. `read_by` records which one wrote each tag.

At most six calls a day.

## The weekend

The crontab entry carries **no `market_hours.gate`**, deliberately — every
other job in that file is gated to trading days because it measures the tape;
this one reads headlines, and he asked for the weekend in those words.

```
20     6     *    *    *    /usr/local/bin/python -m rotation.sector_news_tags
```

A Saturday pass builds off Friday's persisted board with the last 36 hours of
news. `latest_within()` lets the endpoint fall back to the most recent day that
produced tags, and every tag carries its own `date` so the surface can say
which day it is from — a weekend read is never mistaken for a fresh one.

`python -m`, not `curl`: `rotation.api._members_table` falls back to the
persisted `scan_context` document when its in-process cache is cold, which is
exactly the cron container's situation. Same reasoning as
`rotation.history snapshot`; the opposite of the 17:10 rotation warm, which
must be HTTP because it warms an in-process cache.

**A crontab change does not ship with a main deploy** — the mount is the host
tree. Verify in-container after deploying.

## Failure is quiet and total

News down, model off, model returns junk, one side missing → **no tag**. The
sector renders exactly as it did before any of this existed. `attach()` sets
`day_tag: null` explicitly so the frontend reads one shape everywhere.

`attach()` never reorders the board.

## Files

| file | role |
|---|---|
| `backend/rotation/sector_news_tags.py` | build, store, load, attach |
| `backend/rotation/api.py` | `/rotation/hottest` attaches the tag |
| `backend/crontab` | 06:20 local, every day, ungated |
| `backend/tests/test_sector_news_tags_2026_09_19.py` | 46 tests |
| `frontend/src/components/HottestSectors.tsx` | `HsDayTag`, chip, `DayTagRow` |
| `frontend/src/components/HottestSectors.daytag.test.tsx` | 17 tests |

## What it is not

🔥 Hottest is a **discovery surface with no measured edge** — a trailing-return
ranking, never backtested. A tag on top of it inherits exactly that status and
no more. It pushes nothing, gates nothing, sizes nothing, enters no lane, and
moves no S&D rule, threshold or band.
