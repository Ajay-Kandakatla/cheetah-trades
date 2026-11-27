# 👀 Gajjala's Watch LIVE — a per-second candle and a live volume column on every Watch chart (2026-11-16)

> **2026-11-27 — built (frontend, branch `feat/watch-5m-grid-2026-11-27`); data path unchanged.** Every served frame keeps folding its live candle from page open, shown or not, so a frame ticked back on in the new frames menu shows the candle it was building all along; no per-frame subscription exists. With it, the 50-bar average volume line is off on Watch tiles and in ⤢ (opt-in in the menu). See [watch_5m_grid_2026_11_27.md](watch_5m_grid_2026_11_27.md).

> **2026-11-25 — changed.** The live render gate is now "shown and in or near the window" (one IntersectionObserver), not "on the page"; the data path is unchanged. See [watch_columns_scroll_2026_11_25.md](watch_columns_scroll_2026_11_25.md).

Ajay 2026-11-16, on the 👀 Gajjala's Watch tab, four messages in a row:
"Can you make the watch list charts live please" · "Realtime updates.. Like the 1 min chart I need it to be live live.. per sec change" · "Also on the Watch list I need live volume to be shown at the bottom" · "Of each chart".

**Verdict: display only. The last candle of every Watch chart (1-, 3- and 5-min) moves with the prints about once a
second, its volume column grows at the bottom, and the dashed `now` line follows. Every rule, cross, 🔔 and push stays
on the closed stored bars. UNMEASURED.**

## What moves, what does not

Moves (owner's tabs only, 04:00–20:05 ET, rows that are ok, today's and not ⚠️ stale):
- the **forming candle** of each frame — it opens at the first print in a new bucket and its high / low / close follow
  every batch;
- its **volume column** at the bottom of the chart — the summed sizes of the prints the socket saw in that bucket, in
  the house colour rule (`volumePane.volumeColor`: green when close ≥ open, red otherwise);
- the **dashed `now` line** and its gutter label (`boldNowLines` reads the last bar, so the forming bar's close drives it).

Does not move:
- every **9-over-21 cross read, 🔀 blinker, held chip, 🔔 rang chip and push** — all read the stored closed bars
  (`cross_alerts.py` is byte-untouched; its sha256 is pinned);
- a served **50-bar volume average** — it gets a null tail and stops at the last closed bar (a forming bar is never in a
  served average). With no served average, the pane's own fallback average includes the forming bar at its tail (HIS
  CALL #8).

The next minute GET wins by construction: a live bar whose bucket the server now stores is dropped, so the stored bar
(its real volume) replaces it.

## How (one socket, one hub, one event type — no second stack)

1. The board, once it has an ok board in window (`refresh_sec > 0`), POSTs its list to the owner-gated
   `POST /chart-maps/gajjala-watch/live {symbols}` (`frontend/src/hooks/useGgwLive.ts`) on arm and every
   `CARD_LIVE_MS` (30 s) while the page is visible; the hub's interest lives `INTEREST_TTL_SEC` (60 s), so a hidden tab
   lapses in ≤ 60 s. The POST is keyed on the list (`symbols.join(',')`): a minute GET serving the same list re-arms
   nothing; a changed list POSTs at once. A non-owner gets 404 (`require_primary_admin`) and never reaches an ok board.
2. The route → `live_hub.register_interest("gajjala_watch", symbols)`; the watch rides the hub as an extra tab
   (`live_hub.EXTRA_TABS`), never a fourth Variant (a Variant drives stores, passes, ledgers and pushes).
3. The ONE Massive socket's trade prints for those names pass the hub's ONE filter (`PRINT_KINDS = ("regular",)`) and
   reach `live_events.on_print`; at most once a second each variant's batch is flushed as a `gajjala.update` quotes
   event whose quote carries `size` = the summed sizes of the filtered prints since that variant's last batch.
4. The watch batch is published on the bus with an owner-only `audience`; the `/events` loop drops a tagged envelope
   for any connection whose resolved email is not in it, and the `audience` key never reaches the wire.
5. `useGgwLive` holds ONE bus subscription; each raw watch batch is folded by `lib/ggwLive.ggwApplyBatch` into forming
   candles per (symbol, frame) on the server's own grid: the served axis carries `start_epoch` (the session's 04:00 ET)
   and `frame_min`, so the FE buckets a print as `floor((as_of − start_epoch) / (frame_min·60))` with no clock words of
   its own (closed = left: a print at a boundary opens the new bucket). A replayed or older batch is skipped whole, so
   volume is never added twice.
6. `lib/ggwLive.ggwLiveFrame` splices the forming bars after the stored ones at render time (bars + `axis.x`, curves and
   a served `vol_avg` get a null tail); every other key is the same reference, so the cross path never sees a live bar.
   PatternChart is `memo`: an unchanged frame is the same object and does not redraw; an off-page tile gets no live bars.
7. The hub is idle outside 04:00–20:05 ET (`GC.PASS_OPEN_ET`–`GC.PASS_CLOSE_ET`); the board POSTs only in window.

The route's served `stream` block {on, word, state} is the feed's own word (`live_feed.state_word()`); the head prints it
ONLY when the feed is degraded (`streamFeedWord`) — one `.ggw-line`, wrapping at phone width. No "● live" marker when
healthy: the moving candle is the stamp (HIS CALL #7).

## Who sees it (C1)

Only the owner's signed-in tabs. `/events` is behind the auth middleware (it is not a public path), so its audience was
the signed-in household (Doug, Chiranjeevi); the watch batches carry `audience = {owner}` (`gajjala_watch/constants.
live_audience()` = the same identity the board's owner gate uses) and the SSE loop filters per connection. The 🚩
variants' batches are untagged and flow exactly as before. Broadcasting the watch batches to the household = HIS CALL #2.

## When a row goes dark (C2)

ONE rule, `ggwRowLive(row)` = `state === 'ok' && from_session == null && !stale`, used by the reducer's metas AND the
tile. A ⚠️ stale row (its server read failed; its frames are the last GOOD ones) and a prior-session row show their
stored bars only: a batch for them changes nothing, and a row that turns stale on a GET loses the live tail it already
had at the next render. Drawing live candles on a stale row anyway = HIS CALL #10.

> **2026-11-23 — changed (spec ggconn WP-1, [watch_live_tail_stale_2026_11_23.md](watch_live_tail_stale_2026_11_23.md)).**
> The text above is kept as the 11-16 record. Now: `ggwRowLive(row)` = `state === 'ok' && from_session == null &&
> (!stale || stale_keeps_live === true)`. `stale_keeps_live` is set ONLY by `parseRow` (a row of the Watch payload), so
> a ⚠️ stale Watch row of TODAY keeps its live candle through a failed minute read; a prior-session row, a not-ok row
> and the 🚩 / 🧪 card view's stale row (`ggcRow` — an old source doc) still carry none. The live tail still stops
> whenever the socket is blind (28.8 % of 11-23's window by 12:16 ET) — it is fed by the socket only.

## Honest limits

- **The live column counts only the prints the ONE socket saw.** A second Massive client on the key kicks it; until it
  re-authenticates it is blind. How blind is a measured number in
  [watch_live_feed_blind_2026_11_16.md](watch_live_feed_blind_2026_11_16.md) — read it there; it is not re-typed here
  (HIS CALL #11).
- Odd lots and Form T follow `live_hub.PRINT_KINDS` (in); **auction crosses are NOT counted** (the open and close
  crosses are real volume) — the next GET corrects the bar (HIS CALL #3).
- A 1-second batch straddling a bucket boundary lands wholly in the newer bucket (≤ 1 s of prints; HIS CALL #4).
- Two prints with the same stamp in two different batches: the second is skipped (the as-of rule that stops double
  counting; never widened).
- The first after-hours candle waits for the server to extend the axis past 16:00 (≈ 90 s; HIS CALL #5).
- Prints inside the last STORED bar's bucket are ignored — the server has closed it (HIS CALL #6). So the live candle of
  a session starts after its first closed bar is stored, and a forming column can read BELOW the bar the server will
  store until the next GET corrects it.
- The renewal cadence is the existing `CARD_LIVE_MS` (30 s) against the hub's 60 s TTL; no new number (HIS CALL #9).

## The volume-pane finding

The ask said "I need live volume to be shown at the bottom". One read-only GET at 15:00 ET 2026-11-16 (9 names × 3
frames): **every one of the 27 frames already carried the volume pane** — every bar `v > 0`, the served 50-bar average on
27 / 27. Nothing was hiding it (`chartOnly` / `emaStyle` do not touch the pane). What was missing was the FORMING bar's
column; this build adds it. The board test pins one `.pc-vol-pane` on every Watch chart, and (NEGATIVE) none on a frame
whose bars all carry `v = 0`.

## The EMA report (the 9 / 21 tip — ON since his 11-16 word)

- The backend EMA is `orderflow.signals.ema` = pandas `ewm(span, adjust=False).mean()`, rounded to 6 dp for the chart.
- Probed on the host (arm64, Python 3.9.6) and in the api container (aarch64, Python 3.11.16), both pandas 2.3.3: the
  plain recursion `((1−α)·prev + α·close) / ((1−α)+α)` with α = 1/(1+(span−1)/2) and pandas' equal-value guard matches
  the raw double in only ~80% of steps (1 ulp off in the rest); `fma(1−α, prev, α·close)` matches 100% (0 of 59,800 host
  steps, 0 of 35,880 container steps) — pandas' compiled kernel fuses the multiply-add on this CPU, which JS cannot.
  After the backend's own 6-dp rounding, plain vs pandas agreed in 100% of 95,680 steps.
- Built and pinned: the served UNROUNDED tail (`ema_tail`), the FE step (`lib/ggwEma`), and a two-sided golden fixture
  (`backend/tests/fixtures/gajjala/ema_step_golden_2026_11_16.json`). The display is one constant, `GGW_LIVE_EMA_TIP`,
  ON — HIS CALL #1 answered by his "live live.. per sec change" (2026-11-16): the 9 / 21 tips follow the forming close
  between GETs; the cross reads still use only the closed stored bars.

## Tests

- `frontend/src/hooks/useGgwLive.test.tsx` — one POST on arm with {symbols}, renewal at `CARD_LIVE_MS`; the same list on
  a re-render → no extra POST and no re-subscription (C5); a changed list → one POST at once; NEGATIVES: hidden → no POST
  at the tick, visible (overdue) → POST at once; disabled / no symbols / no EventSource → nothing; unmount → nothing;
  only the watch tab's quotes batches reach `onBatch` (raw, `size` kept); the served word only when degraded.
- `frontend/src/components/GajjalaWatchBoard.live.test.tsx` — the REAL board, hook, reducer and PatternChart: a new
  candle + `rect.pc-vol` with `data-vol="500"` in the house colour + the `now` label; NEGATIVE a print inside the served
  3-/5-min buckets adds nothing there; same / older batch, another variant, unknown symbol → unchanged; junk size → no
  column; stale row → nothing moves, ⚠️ stays; a GET that turns a row stale → its tail disappears; the next GET wins
  (`data-vol="123"`, one bar in the slot); owner_only and out of window → no POST, no subscription; no EventSource → the
  GETs exactly as before; 9 / 21 points, blinkers, held, rang unchanged; a served average keeps its line at the last
  closed bar; `.pc-vol-pane` on every svg and none on an all-`v = 0` frame; the stretch view moves; an off-page tile never
  redraws; source guards (imports `useGgwLive` + `ggwRowLive`, never `useCardLive` / `patchTiles` / `mergeQuotesEvt`;
  the two contract sentences; no 📡 / feed word typed).
- Backend and lib pins: see the watch-live spec's WP-A1 / WP-A2 / WP-B / WP-C / WP-E tests.

## HIS CALLs (never decided here)

1. **The 9 / 21 EMA tip on the forming bar** — ON (`GGW_LIVE_EMA_TIP = true`, answered by his "live live" 11-16); equal
   to the backend at its 6-dp precision in 100% of probe steps, not bit-identical in the raw double (FMA). Turning it off
   again = one constant.
2. **Audience** — owner's tabs only (default). Broadcasting his list's prices to the household's tabs instead = his call.
3. **What volume counts** — `PRINT_KINDS = ("regular",)`: odd lots + Form T in; busted / summary / non-flow / auction
   crosses out. Confirm, or widen the hub filter for the watch (a gate change for every consumer).
4. **Boundary straddle** — a 1-s batch across a boundary lands in the newer bucket; accept, or split sizes per bucket
   on the server.
5. **After the regular close** — the first after-hours candle waits ≈ 90 s for the axis; accept, or always serve the
   extended axis.
6. **Prints inside the last stored bar's bucket are ignored.** Confirm.
7. **Feed word only when degraded**, no healthy marker. Confirm, or ask for a served as-of stamp per tile.
8. **The pane's average with a forming bar** — served average → null tail; no served average → the fallback includes
   the forming bar. Confirm the drawing.
9. **Renewal cadence** = `CARD_LIVE_MS` 30 s against the 60 s TTL. Confirm.
10. **A ⚠️ stale row goes dark** (and its drawn tail disappears). Keep drawing live candles on a stale row anyway = his
    call.
    *2026-11-23: answered on his 11-23 words ("I am seeing delays price update for AKAN on the watch chart") — a stale
    Watch row of today now KEEPS its live candle (spec ggconn WP-1,
    [watch_live_tail_stale_2026_11_23.md](watch_live_tail_stale_2026_11_23.md)). His confirm is still owed; reverting is
    the one `stale_keeps_live: true` line in `parseRow`. The 🚩 / 🧪 card ⤢ view is unchanged (dark on a stale card).*
11. **The live column is structurally low** (one socket that a second client kicks; crosses out) — the measured blind
    fraction is in the linked doc. Show it as asked (default, no marker), tint / label a forming column that spans a
    blind window, or stop here.

## UNMEASURED

This is a display. No signal, entry, gate or push reads the live bars, and no study has measured whether watching the
forming candle helps a decision. Prior on any new signal from it: null.
