# 📌 GnT tracker — Tito Adhikary (@GnT_Trades) — 2026-09-12

> Ajay: *"Can you create a new tab on chartmaps tracking this person.. He had
> humongous growth of stocks"* and *"do this daily twice. and create a tab for
> me. I wanna track his stocks for investing"*

## Who he is — verified, not recalled

Read off his live profile on 2026-09-12:

- Bio: *"Investor/Trader | Sharing reflections and ideas | USIC 2025 #1, 2115%"*
- 33.9K followers, 6,568 posts
- Pinned 2026-01-29: won the **$20k+ Enhanced Growth Division with a 2,115%
  return in 2025**, quoting @USICOfficial: *"Congratulation to Tito Adhikary, a
  Harvard cancer researcher, for setting a new world record in the enhanced
  growth division, + 2115.1%!"*

That number is a **cited claim with its source attached**, not something this
app measured — and a contest return is not a transferable track record: those
divisions permit concentration and leverage this app's own risk rules forbid.

## The finding that shaped the whole board

**He does not post a portfolio.** Two incompatible kinds of mention share his
timeline:

| | |
|---|---|
| **Forward idea** | *"$SPCX reclaiming 150 into the close. Definitely on watch next week"* · *"$BBY has a nice look"* · *"$SMCI don't love the stock but can't ignore the chart"* |
| **Closed recap** | *"Great day on $QQQ **puts**, +$12K"* · *"$NFLX turned out to be a *great* trade **with puts**"* · *"Best trades **were** on $NVDA $RKLB $GS $NFLX $META"* · *"Traded $NFLX $NVDA $BBBY today"* (2022; BBBY is bankrupt) |

A naive cashtag scraper produces a "his stocks" list containing **bankrupt
names, index tickers, and bearish put trades read as longs.**

So: **every row leads with his words and its age. The ticker is the label, the
sentence is the content.**

### No row claims a direction — and that is not caution, it is arithmetic

One of his own posts reads:

> *"caught the upside on **$FSLR** and downside on **$META $TSLA**"*

One sentence, two directions, split across three tickers. Any post-level
long/short badge marks META and TSLA as longs. The chips on the board are
therefore **words found in the post** (`puts`, `watch`, `recap`, `long`,
`short`), never a reading of it. Pinned by
`test_THE_CENTRAL_NEGATIVE_one_post_can_carry_both_directions`.

Index and volatility tickers are dropped from the roster — *"Harder week with
$SPY $QQQ weak"* is him describing the tape. Listing SPY as one of his stocks
**while he is calling it weak** inverts him.

## Where the data comes from — two sources, because neither is enough

| | RECENT | TOP |
|---|---|---|
| URL | `x.com/GnT_Trades` | `syndication.twitter.com/srv/timeline-profile/…` |
| Posts | ~5 + the pinned one | ~101 |
| Order | **chronological** | **engagement-ranked** (favourite counts descend monotonically — measured) |
| Span | live | 2022-05 → 2026-01 |
| Carries yesterday's posts | **yes** | **no** |

Neither needs an API key or a login; both are read-only fetches of a public
profile. Syndication alone would have kept the board looking alive while it had
stopped tracking him — it does not contain a single one of the SPCX / BBY /
SMCI ideas. So **`ok: false` the moment the RECENT source yields nothing**,
STORED per account (`trader_feed_status`) and SERVED on the board as
`refresh.note`, and the cron exits non-zero. A tracker that silently stops
updating is worse than one that is visibly broken — and from 2026-09-25 to
2026-10-22 it WAS silently stopped on the board, see below.

**Timestamps come out of the tweet id itself** (snowflake: `(id >> 22) +
1288834974657`) — the 2026-09 recent stream shipped no `created_at`, and without
a date there is no way to tell a live idea from a 2022 recap, which is the one
distinction that matters here. The 2026-10 shape does ship `created_at_ms`; it
is stored beside the post and agrees with the snowflake clock to the second
(pinned by `test_each_post_carries_its_own_sentence_and_X_s_own_timestamp`).

## Schedule

```
40  7,17  *  *  *   python -m traders.feed refresh
```

Twice a day, **07:40 and 17:40 ET** (the stored `first_seen` stamps read
21:40Z, i.e. 17:40 EDT — the container clock is Eastern, whatever the crontab
comment once said), and deliberately **not** gated by
`market_hours.gate`: the SPCX / BBY / SMCI ideas all landed on a Friday evening,
and his weekend wrap is where the next week's watchlist shows up. A closed-day
gate would drop exactly the posts worth reading.

Storage is cumulative and idempotent — `_id` is the tweet's own id — so extra
runs deepen the archive instead of duplicating it, and the history outgrows
what either endpoint returns today.

## The overlay — why this is a Chart Maps tab and not a link to X

Each of his tickers carries **our** read: whether the name is in the `full`
scan universe at all, its demand-band state (reusing `growth.tracker._zone_read`
so the two boards can never disagree), and the 100/100 growth screen.

**It paid off immediately: `SPCX` — his freshest idea — is not in the universe.**
It is invisible to every board, scan and alert in this app, however good the
call is. Same class as the AXTI / UMAC / CLYM finding.

## What it does NOT do

His calls, **not advice**, and not a portfolio. **No scan consumes it, no alert
fires from it, nothing buys from it.** The board reads stored posts and never
fetches on a page load.

## 2026-10-22 — four weeks dark: X changed the page shape on 2026-09-25

**Observed:** from the 2026-09-25 07:40 ET run to 2026-10-22 the cron exited 1
twice a day with `gnt: stored 101 posts, ok=False, sources={'recent': 0,
'top': 101}` (same for martinluk). The board's newest stored GnT post stayed
2026-09-24 while he posted on NBIS, $TWST $TXG, $CRWD and $TSLA on 10-21; Martin
posted 10-01 and 10-08, both missed.

**Measured, not assumed** (from inside `cheetah-market-app-api-1`, with the
module's own `httpx` + browser UA transport):

| | |
|---|---|
| `GET https://x.com/GnT_Trades` | **HTTP 200, 274 KB** — not a TLS/IP block; no curl_cffi needed |
| `client:` key-stream prefixes in the page | **0** (the 2026-09 shape is gone) |
| `VHdlZXQ6` tweet ids / `full_text` bodies | **6 / 6** — the posts are still there |

The timeline now rides in a server-rendered **Relay record**:

```
($R=>$R[19].next($R[21]={kind:"GraphQLRequestStream.Completed",requestId:1,
  key:"F4_4pW9JUsYFURg7T0nnJQ{\"screenName\":\"GnT_Trades\",…}",
  result:$R[22]={kind:"Result.Ok",value:"{\"data\":{\"user_result_by_screen_name\":…}}"}}))
```

`value` is a JS string literal holding the GraphQL JSON:
`data.user_result_by_screen_name.result.profile_user_originals_timeline.timeline.instructions[]`
→ `TimelinePinEntry.entry` + `TimelineAddEntries.entries[]`, each
`entry_id: "tweet-<id>"` → `content.content.tweet_results.result` →
`{rest_id, details:{full_text, created_at_ms, cashtag_entities},
core.user_results.result.core.screen_name, counts.favorite_count}`. Several
`Result.Ok` records ride on one page (finance cards, smart tags, the user
lookup); only the one with `tweet-` entries is the timeline.

**The fix** (`traders/feed.py`):

- `_parse_recent` tries the Relay record first (`_parse_recent_relay`), then
  the old key stream (`_parse_recent_keystream`) — X may roll back. Each post
  carries `shape` (`relay` / `keystream`); the payload carries `recent_shape`.
- A post is read from the entry's OWN tweet object (`rest_id == entry id`), so
  the @USICOfficial post quoted inside his pin is not his. A readable author
  that is not the tracked handle is skipped; an unreadable author is kept
  (unknown is not "someone else").
- Fixtures: `tests/fixtures/x_profile_{GnT_Trades,martinlukkt}_2026_10_22.html`
  — the real pages trimmed to the timeline record plus one non-timeline
  `Result.Ok` record the parser must skip. Hermetic; no network in any test.

**Why nobody saw it for four weeks:** the loud failure went to the cron log
(rc=1) and the board kept typing *"Checked twice a day"*. So:

- Every run's verdict is now **stored** — `trader_feed_status`, one doc per
  account: `at`, `ok`, `sources`, `errors`, `recent_shape`, `stored`, and
  `last_ok_at` which survives a dark run (when the latest-posts source last
  answered).
- `board()` **serves** it as `refresh` with ONE sentence, `refresh.note`,
  which the frontend prints verbatim and never paraphrases:
  - ok: *"Latest posts checked 2026-10-22 17:40 ET: the x.com page answered
    with 5 posts and the history source with 101. Checked twice a day."*
  - dark: *"⚠️ NOT tracking Tito Adhikary's latest posts: at the 2026-10-22
    08:31 ET check the x.com page returned no posts (it last answered
    2026-09-24 17:40 ET). The history source answered with 101 posts, so the
    names below are Tito Adhikary's history, not what was posted today."*
  - no doc yet: *"No refresh recorded yet — the tracker runs twice a day and
    writes its verdict here."*
- **Exit codes** (`traders.feed.exit_code`): `0` every latest-posts source
  answered · `1` PARTIAL — history stored, a latest-posts source dark (the
  board says so) · `2` an account stored NOTHING. For four weeks `rc=1` read
  as "the job failed" while 101 history posts were stored every run; the
  per-account line now prints `ok` / `PARTIAL` / `NOTHING STORED`. The crontab
  COMMAND is unchanged (the host crontab is mounted, not shipped).

Pinned by `tests/test_trader_feed_recent_shape_2026_10_22.py` (23 tests, 8 of
them NEGATIVE), `GntBoard.test.tsx` (the served verdict, 4 tests) and the
frontend contract *📌 GnT: latest-posts source restored + served verdict
(2026-10-22)*.

## 2026-10-27 — algo888 on StockTwits

> Ajay, 2026-10-27 ~08:45 ET: *"Can you track this guy please? and his
> tickers"* (https://stocktwits.com/algo888), then *"Add them to Gajjals, they
> are pretty good"*.

**What changed.** A third registry row, appended last (`DEFAULT_KEY` stays
`gnt`): `algo888`, `"source": "stocktwits"`, `"usic": None`, `"gajjala": True`,
`"curate": False`. GnT and Martin gain `"source": "x"`, `"gajjala": False`,
`"curate": True` and their x.com `profile_url` — their behaviour is unchanged.

**How he is read.** `stocktwits_client.fetch_user_stream` — the SAME page walk
as the symbol streams (`_walk`, moved verbatim out of `fetch_stream`; every
symbol log line is unchanged), the same Cloudflare-passing profiles and the
same served failure sentences. `traders.feed.fetch_stocktwits` →
`parse_stocktwits` turns his messages into posts the board already stores:

- `_id` = `st<message id>` (never collides with a tweet id), `created_at`
  from StockTwits' own UTC stamp, stored `+00:00`, `url` = his message page.
- Only messages whose `user.username` IS `algo888`; an empty body is skipped;
  the INNER message of a reshare is never read (someone else's, or an older
  sentence of his).
- HTML entities unescaped (`&#39;` → `'`, `&amp;` → `&`).
- `sentiment` = HIS own label (`entities.sentiment.basic`) as found, `None`
  when he set none — never inferred. `symbols_meta` keeps exchange /
  instrument class / trade status per name.
- `refresh()` dispatches on `source`: `"x"` runs the x line byte-identical
  (pinned against a frozen copy of the stored posts); `"stocktwits"` reads
  `TRADER_ST_PAGES = 2` pages (Cheetah default, mine — 60 messages per cron
  read). The cron line is unchanged; `refresh_all` simply has three accounts.
- The served verdict names the StockTwits stream (`refresh.note`): ok →
  *"Latest posts checked … the StockTwits stream answered with N posts.
  Checked twice a day, and by Gajjala's scan while it runs."*; dark →
  *"⚠️ NOT tracking algo888's latest posts: at the … check the StockTwits
  stream returned no posts — <the client's sentence> (it last answered …).
  The names below are the stored archive."* An account that stored nothing
  still exits the cron with rc=2.
- `board()` serves `source`, `source_text`, `claim_text`, `profile` and
  `gajjala_text`. **Bug fixed on the way:** `usic` fell back to GnT's
  `USIC_2025`, so a claim-less trader would have served "+2,115.1%" — `usic`
  now has no fallback, and `profile_url` comes from the registry row.

**The real page (fixture `tests/fixtures/stocktwits_user_algo888_2026_10_27.json`,
read 2026-10-27 ~08:59 ET):** 30 messages, all by algo888, 08:14–09:56 ET; 19
carry names — GPUS ×15 (NYSEMkt), MXCT ×4 (NASDAQ), both "Stock"; his label
Bullish ×27, none ×3; 7 reshares. His profile: 3,846 followers, following 0,
joined 2019-06-06, 114,049 ideas. No championship claim anywhere, so no USIC
line.

**His own words (2026-10-27, ET):** *"$GPUS 75,000 purchase @ .1856
pre=loading for the run up to .50 - .70 range then back to 1.00 - 1.25 push"*
(08:28) · *"I used to pump  stockd with regulatity"* (08:52) · *"@WC25 That;s
how I pump.... LOL"* (08:55) · *"$GPUS my 100,000 position is up huge!!!"*
(09:41). His bio: *"DO NOT FOLLOW ME as I move in & out of da markets killing
it like a sniper"*.

**The prior is null or worse — UNMEASURED.** No study in this app has read his
names. The closest class this app measured, promo-account first tags, came out
INVERTED: −4.78pp median 5-session vs a matched placebo, CI [−7.19, −3.41]
(`docs/catalysts/promo_tag_study_2026_09_21.md`). He self-describes pumping.

**What joins Gajjala.** Nothing in this module decides anything. 🚩 Gajjala's
pass reads his STORED posts and adds his fresh names to that scan's candidate
list, tagged 📌 (`chart_maps/gajjala/trader_names.py`, documented in
`docs/gajjala/trader_names_2026_10_27.md`); GG's rules decide every read and
every A+. The traders DISCLAIMER, the feed docstring and the `/traders/{key}`
docstring say so with this date.

**The curator (A1).** His names do NOT enter the `full` universe:
`traders/curate.py run` skips every row with `"curate": False` and names it in
the run summary (`skipped_traders`). Putting him in the curator too is HIS CALL.

**Verify.** Hermetic tests:

```bash
cd backend
/usr/bin/find . -name __pycache__ -type d -prune -exec rm -rf {} +
docker run --rm --network none --name cheetah-tmp-pytest-traders -v "$PWD/..":/repo -w /repo/backend -e PYTHONDONTWRITEBYTECODE=1 cheetah-api:latest python -m pytest -q -p no:cacheprovider tests/test_trader_feed_stocktwits_2026_10_27.py tests/test_trader_feed.py tests/test_trader_feed_recent_shape_2026_10_22.py tests/test_trader_curate.py tests/test_stocktwits_client.py
```

After the deploy, on his surface:

```bash
docker compose exec cron python -m traders.feed refresh
curl -s -H "X-User-Email: ajaykandakatla@gmail.com" http://127.0.0.1:8000/traders/algo888
```

Expect `n_posts` > 0, `usic` null, `source_text` "on StockTwits" and a
`refresh.note` that names the StockTwits stream.

## Re-run

```
docker compose exec cron python -m traders.feed refresh
docker compose exec cron python -m traders.feed show
```
