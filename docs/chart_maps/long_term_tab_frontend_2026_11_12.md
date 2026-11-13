# 📅 Long Term tab — frontend (2026-11-12)

Spec: long-term spec revision 2, §3.10 (payload) and §3.13 (frontend), work package WP-FE.

Ajay, 2026-11-12: "Save this entire list for me. In a New tab - Long Term - Remember this analays criteria I am asking you to for this tab and keep updating it from all the other tabs info.. Weekly and if something gets dropped let me know when to like is Sales drop or Stage 2 to Stage 3 or stage 4 changes." and "Yeah I wanna find out the ones that are actually great in fundamentals and growth and sales and no debt but not growing in price action yet.."

## Where it lives
- Tab key `long_term`, label `📅 Long Term`, slot IMMEDIATELY after `growth` (🚀 Explosive Growth) in `CM_TABS` (his call, spec §7 #12). `parseTab('longterm')` / `'long-term'` do NOT open it (`/longterm` is the ZONETRADER page).
- `isBoardTab('long_term') === false` (its own endpoint, no universe pass, no tile grid, no sort / tier / room controls). Not in `ENTERABLE_KIND`. `BURST_EXEMPT.long_term` = "his saved list keeps its saved order — the ⚡ burst is a daily-volume read".
- `ChartMaps.tsx` mounts `<LongTermBoard />` in the branch right after `growth`, before the SupportLevels fallback.
- Files: `frontend/src/components/LongTermBoard.tsx`, `frontend/src/lib/longTerm.ts` (route `LT_PATH = '/chart-maps/long-term'`, payload types, `textOr`, `FETCH_FAILED`, chart geometry), `frontend/src/styles/longTerm.css`.

## States (one GET on mount, no polling)
| served `state` | what renders |
|---|---|
| `owner_only` | the served `reason` only — nothing else (the server sends nothing else); the bounce-room hook is asked for `[]` |
| `error` | the served `reason` only |
| `seed_only` | every saved row from the baseline + the request-time 🧭 zone read; next-run line; no digest |
| `ready` | everything below |
| request failed / HTTP error / a body with no known state | `FETCH_FAILED` = "Could not load the Long Term list." (the one FE sentence) |

## Section order (`ready` / `seed_only`)
header (title, note, his words, next-run line, per-source as-of lines) → digest (title, lines, push-off line) → 🧭 at-zone strip (served `zones`) → 🌱 started moving → ⚠️ changed (rows) → the categories in seed order (label, source, criteria, caveat, also line, saved rows, the neutral `moved_text` line, the unsaved weekly top strip with ✨ on a served `new`) → forward (served line + counts line; an inline SVG with one polyline per served series only once `too_early` is false) → history → rules + caveats.

- ONE row per symbol: a row in `changed` is not drawn again under its category; a multi-chip name (e.g. NVDA 🌱 🧭, ANET 💎 📈 🧭) draws once with every chip pill. The FE also drops a duplicate the server never sends (`ltSavedRows` / `ltCategoryRows`).
- ⚠️ appears only as the `changed` section mark (and inside served texts). `moved_text` never carries the ⚠️ mark or the changed styling.
- Saved rows carry the four house chips (🚀 `GrowthChip`, 🩳 `ShortInterestChip`, 🧨 `ExplosiveChip`, 🎯 `EnterableChip`) from ONE `useBounceRoom(savedSymbolsShown)` call — the LukBoard pattern. Strip rows carry TickerLink + served text only, no house chips, and never join the room list.
- No ordering toggle, no 🎯 filter, no `ExplosiveFirstToggle`: his saved list keeps its saved order (rows as served, seed order).
- A null / blank served text prints "—".

## Phone (430 px)
- `.lt-card { min-width: 0; max-width: 100%; }`; the grid floor is `minmax(min(100%, 300px), 1fr)`.
- Pills, house chips, fields, lines, statuses and strip items: `white-space: normal; overflow-wrap: anywhere;` rows `flex-wrap: wrap`. The stylesheet never sets the no-wrap value; no element carries an inline width.

## What the FE never types
- No word or number about a stock: every visible string is a served field. FE-typed glyphs only: the 🌱 / ⚠️ section marks, ✨ on a served `new`, the verdict marks (✓ ✗ ? ℹ), "·" separators, the "…" loading glyph and `FETCH_FAILED`.
- No digit in any JSX text literal (pinned by a source test). The `TAB_META.long_term` blurb carries his digit-free quote, "UNMEASURED", the not-a-signal sentence and "owner only" — no digit, no Pankaj text (the blurb ships in the public bundle).

## Word rule scope (spec C8)
- The buy / sell vocabulary rule applies to what the board and `longTerm.ts` type or render themselves, after removing the one allowed sentence "None of these lists is a buy signal" (with or without its full stop — the seed caveat carries it without one). "bounce" never.
- It does NOT reach the four contract-mandated house chips: the 🎯 chip keeps its own wording and its own served title (spec §7 #25). The FE word test therefore renders the board with the four chips mocked to inert markers.
- The four unsourced attribution words are absent from every file here (the guard builds its regex from fragments).

## Tests
- `frontend/src/components/LongTermBoard.test.tsx` — section order, header / digest / 🧭 / 🌱 verbatim, multi-chip row once, changed row not repeated, null → "—", no NaN / Infinity / undefined / null, ⚠️ only with changed rows, moved line without ⚠️, ✨ only on `new`, strip rows without house chips, one `useBounceRoom` over exactly the saved rows, owner_only / error / seed_only / fetch-failure states, one GET and no timer, forward too_early (no chart) vs three polylines, banned words in rendered text (chips mocked) and in the TSX / TS / CSS / fixture sources, no digit in JSX text, NO_TOGGLE phrase, owner_only handled.
- `frontend/src/components/LongTermBoard.phone.test.tsx` — the 430 px stylesheet rules and DOM guards, with a pre-fix NEGATIVE sample.
- `frontend/src/lib/longTerm.test.ts` — route literal, `textOr`, `ltState`, saved-row de-dupe, marks, forward lines (too_early, gaps, empty series).
- `frontend/src/lib/chartMaps.longTerm.test.ts` — slot after growth, parse negatives, not a board, `BURST_EXEMPT`, not in `ENTERABLE_KIND`, blurb has no digit / no Pankaj / no extra buy word.
- Fixtures: `frontend/src/lib/__fixtures__/longTerm.payload.json` (hand-built to §3.10), `longTerm.owner_only.json`. The real-payload fixture comes from the main session's probe.

## 🔔 Zone block in the 🧭 section (added 2026-11-12, pkzone spec §3.7 / §3.9, WP-FE-TAB)
Ajay, 2026-11-12: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the long term tabs in general".

- **Keys read** (`zones.alert`, owner payload only, every value served by `backend/long_term_list/words.py`): `title`, `live` (→ `data-live`), `as_of_text`, `now[] {symbol, his_symbol, zone, text}`, `empty_text`, `reason`, `stale_text`, `push_text`, `log_title`, `log[] {symbol, his_symbol, zone, at_text, text, push_text}`, `log_empty_text`. Types `LtZoneNow` / `LtZoneLog` / `LtZoneAlert` in `longTerm.ts`; `LtZones.alert?: LtZoneAlert | null`.
- **Layout** (inside the existing `lt-zones` section; section order unchanged): `lt-zone-alert` → `<h3>` title → as-of line (`lt-zone-alert-asof`: which alerts pass, or "at the MM-DD close — no live read now" off-hours) → one row per name in a zone now (`lt-zone-now-<SYM>`: ticker link with his sheet symbol as the title + the served text) or the served `empty_text` (`lt-zone-now-empty`) → `reason` (`lt-zone-alert-reason`) and `stale_text` (`lt-zone-alert-stale`), each only when served → `push_text` (`lt-zone-alert-push`) → `<h4>` log title → one row per reach today (`lt-zone-log-<SYM>-<ZONE>`: `at_text · ticker text · push_text`, the push text being THAT row's served outcome: "rang your phone", "no phone has this alert on", "not sent — phone push is off", …) or `log_empty_text` (`lt-zone-log-empty`) → the served `rows_note`.
- **at_zone fallback rule:** `alert` present (an object) → the block replaces the closed-bar strip (its `as_of_text` heading AND the `at_zone` list; never both lists). `alert` absent, null or not an object → the at-zone strip renders exactly as before. `zones.as_of_text` / `at_zone` / `rows_note` stay in the payload for that fallback.
- **The stale line:** when some names have no cached close from the previous session they cannot ring that session; the server says so in `stale_text` (e.g. "3 of 40 names have no cached close from 11-11 — they cannot ring this session.") and the board prints it as its own line. Null → no node.
- The board types no word and no digit here; a null row text prints "—"; no polling (the block is as fresh as the page load — the as-of line says which pass). Phone 430 px: `.lt-alert` and `.lt-alert li` carry `min-width: 0; max-width: 100%; overflow-wrap: anywhere;` (items `white-space: normal`), never the no-wrap value.
- Fixture: `longTerm.payload.json` carries the live variant (two `now` rows, `stale_text` null, three log rows with the three outcomes above); `digest.pushed_text` = "This week's digest rang — one push to your phone when allowed." The close, stale and absent variants are built in `LongTermBoard.zones.test.tsx` from it.
- Tests: `frontend/src/components/LongTermBoard.zones.test.tsx` (live / close / stale / absent, the fallback both ways, null alert, empty lists, null nodes absent, order unchanged, no NaN / undefined / null, buy/sell/entry/exit regex, no FE-typed digit, fixture keys = §3.7); `LongTermBoard.phone.test.tsx` gains the `.lt-alert` rules with a pre-fix NEGATIVE; `LongTermBoard.test.tsx`'s at-zone strip test now deletes `alert` first (the predicted fallback pin).
- Contract `contracts.mjs` §3 (FE fixture keys ⊆ the backend golden) passes only once WP-BE-LT adds the `zones.alert` paths to `backend/tests/fixtures/long_term_list_payload_golden.json`.

## Not done here
- The ✨ entry, the contracts block, the RENDERER / NO_TOGGLE map entries and the real-payload fixture are the main session's.
- `frontend/src/lib/momentumBurst.test.ts:139` pins the non-board count at 19; with `long_term` it is 20 — that file is outside this package and needs the one-line pin update.
