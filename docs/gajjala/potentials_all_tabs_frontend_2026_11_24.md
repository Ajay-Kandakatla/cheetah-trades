# 🧠 from every tab — frontend (2026-11-24, potall spec §3.3, WP fe-potall)

Ajay 2026-11-24: "I need a common place to see all the potnetials from all tabs" · "I mean all Gajjala's tabs".

**2026-11-24.** The 🧠 Potential sub prints the served `all_potentials` block (backend `chart_maps/gajjala/pot_all.block`,
GG5 only) as a dense list UNDER the 🧠 cards and ABOVE 📈 Track. Display only — no rule, gate, count, sort default or push
changes. UNMEASURED. The FE types no word and never sorts.

## What renders where

| Piece | Where | Visible by default |
|---|---|---|
| Rows (`text` verbatim, ✅ `broke_text`, `alert_text`, `read_at_text`, 📌 / 🎪 / 🚫 tags) | `GgPotAll` — after the card grid / card-view portal, before `TrackPanel` | yes |
| `more_text`, `fault_text` | `GgPotAll`, under the rows | yes (faults never fold) |
| `title`, `order_text`, `rule_text`, `as_of_text` | `GgPotAllNotes` inside the 🧠 sub's ⓘ fold (`subPanels`, only when a fold key exists) | no — fold closed by default |

- A row links to its source card only when the served `href` passes `ggHref` (relative, not `//`); it goes through
  `withSource(…, 'chart-maps', search)` with the board's back state. Null / unsafe → plain text.
- The row's `title` attribute = the served `state_label` (the card pill).
- No visible as-of / closed-day stamp from this block (HIS CALL #6 default); the board's own `gg-stale` / `gg-warming`
  lines stay the visible ones.
- `gg-empty` on 🧠 steps aside only while there are no cards AND the block has ≥ 1 printable row. Both empty → today's
  `empty_note`. Block absent / null (older API, a build fault) → today's DOM, byte-identical (pinned).
- Never on another sub (the board mounts both components on `activeSub === 'potential'` only).

## Files

- `frontend/src/components/GgPotAll.tsx` (new) — `GgPotAll`, `GgPotAllNotes`, `ggPotAllRows`.
- `frontend/src/components/GajjalaBoard.tsx` — three mounts (rows, fold notes, the `gg-empty` guard).
- `frontend/src/lib/gajjala.ts` — `GgPotAllRow`, `GgPotAllBlock`, `GgBoard.all_potentials`.
- `frontend/src/styles/gajjala.css` — `.gg-potall*` (one line per row, tags wrap at 430 px, never widen the board).

## Tests

- `frontend/src/components/GgPotAll.test.tsx` — served order, verbatim text, link vs plain text (null / `//` / absolute /
  `javascript:` / non-string), chips present / absent, more / fault, malformed rows skipped, notes as-of null.
- `frontend/src/components/GajjalaBoard.potall_2026_11_24.test.tsx` — placement after the last card and before 📈 Track
  (and never before the grid), fold-only words (closed by default, none outside), fault / more visible, the `gg-empty`
  three cases, absent block = byte-identical DOM, never on another sub, no b-word, no email literal, 430 px class + css.
