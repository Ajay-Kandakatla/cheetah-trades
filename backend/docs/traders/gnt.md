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
| Posts | ~6 | ~101 |
| Order | **chronological** | **engagement-ranked** (favourite counts descend monotonically — measured) |
| Span | live | 2022-05 → 2026-01 |
| Carries yesterday's posts | **yes** | **no** |

Neither needs an API key or a login; both are read-only fetches of a public
profile. Syndication alone would have kept the board looking alive while it had
stopped tracking him — it does not contain a single one of the SPCX / BBY /
SMCI ideas. So **`ok: false` the moment the RECENT source yields nothing**, said
on the board and exiting non-zero from the cron. A tracker that silently stops
updating is worse than one that is visibly broken.

**Timestamps come out of the tweet id itself** (snowflake: `(id >> 22) +
1288834974657`) — the recent stream ships no `created_at`, and without a date
there is no way to tell a live idea from a 2022 recap, which is the one
distinction that matters here.

## Schedule

```
40  7,17  *  *  *   python -m traders.gnt refresh
```

Twice a day, **07:40 and 17:40 CT**, and deliberately **not** gated by
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

## Re-run

```
docker compose exec cron python -m traders.gnt refresh
docker compose exec cron python -m traders.gnt show
```
