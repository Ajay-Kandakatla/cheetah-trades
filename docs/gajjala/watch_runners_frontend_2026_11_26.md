# 📅 Runners on the 👀 Watch — frontend (2026-11-26, spec watchrun rev 2 §3.5, WP-3 `fe-roster`)

Ajay 2026-11-26 ~21:40 ET: "Ok then add them to our watch list and track them please.. I know he tracks them for two weeks
sometimes.. before he discards them.. Can you do that please" · ~21:50 ET: "Make it 30% please after A+".

## 2026-11-26 — what the Watch draws

- **Roster under the tiles** (`components/GgwRunRoster.tsx`, mounted by `GajjalaWatchBoard.tsx` only when the server
  serves `board.runners`). One line per seated runner, in the served order (🚫 last as served): ticker (opens the existing
  continuous 📅 chart, ‹ › = every roster name), the served day chip, the served seat chip (hover = served `seat_title`),
  the served 🚫 word, the served "on your Watch above" words or the shared ➕ button, a 🧾 toggle (that ticker's record,
  `GET …/runners/track?symbol=`, fetched only when opened) and the roster's own × on EVERY row (title = served `remove_title`).
- **Two ×, two lists [C4].** The roster × is its own hook `useGgwRunSeatRemove` → `DELETE /chart-maps/gajjala-watch/runners/seat/{sym}`
  (`ggwRunSeatPath`), the row leaves at once, then the board makes ONE re-GET (`onChanged` → served text in the head line).
  It never calls `ggwSymbolPath`; the board's `write('DELETE')` is not edited and is never handed to the roster. A tile ×
  is unchanged and never calls the seat path. A failed roster × comes back on the re-GET with the served text.
- **Phone**: the roster is served `folded_default` → one header line until tapped; the open is remembered in
  `localStorage["ggw.runners.opened"]` (beside `ggw.opened`, not inside it — the board rewrites that key); a refresh never
  unfolds it. **Desktop**: the first served `fold_at` rows + the served "+n more" / "show less".
- **One ⓘ fold** holds every explanation: the served `hint` (the live reading's rule sentence), the served `not_seated`
  sentences verbatim, then — fetched only while the fold is open, aborted on close — the record's served `summary_text`,
  `note` and closed table. Nothing explanatory is drawn outside the fold.
- **Tiles**: a seated name that also has a tile gets `row.runner`'s two served chips after the when chip (`GgwProvLine`);
  the ⋯ drawer prints the served `seat_title`. A row without `runner` draws nothing new.
- **Chart host**: `pages/ChartMaps.tsx` mounts `GgRunChartHost` on `gajjala_watch` too, for the loaded primary owner
  (`showRunHost`); the 📅 strip stays 🚩 only.
- **430 px**: rows `flex-wrap: wrap; min-width: 0`, tables inside their own `overflow-x: auto` box, no fixed width.
- Parsers (`lib/ggwRunRoster.ts`): junk → null, a row without a ticker dropped, every string verbatim; record tables accept
  the house `[key, label]` heads with `cells` keyed by head key (also arrays, `{key,label}` heads and a `<key>_text` cell
  beside a raw number). No number is formatted in the FE. The golden `lib/__fixtures__/ggwRunRoster.golden.json` was
  hand-copied from the spec's §3.1 words and §3.2 / §3.4 shapes (WP-1 / WP-2 were not built yet) — re-copy from a live GET.

Display + his own 📅 list write only. Nothing rings. UNMEASURED.
