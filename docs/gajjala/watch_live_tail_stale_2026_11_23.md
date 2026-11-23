# 👀 Watch — a failed minute read keeps the live candle (2026-11-23, spec ggconn WP-1)

**This does NOT fix the delay he reported.** The live tail is fed by the ONE Massive socket only, and it STILL stops
whenever the socket is blind — 8,567 s of 29,760 s of 11-23's window by 12:16 ET (**28.8 %**), a second client kicking
the socket about every 110 s (HIS CALL #10–#12, `live_his_calls_2026_11_09.md`). What changed is narrower: a failed
minute READ no longer cuts the live candle of a Watch row. It is never "0 s dark".

Ajay 2026-11-23 ~12:00 ET: "Can you clean up some connection I am seeing delays price update for AKAN on the watch
chart.."

## What changed

ONE rule stays, `ggwRowLive(row)` (`frontend/src/lib/gajjalaWatch.ts`):

```
row.state === 'ok' && row.from_session == null && (!row.stale || row.stale_keeps_live === true)
```

- `GgwRow` gains ONE optional key, `stale_keeps_live?: boolean`. `parseRow` (the Watch payload's row parser) sets it
  `true` on every row, unconditionally. Nothing else sets it.
- On the Watch, `stale` means the last minute read failed or ran out of budget (`build.status_of` → `failed` /
  `over_budget`) while the stored bars are still this session's — so the live tail survives it.
- The 🚩 / 🧪 card ⤢ view builds its rows with `lib/gajjalaCardView.ggcRow` (and `GGC_NO_FRAMES`), which never carry
  the flag: there `stale` is the house verdict on an old source doc, and that row stays dark exactly as before.
- A prior-session row (`from_session` set) and every not-ok row (`pending / failed / no_prints / no_bars /
  over_budget`) carry no live bars, flag or not. A junk flag value (anything but `true`) reads as no flag.
- The per-frame rule (`ggwFrameMetas` drops a frame SERVED with `stale: true`) is unchanged.
- `lib/ggwLive.ts`: comments only. `GajjalaWatchBoard.tsx`, `GajjalaWatchTile.tsx`, `GgCardView.tsx`,
  `useGgCardWatch.ts`, `gajjalaCardView.ts` and every served word are untouched: the ⚠️ chip and the served sentence
  ("⚠️ the HH:MM read failed — showing the HH:MM bars") print as before while the live candle moves.

Mechanism: before, a failed minute read darkened the tail until a later minute loaded AND the next 60 s board GET
landed. Now a failed minute read no longer cuts it. A stale row with NO batch (the feed blind) still does not move —
the board test pins that.

## Effect — UNMEASURED

No count of recovered tile-seconds is claimed. The base rate is one session (11-23, spec §1.5): **~3 Watch minutes with
a failed read of ~530** (~0.6 %: 09:47 CRWV; 11:38 WETO / CRWV / AXTI / KITT; the 11:39 breaker blackout), against a
socket blind 28.8 % of the same window. The size of what this reaches is that ~0.6 %, and only while the socket is
live.

## Tests

- `frontend/src/lib/ggwLive.stale_tail_2026_11_23.test.ts` (new): the rule (hand-built flagged row → live; parsed stale
  NVDA → live; flag on every parsed row); NEGATIVES — no flag → dark, flag + `from_session` → dark, every not-ok state
  → dark, junk flag (`'yes'`, `1`, `'true'`, `{}`, `null`) → dark; `ggcRow` / `GGC_NO_FRAMES` never carry the key (value
  and source); the per-frame `stale` rule unchanged; the reducer opens / adds / prunes live bars on the stale NVDA.
- `frontend/src/components/GajjalaWatchBoard.live.test.tsx` (real board, real hook, real PatternChart): a stale today
  row + a batch → one more candle on each frame, `now` moves, ⚠️ and the served sentence stay; a GET that turns a live
  row stale → the tail stays and the next batch still moves it; NEGATIVE: the same row with `from_session` → nothing
  moves; NEGATIVE: a stale row and no batch → nothing moves, across the next GET too.
- Re-pinned (they asserted the old rule): `gajjalaWatch.test.ts` (NVDA), `ggwLive.test.ts` (metas, the NVDA batch),
  `ggwLive.cardview.test.ts` (the flag stripped — a card row served stale carries no metas),
  `GajjalaWatchBoard.live.test.tsx` (header + the two stale tests). The board source guard passes unchanged.

## HIS CALL

- This answers open HIS CALL #10 of the live build (`watch_live_2026_11_16.md`): built on his 11-23 words, his confirm
  owed. One line to revert (`stale_keeps_live: true` in `parseRow`).
- The 🚩 / 🧪 card ⤢ view stays dark on a stale card. Same treatment there = his call.
- The stale sentence is unchanged while the candle moves. New words (e.g. "live price still streaming") = his call.
- The socket kick itself (the delay he saw) = HIS CALL #10–#12, not built.
