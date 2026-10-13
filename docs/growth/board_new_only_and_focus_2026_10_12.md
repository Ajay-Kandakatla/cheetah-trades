# 🚀 Explosive Growth — ✨ new only, the focus exemption, the MEASURED fold (2026-10-12)

Ajay answered "yes" to eight follow-up questions on the ✨ growth-arrivals feature
(spec: `arrivals-calls/spec.md`, package P2 `board-fe`). This doc covers the four
that land on the 🚀 board itself (`frontend/src/components/ExplosiveGrowth.tsx`).
Nothing here sorts, gates, pushes or trades. It only changes which rows are drawn
and which lines are printed.

## #2 ✨ new only

- A checkbox in the board's control row, after "hide what the engine refuses":
  `✨ new only (N)`. N is the number of rows the server marked `is_new === true`.
  It starts **OFF**.
- When ON it keeps only rows with `is_new === true`. A row with no `is_new` field
  (an older payload) counts as **not new** and is hidden. The count line says how
  many rows were hidden that way.
- It works like its siblings: plain component state, no URL param and no
  localStorage, because the sibling filters have neither. A `?new=1` deep link is
  still HIS CALL (spec §7.4).
- The count line `growth-new-only-hidden` is shown the whole time the box is ON,
  even at 0:
  `✨ new only: {hidden} hidden (not new in the last {new_days} days)`, plus
  `· {k} rows carry no arrival read and count as not new` when k > 0, plus a
  `show all` button that unticks the box. When the server sends no `new_days`,
  the window part is left out.
- `{hidden}` is the stage's own count, `before.length − after.length` on the row
  **arrays** (`stagedFilter(...).dropped`). It never comes from `kept` set sizes,
  because those undercount when a symbol appears twice (critique C10).
- The checkbox is always drawn, even when no row carries a boolean `is_new` (an
  older payload). Then it reads `✨ new only (0)`, and when ON it hides every row
  and the line says all of them carry no arrival read and count as not new
  (refix 2026-10-13: the spec's §0 #2 says the line "says so", so the control
  and its line must be there on an all-old payload).
- The stage code is `new`, placed after `debt` in the board order
  (`growthArrivals.STAGE_LABEL.new = '✨ new only'`). It never drops a new name,
  so it never shows up in the "✨ N new hidden by …" line.

## #6 the focus exemption

When `?focus=SYM` (or the older push's `?symbol=SYM`) names a row that his ON
filters would hide:

- That **one** row is drawn **at the top** of the table. There was no existing
  convention for a pinned row, so the spec chose the top. The row gets
  `className="cm-row-focus cm-row-exempt"` and `data-exempt="true"`.
- A marker line `growth-focus-exempt` reads
  `✨ SYM shown because you opened it from ✨ — hidden by <control>`. The control
  is the **first** stage that dropped it (the same `hiddenArrivals` rule the ✨
  line uses).
- **No filter state is changed or saved.** No setter runs and no storage key is
  written. Every checkbox and select keeps its value.
- Every other hidden row stays hidden.
- The "✨ N new hidden" line no longer counts the exempt row. The old
  `· SYM is one of them` suffix is gone, because the marker line says it now.
- A focus on a symbol that is not on the board still shows only the existing
  `growth-focus-miss` line.

### Count semantics (C3): the same engines, run once more without the focus row

The 🎯 enterable count line and the 💎 quality count line must not count the
exempt row as hidden. They take their numbers from a **second run of the same
engines** over the rows minus the focus row:

`useEnterablePartition(rowsSansFocus, …)` → `partitionCapital(partSans.rows, …)`.

Nothing is subtracted by hand. `hidden`, `hiddenByReason`, `reasons[]`,
`unhidden` and `hiddenByKey` all come from the engine. So the invariant
`sum(reasons[].hidden) === hidden` holds, and the reason chip for the exempt
row's own reason is exactly one lower. The second partition only runs while a
focus row exists. Without one it costs a single inert pass.

Recomputing the counts without the exempt row was the chosen design. The other
option, keeping them as pure filter-drop counts with the marker as the
explanation, is HIS CALL (spec §7.6).

## #7 the board's arrivals line

`growth-arrivals-line` (StudyNote id `growth-arrivals-board`) gets
`freshKey = newestFirstSeen(data.arrivals)`, which is the newest served
`first_seen`. The line follows the same open rule as the Chart Maps strip:

- It opens for a viewer who has never folded it.
- Once he folds it, it stays folded until a batch with a later `first_seen`
  arrives, then it opens again.
- If storage throws or is missing, it opens.

With no served `arrivals` list (an older payload) it keeps the old rule and stays
folded. The strip and the board line remember their folds separately (HIS CALL
§7.7).

## #1 MEASURED wording on the board

- The 📣 just-reported note now ends: "the 100%/100% screen itself was measured
  2026-09-21 — see the MEASURED line on this board." It no longer says "never
  been measured".
- A new folded StudyNote `growth-screen-measured` sits right after the cap-floor
  note. It renders the served `screen_measured.headline` / `.body` word for word.
  If the payload carries no `screen_measured`, or its body is empty, nothing is
  drawn.
- The component types **no number** from the study. A source guard checks that
  the count of `pp` literals in `ExplosiveGrowth.tsx` does not go up compared
  with `git show HEAD:`. The two existing `+8.6pp` demand-cell tooltips are the
  only ones.

## Rule #5 note

The board's control row now has one more checkbox. It is dense but still one
line on desktop. The exempt marker and the new-only count line show up only
while their condition holds, so no line is permanent.

## Tests

`frontend/src/components/ExplosiveGrowthArrivals.test.tsx` covers:

- `stagedFilter` with `onlyNew` and with `dropped`, including the
  duplicated-symbol negative.
- The checkbox when rendered: off on first paint, the count line, the
  unread-row clause, `show all`, and that it changes no order and no other
  control.
- The focus exemption for the refused, sector, new-only, enterable (C3
  invariant) and quality stages, plus negatives for a drawn focus, a missing
  focus and "nothing written".
- The board line's `freshKey` open rule.
- The MEASURED fold and wording guards.

`frontend/src/lib/growthArrivals.test.ts` covers `newRowCounts`,
`newOnlyHiddenLine` and the seven-code `STAGE_LABEL`.
