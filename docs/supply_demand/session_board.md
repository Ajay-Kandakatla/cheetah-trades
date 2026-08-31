# Session board — ORB / FVG / SMC / mood across the demand tabs

Shipped 2026-08-31. Ajay: *"Can you create a tab for ORB/ FVG/ Bullish
sentiment or bearish for all the onces in demand zone. and deep demand zones.
You have this logic for on demand of a ticket in Support levels tab .. and for
entries based. I will use this tab after market open to figure out market
sentiment ... But pull the tickers from Demand and Deep Demand tabs."*

## The question this tab asks

Back in Demand and Deep Demand answer **which names**, on daily structure. That
is settled before the bell. This asks the next one:

> now that the session is running, is the tape confirming or rejecting the
> daily band that put this name on the list?

Same analytics that already exist per-ticker on the Support tab, run across the
union of the two boards instead of one symbol at a time. The daily band travels
with the symbol, so the intraday read always has a level to be about — mood
without a level is a weather report: no level, no stop, no size.

`GET /supply-demand/session-board?tf=15m|60m`

## Why this did not reopen the 2026-08-29 decision

Ajay's earlier correction — *"I do not need these on scans but on demand in the
support levels"* — is locked by `test_the_scan_boards_do_not_take_a_timeframe`,
and **that lock still passes**. It forbids bolting a timeframe knob onto the
daily boards; `chart_maps.board` still takes no `tf` and the daily tabs are
untouched. This is a separate surface with its own explicitly intraday
contract.

The cost objection recorded in `timeframes_orb_fvg.md` ("intraday bars for
~1,700 symbols per refresh") also does not apply. The input here is the ~99
names the two boards already selected — measured 2026-08-31: 58 from Back in
Demand, 42 from Deep Demand, 1 in both.

## What each row carries

| Field | Meaning |
|---|---|
| `bias` | bullish / bearish / neutral / **unknown** — the mood label, not a new blend |
| `mood` | six bounded components, −100…+100 (`supply_demand/mood.py`) |
| `orb` + `orb_state` | opening range and which side price holds |
| `session_gaps` | unfilled FVGs left by **this** session, called out from the rest |
| `smc` | complete sweep → BOS → order block → FVG sequences, graded |
| `at_band` | price is inside the daily demand band that listed the name |
| `signal` | BUY / SELL / WAIT, anchored to that daily band |
| `session_score` | ranking only — **convention**, `cited: false` |

`bias` is deliberately the mood label rather than a second sentiment number.
Inventing one would put two numbers on the same card with no way to say which
is right when they disagree. ORB state and SMC ride alongside as
*confirmations*, reported separately so a reader can see the parts disagree.

## The forming opening range

At 09:31 a "15-minute opening range" is **one bar**. Verified live on
2026-08-31: the first build called that single bar's high/low the opening range
and scored it. Two consequences, both locked by tests:

* `orb.complete` is false until the full window has printed, and the UI says
  `range forming (2/15m)` rather than `above the 15m range`.
* An incomplete range **does not vote** in `session_score`. It is still
  reported — Ajay asked for the first-few-minutes view — it just does not rank
  99 names on which side of one minute price sits, in exactly the window he
  opens the tab.

## Ranking

`session_score` is a **sum of named parts**, not a fitted blend, so every point
on a row traces to the fact that produced it and the UI can print those facts
as chips:

```
mood score (-100..+100)
+25  a COMPLETE SMC sequence exists
+15  price is at the daily band that listed the name
+10  holding above a COMPLETE opening range   (-10 below)
 +5  an unfilled gap left by this session
```

`None` when mood could not be read. Those rows sort **last and are kept** —
dropping them would make a thin-data day look like a calm one, and `null` must
never render as `0`, which is a real neutral reading.

## Rendered like the Demand boards (2026-08-31, same day)

Ajay, on the first rows-only build: *"Can you make this view like Demand view
please with similar information"*. Each row now also carries `tile` — the row
reshaped into the boards' CmTile — and the tab renders a `cm-grid` of the SAME
`PatternChart` the Demand tabs use. On the chart: the daily band (green), the
opening range (neutral — a range has no side, same rule as the 0DTE gamma
walls; labelled "forming" until complete), this session's FVGs (blue/amber),
the best SMC order block (purple), and BUY/STOP/TARGET lines from the
band-anchored signal, else the best SMC leg — never both, two entries on one
tile is unreadable. Stats: Mood / ORB / SMC grade / Score. A name with no
intraday bars shows as a text card naming the reason, because dropping it
would misreport coverage.

Also fixed from the same screenshot: the loading state claimed "Market is
closed — this is the last completed session" before any data had arrived, at
09:40 on a Monday. Loading and warming banners are now neutral; only a real
payload may make session claims.

## Cost and refresh

One 1-minute fetch per symbol per pass, reused for both the resampled frame and
the opening range — which is why `timeframes.intraday_raw` and
`patterns.opening_range_from_bars` exist. Fetching twice doubled today's live
requests and drew Massive read timeouts at 10 workers; workers are now 8.

Completed days are Mongo-cached by `daytrading.data`; only **today** is
re-fetched. Measured 2026-08-31: cold ≈ 12s a name (169s for 99), warm ≈ 1s.
Because a cold pass exceeds Cloudflare's ~100s cutoff (the 524 of 2026-08-14),
the request path never blocks: it serves what it has, warms in a thread, and
the page polls `/session-board/progress`. Server cache is 180s and reports its
own age.

## Out of session

A weekend or pre-open read is legitimate and shows the **last completed
session**, labelled `last session · 2026-08-28` with `live: false`. It never
implies today.

## Source status

ORB is Crabel (1990) / Raschke (1995). Mood, fair-value gaps, the SMC sequence
and `session_score` are **convention** — no canonical text — and every record
carries `cited: false`. See the SMC appendix in `timeframes_orb_fvg.md`.

## Tests

`backend/tests/test_session_board.py` (15) and
`frontend/src/lib/sessionBoard.test.ts` (11) +
`frontend/src/components/SessionBoard.test.tsx` (6). The negatives carry the
weight: a one-bar range is incomplete and does not rank, an unreadable row
scores `None` rather than `0` and is kept, a gap with no session stamp is never
claimed as today's, `bias` says *unknown* rather than *neutral* when mood is
unavailable, a warming source reports warming rather than an empty board, and
`frame_for` must not re-fetch when handed bars.

*Decision-support only. Not investment advice.*
