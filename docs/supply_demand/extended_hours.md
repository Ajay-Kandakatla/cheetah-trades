# Extended hours on Chart Maps — pre-market and after-hours prints (2026-09-08)

Ajay, 2026-09-08 08:10 ET: *"I am not seeing premarket pricing? Can you enable pre market
pricing and let me scan premarket hours please? To see the latest results in Chart maps
based on the pre market pricing … Also after hours."* Then, with ORCL: *"showing last
closed but I would like it to show real time premarket and Extended hours trading info as
well in all the chart maps."* The ticker page already read **$166.73 · Pre-Market** while
the Support tile's `now` line sat on the **$158.78** close.

## What was wrong

- `sepa/prices.with_today_bar` (the one overlay every chart and zone read uses) rejected the
  pre-market snapshot because the day aggregate is all zeros until 09:30 — the frame ended on
  yesterday's close. After 16:00 the day bar froze at the close; after the 16:30 fast-scan the
  frame already held today, so the after-hours print was never read either.
- `supply_demand/zone_edge` (the Breaking / near-demand minute pass) refused outside
  09:31–16:00 ET, so the 🚀 Breaking board and the 🔔 near-demand rows were yesterday's pass
  until the open.
- Every board tab's `now` line was the scan row's `last_price` — the previous close.

## The rule

**One print, three readers, one clock.** The print is Massive's `last_trade_price` +
`last_trade_ts_ms` (the field the demand boards' room gate already read); the clock is the
ET wall clock: pre-market 04:00–09:30, RTH 09:30–16:00, after-hours 16:00–20:00, else closed
(`prices.trade_session`; `zone_edge.session_state` adds the holiday calendar).

1. **Price overlay** (`prices.with_today_bar`, `extended_print`):
   - pre-market (day OHLC zero, print stamped today ≥ 04:00) → a flat synthetic bar
     o=h=l=c=print, volume 0, `info.source="premarket"`;
   - after-hours (print stamped today ≥ 16:00) → the day bar's close = print, high/low
     widened — appended when the frame ends yesterday, `adjusted` in the returned copy when
     the frame already holds today (`info.adjusted`, `info.appended` False);
   - `info.session` names the print's session; prints from another day, before 04:00,
     after 20:00 or on a weekend change nothing. The cache is never written.
   - Readers: `chart_maps.support._overlay_today` (adjusted counts as live; the closed
     frame the caller keeps is the original), `price_zones.for_symbol` (adjusted prices the
     verdict), `chart_maps.board.bars_for` (tiles draw the pre-market bar).
2. **Minute pass** (`zone_edge`): `SESSION_OPEN/CLOSE` 04:00–20:00 ET on trading days;
   `PUSH_OPEN/CLOSE` 09:31–16:00 (`push_window`). `check_once` forces `push=False`
   outside the push window and records `push_window` + `session`; no state row is written
   for a suppressed push, so the first RTH pass can still fire it. Crontab
   `* 4-19 * * 1-5`; the zone-store warm moved from 9:20 to **04:05 ET** so the first
   pre-market pass has bands to read (closed bars only — same data either hour). Paper lane
   unaffected (it gates on the broker clock).
3. **Boards** (`chart_maps.board.attach_live_now`, end of `board()` for EVERY tab): one
   `bulk_live_prices` call for the shown tiles; each tile's `now`-toned line moves to the
   live print and is tagged `now · pre` / `now · AH` when the print is stamped today outside
   RTH (`now_label`); the Breaking tile's line is `LAST · PRE` / `LAST · AH` (`last_label`).
   A tile with no now line (demand / VCP boards) gets one only for an extended-hours print
   (the flat pre-market bar is invisible; in RTH the candle is the marker). The Support tab
   route applies the same overlay to its one tile.
   Tiles record `live_price` / `live_session`; the board records `tape_session`
   (`premarket|rth|afterhours|closed` — NOT `session`, which the 0DTE tab already uses for
   its chain-liveness block).
4. **Page**: one `cm-note` under any board read outside RTH (`sessionNoteText`) and the
   Breaking pass line names the tape (`breakingPassText`); both state the push window.

**Phone pushes (revised the same afternoon).** The first cut kept pushes RTH-only (thin tape).
Ajay, 08:50 ET: *"Make phone push also pre and post market"* — `PUSH_OPEN/CLOSE` are now
04:00–20:00 too, the same gates apply (2 touches, cap ≥ $1B, ≥ 5% room, once per band/day),
and an extended-hours print is tagged `pre-mkt` / `after-hrs` at the end of the push body
(`tape_tag`) so a 5am title is never read as a session print. `push_window` stays a separate
gate so the two windows can be split again by editing two constants. Quiet hours were checked:
off on both of his devices, so early pushes deliver. The 5-minute `zone_bounce_alert` /
`demand_alerts` crons keep their RTH windows — a bounce needs a session low; near-demand
arrivals already push from the minute pass.

## Where it shows

- Chart Maps, every tab: `now · pre` / `now · AH` on the tiles, the note under the tab bar.
- 🚀 Breaking: the pass line reads "pre-market pass as of 08:20 ET · thin tape, no phone
  pushes outside regular hours"; tiles say `LAST · PRE`.
- ℹ️ Rules ▸ Zone alerts: "pass every minute 04:00–20:00 ET incl. pre-market and
  after-hours; phone pushes 04:00–20:00 ET".

## Tests

`backend/tests/test_prices_today_bar.py` (pre-market synthetic bar; after-hours extends the
appended bar and adjusts a frame that already holds today; NEGATIVE stale / off-session /
weekend / unpriced / unstamped prints; the session clock; the support + zones readers),
`test_zone_edge.py` (pass window, push window, session tag, a pre-market pass lists and
tracks but never pushes, constants, crontab hours), `test_chart_maps.py`
(`attach_live_now` moves/tags per tile, runs at the end of `board()`; `last_label`),
`test_alert_status.py` (16:01 is a live pass, 20:01 is not); frontend
`chartMaps.test.ts` (`breakingPassText` tape wording, `sessionNoteText`), `ChartMaps.test.tsx`
(note on a non-Breaking tab; NEGATIVE none in RTH), contract "Chart Maps names the
extended-hours tape under every board (2026-09-08)".
