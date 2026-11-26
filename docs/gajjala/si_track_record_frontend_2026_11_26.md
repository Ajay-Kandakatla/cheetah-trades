# 🏁 🩳 SI track record — frontend (2026-11-26)

Spec `sitrack` §3.7 B, work package `fe-track`, [fixed: OC1]. The backend, the rule and the stats are described in
`docs/gajjala/si_track_record_2026_11_26.md`.

Ajay 2026-11-26: *"I want us to track these patters for future from SI like a track recprd with in SI stocks itself"*

## 2026-11-26 — where it sits and what it draws

- **Where.** `GgSiTrackSection` (NEW `frontend/src/components/GgSiTrack.tsx`) is mounted inside `GgHighSiPanel`
  (`GgHighSi.tsx`), right after `<GgSsrNewSection … />` and on the same source line. `GgSsrNew.test.tsx` pins the ⛔ mount
  as one digit-free line between the faults line and the rule fold. On the 🚩 board the panel sits inside the 🩳 sub's
  closed ⓘ fold (`gg-sub-body`), so nothing of the 🏁 is on the landing. This follows his standing "no explanations on
  landing" rule. `GgHighSiState` (the lines printed outside the closed fold) is not edited and never draws it.
  Putting it outside the fold is his call (spec §7 #9).
- **What.** It reads `high_si.si_track`, the block `si_track.served_block` serves, and draws nothing when the block is
  absent or not an object. A served `fault_text` gives one `cm-note-err` line and nothing else. Otherwise it draws ONE
  closed `<details data-testid="gg-st">` whose summary is the served `summary_text`. The body is mounted only while the
  fold is open. Each item below is drawn only when it is served, in this order:
  1. `title`, `asof_text`
  2. `base_text`: the counted cohort, names on the list before the day
  3. `new_today_text`: the names first listed that day, which are not counted
  4. `empty_text`
  5. the pattern table: the served `pattern_heads` in their served order, the "Shuffled" column among them, and the
     rows in their served order (⛔ SSR first, 🩳 EXTREME second). The label cell also carries `known_text` /
     `unknown_text`, and the row's `title` is its hover.
  6. `where_text`, then one line per `shape_rows` entry
  7. the day tables, all in ONE `.gg-tr-scroll` box (the 🏁 width rule). Each day prints its served `label`, the served
     `heads`, and its counted rows (`counted === true`) in their served order. Then comes the served `new_label`, then
     every other row, so an uncounted row is never drawn above the label, even when the rows are served out of order.
  8. `shown_text`, `pending_text`
  9. a nested closed `<details>` under `rule_label`, holding `rule_text` + `honesty`
- **Ticker cell.** The first served head's column draws the row's `symbol` (a link through `ggHref` when `href` is safe),
  its served `win` (✅) and its served `chips`. Every other column prints `cells[<head key>]`.
- **Words and numbers.** The file types no word and no digit, and formats no number. It never sorts, counts or fetches.
  `n` / `n_days` are never printed. Every string passes its own `servedText` guard, so a NaN, number, null, undefined or
  empty string prints nothing.
- **Types.** `GgSiTrackBlock`, `GgSiTrackPattern`, `GgSiTrackDay`, `GgSiTrackRow`, `GgSiTrackShape` and `GgSiTrackHead` are
  in `lib/gajjala.ts`. `GgHighSiBlock.si_track?: GgSiTrackBlock | null`.
- **Phone (430 px).** NEW `styles/ggSiTrack.css`. The fold, its body, the shape lines and the rule fold wrap
  (`min-width: 0` + `overflow-wrap: anywhere`). Each table scrolls sideways inside its own `.gg-tr-scroll` box (the
  pattern table in one, the day tables in one), so the page itself never scrolls sideways. There is no inline width and
  no nowrap on any element.

**2026-11-26 refix.** After the rows first listed that day, the rows served with `group === "other"` are drawn under
the served `other_label`. These are rows on the list before the day but not graded, or with no listing day on file.
They are never drawn under `new_label`. A label row is drawn only when its part of the table has rows. A row with
`counted === true` stays with the counted rows whatever its `group`. A row with no `group`, or an unknown one, goes
under `new_label` as before. The Ticker cell still draws any served `chips`. The backend now serves `chips` as `[]`,
so a flag prints once, in the Flags column. Four tests were added (24 in all): the order with an `other` row; with only
`other` rows uncounted, no `new_label`; a counted row or an unknown group is never moved; a flag prints once.

## Choices made where the spec left a gap (all reversible)

- `heads` (the day-table column heads) is read in the same `[key, label]` shape that the spec gives for `pattern_heads`.
  Anything else is dropped, so no table is drawn and nothing crashes.
- If `summary_text` is not served, the 🏁 draws nothing. A closed fold with no served line would show the browser's own
  "Details" word.
- `title`, `asof_text`, `empty_text`, `shown_text` and `pending_text` are not placed by §3.7. They print inside the fold,
  in the order above.

## Tests

`frontend/src/components/GgSiTrack.test.tsx` has 24 tests:

- **The fold:** it is closed on first paint, with its body not mounted. Opened, it shows the served order and the
  Shuffled column. There is one day-table scroll box, and the counted rows sit above `new_label`.
- **Negatives:**
  - an uncounted row that is served first, or a `counted` of null or `"true"`, still lands under the label
  - with no `rule_label`, there is no rule fold
  - every text node is a fixture string
  - NaN, number, null and `""` cells print nothing
  - a fault draws one line, with no fold and no table
  - an absent, null or junk block, or a block with no summary, draws nothing
  - junk heads or rows draw no table and do not crash
- **Phone and source guards:** the phone CSS pins hold. The source guards: no digit, no b-word, no number formatting,
  no admin address, no typed text between tags.
- **In the panel:** the 🏁 sits right after `gg-ssrn` and is drawn once. With `si_track` absent, null or junk, the panel
  HTML is byte-identical to a block without the key. A fault puts one line in the panel. `GgHighSiState`'s HTML is
  identical with and without the block, over four shapes.
- **On the board** (the 🩳 sub of `GajjalaBoard`): every `gg-st*` node sits inside `gg-sub-body`. With the ⓘ fold
  closed, no 🏁 string is visible on the page. Opening ⓘ shows the closed 🏁 line with its body still closed. A fault
  line also stays inside the fold.

A mutation that drops the counted / uncounted split turns two tests red.
