# 🎬 Replays tab — frontend (2026-11-17)

Ajay 2026-11-17: **"Can you store the videos in to the app please"**. 2026-11-16: "I only wanna see ones from 4 AM to 8 pm please" (the server applies it).

Backend side: `docs/chart_maps/replays_tab_2026_11_17.md`. Storage / mounts: `docs/chart_maps/replays_storage_2026_11_17.md`. Spec: replays spec §3.3, §4 WP-FE.

## The board

- Tab `replays` in `frontend/src/lib/chartMaps.ts`: `CmTab`, `CM_TABS` right after `long_term` (before `ipo`), `isBoardTab` → false (own endpoint), `TAB_META.replays` (label `🎬 Replays`, his two asks verbatim, owner only, UNMEASURED). **No `ENTERABLE_KIND` entry** — that map is a cast; `long_term` / `gajjala_watch` carry none (spec C4).
- `BURST_EXEMPT.replays = 'videos in the served group order — never ranked'` (`frontend/src/lib/momentumBurst.ts`).
- `frontend/src/pages/ChartMaps.tsx`: hidden beside `gajjala_watch` for a loaded non-owner (`canWatch` gate — offered while `/auth/me` loads); `?tab=replays` for a non-owner lands on the first tab. `<ReplaysBoard />` mounts right after the `long_term` branch, before the SupportLevels fallback. The page keeps its capped width (no `cm-page--wide`).
- `frontend/src/components/ReplaysBoard.tsx`: ONE fetch on mount and on every `?date=` change (`credentials: 'include'`, `cache: 'no-store'`). The session `<select aria-label="session">` lists the served `dates`; a change calls `setParams((prev) => rpDateParams(prev, v), { replace: true })` — only `date` moves, every other param survives (spec C7). A served `date` not in `dates` (a well-formed day with no folder) is prepended as a **disabled** option so the select always reads the served date (spec C8).
- States: `no_folder` / `empty` → served title + served `text` (+ the select when dates are served). `ready` → served `window_note` → one `<section>` per served group (served label, served order) on the house `.cm-grid` → the 🎾 tracker (served title, served note always, then the table or the served `text`).
- **2026-11-17 refix — the 🎾 tracker on `empty` too.** The server serves `rs` with `empty` as well as `ready`, so a session that has 🎾 ledger rows but no 04:00–20:00 video used to show no tracker. `empty` now prints the served `text` and then the same 🎾 block (served title, note, table or served `text`) whenever `rs` is served. `empty` still shows no window note, groups or videos. `no_folder` never shows a tracker. This goes past §3.3 as first written ("served `text` only"), which the review flagged as the owner's call. Tests: `ReplaysBoard.test.tsx` → `🎬 empty and no_folder print the served text (empty: + the served 🎾 tracker)` (the old "no tracker" pin is marked WIDENED).
- Card: `TickerLink` symbol; chips `setup_text`, `page_text`, `grade`, `speed_text`, `length_text`; `ring_day` chip only when `carried === true`; `<video controls preload="metadata" playsInline>` — no autoplay, muted, poster, loop or download; `why[]` lines; `story`; the 🎾 `potential` fields as ONE line joined by ` · `. A served `src` off `/chart-maps/replays/video/` renders no `<video>` (`rpVideoSrc` guard).

## Served vs typed

| Printed | Source |
|---|---|
| title, window_note, text, group labels | served |
| symbol, setup_text, page_text, grade, speed_text, length_text, ring_day, why[], story, potential.* | served |
| rs.title, rs.note, rs.columns[].label, rs.rows[].cells, rs.text | served |
| `Could not load the replays.` (FETCH_FAILED) | FE — the request failed, nothing was served |
| `session` (select aria-label), ` · ` | FE — structural |

A source guard (`ReplaysBoard.test.tsx`) pins that the board file types none of `A+`, `winner`, `loser`, `biggest mover`, `Reversal`, `04:00`, `20:00`, `ajaykandakatla`, and that it carries the two written exemptions the contracts read: "No house chips on this tab" and "served group order orders this board".

## 430 px rules (`frontend/src/styles/replays.css`)

`.rp-board` / `.rp-card` `min-width: 0; max-width: 100%` · `.rp-video` `width: 100%; max-width: 100%; aspect-ratio: 16 / 9` · `.rp-chips` flex-wrap · `.rp-chip, .rp-why, .rp-story, .rp-plan, .rp-line` `white-space: normal; overflow-wrap: anywhere; min-width: 0` · `.rp-rs-wrap` `overflow-x: auto; max-width: 100%` (the 17 tracker columns scroll inside the wrapper, never the page) · `@media (max-width: 640px) .rp-chip` font step-down. Pinned by `ReplaysBoard.phone.test.tsx` with a pre-fix NEGATIVE sheet.

## Pins moved (each carries a `WIDENED 2026-11-17` note)

1. `frontend/src/lib/chartMaps.test.ts` — the full `CM_TABS` array: `'replays'` after `'long_term'`.
2. `frontend/src/lib/chartMaps.test.ts` — the full non-board list: `'replays'` after `'long_term'` (every own-endpoint tab is non-board).
3. `frontend/src/lib/chartMaps.test.ts` — the `CM_TABS_6D3AD93` insertion filter: `&& t !== 'replays'`.
4. `frontend/src/lib/momentumBurst.test.ts` — non-board count 21 → 22 (`BURST_EXEMPT` keys == non-board tabs).
5. `frontend/src/pages/ChartMaps.watch.test.tsx` — the co-owner strip excludes `replays` too (the co-owner never sees either owner-only tab).

**Not moved — a sixth pin the spec did not map:** `frontend/src/lib/chartMaps.test.ts:1849` `expect(CM_TABS).toHaveLength(44)` now reads 45. Left failing for the main session (the executor may move only the spec's five).

## Contracts (main session)

`node scripts/contracts.mjs` fails three contracts until the main session adds `replays: 'src/components/ReplaysBoard.tsx'` to the three RENDERER maps (🚀 growth chip, 🧨 explosive chip, 🩳 short interest) plus the NO_CHIP / NO_TOGGLE exemptions (spec §4 main-session block).

## Tests

`frontend/src/lib/replays.test.ts` · `frontend/src/components/ReplaysBoard.test.tsx` · `frontend/src/components/ReplaysBoard.phone.test.tsx` · `frontend/src/pages/ChartMaps.replays.test.tsx`; fixture `frontend/src/components/__fixtures__/replays_2026_11_17.json` (a hand fixture in the §3.1 shape: `ready` with all five groups, a carried card and a 🎾 card with `potential`; `empty` whose `date` is not in `dates`; `no_folder`).

## Preview recipe

Copy `vite.local.config.ts` from `/Users/ajay/clinet-test/.wt-gg-chart/frontend/` into the worktree's `frontend/`, start Vite with it (its `/api` proxy adds the owner header), open `?tab=replays` at 430×932 and 375 px: no `.rp-card` wider than the board, the 🎾 table scrolls inside `.rp-rs-wrap`. Before the deploy mounts the folder the live api answers `no_folder` — that sentence is itself the listing proof there.

UNMEASURED — a replay is for his eyes, not a signal.
