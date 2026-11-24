# 🩳 High SI 9/21 EMA cross push — the frontend (2026-11-23)

Ajay 2026-11-23: "And also add alerts for these talks when they are crossing EMA, 9 EMA over 21 EMA."

Spec: high-SI spec §3.9, WP `fe-push` (ship shape S2 only). The backend kind is `gajjala_si_cross`
(`backend/chart_maps/gajjala/high_si_cross.py`, doc `high_si_cross_alerts_2026_11_23.md`). UNMEASURED: information,
not an entry.

## The one live date

`frontend/src/lib/alertKinds.ts` exports `GAJJALA_SI_CROSS_LIVE_SINCE`. It is the only place the frontend types the
live date. The /notifications row, the Essentials preset and the /alerts eyebrow all read this constant. If the
deploy day moves, the main session edits that one line. A test checks that the date appears once in `alertKinds.ts`
and never in `Notifications.tsx` or `Alerts.tsx`.

## The kind

`ALERT_KINDS.gajjala_si_cross = { emoji: '🩳', label: 'High SI EMA cross', group: 'trading' }`, placed after
`long_term`. Every surface that labels a push (the /alerts list, the bell, the history panel) shows
"🩳 High SI EMA cross" and never the raw id. The kind is not sticky: `public/sw.js` is not touched and
`swReceipt.test.ts` checks that it is not sticky.

## /notifications

- `NotificationPrefs.gajjala_si_cross?: boolean` (`hooks/useNotificationPrefs.ts`).
- The row comes right after 📅 Long Term: "High SI EMA cross" 🩳, trading group. Its detail starts with
  "ON FOR YOUR PHONE — LIVE SINCE {date}" and quotes his words verbatim. It then says what fires: a name on 🚩
  Gajjala's 🩳 High SI sub (short interest High or EXTREME, a low float on both float reads) whose 9 EMA crosses above
  its 21 EMA on a CLOSED 5-minute or 15-minute candle, once per name, chart and cross, listed on /alerts. It never
  fires on a closed day or on a candle that started in his first minutes after the open. The detail ends with
  "UNMEASURED — information, not an entry. Not a recommendation." The only digits it types are the EMA names, the
  frame names and the interpolated date.
- Essentials preset: now NINE kinds (`gajjala_si_cross: true`). Its detail gains "plus 🩳 High SI EMA crosses since
  {date} (your call: "…")". "All off" and "Household only" turn it off; "All on" and "Trading only" turn it on.

## /alerts

- `GGS_PASSES = [{ key: 'gajjala_si_cross', label: '🩳 High SI 9/21 EMA crosses', fallbackCadenceSec: 300 }]` has its
  OWN strip (`ggs-passes`). The strip sits right after the 🥇 Luk block and before the 🧪 strip, under the eyebrow
  `ggs-passes-head`: "🩳 High SI cross pass · rings your phone since {date} · not counted in the header". It is never
  part of `PASSES`, so the "all N passes" header does not change (HIS CALL #16).
- The headline is `pushed` → "pushes delivered" (the 🧠 headline). A send that no device took gets its own chip.
- Chip words (`ggSiCrossChipText`, keys `GAJJALA_SI_CROSS_KEYS`; a zero count draws no chip):

| Counter | Chip |
|---|---|
| `listed` | 🩳 {n} names listed |
| `cross` | {n} up crosses seen |
| `muted` | {n} held: the candle started in his first minutes after the open |
| `outside_hours` | {n} held: outside the push hours |
| `closed_day` | {n} held: market closed |
| `under_floor` | {n} held: under GG's session floor |
| `late` | {n} older crosses — not the latest candle, never sent late |
| `claimed_before` | {n} already rang for this cross |
| `off` | {n} held: the push is switched off |
| `si_unread` | short interest could not be read — nothing rang |
| `no_store` | {n} held: store error |
| `no_target` | {n} no device took it (toggle off, quiet hours or none registered) |
| `failed` | {n} send failed |

- 2026-11-23 refix: `under_floor` reads "session floor", not the spec's §3.9 "session-volume floor". The words
  "volume floor" in `Alerts.tsx` trip two existing NEGATIVE guards (`Alerts.trader_hold.test.tsx`,
  `Alerts.promo_chip.test.tsx`) and the 📌 algo888 contracts block, so the chip was reworded instead of narrowing them.
- `muted` is the candle-START rule [C4] and contains no minute count. `late` also counts a cross that was held on its
  own candle and is no longer the latest one on a later pass [C11], so it says "older crosses" and never "found late".
- All other counters stay in the hover "Also counted". That covers the not-listed reasons (`names`, `no_si`, `stale`,
  `no_tier`, `not_high`, `floats_disagree`, `float_unknown`, `float_over`, `si_float_over`) and `dry`.
- Before the first pass the row reads "no pass yet today".
- `KIND_CHIPS` gains `'gajjala_si_cross'` right after `'gajjala_potential'`. The chip's text is `kindLabel()`.

## Tests

`src/pages/Alerts.si_cross.test.tsx`, `src/pages/Notifications.si_cross.test.tsx`. Pins updated, each with a dated
comment: `Notifications.keepset.test.tsx` (eight → NINE), `swReceipt.test.ts` (not sticky), `Alerts.test.tsx`
(🎚️ is now `gajjala_potential + 2`), `Alerts.luk.test.tsx` (luk → ggs → gga).
