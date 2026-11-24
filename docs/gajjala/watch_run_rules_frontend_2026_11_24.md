# ▶ Rules on the 👀 Watch — the frontend (2026-11-24)

Spec: `ggrun` rev 2, §3.5 and §4 `fe-run`. Backend engine and route: `docs/gajjala/watch_run_rules_2026_11_24.md`.

## His words

> On the Watch list I need a run button to run against Gajjalas rules of a stock to see for patterns of 5 patterns he has
> especially reversal squeeze.. so can check for patterns mid day when I can add a small slide in in the chart window for
> giving verbatim of passed rules and failed rules of that stock like you do in other tabs..

## What a tap does

- **The button**: "▶ Rules" (`GgwRunButton`, `frontend/src/components/GgwRunRules.tsx`) sits in every Watch tile's
  action group right after 🚫, and in the ⤢ view. It never hides. While its run is reading it is disabled and
  `aria-busy` (a soft pulse; no pulse under reduced motion).
- **One tap = ONE owner-only POST** to `${API}/chart-maps/gajjala-watch/run/{symbol}` (`lib/ggwRun.ggwRunPath`). The board
  is NOT re-fetched and its load chain is not touched. Two clicks in one tick still make one POST (a ref).
- **The panel** (`GgwRunPanel`) opens at once with the busy word "Reading the bars…" and an enabled ✕. When the answer
  lands it prints, every string VERBATIM from the server: the title; the 🔁 reuse line (when served); the 🕐 as-of line;
  a non-ok state's ONE sentence (not on the Watch / market closed / no prints / another run busy / …); the 📋 scanner
  line; the float line; the volume line; then ONE section per setup **in the served order** (🎾 first): the setup
  label, the state pill (`gg-state gg-state-{state}`, the 🚩 card's look), the 🎾 float-gate sentence RIGHT under the
  pill when served, the variant / grade / 💧 words when served, the plan, the count line, and the rule rows through
  `GgCriteriaList` — the 🚩 card's own printer; then the note.
- **What he will see on 🎾**: rule rows only when the structure is on the chart AND the float gate passes; otherwise the
  one failed rule as a sentence, and — behind a float gate — the served gate sentence saying the structure is there.
  This is the detector's design; the panel never draws a ✓ / ✗ the detector did not write.
- **✕ works in every phase.** ✕ while the run is reading closes the panel, re-enables the button, and an answer that
  lands later prints NOTHING (a per-symbol request token). There is no FE timer — the server bounds the wait.
- **404** (not the primary owner) → nothing at all. Another failed status → the served `detail` when it is a string,
  else "Could not run Gajjala's rules."; a network failure or junk JSON → the same failed words.
- The FE types no rule word, no state word and no number: only the control chrome in `lib/ggwRun.GGW_RUN`
  (button label, ✕, titles, the busy word, the failed word) — the `GGW_STRETCH` / `GGW_DRAWER` / `GGW_FETCH_FAILED`
  precedent.

Display only — the run rings nothing and records nothing. UNMEASURED.

## Files

| file | what |
|---|---|
| `frontend/src/lib/ggwRun.ts` | the route, the chrome words, the answer types, `parseGgwRun` (flattens `as_of` / `scanner`, keeps the served order, drops a row without a string key + label) |
| `frontend/src/components/GgCriteria.tsx` | `GgCriteriaList` — the ONE rule-row printer (a pure move of the 🚩 card's inline list) |
| `frontend/src/components/GajjalaBoard.tsx` | the pure move: the inline list became `<GgCriteriaList criteria={read.criteria} />`; `criteriaText` left the import |
| `frontend/src/components/GgwRunRules.tsx` | `useGgwRun`, `GgwRunButton`, `GgwRunPanel` |
| `frontend/src/styles/ggwRun.css` | the panel's look (below) |
| `frontend/src/components/GajjalaWatchTile.tsx` | ONE opt-in prop `run` on `Tile` and `GgwStretch` |
| `frontend/src/components/GajjalaWatchBoard.tsx` | `useGgwRun()` next to the 🚫 hook; `run={runOf(r)}` on every tile and on the ⤢ view |

## The Tile prop

`run?: { button: ReactNode; panel: ReactNode; open: boolean }` (type `GgwRunSlot`).

- `run.button` renders right after `actions` in the action group — on the board AND in the ⤢ view.
  Board order: 🚫 ▶ ⋯ ⤢ TV Y ✕ (⋯ only on a compact tile). ⤢ view: ▶ Rules ⋯ TV Y ◀ ▶ ⤡.
- `run.open` → the chart window gains `ggw-charts--run` and `run.panel` as its LAST child (both chart branches: the
  board's split and the ⤢ / stacked block). A pending tile (no chart yet) hosts the panel in
  `<div class="ggw-dark ggw-run-host">` right after its pending words.
- Absent, or closed → today's DOM byte for byte (apart from the button when `run` is passed). `GgCardGrid` /
  `GgCardView` never pass it, so the 🚩 / 🧪 card grid and the card's ⤢ view are unchanged.

## The look and the phone

- The panel is `position: absolute` inside the chart window, slides in from the LEFT (the newest bars on the right stay
  visible), `width: min(100%, 24rem)`, and scrolls inside itself (`overflow-y: auto`).
- **Phone (≤ 640 px): full width**, no right border. Every text child wraps (`white-space: normal;
  overflow-wrap: anywhere; min-width: 0`) — nothing passes the tile's right edge at 430 px.
- `z-index: 1` — UNDER the compact ⋯ drawer's `z-index: 2` (a test parses both sheets and compares).
- The head is sticky (`position: sticky; top: 0`, a solid background) — ✕ never scrolls away.
- A fitted pending tile: the host takes the room the pending words leave and scrolls inside it
  (`flex: 1 1 0; min-height: 0; overflow-y: auto`).
- The `.gg-criteria` / `.gg-state` rules are SCOPED copies of `gajjala.css` (the same custom properties) under
  `.ggw-run` — the Watch chunk does not load `gajjala.css`.
- Reduced motion: no slide, no pulse.

## Pins widened (dated)

- `frontend/src/components/GajjalaWatchBoard.notEligible.test.tsx` — the action-group class list gains
  `'ggw-btn ggw-run-btn'` after the 🚫; with no 🚫 block the first child is now `'ggw-btn ggw-run-btn'`. Both lines carry
  a `WIDENED 2026-11-24` comment. No other pin moved; the `GajjalaBoard.card_watch_off` snapshot is unchanged.

## The two-▶ row in the ⤢ view (HIS CALL 8)

In the ⤢ view the action row holds "▶ Rules" first and, later, the pager's "▶" (Next). The label word "Rules" tells
them apart. Alternatives for him: another glyph ("🚩 Rules"), or no run button inside ⤢.

## Tests

- `frontend/src/lib/ggwRun.test.ts` — the path, the chrome, the parser (served order, verbatim strings, flattening);
  NEGATIVES: junk → null, rows / setups without their keys dropped, never re-sorted, no rule word / owner check / timer.
- `frontend/src/components/GgCriteria.test.tsx` — HTML equals the legacy inline markup for ✓ / ✗ / · rows; empty →
  nothing; both surfaces mount it and neither calls `criteriaText(`.
- `frontend/src/components/GgwRunRules.test.tsx` — the panel's words verbatim and in order; the gate sentence right
  under the pill; the hook (one POST, busy, ✕ while busy drops the late answer, 404, 500 detail / failed, reject, junk,
  two names at once, unmount); source guards; CSS guards (z-index under the drawer, sticky head, fitted host, phone
  width, reduced motion, scoped colours equal `gajjala.css`'s).
- `frontend/src/components/GajjalaWatchBoard.run_rules_2026_11_24.test.tsx` — the real board: one ▶ per tile in order,
  one POST and no board re-GET, the panel inside THAT tile's chart window, the minute re-GET keeps it open, the ⤢ view,
  ✕, a second ▶, the pending host; NEGATIVES: no other tile, the late answer after ✕, 404, `Tile` without / closed
  `run`, the card grid / view never pass `run=`.
