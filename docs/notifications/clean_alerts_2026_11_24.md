# 🔕 Clean Gajjala alerts — the frontend copy (24 Nov 2026)

> "ok remove EMA entry alerts and divergence alerts. Keep Gajjals clean entries when we find new potentials with all the rules getting satisfied.." · "and then A+ entries.." · "Honestly The potenail alerts are not bad.."

Ajay, 24 Nov 2026 ~22:15 ET. The three 🔀 9 / 21 EMA cross pushes — 👀 Gajjala's Watch (1-min), ➖ Horizontal Fade
and 🩳 High SI — are switched off at the source by their backend mode constants (backend side:
`docs/gajjala/clean_alerts_2026_11_24.md`). 🎯 A+ (`gajjala_setup`), 🧠 potentials (`gajjala_potential`) and 💧
volume dried (`gajjala_vol_dried`) keep ringing. Divergence never rang. This page records the frontend words only.

## The one date

`frontend/src/lib/alertKinds.ts` → `GAJJALA_CROSS_PUSH_OFF_SINCE` — the first session the crosses are silent. It is
the ONE typed switch-off date: `Notifications.tsx` and `Alerts.tsx` interpolate it and type no ISO date. It shares
its value with `GAJJALA_VOL_DRIED_LIVE_SINCE` by coincidence of the day; the 🩳 date-once pin (the count of
`GAJJALA_SI_CROSS_LIVE_SINCE`'s literal in `alertKinds.ts`) is unchanged.

## What changed on the surfaces

| surface | before | after |
| --- | --- | --- |
| /notifications 🩳 `gajjala_si_cross` row | leads "ON FOR YOUR PHONE — LIVE SINCE …" | leads "SWITCHED OFF {date} — your call: "…his full words…"", then "rings nothing", then the live history "It was ON FOR YOUR PHONE — LIVE SINCE …", "WHAT FIRED:", "The crosses stay drawn on the 🩳 cards." (the RETIRED 1-min precedent) |
| /notifications 🧠 `gajjala_potential` row | — | one sentence before WHAT NEVER FIRES: the 🔀 Watch / Fade cross pushes that rode this toggle are off since {date} ("ok remove EMA entry alerts and divergence alerts"); no "shadow" |
| Essentials preset detail | "plus 🩳 High SI EMA crosses since …" | "🩳 High SI EMA crosses rang from … and are switched off since … ("ok remove EMA entry alerts and divergence alerts")"; pref map unchanged (TEN on) |
| /alerts 🩳 eyebrow | "rings your phone since …" | "switched off since {date} — counted, never sent · not counted in the header" |
| 👀 Watch ℹ️ / 🩳 cards | backend sentences | no FE edit — the served off sentence renders as is |

His full words are typed ONCE in `Notifications.tsx` (`CLEAN_ALERTS_ASK`) and served once on the page (the 🩳 row);
the 🧠 row and Essentials quote only his first sentence, derived (`CLEAN_ALERTS_SHORT`).

## NOT changed

The pref map, `OWNER_KEEP_SET`, the 🎯 / 💧 / 🥇 Luk rows and the 🥇 Luk eyebrow, every board, sort and chip word
(`ggSiCrossChipText('off')` already read "held: the push is switched off"). The ✨ entry and `contracts.mjs` belong to
the main session.

## Tests

- NEW `frontend/src/pages/Notifications.clean_alerts.test.tsx` — the date, the 🩳 lead, the 🧠 sentence, the over-mute
  guard (🎯 / 💧 / 🥇 still lead ON), Essentials, source guards (no typed date, words typed once, the 💧 extraction
  still matches), the /alerts eyebrow with the Luk eyebrow unchanged, and the backend off sentence rendered through
  GajjalaWatchBoard (negative: never "rings once per ticker"; the old fixture sentence proves the check bites).
- Re-pinned (each marked `RE-PINNED 24 Nov 2026`): `Notifications.si_cross.test.tsx` (lead, stripAllowed, Essentials),
  `Notifications.vol_dried.test.tsx` (Essentials 🩳 clause), `Notifications.keepset.test.tsx` (🩳 leaves the ON-lead
  list for a SWITCHED-OFF check that still carries "ON FOR YOUR PHONE — LIVE SINCE"), `Alerts.si_cross.test.tsx`
  (eyebrow).

UNMEASURED — a mute, not a signal. Not a recommendation.
