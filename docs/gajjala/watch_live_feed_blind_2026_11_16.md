# 👀 Watch LIVE — how blind is the one Massive socket? (2026-11-16, WP-E, critique C7)

Ajay 2026-11-16: "Also on the Watch list I need live volume to be shown at the bottom" · "Of each chart".

## The question

The live candle and live volume column on every Watch chart count only the prints THE one Massive socket saw. A
second client on the same key kicks it; until the next auth it sees nothing. How low is the live column,
structurally? Memory said "a second Massive client kicks every ~2 min" — a sentence. This turns it into a number.

## Verdict

**Blind 15.27 % of the hub window (median) over 6 sessions; 242.3 kicks/session; p50 gap 30.2 s** (mean 15.31 %,
p90 gap 30.3 s; worst day 19.53 %, best 8.75 %). The typical gap is the feed's own 30 s reconnect wait after a kick — the
socket is not slow to come back, it is kicked about every 4 minutes of the 04:00–20:05 window.

## The rule replayed (the feed's own, never a new counter)

- `backend/live_feed.py` `_on_drop`: a drop opens the blind window only when the link was authed OR the drop is a
  kick, and only when no window is open (`not _link.get("drop_ts")`) — a second close before an auth never re-opens.
- `_on_auth`: the next auth closes it, gap = auth − first drop; an auth with no open window adds nothing.
- `_is_kick` per drop: a `KICK_STATUS` status in this connection, close code `KICK_CLOSE_CODE`, or the status text in
  the close message. ONE kick per drop — Massive sends the status row AND the kick close for the same kick (1,967 of
  each in the timeline), so counting rows would double it.
- Source: Mongo `live_feed.LIVE_FEED_EVENTS_COLL` (TTL `LIVE_FEED_EVENTS_TTL_DAYS` = 14 days), written by
  `_timeline` → `_persist_event`. Window per market day (`market_hours.gate.closed_reason`) =
  `GC.PASS_OPEN_ET`–`GC.PASS_CLOSE_ET` (the hub's `active()` window, 57,900 s), clipped at the run time for today.
- Script: `backend/scripts/live_feed_blind_fraction.py` (read-only: one `find`, no index build, no file, never prints
  a row's message). Tests: `backend/tests/test_live_feed_blind_fraction_2026_11_16.py` (33, incl. a pin that replays
  rows the real feed functions emit and gets the feed's own `blind_s` and `kicks`).

## The table (run 2026-11-16 15:41 ET, 10,141 rows)

| day | kicks | blind s | blind % | p50 gap |
|---|---|---|---|---|
| 2026-11-02 | — | — | no rows | — |
| 2026-11-03 | — | — | no rows | — |
| 2026-11-04 | — | — | no rows | — |
| 2026-11-05 | — | — | no rows | — |
| 2026-11-06 | — | — | no rows | — |
| 2026-11-09 | 363 | 11309.7 | 19.53 % | 30.2 s |
| 2026-11-10 | 292 | 8888.4 | 15.35 % | 30.2 s |
| 2026-11-11 | 163 | 5069.0 | 8.75 % | 30.2 s |
| 2026-11-12 | 243 | 7886.8 | 13.62 % | 30.2 s |
| 2026-11-13 | 355 | 11262.0 | 19.45 % | 30.2 s |
| 2026-11-16 | 38 | 6388.1 | 15.18 % | 31.2 s |

2026-11-16 is partial (04:00 → 15:41 ET, 42,092 s); no kick since 12:43 ET at the run. 11-02 → 11-06 predate the
timeline collection (first row 2026-11-09 02:29 ET) — "no rows", never 0 %, and excluded from the summary.

## Cross-check against the feed's own counters

ONE `GET /live/feed-status` at the run: `blind_s_today 5952.0`, `kicks_today 24`. The api container restarted at
08:46:09 ET (the feed's day counters live in memory and reset with it). The probe's rule over the rows since that
restart: **blind 5952.0 s, 24 kicks — exact match**. The table's today row (6388.1 s, 38 kicks) adds 04:00–08:46 ET
(436.1 s, 14 kicks) from before the restart.

## Limits

- ONE socket; "blind" is the time between the first drop and the next auth — prints in that time are lost to the live
  column until the next minute GET serves the stored bar.
- The window is the hub's 04:00–20:05 ET; a regular-hours-only fraction is not computed here.
- The in-memory ring (`EVENTS_MAX` 500 rows) is NOT the source; the Mongo timeline is (14 days). Days the persist was
  disabled (`_EVENTS_DISABLED`) or a day the socket stayed up from the day before with no row at all read "no rows".
- Equal timestamps keep the read order (`ts`, then `_id`).
- DESCRIPTIVE only: 5 full sessions + 1 partial; no CI, no placebo — it is a count of the feed's own events, not an
  edge or a signal.

## Re-run

```bash
docker exec -i -w /app -e PYTHONPATH=/app cheetah-market-app-api-1 python - --md < backend/scripts/live_feed_blind_fraction.py
```
