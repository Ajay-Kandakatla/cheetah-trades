# 🧨 Weak lid on the room read — frontend (2026-11-26)

Spec `sitrack` §3.5 (A7), work package `fe-room`, critique fix [C6]. Backend half: `docs/supply_demand/room_weak_lids.md`.

## The ask

Ajay 2026-11-26: "can we make sure in the future these # are accurate ?" — WHLR's 🧨 chip read `room +6666279%`, measured
to the first band tested 2 times or more (`alert_gates.LID_MIN_TOUCHES`), with 13 untested bands under it.

## What changed (frontend)

- `frontend/src/lib/bounceRoom.ts`: `RoomRead` gains five optional served fields — `weak` (`RoomWeakLid`, the
  `alert_gates.first_weak_lid` dict), `skipped`, `target_age`, `weak_text`, `weak_title`.
- `explosiveChipText` ONLY: in the muted (not-scored) branch, when `room.weak_text` is a non-empty string, it appends
  ` · ${weak_text}` after the room part, and the served `weak_title` leads the hover. Anything else (absent, a number,
  NaN, `''`) appends nothing and the chip is today's byte for byte. The scored `separates` chip never prints it.
- No number is formatted on the frontend: the suffix and the sentence are the server's strings (`bounce_room.WEAK_TEXT`,
  `WEAK_TITLE`, one rounding `_room_pct_words`).

WHLR after: `🧨 room +6666279% · 1× band +154% first · floor held`.

## What did NOT change

- `roomLabel` — Catalysts (`Catalysts.tsx:617`) and the demand panel (`DemandReentryPanel.tsx:440`) print the same
  words as before.
- `compareExplosive`, `explosiveOrderKey`, `roomRank`, `roomOk`, `intoSupply`, `roomGroup` read none of the new keys;
  room-sorted boards still sort WHLR-class names first (§7 #8, unchanged on purpose).
- `ExplosiveChip.tsx`, `GajjalaWatchTags.tsx` (👀 tag) and `outerChips.ts` are not edited; they inherit the string.
  `outerChipsFor` compares the two chip strings, both carrying the served suffix, so a wrapper and its tile with the
  same read still print ONE 🧨; a different `weak_text` prints both (today's equality rule).

## Tests

- `frontend/src/lib/bounceRoom.weak_lid_2026_11_26.test.ts` — the WHLR string, hover lead, byte-for-byte negatives
  (five fixtures, bad `weak_text` / `weak_title`), separates branch, `roomLabel` both ways, mirror-fixture ordering and
  `roomRank` both ways, no b-word.
- `frontend/src/lib/outerChips.weak_lid_2026_11_26.test.ts` — one 🧨 on equal reads, both on different / one-sided.
- `frontend/src/components/GajjalaWatchTags.weak_lid_2026_11_26.test.tsx` — the 👀 tag prints the suffix once, nothing
  when absent, no 🧨 for an uncarded name.

Display only. Nothing rings, gates, orders or sizes on these fields. UNMEASURED.
