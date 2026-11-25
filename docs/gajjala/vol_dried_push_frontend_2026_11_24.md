# 💧 Volume dried push — frontend (2026-11-24)

Ajay 2026-11-24: "Can you track something for me how many times have the stocks bumped right after volume dried up.. I noticed that the best entries so far have been after volume dried up.. after all the other rules. Can you send me notification of volume dried please.."

Spec: voldry §3.9, WP `fe`. Backend: `docs/gajjala/vol_dried_push_2026_11_24.md`.

## What changed

| File | Change |
|---|---|
| `frontend/src/lib/alertKinds.ts` | `gajjala_vol_dried` → 💧 "Volume dried", trading group, right after 🩳. `GAJJALA_VOL_DRIED_LIVE_SINCE = '2026-11-25'`: the ONE typed live date for this kind. |
| `frontend/src/hooks/useNotificationPrefs.ts` | `gajjala_vol_dried?: boolean`. The save spreads the stored prefs, so the key survives. |
| `frontend/src/pages/Notifications.tsx` | A row right after 🩳. It quotes his words once (`VOL_DRIED_ASK`), names "Armed, volume dried", and interpolates the date from the constant. Essentials preset: `gajjala_vol_dried: true` plus one dated clause. All on / Trading only → on. All off / Household only → off. |
| `frontend/src/lib/gajjala.ts` | `push_vol_dried?: GgPushBreak \| null` on the board type. |
| `frontend/src/components/GajjalaBoard.tsx` | Segment C (`gg-head-body-c`, inside the ⓘ header fold) prints the served `push_vol_dried.text` verbatim right after ⚡ (`data-testid="gg-push-vol-dried"`). Only a non-blank string prints. |

## Rules kept

- **Landing.** Only 🔄 · 🧾 · ⓘ are visible. The 💧 line sits inside the closed ⓘ fold (STANDING declutter rule).
- **No numbers typed.** The FE types no threshold. The count line is served; the FE prints it unchanged.
- **One date.** The date is typed only in `alertKinds.ts`. The 💧 comments write "24 Nov 2026" because the 🩳 date-once pin (`Alerts.si_cross.test.tsx`) counts the ISO literal `2026-11-24` in that file.
- **Not sticky.** `public/sw.js` is untouched (sticky = A+ only).
- **Words.** "Reversal", never the b-word.

## Tests

- NEW `frontend/src/components/GajjalaBoard.vol_dried.test.tsx`: the line prints verbatim inside the fold right after ⚡, hidden while closed and visible after the ⓘ tap. A count line prints unchanged. NEGATIVES: the landing stays 🔄 · 🧾 · ⓘ; the node is never outside `.gg-fold-body`; no node for absent / undefined / null / '' / whitespace / a number / a text-less block; no node on a 🧪 or 1-minute board without the key; no b-word.
- NEW `frontend/src/pages/Notifications.vol_dried.test.tsx`: `kindLabel` → "💧 Volume dried"; the row text (his words, "Armed, volume dried", UNMEASURED); the presets. NEGATIVES: no threshold digit (the check bites), the date never typed in `Notifications.tsx`, no b-word, the raw id never printed.
- Re-pinned nine → TEN: `Notifications.keepset.test.tsx`, `Notifications.si_cross.test.tsx`. `swReceipt.test.ts`: 💧 is in the not-sticky list. `GajjalaBoard.fold_2026_11_24.test.tsx`: `gg-push-vol-dried` is in both in-fold id lists.

## Not done here (main session)

- ✨ entry in `newFeatures.ts`; the `contracts.mjs` block and keep-set arrays.
- HIS CALL #1 (the twin buzz with 🧠) goes to him before the deploy. If he picks "off", the row's "ON FOR YOUR PHONE — LIVE SINCE" lead is dropped in the same commit.
